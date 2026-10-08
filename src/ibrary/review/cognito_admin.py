"""Cognito user administration for the reviewer portal (optional)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ibrary.config import (
    COGNITO_GROUP_ADMIN,
    COGNITO_GROUP_REVIEWER,
    COGNITO_REGION,
    COGNITO_USER_POOL_ID,
)

UserRole = Literal["admin", "reviewer"]


@dataclass
class PortalUser:
    username: str
    email: str
    status: str
    enabled: bool
    groups: list[str]


def cognito_enabled() -> bool:
    return bool(COGNITO_USER_POOL_ID.strip())


def _client():
    import boto3

    return boto3.client("cognito-idp", region_name=COGNITO_REGION)


def _group_for_role(role: UserRole) -> str:
    return COGNITO_GROUP_ADMIN if role == "admin" else COGNITO_GROUP_REVIEWER


def list_portal_users() -> list[PortalUser]:
    if not cognito_enabled():
        return []
    client = _client()
    users: list[PortalUser] = []
    token: str | None = None
    while True:
        kwargs: dict = {"UserPoolId": COGNITO_USER_POOL_ID, "Limit": 60}
        if token:
            kwargs["PaginationToken"] = token
        resp = client.list_users(**kwargs)
        for row in resp.get("Users") or []:
            username = row.get("Username") or ""
            email = username
            for attr in row.get("Attributes") or []:
                if attr.get("Name") == "email":
                    email = attr.get("Value") or email
            groups_resp = client.admin_list_groups_for_user(
                UserPoolId=COGNITO_USER_POOL_ID,
                Username=username,
            )
            groups = [g["GroupName"] for g in groups_resp.get("Groups") or []]
            users.append(
                PortalUser(
                    username=username,
                    email=email,
                    status=row.get("UserStatus") or "UNKNOWN",
                    enabled=row.get("Enabled", True),
                    groups=groups,
                )
            )
        token = resp.get("PaginationToken")
        if not token:
            break
    return users


def create_portal_user(
    *,
    email: str,
    role: UserRole,
    temporary_password: str,
    send_invite: bool = False,
) -> PortalUser:
    if not cognito_enabled():
        raise RuntimeError("COGNITO_USER_POOL_ID is not configured")
    email = email.strip().lower()
    client = _client()
    message_action = "SUPPRESS" if not send_invite else None
    kwargs: dict = {
        "UserPoolId": COGNITO_USER_POOL_ID,
        "Username": email,
        "UserAttributes": [
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ],
        "TemporaryPassword": temporary_password,
    }
    if message_action:
        kwargs["MessageAction"] = message_action
    client.admin_create_user(**kwargs)
    client.admin_add_user_to_group(
        UserPoolId=COGNITO_USER_POOL_ID,
        Username=email,
        GroupName=_group_for_role(role),
    )
    return PortalUser(
        username=email,
        email=email,
        status="FORCE_CHANGE_PASSWORD",
        enabled=True,
        groups=[_group_for_role(role)],
    )
