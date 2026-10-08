#!/usr/bin/env bash
# Export temporary AWS credentials for Terraform (MFA via ibrary-dev → content-dev).
#
# Git Bash — must SOURCE (do not run with bash):
#   cd ~/Documents/IBrary
#   source scripts/terraform-aws-env.sh
#
# PowerShell is easier on Windows:
#   . .\scripts\terraform-aws-env.ps1

_terraform_aws_env() {
  local profile="${1:-ibrary-dev}"

  export AWS_SDK_LOAD_CONFIG=1
  if [[ -d "/c/Program Files/Amazon/AWSCLIV2" ]]; then
    export PATH="/c/Program Files/Amazon/AWSCLIV2:$PATH"
  fi

  if ! command -v aws >/dev/null 2>&1; then
    echo "aws CLI not found. Add AWS CLI to PATH or use PowerShell script." >&2
    return 1
  fi

  echo "Requesting credentials for profile: $profile (MFA may prompt)..."
  local creds
  if ! creds="$(aws configure export-credentials --profile "$profile" --format env 2>&1)"; then
    echo "$creds" >&2
    echo "Failed. Try: aws configure export-credentials --profile $profile --format env" >&2
    return 1
  fi

  eval "$creds"
  unset AWS_PROFILE

  echo "OK — session credentials exported for Terraform."
  aws sts get-caller-identity || return 1
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Do not run this script directly. Use:" >&2
  echo "  source scripts/terraform-aws-env.sh" >&2
  exit 1
fi

_terraform_aws_env "$@"
