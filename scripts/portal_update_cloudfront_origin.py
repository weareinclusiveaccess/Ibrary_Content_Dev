#!/usr/bin/env python3
"""Update the EC2 API origin domain on the reviewer-portal CloudFront distribution.

Why: when the EC2 portal instance is stopped and restarted, its public DNS
changes. CloudFront keeps a fixed origin, so we have to swap it out-of-band.
The terraform module ignores `origin` changes in lifecycle, so this script
doesn't fight Terraform.

Usage:
  python scripts/portal_update_cloudfront_origin.py \
      --distribution-id E1ABCDEF12345 --instance-id i-0123456789abcdef0

If --instance-id is omitted, the script reads it from terraform output
`portal_instance_id`. If --distribution-id is omitted, it reads
`portal_cloudfront_distribution_id`.

Exit codes:
  0 — submitted update (or no change needed); CloudFront propagation takes 5–10 min.
  2 — instance not running; start it first with `make portal-start`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

import boto3


def _terraform_output(name: str) -> str | None:
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


def _instance_public_dns(instance_id: str, region: str | None) -> str:
    ec2 = boto3.client("ec2", region_name=region)
    resp = ec2.describe_instances(InstanceIds=[instance_id])
    reservations = resp.get("Reservations", [])
    if not reservations or not reservations[0].get("Instances"):
        raise SystemExit(f"Instance {instance_id} not found")
    inst = reservations[0]["Instances"][0]
    state = inst.get("State", {}).get("Name")
    if state != "running":
        print(f"Instance state is '{state}'; start it first.", file=sys.stderr)
        raise SystemExit(2)
    dns = inst.get("PublicDnsName") or ""
    if not dns:
        raise SystemExit("Instance has no public DNS name (is it in a public subnet?)")
    return dns


def _update_distribution(distribution_id: str, ec2_dns: str) -> tuple[bool, str]:
    cf = boto3.client("cloudfront")
    resp = cf.get_distribution_config(Id=distribution_id)
    etag = resp["ETag"]
    config: dict[str, Any] = resp["DistributionConfig"]

    origins = config.get("Origins", {}).get("Items", [])
    target = next((o for o in origins if o["Id"] == "ec2-api"), None)
    if not target:
        raise SystemExit("Origin 'ec2-api' not found in distribution config")

    if target["DomainName"] == ec2_dns:
        return False, "no change"

    target["DomainName"] = ec2_dns
    cf.update_distribution(DistributionConfig=config, Id=distribution_id, IfMatch=etag)
    return True, ec2_dns


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--distribution-id", default=None)
    p.add_argument("--instance-id", default=None)
    p.add_argument("--region", default=None)
    args = p.parse_args()

    distribution_id = args.distribution_id or _terraform_output("portal_cloudfront_distribution_id")
    instance_id = args.instance_id or _terraform_output("portal_instance_id")
    if not distribution_id or not instance_id:
        print(
            "Could not resolve distribution/instance ID. Pass --distribution-id and --instance-id "
            "or run from a workspace with `terraform init` and outputs available.",
            file=sys.stderr,
        )
        return 2

    dns = _instance_public_dns(instance_id, args.region)
    changed, detail = _update_distribution(distribution_id, dns)

    out = {
        "distribution_id": distribution_id,
        "instance_id": instance_id,
        "ec2_public_dns": dns,
        "changed": changed,
        "detail": detail,
        "note": "CloudFront propagation typically takes 5–10 minutes." if changed else None,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
