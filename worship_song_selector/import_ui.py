from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import streamlit as st
from supabase import Client

from worship_song_selector.marker_aliases import fetch_marker_aliases, upsert_marker_aliases
from worship_song_selector.parser import marker_alias_key, parse_song_text, sections_to_lyrics_payload
from worship_song_selector.songs import build_song_row, insert_songs

IMPORT_BATCH_KEY = "import_batch"
IMPORT_PENDING_ALIASES_KEY = "import_pending_marker_aliases"

MARKER_MAPPING_CHOICES: list[tuple[str, str]] = [
    ("", "— изберете —"),
    ("verse", "Verse"),
    ("pre_chorus", "Pre-chorus"),
    ("chorus", "Chorus"),
    ("bridge", "Bridge"),
    ("tag", "Tag / Ending"),
    ("ignore_line", "Ignore line"),
    ("not_a_marker", "Not a marker (keep as lyric)"),
]


@dataclass
class ImportDraft:
    filename: str
    raw_text: str
    title: str
    author: str
    lyrics: list[dict[str, Any]]
    unknown_markers: frozenset[str] = field(default_factory=frozenset)


def _filename_stem(filename: str) -> str:
    if filename.lower().endswith(".txt"):
        return filename[:-4]
    return filename


def _example_line_for_marker_key(raw_text: str, key: str) -> str:
    for line in raw_text.splitlines():
        if marker_alias_key(line) == key:
            return line.strip()
    return key


def _merged_marker_aliases(
    saved: dict[str, str],
    pending: dict[str, str],
) -> dict[str, str]:
    return {**saved, **pending}


def _apply_parse_to_draft(draft: ImportDraft, marker_aliases: dict[str, str]) -> None:
    parsed = parse_song_text(
        draft.raw_text,
        filename_stem=_filename_stem(draft.filename),
        marker_aliases=marker_aliases,
    )
    draft.unknown_markers = parsed.unknown_markers
    draft.lyrics = sections_to_lyrics_payload(parsed.sections)


def _refresh_batch(batch: list[ImportDraft], marker_aliases: dict[str, str]) -> None:
    for draft in batch:
        _apply_parse_to_draft(draft, marker_aliases)


def drafts_from_uploads(
    uploads: list[Any],
    marker_aliases: dict[str, str],
) -> list[ImportDraft]:
    drafts: list[ImportDraft] = []
    for upload in uploads:
        raw_bytes = upload.getvalue()
        raw_text = raw_bytes.decode("utf-8")
        parsed = parse_song_text(
            raw_text,
            filename_stem=_filename_stem(upload.name),
            marker_aliases=marker_aliases,
        )
        drafts.append(
            ImportDraft(
                filename=upload.name,
                raw_text=raw_text,
                title=parsed.title,
                author=parsed.author or "",
                lyrics=sections_to_lyrics_payload(parsed.sections),
                unknown_markers=parsed.unknown_markers,
            ),
        )
    return drafts


def _clear_import_session() -> None:
    st.session_state.pop(IMPORT_BATCH_KEY, None)
    st.session_state.pop("import_upload_key", None)
    st.session_state.pop(IMPORT_PENDING_ALIASES_KEY, None)


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


def _batch_unknown_markers(batch: list[ImportDraft]) -> frozenset[str]:
    unknown: set[str] = set()
    for draft in batch:
        unknown.update(draft.unknown_markers)
    return frozenset(unknown)


def render_import_tab(client: Client) -> None:
    st.subheader("Импорт")
    st.caption(
        "Качете един или повече `.txt` файла (една песен на файл). "
        "Нищо не се записва, докато не потвърдите.",
    )

    saved_aliases = fetch_marker_aliases(client)
    pending_aliases: dict[str, str] = st.session_state.setdefault(
        IMPORT_PENDING_ALIASES_KEY,
        {},
    )
    merged_aliases = _merged_marker_aliases(saved_aliases, pending_aliases)

    uploads = st.file_uploader(
        "Файлове с песни",
        type=["txt"],
        accept_multiple_files=True,
        key="import_file_uploader",
    )

    upload_key = tuple(upload.name for upload in uploads) if uploads else ()
    if uploads:
        if st.session_state.get("import_upload_key") != upload_key:
            st.session_state[IMPORT_PENDING_ALIASES_KEY] = {}
            merged_aliases = _merged_marker_aliases(saved_aliases, {})
            st.session_state[IMPORT_BATCH_KEY] = drafts_from_uploads(uploads, merged_aliases)
            st.session_state["import_upload_key"] = upload_key

    batch: list[ImportDraft] | None = st.session_state.get(IMPORT_BATCH_KEY)
    if not batch:
        return

    unknown_keys = _batch_unknown_markers(batch)
    if unknown_keys:
        st.warning(
            "Има неразпознати маркери за секции. Задайте тип за всеки, "
            "преди да потвърдите импорта.",
        )
        choice_labels = {value: label for value, label in MARKER_MAPPING_CHOICES}
        choice_values = [value for value, _ in MARKER_MAPPING_CHOICES]
        aliases_updated = False
        for key in sorted(unknown_keys):
            example = _example_line_for_marker_key(
                next(d.raw_text for d in batch if key in d.unknown_markers),
                key,
            )
            current = pending_aliases.get(key, "")
            selected = st.selectbox(
                f"Маркер «{example}»",
                options=choice_values,
                index=choice_values.index(current) if current in choice_values else 0,
                format_func=lambda value: choice_labels.get(value, value),
                key=f"import_marker_map_{key}",
            )
            if selected and pending_aliases.get(key) != selected:
                pending_aliases[key] = selected
                aliases_updated = True
        if aliases_updated:
            merged_aliases = _merged_marker_aliases(saved_aliases, pending_aliases)
            _refresh_batch(batch, merged_aliases)
            st.rerun()

    st.divider()
    for index, draft in enumerate(batch):
        header = draft.filename
        if draft.unknown_markers:
            header = f"{draft.filename} — неразпознати маркери"
        st.markdown(f"**{header}**")
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

    batch_has_unknown = bool(_batch_unknown_markers(batch))

    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button(
            "Потвърди и запиши",
            type="primary",
            disabled=batch_has_unknown,
        ):
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
                if pending_aliases:
                    upsert_marker_aliases(client, pending_aliases)
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

    if batch_has_unknown:
        st.caption("Потвърждението е изключено, докато всички маркери имат зададен тип.")
