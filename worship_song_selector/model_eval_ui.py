from __future__ import annotations

import streamlit as st
from supabase import Client

from worship_song_selector.config import OpenAIConfig
from worship_song_selector.flow_settings import fetch_flow_template
from worship_song_selector.model_eval import (
    DEFAULT_EVAL_THEMES,
    extrapolate_recommendation_prompt_tokens,
)
from worship_song_selector.openai_metrics import approximate_input_tokens
from worship_song_selector.recommendation import build_recommendation_messages
from worship_song_selector.songs import list_analysed_songs_for_recommendation


def render_model_eval_helper(client: Client, openai_config: OpenAIConfig) -> None:
    st.markdown("**Оценка на модела (ticket 13)**")
    st.caption(
        "Преди пълен импорт (~400 песни): импортирайте 10–20 реални песни, "
        "анализирайте ги, тествайте теми в «Препоръка», после пуснете "
        "скрипта за токени и латентност.",
    )
    st.code("python scripts/model_quality_eval.py --analysis-sample 5", language="bash")
    st.caption(
        f"Модел: `{openai_config.model}`. "
        "Запишете markdown отчета в Comments на issue 13 и попълнете "
        "човешката оценка на анализ и сетове.",
    )

    try:
        songs = list_analysed_songs_for_recommendation(client)
        flow_slots = fetch_flow_template(client)
    except Exception as exc:
        st.warning(f"Неуспешно зареждане на библиотеката: {exc}")
        return

    if len(songs) < 5:
        st.info(
            f"За оценка са нужни поне 5 анализирани песни (сега: {len(songs)}).",
        )
        return

    sample_theme = DEFAULT_EVAL_THEMES[0]
    messages = build_recommendation_messages(
        theme=sample_theme,
        flow_slots=flow_slots,
        songs=songs,
    )
    approx_tokens = approximate_input_tokens(messages)
    extrapolated = extrapolate_recommendation_prompt_tokens(
        prompt_tokens=approx_tokens,
        catalogue_size=len(songs),
        target_catalogue=400,
    )
    st.markdown(
        f"Приблизителни **input** токени за една препоръка сега: **{approx_tokens:,}** "
        f"(екстраполация при ~400 песни: **{extrapolated:,}**). "
        "Точни стойности — от `model_quality_eval.py` след реални API повиквания.",
    )
