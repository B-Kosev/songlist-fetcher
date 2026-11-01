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
class OpenAIConfig:
    api_key: str
    model: str = "gpt-4o-mini"


@dataclass(frozen=True)
class AppConfig:
    auth: AuthConfig
    supabase: SupabaseConfig
    openai: OpenAIConfig


def load_config() -> AppConfig:
    secrets = st.secrets
    openai_raw = secrets.get("openai", {})
    return AppConfig(
        auth=AuthConfig(
            team_passcode_hash=str(secrets["team_passcode_hash"]),
            admin_passcode_hash=str(secrets["admin_passcode_hash"]),
        ),
        supabase=SupabaseConfig(
            url=str(secrets["supabase"]["url"]),
            key=str(secrets["supabase"]["key"]),
        ),
        openai=OpenAIConfig(
            api_key=str(openai_raw.get("api_key", "")),
            model=str(openai_raw.get("model", "gpt-4o-mini")),
        ),
    )
