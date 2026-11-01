from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal


class ImportMatchKind(str, Enum):
    NEW = "new"
    UPDATE = "update"
    IDENTICAL = "identical"


class ImportActionKind(str, Enum):
    INSERT = "insert"
    UPDATE = "update"
    SKIP = "skip"


ImportOverride = Literal["new"] | str | None


@dataclass(frozen=True)
class ResolvedImportAction:
    kind: ImportActionKind
    song_id: str | None = None


@dataclass(frozen=True)
class ImportAction:
    kind: ImportActionKind
    song_id: str | None = None
    row: dict[str, Any] | None = None
    overwrite_hand_edits: bool = False


def lyrics_equal(
    left: list[dict[str, Any]] | None,
    right: list[dict[str, Any]] | None,
) -> bool:
    return left == right


def classify_against_existing(
    lyrics: list[dict[str, Any]],
    existing: dict[str, Any] | None,
) -> ImportMatchKind:
    if existing is None:
        return ImportMatchKind.NEW
    if lyrics_equal(lyrics, existing.get("lyrics")):
        return ImportMatchKind.IDENTICAL
    return ImportMatchKind.UPDATE


def batch_duplicate_normalized_titles(normalized_titles: list[str]) -> frozenset[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for title in normalized_titles:
        if title in seen:
            duplicates.add(title)
        seen.add(title)
    return frozenset(duplicates)


def auto_match_kind(
    *,
    lyrics: list[dict[str, Any]],
    normalized_title: str,
    existing_by_normalized: dict[str, dict[str, Any]],
) -> ImportMatchKind:
    existing = existing_by_normalized.get(normalized_title)
    return classify_against_existing(lyrics, existing)


def resolve_import_action(
    *,
    lyrics: list[dict[str, Any]],
    normalized_title: str,
    existing_by_normalized: dict[str, dict[str, Any]],
    existing_songs_by_id: dict[str, dict[str, Any]],
    override: ImportOverride,
) -> ResolvedImportAction:
    if override == "new":
        return ResolvedImportAction(kind=ImportActionKind.INSERT)

    if override is not None:
        target = existing_songs_by_id.get(override)
        if target is None:
            raise ValueError(f"Unknown song id override: {override}")
        if lyrics_equal(lyrics, target.get("lyrics")):
            return ResolvedImportAction(kind=ImportActionKind.SKIP, song_id=override)
        return ResolvedImportAction(kind=ImportActionKind.UPDATE, song_id=override)

    kind = auto_match_kind(
        lyrics=lyrics,
        normalized_title=normalized_title,
        existing_by_normalized=existing_by_normalized,
    )
    if kind == ImportMatchKind.NEW:
        return ResolvedImportAction(kind=ImportActionKind.INSERT)
    existing = existing_by_normalized[normalized_title]
    if kind == ImportMatchKind.IDENTICAL:
        return ResolvedImportAction(kind=ImportActionKind.SKIP, song_id=existing["id"])
    return ResolvedImportAction(kind=ImportActionKind.UPDATE, song_id=existing["id"])


def import_preview_label(kind: ImportMatchKind, existing_title: str | None) -> str:
    if kind == ImportMatchKind.NEW:
        return "Нова"
    if kind == ImportMatchKind.UPDATE:
        return f"Обновява: {existing_title or '?'}"
    return "Същата — пропуск"


def import_action_preview_label(
    resolved: ResolvedImportAction,
    *,
    existing_songs_by_id: dict[str, dict[str, Any]],
) -> str:
    if resolved.kind == ImportActionKind.INSERT:
        return "Нова"
    if resolved.kind == ImportActionKind.SKIP:
        return "Същата — пропуск"
    title = "?"
    if resolved.song_id and resolved.song_id in existing_songs_by_id:
        title = str(existing_songs_by_id[resolved.song_id]["title"])
    return f"Обновява: {title}"


def plan_import_actions(
    drafts: list[dict[str, Any]],
    *,
    existing_by_normalized: dict[str, dict[str, Any]],
    existing_songs_by_id: dict[str, dict[str, Any]],
) -> list[ImportAction]:
    actions: list[ImportAction] = []
    for draft in drafts:
        resolved = resolve_import_action(
            lyrics=draft["lyrics"],
            normalized_title=draft["normalized_title"],
            existing_by_normalized=existing_by_normalized,
            existing_songs_by_id=existing_songs_by_id,
            override=draft.get("override"),
        )
        kind = resolved.kind
        song_id = resolved.song_id
        row = {
            "title": draft["title"],
            "normalized_title": draft["normalized_title"],
            "author": draft.get("author"),
            "lyrics": draft["lyrics"],
            "raw_text": draft["raw_text"],
            "analysis_status": "pending",
        }
        actions.append(
            ImportAction(
                kind=kind,
                song_id=song_id,
                row=row if kind != ImportActionKind.SKIP else None,
                overwrite_hand_edits=bool(draft.get("overwrite_hand_edits")),
            ),
        )
    return actions
