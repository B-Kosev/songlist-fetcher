from __future__ import annotations

from typing import Any

from supabase import Client, create_client

from worship_song_selector.config import SupabaseConfig
from worship_song_selector.titles import normalize_title


def create_supabase_client(config: SupabaseConfig) -> Client:
    return create_client(config.url, config.key)


def count_songs(client: Client) -> int:
    response = (
        client.table("songs")
        .select("id", count="exact", head=True)
        .execute()
    )
    if response.count is None:
        raise ValueError("Supabase did not return a row count")
    return int(response.count)


def list_songs(client: Client) -> list[dict[str, Any]]:
    response = (
        client.table("songs")
        .select("id, title, author")
        .order("title")
        .execute()
    )
    return list(response.data or [])


def insert_songs(client: Client, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    client.table("songs").insert(rows).execute()


def build_song_row(
    *,
    title: str,
    author: str | None,
    lyrics: list[dict[str, Any]],
    raw_text: str,
) -> dict[str, Any]:
    return {
        "title": title,
        "normalized_title": normalize_title(title),
        "author": author,
        "lyrics": lyrics,
        "raw_text": raw_text,
        "analysis_status": "pending",
    }
