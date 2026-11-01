from __future__ import annotations

import re
from dataclasses import dataclass

CHORD_PATTERN = re.compile(r"\s*\[[^\]]*\]")
TITLE_LINE = re.compile(r"^(?:title|заглавие)\s*:\s*(.+)$", re.IGNORECASE)
AUTHOR_LINE = re.compile(r"^(?:author|автор)\s*:\s*(.+)$", re.IGNORECASE)


@dataclass
class LyricSection:
    section_type: str
    lines: list[str]
    number: int | None = None
    marker: str | None = None


@dataclass(frozen=True)
class ParsedSong:
    title: str
    author: str | None
    sections: list[LyricSection]
    raw_text: str


def strip_chord_brackets(line: str) -> str:
    return CHORD_PATTERN.sub("", line)


def sections_to_lyrics_payload(sections: list[LyricSection]) -> list[dict]:
    payload: list[dict] = []
    for section in sections:
        entry: dict = {
            "section_type": section.section_type,
            "lines": section.lines,
        }
        if section.number is not None:
            entry["number"] = section.number
        if section.marker is not None:
            entry["marker"] = section.marker
        payload.append(entry)
    return payload


def _parse_marker_line(line: str) -> tuple[str, int | None, str] | None:
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.endswith(":"):
        stripped = stripped[:-1].strip()
    if not stripped:
        return None

    lower = stripped.casefold()
    verse_match = re.fullmatch(r"v(\d+)", lower)
    if verse_match:
        number = int(verse_match.group(1))
        return ("verse", number, stripped)

    if lower == "v":
        return ("verse", 1, stripped)

    chorus_match = re.fullmatch(r"c(\d*)", lower)
    if chorus_match:
        number_str = chorus_match.group(1)
        number = int(number_str) if number_str else None
        return ("chorus", number, stripped)

    bridge_match = re.fullmatch(r"b(\d*)", lower)
    if bridge_match:
        number_str = bridge_match.group(1)
        number = int(number_str) if number_str else None
        return ("bridge", number, stripped)

    if lower in {"pc", "pre-chorus", "pre_chorus", "prechorus"}:
        return ("pre_chorus", None, stripped)

    if lower in {"t", "tag"}:
        return ("tag", None, stripped)

    return None


def parse_song_text(raw_text: str, *, filename_stem: str) -> ParsedSong:
    lines = raw_text.splitlines()
    title: str | None = None
    author: str | None = None
    body_lines: list[str] = []

    for line in lines:
        title_match = TITLE_LINE.match(line.strip())
        if title_match and title is None:
            title = title_match.group(1).strip()
            continue
        author_match = AUTHOR_LINE.match(line.strip())
        if author_match and author is None:
            author = author_match.group(1).strip()
            continue
        body_lines.append(line)

    if title is None:
        title = filename_stem

    sections: list[LyricSection] = []
    current: LyricSection | None = None

    for line in body_lines:
        marker = _parse_marker_line(line)
        if marker is not None:
            section_type, number, marker_text = marker
            current = LyricSection(
                section_type=section_type,
                lines=[],
                number=number,
                marker=marker_text,
            )
            sections.append(current)
            continue

        if current is None:
            continue

        lyric_line = strip_chord_brackets(line)
        current.lines.append(lyric_line)

    return ParsedSong(
        title=title,
        author=author,
        sections=sections,
        raw_text=raw_text,
    )
