from __future__ import annotations

from typing import Any

import streamlit as st
from supabase import Client

from worship_song_selector.config import OpenAIConfig
from worship_song_selector.song_analysis import (
    SongAnalysis,
    analyze_songs_concurrently,
    make_openai_completion_fn,
)
from worship_song_selector.songs import fetch_songs_needing_analysis, save_analysis_result


def run_song_analysis_batch(
    client: Client,
    songs: list[dict[str, Any]],
    openai_config: OpenAIConfig,
    *,
    overwrite_hand_edits: bool = True,
) -> tuple[int, int]:
    if not songs:
        return 0, 0
    if not openai_config.api_key.strip():
        st.error("Липсва OpenAI API ключ в Streamlit secrets ([openai].api_key).")
        return 0, 0

    completion = make_openai_completion_fn(
        api_key=openai_config.api_key,
        model=openai_config.model,
    )
    progress = st.progress(0.0, text="Анализ на песни…")

    def apply_result(song_id: str, analysis: SongAnalysis | None) -> None:
        save_analysis_result(
            client,
            song_id,
            analysis=analysis,
            overwrite_hand_edits=overwrite_hand_edits,
        )

    def on_progress(completed: int, total: int) -> None:
        progress.progress(completed / total, text=f"Анализ: {completed}/{total}")

    done_count, failed_count = analyze_songs_concurrently(
        songs,
        completion=completion,
        model=openai_config.model,
        apply_result=apply_result,
        on_progress=on_progress,
    )
    progress.empty()
    return done_count, failed_count


def render_analyse_pending_control(client: Client, openai_config: OpenAIConfig) -> None:
    pending = fetch_songs_needing_analysis(client)
    if not pending:
        return
    st.caption(f"{len(pending)} песни чакат анализ (pending/failed).")
    if st.button("Анализирай pending/failed", type="secondary"):
        done, failed = run_song_analysis_batch(client, pending, openai_config)
        if done or failed:
            st.success(f"Готово: {done} анализирани, {failed} неуспешни.")
            st.rerun()
