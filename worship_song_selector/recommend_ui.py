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
SESSION_RECOMMEND_PICKS_KEY = "recommend_picks"
SESSION_RECOMMEND_LOCKED_SLOTS_KEY = "recommend_locked_slots"
SESSION_RECOMMEND_FORM_EXCLUDED_KEY = "recommend_form_excluded_ids"
SESSION_RECOMMEND_REPLACE_EXCLUDED_KEY = "recommend_replace_excluded_ids"


def clear_recommend_session_state() -> None:
    for key in (
        SESSION_RECOMMEND_RESULTS_KEY,
        SESSION_RECOMMEND_THEME_KEY,
        SESSION_RECOMMEND_PICKS_KEY,
        SESSION_RECOMMEND_LOCKED_SLOTS_KEY,
        SESSION_RECOMMEND_FORM_EXCLUDED_KEY,
        SESSION_RECOMMEND_REPLACE_EXCLUDED_KEY,
    ):
        st.session_state.pop(key, None)
    for slot_index in range(5):
        st.session_state.pop(f"recommend_lock_{slot_index}", None)


def clear_recommend_refinement_state() -> None:
    st.session_state.pop(SESSION_RECOMMEND_LOCKED_SLOTS_KEY, None)
    st.session_state[SESSION_RECOMMEND_FORM_EXCLUDED_KEY] = []
    st.session_state[SESSION_RECOMMEND_REPLACE_EXCLUDED_KEY] = []
    for slot_index in range(5):
        st.session_state.pop(f"recommend_lock_{slot_index}", None)


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
                "slot_index": index,
                "song_id": pick.song_id,
                "number": index + 1,
                "title": str(song.get("title") or ""),
                "author": str(song.get("author") or "—"),
                "slot_role": slot.role,
                "energy": ENERGY_LABELS.get(str(song.get("energy")), song.get("energy") or "—"),
                "reason": pick.reason,
            },
        )
    return rows


def _picks_from_session() -> list[RecommendationPick] | None:
    raw = st.session_state.get(SESSION_RECOMMEND_PICKS_KEY)
    if not raw:
        return None
    return [
        RecommendationPick(song_id=str(item["song_id"]), reason=str(item["reason"]))
        for item in raw
    ]


def _store_picks(
    picks: list[RecommendationPick],
    *,
    songs_by_id: dict[str, dict[str, Any]],
    flow_slots: list[FlowSlot],
) -> None:
    st.session_state[SESSION_RECOMMEND_PICKS_KEY] = [
        {"song_id": pick.song_id, "reason": pick.reason} for pick in picks
    ]
    st.session_state[SESSION_RECOMMEND_RESULTS_KEY] = _build_display_lines(
        picks,
        songs_by_id=songs_by_id,
        flow_slots=flow_slots,
    )


def _excluded_ids() -> set[str]:
    form_raw = st.session_state.get(SESSION_RECOMMEND_FORM_EXCLUDED_KEY, [])
    replace_raw = st.session_state.get(SESSION_RECOMMEND_REPLACE_EXCLUDED_KEY, [])
    return {str(item) for item in form_raw} | {str(item) for item in replace_raw}


def _locked_slot_indices() -> set[int]:
    raw = st.session_state.get(SESSION_RECOMMEND_LOCKED_SLOTS_KEY, [])
    return {int(item) for item in raw}


def _locked_by_slot(picks: list[RecommendationPick]) -> dict[int, str]:
    locked = _locked_slot_indices()
    return {
        slot_index: picks[slot_index].song_id
        for slot_index in locked
        if 0 <= slot_index < len(picks)
    }


def _copy_titles_to_clipboard(text: str) -> None:
    escaped = json.dumps(text)
    components.html(
        f"""<script>
        navigator.clipboard.writeText({escaped});
        </script>""",
        height=0,
    )


def _run_completion(
    *,
    theme: str,
    songs: list[dict[str, Any]],
    openai_config: OpenAIConfig,
    locked_by_slot: dict[int, str] | None = None,
    excluded_ids: set[str] | None = None,
    required_by_slot: dict[int, str] | None = None,
    replace_slot: int | None = None,
    replace_rejected_id: str | None = None,
) -> list[RecommendationPick] | None:
    flow_slots = default_flow_template()
    valid_ids = {str(s["id"]) for s in songs}
    completion = make_openai_completion_fn(
        api_key=openai_config.api_key,
        model=openai_config.model,
    )
    return recommend_set_with_completion(
        completion,
        theme=theme,
        flow_slots=flow_slots,
        songs=songs,
        valid_ids=valid_ids,
        locked_by_slot=locked_by_slot,
        excluded_ids=excluded_ids,
        required_by_slot=required_by_slot,
        replace_slot=replace_slot,
        replace_rejected_id=replace_rejected_id,
    )


def render_recommend_tab(client: Client, openai_config: OpenAIConfig) -> None:
    st.subheader("Препоръка")
    st.caption(
        "Въведете тема, откъс или бележки — ще получите 5 песни от библиотеката.",
    )

    try:
        catalogue_songs = list_analysed_songs_for_recommendation(client)
    except Exception as exc:
        st.error(f"Неуспешна връзка с базата данни: {exc}")
        catalogue_songs = []

    title_by_id = {
        str(song["id"]): str(song.get("title") or song["id"]) for song in catalogue_songs
    }
    if title_by_id:
        sorted_ids = sorted(title_by_id.keys(), key=lambda sid: title_by_id[sid].lower())
        st.session_state.setdefault(SESSION_RECOMMEND_FORM_EXCLUDED_KEY, [])
        st.session_state.setdefault(SESSION_RECOMMEND_REPLACE_EXCLUDED_KEY, [])
        st.multiselect(
            "Изключи песни",
            options=sorted_ids,
            format_func=lambda sid: title_by_id[sid],
            key=SESSION_RECOMMEND_FORM_EXCLUDED_KEY,
        )

    theme = st.text_area(
        "Тема",
        value=st.session_state.get(SESSION_RECOMMEND_THEME_KEY, ""),
        height=120,
        key="recommend_theme_input",
    )

    if st.button("Генерирай сет", type="primary"):
        previous_theme = str(st.session_state.get(SESSION_RECOMMEND_THEME_KEY, "")).strip()
        new_theme = theme.strip()
        if new_theme != previous_theme:
            clear_recommend_refinement_state()
        st.session_state[SESSION_RECOMMEND_THEME_KEY] = theme
        if not new_theme:
            st.error("Моля, въведете тема.")
            return
        if not openai_config.api_key:
            st.error("Липсва OpenAI API ключ в secrets.")
            return
        if len(catalogue_songs) < 5:
            st.error(
                "Трябват поне 5 анализирани песни в библиотеката "
                f"(налични: {len(catalogue_songs)}).",
            )
            return

        flow_slots = default_flow_template()
        excluded = _excluded_ids()
        started = time.perf_counter()
        with st.spinner("Генериране…"):
            picks = _run_completion(
                theme=theme,
                songs=catalogue_songs,
                openai_config=openai_config,
                excluded_ids=excluded,
            )
        elapsed = time.perf_counter() - started

        if picks is None:
            st.error(
                "Моделът върна невалиден отговор след повторен опит. "
                "Опитайте отново или сменете темата.",
            )
            return

        songs_by_id = _songs_by_id(catalogue_songs)
        _store_picks(picks, songs_by_id=songs_by_id, flow_slots=flow_slots)
        st.session_state[SESSION_RECOMMEND_LOCKED_SLOTS_KEY] = []
        for slot_index in range(5):
            st.session_state.pop(f"recommend_lock_{slot_index}", None)
        st.caption(f"Готово за {elapsed:.1f} s.")

    display_rows = st.session_state.get(SESSION_RECOMMEND_RESULTS_KEY)
    if not display_rows:
        return

    st.divider()
    title_lines = [(row["number"], row["title"]) for row in display_rows]
    copy_text = format_numbered_titles(title_lines)
    header_cols = st.columns([2, 1])
    with header_cols[0]:
        if st.button("Копирай заглавия"):
            _copy_titles_to_clipboard(copy_text)
            st.success("Заглавията са копирани в клипборда.")
    with header_cols[1]:
        regenerate_clicked = st.button("Прегенерирай отключените")

    theme_for_refine = str(st.session_state.get(SESSION_RECOMMEND_THEME_KEY, "")).strip()
    picks = _picks_from_session()
    flow_slots = default_flow_template()

    if regenerate_clicked and picks and theme_for_refine:
        if not openai_config.api_key:
            st.error("Липсва OpenAI API ключ в secrets.")
        elif len(catalogue_songs) < 5:
            st.error("Недостатъчно песни в библиотеката.")
        else:
            locked = _locked_by_slot(picks)
            started = time.perf_counter()
            with st.spinner("Прегенериране…"):
                new_picks = _run_completion(
                    theme=theme_for_refine,
                    songs=catalogue_songs,
                    openai_config=openai_config,
                    locked_by_slot=locked or None,
                    excluded_ids=_excluded_ids(),
                )
            elapsed = time.perf_counter() - started
            if new_picks is None:
                st.error("Прегенерирането не успя след повторен опит.")
            else:
                _store_picks(
                    new_picks,
                    songs_by_id=_songs_by_id(catalogue_songs),
                    flow_slots=flow_slots,
                )
                st.caption(f"Готово за {elapsed:.1f} s.")
                st.rerun()

    display_rows = st.session_state.get(SESSION_RECOMMEND_RESULTS_KEY, [])
    locked_indices = _locked_slot_indices()

    for row in display_rows:
        slot_index = int(row["slot_index"])
        lock_key = f"recommend_lock_{slot_index}"
        if lock_key not in st.session_state:
            st.session_state[lock_key] = slot_index in locked_indices
        line_cols = st.columns([7, 1, 1])
        with line_cols[0]:
            st.markdown(
                f"**{row['number']}. {row['title']}** — {row['author']} · "
                f"{row['slot_role']} · {row['energy']}",
            )
            st.markdown(f"<small>{row['reason']}</small>", unsafe_allow_html=True)
        with line_cols[1]:
            st.checkbox(
                "Заключи",
                key=lock_key,
                label_visibility="collapsed",
            )
        with line_cols[2]:
            if st.button("Смени", key=f"recommend_replace_{slot_index}"):
                if not picks or not theme_for_refine:
                    st.error("Липсва активен сет.")
                elif not openai_config.api_key:
                    st.error("Липсва OpenAI API ключ в secrets.")
                else:
                    rejected_id = str(row["song_id"])
                    excluded = _excluded_ids() | {rejected_id}
                    required = {
                        i: picks[i].song_id for i in range(len(picks)) if i != slot_index
                    }
                    with st.spinner("Смяна…"):
                        new_picks = _run_completion(
                            theme=theme_for_refine,
                            songs=catalogue_songs,
                            openai_config=openai_config,
                            locked_by_slot=_locked_by_slot(picks) or None,
                            excluded_ids=excluded,
                            required_by_slot=required,
                            replace_slot=slot_index,
                            replace_rejected_id=rejected_id,
                        )
                    if new_picks is None:
                        st.error("Смяната не успя след повторен опит.")
                    else:
                        replace_excluded = set(
                            st.session_state.get(SESSION_RECOMMEND_REPLACE_EXCLUDED_KEY, []),
                        )
                        replace_excluded.add(rejected_id)
                        st.session_state[SESSION_RECOMMEND_REPLACE_EXCLUDED_KEY] = sorted(
                            replace_excluded,
                        )
                        _store_picks(
                            new_picks,
                            songs_by_id=_songs_by_id(catalogue_songs),
                            flow_slots=flow_slots,
                        )
                        st.rerun()

    st.session_state[SESSION_RECOMMEND_LOCKED_SLOTS_KEY] = [
        index
        for index in range(len(display_rows))
        if st.session_state.get(f"recommend_lock_{index}", False)
    ]
