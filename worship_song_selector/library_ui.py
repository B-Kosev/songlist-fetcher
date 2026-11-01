from __future__ import annotations

from typing import Any

import streamlit as st
from supabase import Client

from worship_song_selector.library_search import filter_library_songs
from worship_song_selector.songs import list_songs_for_library

LIBRARY_SELECTED_SONG_KEY = "library_selected_song_id"

ENERGY_FILTER_OPTIONS: list[tuple[str, str | None]] = [
    ("Всички", None),
    ("Бърза", "fast"),
    ("Средна", "medium"),
    ("Бавна", "slow"),
]

ENERGY_LABELS = {
    "fast": "Бърза",
    "medium": "Средна",
    "slow": "Бавна",
}


def _format_tags(tags: list[str] | None) -> str:
    if not tags:
        return "—"
    return ", ".join(tags)


def _format_energy(energy: str | None) -> str:
    if not energy:
        return "—"
    return ENERGY_LABELS.get(energy, energy)


def _format_lyrics_for_display(lyrics: list[dict[str, Any]] | None) -> str:
    if not lyrics:
        return "—"
    parts: list[str] = []
    for section in lyrics:
        label = str(section.get("section_type", "section"))
        if "number" in section:
            label = f"{label} {section['number']}"
        parts.append(f"[{label}]")
        parts.extend(str(line) for line in section.get("lines") or [])
        parts.append("")
    return "\n".join(parts).strip()


def _analysis_field(value: str | None, *, status: str) -> str:
    if status == "done":
        return (value or "").strip() or "—"
    if status == "failed":
        return "Анализът неуспешен"
    return "Очаква анализ"


def _selected_song_from_table(
    filtered: list[dict[str, Any]],
    selection_rows: list[int],
) -> dict[str, Any]:
    ids = {song["id"] for song in filtered}
    current_id = st.session_state.get(LIBRARY_SELECTED_SONG_KEY)
    if selection_rows:
        row_index = selection_rows[0]
        if 0 <= row_index < len(filtered):
            current_id = filtered[row_index]["id"]
    if current_id not in ids:
        current_id = filtered[0]["id"]
    st.session_state[LIBRARY_SELECTED_SONG_KEY] = current_id
    return next(song for song in filtered if song["id"] == current_id)


def _render_song_detail(song: dict[str, Any]) -> None:
    st.markdown(f"### {song['title']}")
    author = song.get("author") or "—"
    st.caption(f"Автор: {author} · Енергия: {_format_energy(song.get('energy'))}")

    status = str(song.get("analysis_status") or "pending")
    if status != "done":
        st.info("AI анализът все още не е готов за тази песен.")

    summary = _analysis_field(song.get("summary"), status=status)
    st.markdown(f"**Резюме:** {summary}")

    if status == "done":
        tags_display = _format_tags(song.get("tags"))
    else:
        tags_display = _analysis_field(None, status=status)
    st.markdown(f"**Етикети:** {tags_display}")

    if status == "done":
        refs = song.get("scripture_refs") or []
        refs_display = ", ".join(refs) if refs else "—"
    else:
        refs_display = _analysis_field(None, status=status)
    st.markdown(f"**Препратки:** {refs_display}")

    st.text_area(
        "Текст",
        value=_format_lyrics_for_display(song.get("lyrics")),
        height=320,
        disabled=True,
    )


def render_library_tab(client: Client) -> None:
    st.subheader("Библиотека")
    try:
        songs = list_songs_for_library(client)
    except Exception as exc:
        st.error(f"Неуспешна връзка с базата данни: {exc}")
        return

    if not songs:
        st.write("Няма песни в библиотеката.")
        return

    search_col, energy_col = st.columns([3, 1])
    with search_col:
        query = st.text_input(
            "Търсене",
            placeholder="Заглавие, автор, текст или етикет…",
        )
    with energy_col:
        energy_labels = [label for label, _ in ENERGY_FILTER_OPTIONS]
        energy_choice = st.selectbox(
            "Енергия",
            energy_labels,
            index=0,
        )
    energy_value = next(
        value for label, value in ENERGY_FILTER_OPTIONS if label == energy_choice
    )

    filtered = filter_library_songs(songs, query=query, energy=energy_value)
    st.caption(f"{len(filtered)} от {len(songs)} песни")

    if not filtered:
        st.warning("Няма резултати за текущите филтри.")
        return

    table_rows = [
        {
            "Заглавие": song["title"],
            "Автор": song.get("author") or "—",
            "Енергия": _format_energy(song.get("energy")),
            "Етикети": _format_tags(song.get("tags")),
        }
        for song in filtered
    ]
    table_event = st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="library_songs_table",
    )
    selection_rows = (
        list(table_event.selection.rows)
        if table_event.selection is not None
        else []
    )

    detail_song = _selected_song_from_table(filtered, selection_rows)
    st.divider()
    _render_song_detail(detail_song)
