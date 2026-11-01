from __future__ import annotations

from typing import Any

from supabase import Client, create_client

from worship_song_selector.config import SupabaseConfig
from worship_song_selector.song_analysis import SongAnalysis
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
        .select("id, title, author, energy, tags, analysis_status")
        .order("title")
        .execute()
    )
    return list(response.data or [])


def insert_songs(client: Client, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    response = client.table("songs").insert(rows).execute()
    return list(response.data or [])


def fetch_songs_needing_analysis(client: Client) -> list[dict[str, Any]]:
    response = (
        client.table("songs")
        .select("id, title, author, lyrics, analysis_status")
        .in_("analysis_status", ["pending", "failed"])
        .order("title")
        .execute()
    )
    return list(response.data or [])


def save_analysis_result(
    client: Client,
    song_id: str,
    *,
    analysis: SongAnalysis | None,
) -> None:
    if analysis is None:
        client.table("songs").update({"analysis_status": "failed"}).eq("id", song_id).execute()
        return
    client.table("songs").update(
        {
            "tags": analysis.tags,
            "scripture_refs": analysis.scripture_refs,
            "energy": analysis.energy,
            "summary": analysis.summary,
            "analysis_status": "done",
        },
    ).eq("id", song_id).execute()


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
