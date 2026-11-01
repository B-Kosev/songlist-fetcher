from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Energy = Literal["fast", "medium", "slow"] | None

VALID_ENERGY: frozenset[str] = frozenset({"fast", "medium", "slow"})


class TitleClashError(ValueError):
    """Another song already uses this normalized title."""


class InvalidEnergyError(ValueError):
    pass


@dataclass(frozen=True)
class AdminSongFields:
    title: str
    author: str | None
    energy: Energy
    tags: list[str]
    summary: str | None
    scripture_refs: list[str]


def parse_comma_separated_list(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def parse_energy_value(raw: str | None) -> Energy:
    if raw is None or not str(raw).strip():
        return None
    value = str(raw).strip()
    if value not in VALID_ENERGY:
        raise InvalidEnergyError(f"invalid energy: {value}")
    return value  # type: ignore[return-value]


def ai_fields_changed(
    existing: dict[str, Any],
    *,
    energy: Energy,
    tags: list[str],
    summary: str | None,
    scripture_refs: list[str],
) -> bool:
    if energy != existing.get("energy"):
        return True
    if tags != list(existing.get("tags") or []):
        return True
    existing_summary = (existing.get("summary") or "").strip() or None
    new_summary = (summary or "").strip() or None
    if new_summary != existing_summary:
        return True
    if scripture_refs != list(existing.get("scripture_refs") or []):
        return True
    return False


def should_set_tags_edited(existing: dict[str, Any], fields: AdminSongFields) -> bool:
    if existing.get("tags_edited"):
        return True
    return ai_fields_changed(
        existing,
        energy=fields.energy,
        tags=fields.tags,
        summary=fields.summary,
        scripture_refs=fields.scripture_refs,
    )


def normalized_title_clash(
    normalized_title: str,
    *,
    songs_by_normalized: dict[str, dict[str, Any]],
    exclude_song_id: str | None,
) -> bool:
    other = songs_by_normalized.get(normalized_title)
    if other is None:
        return False
    if exclude_song_id is not None and other.get("id") == exclude_song_id:
        return False
    return True


def import_update_preserves_hand_edits(
    *,
    tags_edited: bool,
    overwrite_hand_edits: bool,
) -> bool:
    return tags_edited and not overwrite_hand_edits


def analysis_result_may_overwrite_hand_edits(
    *,
    tags_edited: bool,
    overwrite_hand_edits: bool,
) -> bool:
    if not tags_edited:
        return True
    return overwrite_hand_edits
