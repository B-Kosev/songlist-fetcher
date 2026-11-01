from __future__ import annotations

import streamlit as st
from supabase import Client

from worship_song_selector.analysis_ui import run_song_analysis_batch
from worship_song_selector.config import OpenAIConfig
from worship_song_selector.flow_settings import (
    FlowTemplateValidationError,
    energies_from_slot_energy,
    fetch_flow_template,
    reset_flow_template,
    save_flow_template,
    slot_energy_from_energies,
)
from worship_song_selector.recommendation import FlowSlot
from worship_song_selector.songs import list_songs_for_reanalysis

_ENERGY_OPTIONS = ["fast", "medium", "slow"]
_ENERGY_LABELS = {
    "fast": "бърза",
    "medium": "средна",
    "slow": "бавна",
}
_FLOW_FORM_VERSION_KEY = "flow_template_form_version"


def _flow_form_version() -> int:
    return int(st.session_state.get(_FLOW_FORM_VERSION_KEY, 0))


def _bump_flow_form_version() -> None:
    st.session_state[_FLOW_FORM_VERSION_KEY] = _flow_form_version() + 1


def _render_flow_template_editor(client: Client) -> None:
    st.markdown("**Шаблон за поток (5 слота)**")
    st.caption(
        "Роля, целева енергия и цел на всеки слот се подават на модела при препоръка.",
    )
    try:
        stored_slots = fetch_flow_template(client)
    except Exception as exc:
        st.error(f"Неуспешно зареждане на шаблона: {exc}")
        return

    draft: list[FlowSlot] = []
    form_version = _flow_form_version()
    with st.form("flow_template_form", clear_on_submit=False):
        for index, slot in enumerate(stored_slots):
            st.markdown(f"**Слот {index + 1}**")
            role = st.text_input(
                "Роля",
                value=slot.role,
                key=f"flow_role_{form_version}_{index}",
            )
            energy_parts = energies_from_slot_energy(slot.energy)
            selected = st.multiselect(
                "Енергия (1–2)",
                options=_ENERGY_OPTIONS,
                default=energy_parts,
                max_selections=2,
                format_func=lambda value: _ENERGY_LABELS.get(value, value),
                key=f"flow_energy_{form_version}_{index}",
            )
            purpose = st.text_area(
                "Цел (за модела)",
                value=slot.purpose,
                height=68,
                key=f"flow_purpose_{form_version}_{index}",
            )
            draft.append(
                FlowSlot(
                    role=role,
                    energy=slot_energy_from_energies(selected),
                    purpose=purpose,
                ),
            )
            if index < len(stored_slots) - 1:
                st.divider()

        save_clicked = st.form_submit_button("Запази шаблона", type="primary")
        reset_clicked = st.form_submit_button("Възстанови по подразбиране")

    if reset_clicked:
        try:
            reset_flow_template(client)
        except Exception as exc:
            st.error(f"Неуспешно възстановяване: {exc}")
        else:
            _bump_flow_form_version()
            st.success("Шаблонът е възстановен по подразбиране.")
            st.rerun()

    if save_clicked:
        try:
            save_flow_template(client, draft)
        except FlowTemplateValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Неуспешно записване: {exc}")
        else:
            _bump_flow_form_version()
            st.success("Шаблонът е запазен.")
            st.rerun()


def render_settings_tab(client: Client, openai_config: OpenAIConfig) -> None:
    st.subheader("Настройки")
    _render_flow_template_editor(client)

    st.divider()
    st.markdown("**Повторен AI анализ**")
    st.caption(
        "Пуска анализ отново за всички песни в библиотеката "
        "(напр. след промяна на prompt-а).",
    )
    overwrite_hand_edits = st.checkbox(
        "Презапиши ръчно редактираните AI полета",
        value=False,
        key="settings_reanalyse_all_overwrite",
    )
    if st.button("Анализирай всички отново", type="secondary"):
        try:
            songs = list_songs_for_reanalysis(client)
        except Exception as exc:
            st.error(f"Неуспешна връзка с базата данни: {exc}")
            return
        if not songs:
            st.info("Няма песни за анализ.")
            return
        if not overwrite_hand_edits:
            hand_edited = sum(1 for song in songs if song.get("tags_edited"))
            songs = [song for song in songs if not song.get("tags_edited")]
            if hand_edited:
                st.caption(
                    f"Пропускане на {hand_edited} песни с ръчни редакции "
                    "(отметнете презаписване, за да ги включите).",
                )
        if not songs:
            st.info("Няма песни за анализ с текущите настройки.")
            return
        done, failed = run_song_analysis_batch(
            client,
            songs,
            openai_config,
            overwrite_hand_edits=overwrite_hand_edits,
        )
        if done or failed:
            st.success(
                f"Готово: {done} анализирани, {failed} неуспешни "
                f"(от {len(songs)} песни).",
            )
            st.rerun()
