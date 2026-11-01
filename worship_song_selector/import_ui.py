from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import streamlit as st
from supabase import Client

from worship_song_selector.analysis_ui import (
    render_analyse_pending_control,
    run_song_analysis_batch,
)
from worship_song_selector.config import OpenAIConfig
from worship_song_selector.marker_aliases import fetch_marker_aliases, upsert_marker_aliases
from worship_song_selector.import_matching import (
    ImportActionKind,
    batch_duplicate_normalized_titles,
    import_action_preview_label,
    plan_import_actions,
    resolve_import_action,
)
from worship_song_selector.parser import marker_alias_key, parse_song_text, sections_to_lyrics_payload
from worship_song_selector.songs import apply_import_actions, fetch_songs_for_import
from worship_song_selector.titles import normalize_title

IMPORT_BATCH_KEY = "import_batch"
IMPORT_PENDING_ALIASES_KEY = "import_pending_marker_aliases"
MATCH_OVERRIDE_AUTO = "__auto__"
MATCH_OVERRIDE_NEW = "new"

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
    match_override: str | None = None
    overwrite_hand_edits: bool = False


def _draft_normalized_title(draft: ImportDraft) -> str:
    display_title = draft.title.strip() or _filename_stem(draft.filename)
    return normalize_title(display_title)


def _import_match_maps(
    existing_songs: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_normalized = {song["normalized_title"]: song for song in existing_songs}
    by_id = {song["id"]: song for song in existing_songs}
    return by_normalized, by_id


def _draft_import_payload(draft: ImportDraft) -> dict[str, Any]:
    display_title = draft.title.strip() or _filename_stem(draft.filename)
    return {
        "title": display_title,
        "normalized_title": normalize_title(display_title),
        "author": draft.author.strip() or None,
        "lyrics": draft.lyrics,
        "raw_text": draft.raw_text,
        "override": draft.match_override,
        "overwrite_hand_edits": draft.overwrite_hand_edits,
    }


def _batch_duplicate_titles(batch: list[ImportDraft]) -> frozenset[str]:
    return batch_duplicate_normalized_titles([_draft_normalized_title(d) for d in batch])


def _match_override_options(existing_songs: list[dict[str, Any]]) -> list[str]:
    return [MATCH_OVERRIDE_AUTO, MATCH_OVERRIDE_NEW, *[song["id"] for song in existing_songs]]


def _match_override_label(
    value: str,
    existing_songs_by_id: dict[str, dict[str, Any]],
) -> str:
    if value == MATCH_OVERRIDE_AUTO:
        return "Автоматично"
    if value == MATCH_OVERRIDE_NEW:
        return "Принуди като нова"
    song = existing_songs_by_id.get(value)
    if song:
        return f"Обнови: {song['title']}"
    return value


def _match_override_index(options: list[str], override: str | None) -> int:
    if override is None:
        desired = MATCH_OVERRIDE_AUTO
    elif override == MATCH_OVERRIDE_NEW:
        desired = MATCH_OVERRIDE_NEW
    else:
        desired = override
    return options.index(desired) if desired in options else 0


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


def render_import_tab(client: Client, openai_config: OpenAIConfig) -> None:
    st.subheader("Импорт")
    render_analyse_pending_control(client, openai_config)
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

    existing_songs = fetch_songs_for_import(client)
    existing_by_normalized, existing_by_id = _import_match_maps(existing_songs)
    duplicate_norms = _batch_duplicate_titles(batch)
    if duplicate_norms:
        shown = ", ".join(sorted(duplicate_norms))
        st.error(
            "В партидата има повече от един файл с еднакво нормализирано заглавие "
            f"({shown}). Променете заглавия или съвпаденията, преди да потвърдите.",
        )

    override_options = _match_override_options(existing_songs)

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
            payload = _draft_import_payload(draft)
            selected_override = st.selectbox(
                "Съвпадение",
                options=override_options,
                index=_match_override_index(override_options, draft.match_override),
                format_func=lambda value: _match_override_label(value, existing_by_id),
                key=f"import_match_{index}",
            )
            if selected_override == MATCH_OVERRIDE_AUTO:
                draft.match_override = None
            elif selected_override == MATCH_OVERRIDE_NEW:
                draft.match_override = MATCH_OVERRIDE_NEW
            else:
                draft.match_override = selected_override

            resolved = resolve_import_action(
                lyrics=payload["lyrics"],
                normalized_title=payload["normalized_title"],
                existing_by_normalized=existing_by_normalized,
                existing_songs_by_id=existing_by_id,
                override=draft.match_override,
            )
            st.caption(import_action_preview_label(resolved, existing_songs_by_id=existing_by_id))
            target_id = resolved.song_id
            if (
                resolved.kind == ImportActionKind.UPDATE
                and target_id
                and existing_by_id.get(target_id, {}).get("tags_edited")
            ):
                draft.overwrite_hand_edits = st.checkbox(
                    "Презапиши моите ръчни редакции на AI полетата",
                    value=draft.overwrite_hand_edits,
                    key=f"import_overwrite_{index}",
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
    batch_has_duplicate_titles = bool(duplicate_norms)

    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button(
            "Потвърди и запиши",
            type="primary",
            disabled=batch_has_unknown or batch_has_duplicate_titles,
        ):
            drafts_payload = [_draft_import_payload(item) for item in batch]
            actions = plan_import_actions(
                drafts_payload,
                existing_by_normalized=existing_by_normalized,
                existing_songs_by_id=existing_by_id,
            )
            try:
                inserted_count, updated_count, skipped_count, for_analysis = apply_import_actions(
                    client,
                    actions,
                )
                if pending_aliases:
                    upsert_marker_aliases(client, pending_aliases)
            except Exception as exc:
                st.error(f"Неуспешен запис в базата: {exc}")
            else:
                done, failed = run_song_analysis_batch(client, for_analysis, openai_config)
                _clear_import_session()
                msg = (
                    f"Нови: {inserted_count}, обновени: {updated_count}, "
                    f"пропуснати: {skipped_count}."
                )
                if done or failed:
                    msg += f" Анализ: {done} готови, {failed} неуспешни."
                elif for_analysis:
                    msg += " Анализът не стартира (проверете OpenAI secrets)."
                st.success(msg)
                st.rerun()
    with cancel_col:
        if st.button("Отказ"):
            _clear_import_session()
            st.rerun()

    if batch_has_unknown:
        st.caption("Потвърждението е изключено, докато всички маркери имат зададен тип.")
    if batch_has_duplicate_titles:
        st.caption(
            "Потвърждението е изключено, докато нормализираните заглавия в партидата са уникални.",
        )
