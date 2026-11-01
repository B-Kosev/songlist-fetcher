from __future__ import annotations

from typing import Any

from supabase import Client, create_client

from worship_song_selector.config import SupabaseConfig
from worship_song_selector.import_matching import ImportAction, ImportActionKind
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


def fetch_songs_for_import(client: Client) -> list[dict[str, Any]]:
    response = (
        client.table("songs")
        .select("id, title, normalized_title, lyrics, raw_text")
        .order("title")
        .execute()
    )
    return list(response.data or [])


def update_song_from_import(
    client: Client,
    song_id: str,
    row: dict[str, Any],
) -> None:
    client.table("songs").update(
        {
            "title": row["title"],
            "normalized_title": row["normalized_title"],
            "author": row["author"],
            "lyrics": row["lyrics"],
            "raw_text": row["raw_text"],
            "analysis_status": "pending",
        },
    ).eq("id", song_id).execute()


def apply_import_actions(
    client: Client,
    actions: list[ImportAction],
) -> tuple[int, int, int, list[dict[str, Any]]]:
    """Returns inserted_count, updated_count, skipped_count, songs_for_analysis."""
    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    for_analysis: list[dict[str, Any]] = []

    for action in actions:
        if action.kind == ImportActionKind.SKIP:
            skipped_count += 1
            continue
        if action.row is None:
            raise ValueError("Import action missing row payload")
        if action.kind == ImportActionKind.INSERT:
            created = insert_songs(client, [action.row])
            inserted_count += len(created)
            for_analysis.extend(created)
        elif action.kind == ImportActionKind.UPDATE:
            if not action.song_id:
                raise ValueError("Update action missing song id")
            update_song_from_import(client, action.song_id, action.row)
            updated_count += 1
            for_analysis.append(
                {
                    "id": action.song_id,
                    "title": action.row["title"],
                    "author": action.row.get("author"),
                    "lyrics": action.row["lyrics"],
                },
            )
        else:
            raise ValueError(f"Unsupported import action: {action.kind}")

    return inserted_count, updated_count, skipped_count, for_analysis


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
