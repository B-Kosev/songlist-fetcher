from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class AuthConfig:
    team_passcode_hash: str
    admin_passcode_hash: str


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    key: str


@dataclass(frozen=True)
class AppConfig:
    auth: AuthConfig
    supabase: SupabaseConfig


def load_config() -> AppConfig:
    secrets = st.secrets
    return AppConfig(
        auth=AuthConfig(
            team_passcode_hash=str(secrets["team_passcode_hash"]),
            admin_passcode_hash=str(secrets["admin_passcode_hash"]),
        ),
        supabase=SupabaseConfig(
            url=str(secrets["supabase"]["url"]),
            key=str(secrets["supabase"]["key"]),
        ),
    )
