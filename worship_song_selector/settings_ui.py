from __future__ import annotations

import streamlit as st
from supabase import Client

from worship_song_selector.analysis_ui import run_song_analysis_batch
from worship_song_selector.config import OpenAIConfig
from worship_song_selector.songs import list_songs_for_reanalysis


def render_settings_tab(client: Client, openai_config: OpenAIConfig) -> None:
    st.subheader("Настройки")
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

    st.divider()
    st.info("Шаблонът за поток ще бъде добавен в следващите версии.")
