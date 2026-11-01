from __future__ import annotations

from supabase import Client

from worship_song_selector.config import OpenAIConfig
from worship_song_selector.flow_settings import fetch_flow_template
from worship_song_selector.model_eval import DEFAULT_EVAL_THEMES
from worship_song_selector.openai_metrics import OpenAIUsageRecord
from worship_song_selector.recommendation import recommend_set_with_completion
from worship_song_selector.song_analysis import (
    analyze_song_with_completion,
    lyrics_to_plain_text,
    make_openai_completion_fn,
)
from worship_song_selector.songs import list_analysed_songs_for_recommendation, list_songs_for_library


def measure_recommendation_queries(
    client: Client,
    *,
    openai_config: OpenAIConfig,
    themes: list[str],
) -> tuple[list[tuple[str, list[OpenAIUsageRecord]]], int]:
    songs = list_analysed_songs_for_recommendation(client)
    if len(songs) < 5:
        raise ValueError(
            f"Need at least 5 analysed songs for recommendation eval (have {len(songs)}).",
        )
    flow_slots = fetch_flow_template(client)
    valid_ids = {str(song["id"]) for song in songs}
    by_theme: list[tuple[str, list[OpenAIUsageRecord]]] = []

    for theme in themes:
        theme_records: list[OpenAIUsageRecord] = []

        def on_usage(record: OpenAIUsageRecord) -> None:
            theme_records.append(record)

        completion = make_openai_completion_fn(
            api_key=openai_config.api_key,
            model=openai_config.model,
            on_usage=on_usage,
        )
        recommend_set_with_completion(
            completion,
            theme=theme,
            flow_slots=flow_slots,
            songs=songs,
            valid_ids=valid_ids,
        )
        by_theme.append((theme, theme_records))
    return by_theme, len(songs)


def measure_analysis_samples(
    client: Client,
    *,
    openai_config: OpenAIConfig,
    sample_size: int,
) -> list[OpenAIUsageRecord]:
    if sample_size <= 0:
        return []
    library = list_songs_for_library(client)
    candidates = [song for song in library if song.get("lyrics")]
    if not candidates:
        raise ValueError("No songs with lyrics in the library for analysis sampling.")
    sample = candidates[:sample_size]
    records: list[OpenAIUsageRecord] = []

    for song in sample:
        call_records: list[OpenAIUsageRecord] = []

        def on_usage(record: OpenAIUsageRecord) -> None:
            call_records.append(record)

        completion = make_openai_completion_fn(
            api_key=openai_config.api_key,
            model=openai_config.model,
            on_usage=on_usage,
        )
        analyze_song_with_completion(
            completion,
            model=openai_config.model,
            title=str(song.get("title") or ""),
            author=song.get("author"),
            lyrics_plain=lyrics_to_plain_text(song.get("lyrics") or []),
        )
        records.extend(call_records)
    return records


def default_eval_themes(*, max_themes: int | None = None) -> list[str]:
    themes = list(DEFAULT_EVAL_THEMES)
    if max_themes is not None:
        themes = themes[:max_themes]
    return themes
