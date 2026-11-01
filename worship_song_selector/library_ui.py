from __future__ import annotations

from typing import Any

import streamlit as st
from supabase import Client

from worship_song_selector.analysis_ui import run_song_analysis_batch
from worship_song_selector.auth import Role
from worship_song_selector.config import OpenAIConfig
from worship_song_selector.library_search import filter_library_songs
from worship_song_selector.song_maintenance import (
    AdminSongFields,
    InvalidEnergyError,
    TitleClashError,
    parse_comma_separated_list,
    parse_energy_value,
)
from worship_song_selector.songs import (
    delete_song,
    fetch_songs_for_title_clash_check,
    list_songs_for_library,
    update_song_admin,
)

LIBRARY_SELECTED_SONG_KEY = "library_selected_song_id"

ENERGY_FILTER_OPTIONS: list[tuple[str, str | None]] = [
    ("Всички", None),
    ("Бърза", "fast"),
    ("Средна", "medium"),
    ("Бавна", "slow"),
]

ENERGY_EDIT_OPTIONS: list[tuple[str, str | None]] = [
    ("—", None),
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


def _energy_edit_index(energy: str | None) -> int:
    for index, (_, value) in enumerate(ENERGY_EDIT_OPTIONS):
        if value == energy:
            return index
    return 0


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


def _render_admin_song_detail(
    client: Client,
    song: dict[str, Any],
    *,
    openai_config: OpenAIConfig,
    songs_by_normalized: dict[str, dict[str, Any]],
) -> None:
    song_id = str(song["id"])
    if song.get("tags_edited"):
        st.caption("AI полетата са редактирани на ръка.")

    with st.form(f"admin_edit_{song_id}"):
        title = st.text_input("Заглавие", value=song.get("title") or "")
        author = st.text_input("Автор", value=song.get("author") or "")
        energy_labels = [label for label, _ in ENERGY_EDIT_OPTIONS]
        energy_choice = st.selectbox(
            "Енергия",
            energy_labels,
            index=_energy_edit_index(song.get("energy")),
        )
        energy_value = next(
            value for label, value in ENERGY_EDIT_OPTIONS if label == energy_choice
        )
        tags_raw = st.text_input(
            "Етикети",
            value=", ".join(song.get("tags") or []),
            help="Разделени със запетая",
        )
        summary = st.text_input("Резюме", value=song.get("summary") or "")
        refs_raw = st.text_input(
            "Препратки",
            value=", ".join(song.get("scripture_refs") or []),
            help="Разделени със запетая",
        )
        save_clicked = st.form_submit_button("Запази промените", type="primary")

    if save_clicked:
        try:
            parsed_energy = parse_energy_value(energy_value)
            fields = AdminSongFields(
                title=title.strip(),
                author=author.strip() or None,
                energy=parsed_energy,
                tags=parse_comma_separated_list(tags_raw),
                summary=summary.strip() or None,
                scripture_refs=parse_comma_separated_list(refs_raw),
            )
            if not fields.title:
                st.error("Заглавието не може да е празно.")
            else:
                update_song_admin(
                    client,
                    song_id,
                    fields,
                    existing=song,
                    songs_by_normalized=songs_by_normalized,
                )
                st.success("Промените са записани.")
                st.rerun()
        except TitleClashError:
            st.error(
                "Друга песен вече използва това заглавие (след нормализация). "
                "Изберете друго заглавие.",
            )
        except InvalidEnergyError:
            st.error("Невалидна стойност за енергия.")
        except Exception as exc:
            st.error(f"Неуспешен запис: {exc}")

    st.text_area(
        "Текст",
        value=_format_lyrics_for_display(song.get("lyrics")),
        height=320,
        disabled=True,
    )

    st.divider()
    st.markdown("**Администриране**")

    overwrite_reanalyse = True
    if song.get("tags_edited"):
        overwrite_reanalyse = st.checkbox(
            "Презапиши ръчните редакции при повторен анализ",
            value=False,
            key=f"reanalyse_overwrite_{song_id}",
        )
    if st.button("Анализирай отново", key=f"reanalyse_{song_id}"):
        if song.get("tags_edited") and not overwrite_reanalyse:
            st.warning(
                "Отметнете презаписване на ръчните редакции, "
                "ако искате нов AI анализ да замени полетата.",
            )
        else:
            payload = {
                "id": song_id,
                "title": song.get("title"),
                "author": song.get("author"),
                "lyrics": song.get("lyrics") or [],
            }
            done, failed = run_song_analysis_batch(
                client,
                [payload],
                openai_config,
                overwrite_hand_edits=overwrite_reanalyse,
            )
            if done or failed:
                st.success(f"Анализ: {done} готови, {failed} неуспешни.")
                st.rerun()

    delete_confirm = st.checkbox(
        "Потвърждавам изтриването на песента",
        key=f"delete_confirm_{song_id}",
    )
    if st.button(
        "Изтрий песента",
        type="secondary",
        disabled=not delete_confirm,
        key=f"delete_{song_id}",
    ):
        try:
            delete_song(client, song_id)
            st.session_state.pop(LIBRARY_SELECTED_SONG_KEY, None)
            st.success("Песента е изтрита.")
            st.rerun()
        except Exception as exc:
            st.error(f"Неуспешно изтриване: {exc}")


def _render_song_detail_for_role(
    client: Client,
    song: dict[str, Any],
    *,
    role: Role,
    openai_config: OpenAIConfig | None,
    songs_by_normalized: dict[str, dict[str, Any]] | None,
) -> None:
    if role is Role.ADMIN and openai_config is not None and songs_by_normalized is not None:
        _render_admin_song_detail(
            client,
            song,
            openai_config=openai_config,
            songs_by_normalized=songs_by_normalized,
        )
        return
    _render_song_detail(song)


def render_library_tab(
    client: Client,
    *,
    role: Role = Role.TEAM,
    openai_config: OpenAIConfig | None = None,
) -> None:
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
    clash_rows = fetch_songs_for_title_clash_check(client) if role is Role.ADMIN else []
    songs_by_normalized = (
        {row["normalized_title"]: row for row in clash_rows}
        if role is Role.ADMIN
        else None
    )
    _render_song_detail_for_role(
        client,
        detail_song,
        role=role,
        openai_config=openai_config,
        songs_by_normalized=songs_by_normalized,
    )
