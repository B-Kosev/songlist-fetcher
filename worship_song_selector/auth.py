from __future__ import annotations

import hashlib
import hmac
from enum import Enum


class Role(str, Enum):
    TEAM = "team"
    ADMIN = "admin"


def hash_passcode(passcode: str) -> str:
    return hashlib.sha256(passcode.encode("utf-8")).hexdigest()


def resolve_role(
    passcode: str,
    *,
    team_passcode_hash: str,
    admin_passcode_hash: str,
) -> Role | None:
    candidate = hash_passcode(passcode)
    if hmac.compare_digest(candidate, admin_passcode_hash):
        return Role.ADMIN
    if hmac.compare_digest(candidate, team_passcode_hash):
        return Role.TEAM
    return None
