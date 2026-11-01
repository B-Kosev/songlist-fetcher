from __future__ import annotations

import streamlit as st

from worship_song_selector.auth import Role, resolve_role
from worship_song_selector.config import load_config
from worship_song_selector.import_ui import render_import_tab
from worship_song_selector.songs import create_supabase_client, list_songs

SESSION_ROLE_KEY = "role"


def init_session_state() -> None:
    if SESSION_ROLE_KEY not in st.session_state:
        st.session_state[SESSION_ROLE_KEY] = None


def current_role() -> Role | None:
    raw = st.session_state.get(SESSION_ROLE_KEY)
    if raw is None:
        return None
    return Role(raw)


def set_role(role: Role | None) -> None:
    st.session_state[SESSION_ROLE_KEY] = role.value if role is not None else None


def render_passcode_gate() -> None:
    st.title("Worship Song Selector")
    st.caption("Въведете код за достъп, за да продължите.")
    with st.form("passcode_form", clear_on_submit=False):
        passcode = st.text_input("Код за достъп", type="password")
        submitted = st.form_submit_button("Вход")
    if submitted:
        config = load_config()
        role = resolve_role(
            passcode,
            team_passcode_hash=config.auth.team_passcode_hash,
            admin_passcode_hash=config.auth.admin_passcode_hash,
        )
        if role is None:
            st.error("Грешен код. Опитайте отново.")
        else:
            set_role(role)
            st.rerun()


def render_recommend_tab() -> None:
    st.subheader("Препоръка")
    st.info("Генерирането на сетове ще бъде добавено в следващите версии.")


def render_library_tab() -> None:
    st.subheader("Библиотека")
    config = load_config()
    client = create_supabase_client(config.supabase)
    try:
        songs = list_songs(client)
    except Exception as exc:
        st.error(f"Неуспешна връзка с базата данни: {exc}")
        return
    if not songs:
        st.write("0 songs")
        return
    st.caption(f"{len(songs)} songs")
    for song in songs:
        author = song.get("author") or "—"
        st.write(f"**{song['title']}** — {author}")


def render_admin_import_tab() -> None:
    config = load_config()
    client = create_supabase_client(config.supabase)
    render_import_tab(client)


def render_settings_tab() -> None:
    st.subheader("Настройки")
    st.info("Настройките на шаблона за поток ще бъдат добавени в следващите версии.")


def render_main_app(role: Role) -> None:
    st.title("Worship Song Selector")
    if st.button("Изход"):
        set_role(None)
        st.rerun()

    if role is Role.ADMIN:
        tab_recommend, tab_library, tab_import, tab_settings = st.tabs(
            ["Препоръка", "Библиотека", "Импорт", "Настройки"],
        )
        with tab_recommend:
            render_recommend_tab()
        with tab_library:
            render_library_tab()
        with tab_import:
            render_admin_import_tab()
        with tab_settings:
            render_settings_tab()
    else:
        tab_recommend, tab_library = st.tabs(["Препоръка", "Библиотека"])
        with tab_recommend:
            render_recommend_tab()
        with tab_library:
            render_library_tab()


def main() -> None:
    st.set_page_config(page_title="Worship Song Selector", layout="wide")
    init_session_state()
    role = current_role()
    if role is None:
        render_passcode_gate()
        return
    render_main_app(role)


if __name__ == "__main__":
    main()
