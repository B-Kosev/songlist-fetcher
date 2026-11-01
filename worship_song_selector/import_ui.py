from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st
from supabase import Client

from worship_song_selector.parser import parse_song_text, sections_to_lyrics_payload
from worship_song_selector.songs import build_song_row, insert_songs

IMPORT_BATCH_KEY = "import_batch"


@dataclass
class ImportDraft:
    filename: str
    raw_text: str
    title: str
    author: str
    lyrics: list[dict[str, Any]]


def _filename_stem(filename: str) -> str:
    if filename.lower().endswith(".txt"):
        return filename[:-4]
    return filename


def drafts_from_uploads(uploads: list[Any]) -> list[ImportDraft]:
    drafts: list[ImportDraft] = []
    for upload in uploads:
        raw_bytes = upload.getvalue()
        raw_text = raw_bytes.decode("utf-8")
        parsed = parse_song_text(raw_text, filename_stem=_filename_stem(upload.name))
        drafts.append(
            ImportDraft(
                filename=upload.name,
                raw_text=raw_text,
                title=parsed.title,
                author=parsed.author or "",
                lyrics=sections_to_lyrics_payload(parsed.sections),
            ),
        )
    return drafts


def _clear_import_session() -> None:
    st.session_state.pop(IMPORT_BATCH_KEY, None)
    st.session_state.pop("import_upload_key", None)


def _format_sections_preview(lyrics: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for section in lyrics:
        label = section["section_type"]
        if "number" in section:
            label = f"{label} {section['number']}"
        parts.append(f"[{label}]")
        parts.extend(section.get("lines", []))
        parts.append("")
    return "\n".join(parts).strip()


def render_import_tab(client: Client) -> None:
    st.subheader("Импорт")
    st.caption("Качете един или повече `.txt` файла (една песен на файл). Нищо не се записва, докато не потвърдите.")

    uploads = st.file_uploader(
        "Файлове с песни",
        type=["txt"],
        accept_multiple_files=True,
        key="import_file_uploader",
    )

    upload_key = tuple(upload.name for upload in uploads) if uploads else ()
    if uploads:
        if st.session_state.get("import_upload_key") != upload_key:
            st.session_state[IMPORT_BATCH_KEY] = drafts_from_uploads(uploads)
            st.session_state["import_upload_key"] = upload_key

    batch: list[ImportDraft] | None = st.session_state.get(IMPORT_BATCH_KEY)
    if not batch:
        return

    st.divider()
    for index, draft in enumerate(batch):
        st.markdown(f"**{draft.filename}**")
        left, right = st.columns(2)
        with left:
            st.text_area(
                "Оригинален текст",
                value=draft.raw_text,
                height=280,
                disabled=True,
                key=f"import_raw_{index}",
            )
        with right:
            draft.title = st.text_input(
                "Заглавие",
                value=draft.title,
                key=f"import_title_{index}",
            )
            draft.author = st.text_input(
                "Автор",
                value=draft.author,
                key=f"import_author_{index}",
            )
            st.text_area(
                "Разпознати секции",
                value=_format_sections_preview(draft.lyrics),
                height=180,
                disabled=True,
                key=f"import_sections_{index}",
            )
        st.divider()

    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Потвърди и запиши", type="primary"):
            rows = [
                build_song_row(
                    title=item.title.strip() or _filename_stem(item.filename),
                    author=item.author.strip() or None,
                    lyrics=item.lyrics,
                    raw_text=item.raw_text,
                )
                for item in batch
            ]
            try:
                insert_songs(client, rows)
            except Exception as exc:
                st.error(f"Неуспешен запис в базата: {exc}")
            else:
                _clear_import_session()
                st.success(f"Записани са {len(rows)} песни.")
                st.rerun()
    with cancel_col:
        if st.button("Отказ"):
            _clear_import_session()
            st.rerun()
