#!/usr/bin/env python3
"""Portal lifecycle and ops helpers (start/stop/status/logs/roll).

Why a Python script instead of inline shell in the Makefile: GNU make on
Windows uses cmd.exe as the recipe shell, and `cmd` doesn't support POSIX
`$()` command substitution. Putting the AWS work behind one script keeps the
Makefile platform-neutral (it just calls `uv run python scripts/portal_admin.py
<subcommand>`) and lets us share helpers with `portal_update_cloudfront_origin.py`.

Subcommands:
  start      Start the EC2 portal instance and repoint CloudFront origin.
  stop       Stop the EC2 portal instance (preserves EBS, ~$0.65/mo).
  status     Show instance state + container status + portal URL.
  logs       Tail the last 80 lines of the portal container.
  roll       Pull :latest from ECR and restart the container on EC2.
  cf-origin  Force CloudFront origin to the current EC2 public DNS.

All subcommands read instance id + region + distribution id from
`terraform output` (run from `infra/terraform/environments/dev`) unless
overridden via flags. AWS auth comes from the ambient session (see
scripts/terraform-aws-env.{sh,ps1}).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from typing import Any

import boto3

PORTAL_REGION_DEFAULT = "eu-west-1"
ECR_IMAGE_DEFAULT = "681986854278.dkr.ecr.eu-west-1.amazonaws.com/ibrary-review-api:latest"
SSM_POLL_INTERVAL = 2.0
SSM_POLL_MAX_S = 60.0


def _terraform_output(name: str) -> str | None:
    """Return a Terraform output value or None if not available."""
    try:
        proc = subprocess.run(
            ["terraform", "-chdir=infra/terraform/environments/dev", "output", "-raw", name],
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _resolve_instance_id(cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    value = _terraform_output("portal_instance_id")
    if not value:
        raise SystemExit(
            "Could not resolve instance id. Pass --instance-id or run from a "
            "directory where `terraform output portal_instance_id` works."
        )
    return value


def _resolve_distribution_id(cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    value = _terraform_output("portal_cloudfront_distribution_id")
    if not value:
        raise SystemExit(
            "Could not resolve CloudFront distribution id. Pass --distribution-id."
        )
    return value


def _run_ssm(instance_id: str, region: str, commands: list[str]) -> str:
    """Send a shell command via SSM, wait up to SSM_POLL_MAX_S, return stdout."""
    ssm = boto3.client("ssm", region_name=region)
    resp = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands},
    )
    command_id = resp["Command"]["CommandId"]

    deadline = time.time() + SSM_POLL_MAX_S
    last_status = "Pending"
    while time.time() < deadline:
        time.sleep(SSM_POLL_INTERVAL)
        try:
            inv = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        last_status = inv["Status"]
        if last_status in ("Success", "Failed", "Cancelled", "TimedOut"):
            stdout = inv.get("StandardOutputContent", "") or ""
            stderr = inv.get("StandardErrorContent", "") or ""
            if last_status != "Success" and stderr:
                stdout = f"{stdout}\n[stderr]\n{stderr}"
            return stdout
    raise SystemExit(f"SSM command timed out after {SSM_POLL_MAX_S}s (last status: {last_status})")


def _instance_state(instance_id: str, region: str) -> dict[str, Any]:
    ec2 = boto3.client("ec2", region_name=region)
    resp = ec2.describe_instances(InstanceIds=[instance_id])
    inst = resp["Reservations"][0]["Instances"][0]
    return {
        "state": inst["State"]["Name"],
        "public_dns": inst.get("PublicDnsName") or "",
        "type": inst["InstanceType"],
    }


def _cf_url() -> str:
    return _terraform_output("portal_cloudfront_url") or "(unknown — terraform output unavailable)"


# --- subcommands ------------------------------------------------------------


def cmd_start(args: argparse.Namespace) -> int:
    instance_id = _resolve_instance_id(args.instance_id)
    region = args.region

    ec2 = boto3.client("ec2", region_name=region)
    print(f"Starting {instance_id}...")
    ec2.start_instances(InstanceIds=[instance_id])
    waiter = ec2.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id])
    print("Instance running.")

    # Repoint CloudFront so /review/* hits the new public DNS.
    print("Repointing CloudFront origin...")
    rc = subprocess.call(
        [sys.executable, "scripts/portal_update_cloudfront_origin.py"],
    )
    if rc != 0:
        print("CloudFront origin update failed.", file=sys.stderr)
        return rc
    print("Done. CloudFront propagation may take 5-10 minutes.")
    print(f"Portal URL: {_cf_url()}")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    instance_id = _resolve_instance_id(args.instance_id)
    region = args.region

    ec2 = boto3.client("ec2", region_name=region)
    print(f"Stopping {instance_id}...")
    ec2.stop_instances(InstanceIds=[instance_id])
    waiter = ec2.get_waiter("instance_stopped")
    waiter.wait(InstanceIds=[instance_id])
    print("Instance stopped. CloudFront will return 5xx until you run `portal start`.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    instance_id = _resolve_instance_id(args.instance_id)
    region = args.region

    print("--- Instance ---")
    state = _instance_state(instance_id, region)
    print(f"  id        : {instance_id}")
    print(f"  state     : {state['state']}")
    print(f"  type      : {state['type']}")
    print(f"  publicDns : {state['public_dns'] or '(none)'}")

    if state["state"] == "running":
        print("\n--- Container (via SSM) ---")
        out = _run_ssm(
            instance_id,
            region,
            [
                "systemctl is-active ibrary-portal.service",
                'docker ps --format "{{.Names}} {{.Status}}"',
            ],
        )
        for line in out.strip().splitlines():
            print(f"  {line}")
    else:
        print("\nContainer status skipped (instance not running).")

    print(f"\nPortal URL: {_cf_url()}")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    instance_id = _resolve_instance_id(args.instance_id)
    out = _run_ssm(
        instance_id,
        args.region,
        [f"docker logs portal --tail {args.tail} 2>&1 || true"],
    )
    print(out)
    return 0


def cmd_roll(args: argparse.Namespace) -> int:
    instance_id = _resolve_instance_id(args.instance_id)
    image = args.image
    print(f"Pulling {image} on {instance_id} and restarting service...")
    out = _run_ssm(
        instance_id,
        args.region,
        [
            f"docker pull {image}",
            "systemctl restart ibrary-portal.service",
            "sleep 6",
            "systemctl is-active ibrary-portal.service",
            'docker ps --format "{{.Names}} {{.Status}}"',
        ],
    )
    print(out)
    return 0


def cmd_cf_origin(args: argparse.Namespace) -> int:
    rc = subprocess.call(
        [sys.executable, "scripts/portal_update_cloudfront_origin.py"],
    )
    return rc


# --- entry point ------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(prog="portal_admin", description=__doc__)
    parser.add_argument("--region", default=PORTAL_REGION_DEFAULT)
    parser.add_argument("--instance-id", default=None)

    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("start").set_defaults(func=cmd_start)
    sub.add_parser("stop").set_defaults(func=cmd_stop)
    sub.add_parser("status").set_defaults(func=cmd_status)

    p_logs = sub.add_parser("logs")
    p_logs.add_argument("--tail", type=int, default=80)
    p_logs.set_defaults(func=cmd_logs)

    p_roll = sub.add_parser("roll")
    p_roll.add_argument("--image", default=ECR_IMAGE_DEFAULT)
    p_roll.set_defaults(func=cmd_roll)

    sub.add_parser("cf-origin").set_defaults(func=cmd_cf_origin)

    args = parser.parse_args()
    return args.func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
