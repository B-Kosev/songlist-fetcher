from __future__ import annotations

import json
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Literal

from worship_song_selector.openai_metrics import OpenAIUsageRecord, UsageCallback

Energy = Literal["fast", "medium", "slow"]

VALID_ENERGY: frozenset[str] = frozenset({"fast", "medium", "slow"})


class AnalysisValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SongAnalysis:
    tags: list[str]
    scripture_refs: list[str]
    energy: Energy
    summary: str


CompletionFn = Callable[[list[dict[str, str]]], str]


def lyrics_to_plain_text(lyrics: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for section in lyrics:
        label = str(section.get("section_type", "section"))
        if "number" in section:
            label = f"{label} {section['number']}"
        parts.append(f"[{label}]")
        for line in section.get("lines") or []:
            parts.append(str(line))
        parts.append("")
    return "\n".join(parts).strip()


def build_analysis_messages(
    *,
    title: str,
    author: str | None,
    lyrics_plain: str,
) -> list[dict[str, str]]:
    author_line = author.strip() if author else "неизвестен"
    user_content = (
        f"Заглавие: {title.strip()}\n"
        f"Автор: {author_line}\n\n"
        f"Текст на песента:\n{lyrics_plain}"
    )
    system_content = (
        "Ти анализираш християнски worship песни за българска църква. "
        "Отговори само с валиден JSON обект (без markdown) с ключове:\n"
        '- "tags": масив от кратки тематични етикети на български '
        "(2–6 думи, до 8 етикета)\n"
        '- "scripture_refs": масив от кратки библейски препратки (може празен)\n'
        '- "energy": точно една от стойностите "fast", "medium", "slow"\n'
        '- "summary": едно кратко изречение на български (до ~120 символа)\n'
        "Дръж етикетите и резюмето компактни."
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def parse_analysis_response(raw: str) -> SongAnalysis:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AnalysisValidationError("invalid json") from exc
    if not isinstance(data, dict):
        raise AnalysisValidationError("expected object")

    tags_raw = data.get("tags")
    refs_raw = data.get("scripture_refs")
    energy_raw = data.get("energy")
    summary_raw = data.get("summary")

    if not isinstance(tags_raw, list) or not all(isinstance(t, str) for t in tags_raw):
        raise AnalysisValidationError("invalid tags")
    tags = [t.strip() for t in tags_raw if t.strip()]
    if not tags:
        raise AnalysisValidationError("empty tags")

    if not isinstance(refs_raw, list) or not all(isinstance(r, str) for r in refs_raw):
        raise AnalysisValidationError("invalid scripture_refs")
    scripture_refs = [r.strip() for r in refs_raw if r.strip()]

    if not isinstance(energy_raw, str) or energy_raw not in VALID_ENERGY:
        raise AnalysisValidationError("invalid energy")

    if not isinstance(summary_raw, str) or not summary_raw.strip():
        raise AnalysisValidationError("invalid summary")

    return SongAnalysis(
        tags=tags,
        scripture_refs=scripture_refs,
        energy=energy_raw,  # type: ignore[arg-type]
        summary=summary_raw.strip(),
    )


def analyze_song_with_completion(
    completion: CompletionFn,
    *,
    model: str,
    title: str,
    author: str | None,
    lyrics_plain: str,
    max_attempts: int = 2,
) -> SongAnalysis | None:
    messages = build_analysis_messages(
        title=title,
        author=author,
        lyrics_plain=lyrics_plain,
    )
    for _ in range(max_attempts):
        raw = completion(messages)
        try:
            return parse_analysis_response(raw)
        except AnalysisValidationError:
            continue
    return None


def make_openai_completion_fn(
    *,
    api_key: str,
    model: str,
    on_usage: UsageCallback | None = None,
) -> CompletionFn:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    def complete(messages: list[dict[str, str]]) -> str:
        started = time.perf_counter()
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        latency = time.perf_counter() - started
        usage = response.usage
        if on_usage is not None and usage is not None:
            on_usage(
                OpenAIUsageRecord(
                    prompt_tokens=int(usage.prompt_tokens or 0),
                    completion_tokens=int(usage.completion_tokens or 0),
                    latency_seconds=latency,
                ),
            )
        return response.choices[0].message.content or ""

    return complete


def analyze_songs_concurrently(
    songs: list[dict[str, Any]],
    *,
    completion: CompletionFn,
    model: str,
    apply_result: Callable[[str, SongAnalysis | None], None],
    max_workers: int = 8,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[int, int]:
    if not songs:
        return 0, 0

    done_count = 0
    failed_count = 0
    total = len(songs)

    def analyse_one(song: dict[str, Any]) -> tuple[str, SongAnalysis | None]:
        song_id = str(song["id"])
        lyrics = song.get("lyrics") or []
        result = analyze_song_with_completion(
            completion,
            model=model,
            title=str(song.get("title") or ""),
            author=song.get("author"),
            lyrics_plain=lyrics_to_plain_text(lyrics),
        )
        return song_id, result

    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(analyse_one, song): song for song in songs}
        for future in as_completed(futures):
            song_id, analysis = future.result()
            apply_result(song_id, analysis)
            if analysis is None:
                failed_count += 1
            else:
                done_count += 1
            completed += 1
            if on_progress is not None:
                on_progress(completed, total)

    return done_count, failed_count
