from __future__ import annotations

from typing import Any

from supabase import Client, create_client

from worship_song_selector.config import SupabaseConfig
from worship_song_selector.import_matching import ImportAction, ImportActionKind
from worship_song_selector.song_analysis import SongAnalysis
from worship_song_selector.song_maintenance import (
    AdminSongFields,
    TitleClashError,
    import_update_preserves_hand_edits,
    normalized_title_clash,
    should_set_tags_edited,
)
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


def list_songs_for_library(client: Client) -> list[dict[str, Any]]:
    response = (
        client.table("songs")
        .select(
            "id, title, author, energy, tags, lyrics, summary, "
            "scripture_refs, analysis_status, tags_edited",
        )
        .order("title")
        .execute()
    )
    return list(response.data or [])


def fetch_songs_for_title_clash_check(client: Client) -> list[dict[str, Any]]:
    response = (
        client.table("songs")
        .select("id, title, normalized_title")
        .execute()
    )
    return list(response.data or [])


def update_song_admin(
    client: Client,
    song_id: str,
    fields: AdminSongFields,
    *,
    existing: dict[str, Any],
    songs_by_normalized: dict[str, dict[str, Any]],
) -> None:
    normalized = normalize_title(fields.title)
    if normalized_title_clash(
        normalized,
        songs_by_normalized=songs_by_normalized,
        exclude_song_id=song_id,
    ):
        raise TitleClashError(normalized)

    tags_edited = should_set_tags_edited(
        existing,
        fields,
    )
    client.table("songs").update(
        {
            "title": fields.title.strip(),
            "normalized_title": normalized,
            "author": fields.author,
            "energy": fields.energy,
            "tags": fields.tags,
            "summary": fields.summary,
            "scripture_refs": fields.scripture_refs,
            "tags_edited": tags_edited,
        },
    ).eq("id", song_id).execute()


def delete_song(client: Client, song_id: str) -> None:
    client.table("songs").delete().eq("id", song_id).execute()


def list_songs_for_reanalysis(client: Client) -> list[dict[str, Any]]:
    response = (
        client.table("songs")
        .select("id, title, author, lyrics, tags_edited")
        .order("title")
        .execute()
    )
    return list(response.data or [])


def fetch_song_tags_edited(client: Client, song_id: str) -> bool:
    response = (
        client.table("songs")
        .select("tags_edited")
        .eq("id", song_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        return False
    return bool(rows[0].get("tags_edited"))


def insert_songs(client: Client, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    response = client.table("songs").insert(rows).execute()
    return list(response.data or [])


def fetch_songs_for_import(client: Client) -> list[dict[str, Any]]:
    response = (
        client.table("songs")
        .select(
            "id, title, normalized_title, lyrics, raw_text, tags_edited, "
            "energy, tags, summary, scripture_refs, analysis_status",
        )
        .order("title")
        .execute()
    )
    return list(response.data or [])


def update_song_from_import(
    client: Client,
    song_id: str,
    row: dict[str, Any],
    *,
    existing: dict[str, Any],
    overwrite_hand_edits: bool,
) -> bool:
    """Returns True if the song should be queued for analysis after import."""
    preserve = import_update_preserves_hand_edits(
        tags_edited=bool(existing.get("tags_edited")),
        overwrite_hand_edits=overwrite_hand_edits,
    )
    payload: dict[str, Any] = {
        "title": row["title"],
        "normalized_title": row["normalized_title"],
        "author": row["author"],
        "lyrics": row["lyrics"],
        "raw_text": row["raw_text"],
    }
    if preserve:
        payload["analysis_status"] = existing.get("analysis_status") or "done"
    else:
        payload["analysis_status"] = "pending"
        if overwrite_hand_edits and existing.get("tags_edited"):
            payload["tags_edited"] = False
    client.table("songs").update(payload).eq("id", song_id).execute()
    return not preserve


def apply_import_actions(
    client: Client,
    actions: list[ImportAction],
) -> tuple[int, int, int, list[dict[str, Any]]]:
    """Returns inserted_count, updated_count, skipped_count, songs_for_analysis."""
    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    for_analysis: list[dict[str, Any]] = []
    existing_by_id = {song["id"]: song for song in fetch_songs_for_import(client)}

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
            existing_row = existing_by_id.get(action.song_id)
            if existing_row is None:
                raise ValueError(f"Import update target missing: {action.song_id}")
            needs_analysis = update_song_from_import(
                client,
                action.song_id,
                action.row,
                existing=existing_row,
                overwrite_hand_edits=action.overwrite_hand_edits,
            )
            updated_count += 1
            if needs_analysis:
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
    overwrite_hand_edits: bool = True,
) -> None:
    if analysis is None:
        client.table("songs").update({"analysis_status": "failed"}).eq("id", song_id).execute()
        return
    tags_edited = fetch_song_tags_edited(client, song_id)
    if tags_edited and not overwrite_hand_edits:
        client.table("songs").update({"analysis_status": "done"}).eq("id", song_id).execute()
        return
    client.table("songs").update(
        {
            "tags": analysis.tags,
            "scripture_refs": analysis.scripture_refs,
            "energy": analysis.energy,
            "summary": analysis.summary,
            "analysis_status": "done",
            "tags_edited": False,
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
