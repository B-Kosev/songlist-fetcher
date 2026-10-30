import hashlib

import pytest

from worship_song_selector.auth import Role, hash_passcode, resolve_role

TEAM_PLAIN = "team-secret-01"
ADMIN_PLAIN = "admin-secret-01"
TEAM_HASH = hashlib.sha256(TEAM_PLAIN.encode("utf-8")).hexdigest()
ADMIN_HASH = hashlib.sha256(ADMIN_PLAIN.encode("utf-8")).hexdigest()


def test_wrong_passcode_returns_none():
    assert (
        resolve_role(
            "wrong",
            team_passcode_hash=TEAM_HASH,
            admin_passcode_hash=ADMIN_HASH,
        )
        is None
    )


def test_team_passcode_resolves_to_team_role():
    assert (
        resolve_role(
            TEAM_PLAIN,
            team_passcode_hash=TEAM_HASH,
            admin_passcode_hash=ADMIN_HASH,
        )
        is Role.TEAM
    )


def test_admin_passcode_resolves_to_admin_role():
    assert (
        resolve_role(
            ADMIN_PLAIN,
            team_passcode_hash=TEAM_HASH,
            admin_passcode_hash=ADMIN_HASH,
        )
        is Role.ADMIN
    )


def test_hash_passcode_matches_known_digest():
    assert hash_passcode("hello") == hashlib.sha256(b"hello").hexdigest()
