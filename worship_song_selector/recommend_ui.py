from __future__ import annotations

import json
import time
from typing import Any

import streamlit as st
import streamlit.components.v1 as components
from supabase import Client

from worship_song_selector.config import OpenAIConfig
from worship_song_selector.library_ui import ENERGY_LABELS
from worship_song_selector.recommendation import (
    FlowSlot,
    RecommendationPick,
    default_flow_template,
    recommend_set_with_completion,
)
from worship_song_selector.song_analysis import make_openai_completion_fn
from worship_song_selector.songs import list_analysed_songs_for_recommendation

SESSION_RECOMMEND_RESULTS_KEY = "recommend_results"
SESSION_RECOMMEND_THEME_KEY = "recommend_theme"


def format_numbered_titles(lines: list[tuple[int, str]]) -> str:
    return "\n".join(f"{number}. {title}" for number, title in lines)


def _songs_by_id(songs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(song["id"]): song for song in songs}


def _build_display_lines(
    picks: list[RecommendationPick],
    *,
    songs_by_id: dict[str, dict[str, Any]],
    flow_slots: list[FlowSlot],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, pick in enumerate(picks):
        song = songs_by_id[pick.song_id]
        slot = flow_slots[index]
        rows.append(
            {
                "number": index + 1,
                "title": str(song.get("title") or ""),
                "author": str(song.get("author") or "—"),
                "slot_role": slot.role,
                "energy": ENERGY_LABELS.get(str(song.get("energy")), song.get("energy") or "—"),
                "reason": pick.reason,
            },
        )
    return rows


def _copy_titles_to_clipboard(text: str) -> None:
    escaped = json.dumps(text)
    components.html(
        f"""<script>
        navigator.clipboard.writeText({escaped});
        </script>""",
        height=0,
    )


def render_recommend_tab(client: Client, openai_config: OpenAIConfig) -> None:
    st.subheader("Препоръка")
    st.caption(
        "Въведете тема, откъс или бележки — ще получите 5 песни от библиотеката.",
    )

    theme = st.text_area(
        "Тема",
        value=st.session_state.get(SESSION_RECOMMEND_THEME_KEY, ""),
        height=120,
        key="recommend_theme_input",
    )

    if st.button("Генерирай сет", type="primary"):
        st.session_state[SESSION_RECOMMEND_THEME_KEY] = theme
        if not theme.strip():
            st.error("Моля, въведете тема.")
            return
        if not openai_config.api_key:
            st.error("Липсва OpenAI API ключ в secrets.")
            return
        try:
            songs = list_analysed_songs_for_recommendation(client)
        except Exception as exc:
            st.error(f"Неуспешна връзка с базата данни: {exc}")
            return
        if len(songs) < 5:
            st.error(
                "Трябват поне 5 анализирани песни в библиотеката "
                f"(налични: {len(songs)}).",
            )
            return

        flow_slots = default_flow_template()
        valid_ids = {str(s["id"]) for s in songs}
        completion = make_openai_completion_fn(
            api_key=openai_config.api_key,
            model=openai_config.model,
        )
        started = time.perf_counter()
        with st.spinner("Генериране…"):
            picks = recommend_set_with_completion(
                completion,
                theme=theme,
                flow_slots=flow_slots,
                songs=songs,
                valid_ids=valid_ids,
            )
        elapsed = time.perf_counter() - started

        if picks is None:
            st.error(
                "Моделът върна невалиден отговор след повторен опит. "
                "Опитайте отново или сменете темата.",
            )
            return

        display = _build_display_lines(
            picks,
            songs_by_id=_songs_by_id(songs),
            flow_slots=flow_slots,
        )
        st.session_state[SESSION_RECOMMEND_RESULTS_KEY] = display
        st.caption(f"Готово за {elapsed:.1f} s.")

    display_rows = st.session_state.get(SESSION_RECOMMEND_RESULTS_KEY)
    if not display_rows:
        return

    st.divider()
    title_lines = [(row["number"], row["title"]) for row in display_rows]
    copy_text = format_numbered_titles(title_lines)
    if st.button("Копирай заглавия"):
        _copy_titles_to_clipboard(copy_text)
        st.success("Заглавията са копирани в клипборда.")

    for row in display_rows:
        st.markdown(
            f"**{row['number']}. {row['title']}** — {row['author']} · "
            f"{row['slot_role']} · {row['energy']}",
        )
        st.markdown(f"<small>{row['reason']}</small>", unsafe_allow_html=True)
