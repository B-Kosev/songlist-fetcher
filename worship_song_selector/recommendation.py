from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

CompletionFn = Callable[[list[dict[str, str]]], str]


class RecommendationValidationError(ValueError):
    pass


@dataclass(frozen=True)
class FlowSlot:
    role: str
    energy: str
    purpose: str


@dataclass(frozen=True)
class RecommendationPick:
    song_id: str
    reason: str


def default_flow_template() -> list[FlowSlot]:
    return [
        FlowSlot(
            role="Хваление",
            energy="fast",
            purpose="Opening, celebratory, invites the church to gather",
        ),
        FlowSlot(
            role="Хваление",
            energy="fast / medium",
            purpose="Sustains energy, starts moving toward the theme",
        ),
        FlowSlot(
            role="Преход",
            energy="medium",
            purpose="Bridges into reflection, closest to the theme",
        ),
        FlowSlot(
            role="Поклонение",
            energy="slow",
            purpose="Intimate, focused on God's character as it relates to the theme",
        ),
        FlowSlot(
            role="Отговор",
            energy="medium / slow",
            purpose="Response: commitment, sending, consecration",
        ),
    ]


def _format_flow_for_prompt(slots: list[FlowSlot]) -> str:
    lines: list[str] = []
    for index, slot in enumerate(slots, start=1):
        lines.append(
            f"{index}. {slot.role} | energy: {slot.energy} | {slot.purpose}",
        )
    return "\n".join(lines)


def _format_songs_for_prompt(songs: list[dict[str, Any]]) -> str:
    compact: list[dict[str, Any]] = []
    for song in songs:
        compact.append(
            {
                "id": str(song["id"]),
                "title": str(song.get("title") or ""),
                "energy": song.get("energy"),
                "tags": song.get("tags") or [],
                "scripture_refs": song.get("scripture_refs") or [],
                "summary": str(song.get("summary") or ""),
            },
        )
    return json.dumps(compact, ensure_ascii=False)


def build_recommendation_messages(
    *,
    theme: str,
    flow_slots: list[FlowSlot],
    songs: list[dict[str, Any]],
) -> list[dict[str, str]]:
    system_content = (
        "Ти помагаш на българска worship група да подбере 5 песни за служба. "
        "Отговори само с валиден JSON обект (без markdown) с ключ "
        '"picks": масив от точно 5 обекта, всеки с:\n'
        '- "song_id": id от каталога (стринг)\n'
        '- "reason": едно кратко изречение на български защо песента пасва на слота\n'
        "Редът на масива е редът на слотовете в шаблона (1–5). "
        "Използвай само song_id от каталога; без повторения."
    )
    user_content = (
        f"Тема на службата:\n{theme.strip()}\n\n"
        f"Шаблон за поток (5 слота):\n{_format_flow_for_prompt(flow_slots)}\n\n"
        f"Каталог на анализирани песни (JSON):\n{_format_songs_for_prompt(songs)}"
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def parse_recommendation_response(
    raw: str,
    *,
    valid_ids: set[str],
) -> list[RecommendationPick]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RecommendationValidationError("invalid json") from exc
    if not isinstance(data, dict):
        raise RecommendationValidationError("expected object")

    picks_raw = data.get("picks")
    if not isinstance(picks_raw, list) or len(picks_raw) != 5:
        raise RecommendationValidationError("expected five picks")

    picks: list[RecommendationPick] = []
    seen: set[str] = set()
    for item in picks_raw:
        if not isinstance(item, dict):
            raise RecommendationValidationError("invalid pick")
        song_id_raw = item.get("song_id")
        reason_raw = item.get("reason")
        if not isinstance(song_id_raw, str) or not song_id_raw.strip():
            raise RecommendationValidationError("invalid song_id")
        song_id = song_id_raw.strip()
        if song_id not in valid_ids:
            raise RecommendationValidationError("unknown song_id")
        if song_id in seen:
            raise RecommendationValidationError("duplicate song_id")
        seen.add(song_id)
        if not isinstance(reason_raw, str) or not reason_raw.strip():
            raise RecommendationValidationError("invalid reason")
        picks.append(RecommendationPick(song_id=song_id, reason=reason_raw.strip()))

    return picks


def recommend_set_with_completion(
    completion: CompletionFn,
    *,
    theme: str,
    flow_slots: list[FlowSlot],
    songs: list[dict[str, Any]],
    valid_ids: set[str],
    max_attempts: int = 2,
) -> list[RecommendationPick] | None:
    messages = build_recommendation_messages(
        theme=theme,
        flow_slots=flow_slots,
        songs=songs,
    )
    for _ in range(max_attempts):
        raw = completion(messages)
        try:
            return parse_recommendation_response(raw, valid_ids=valid_ids)
        except RecommendationValidationError:
            continue
    return None
