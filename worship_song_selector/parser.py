from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

CHORD_PATTERN = re.compile(r"\s*\[[^\]]*\]")
COMMENT_PATTERN = re.compile(r"\{[^}]*\}")
TITLE_LINE = re.compile(r"^(?:title|заглавие)\s*:\s*(.+)$", re.IGNORECASE)
AUTHOR_LINE = re.compile(r"^(?:author|автор)\s*:\s*(.+)$", re.IGNORECASE)
NOISE_LINE = re.compile(
    r"^(?:"
    r"worship\s*tools|worshiptools|planning\s+export|ccli|song\s*#|song\s*id|"
    r"propresenter|arrangement|category|version|"
    r"key|tempo|bpm|time\s*signature|length"
    r")\b",
    re.IGNORECASE,
)
MARKER_CANDIDATE_LINE = re.compile(r"^[\w\s\-–—.:]+$", re.UNICODE)

MARKER_ALIAS_SECTION_TYPES = frozenset(
    {
        "verse",
        "pre_chorus",
        "chorus",
        "bridge",
        "tag",
        "ignore_line",
        "not_a_marker",
    },
)


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
    unknown_markers: frozenset[str] = field(default_factory=frozenset)


def strip_chord_brackets(line: str) -> str:
    return CHORD_PATTERN.sub("", line)


def strip_curly_brace_comments(line: str) -> str:
    return COMMENT_PATTERN.sub("", line)


def _clean_lyric_line(line: str) -> str:
    return strip_curly_brace_comments(strip_chord_brackets(line)).rstrip()


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


def marker_alias_key(line: str) -> str:
    stripped = line.strip()
    if stripped.endswith(":"):
        stripped = stripped[:-1].strip()
    return re.sub(r"[\s_-]+", "", stripped.casefold())


def _parse_number_suffix(compact: str, prefix: str) -> int | None:
    if compact == prefix:
        return None
    if compact.startswith(prefix):
        suffix = compact[len(prefix) :]
        if suffix.isdigit():
            return int(suffix)
    return None


def _parse_builtin_marker_line(line: str) -> tuple[str, int | None, str] | None:
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.endswith(":"):
        stripped = stripped[:-1].strip()
    if not stripped:
        return None

    lower = stripped.casefold()
    compact = marker_alias_key(stripped)

    verse_match = re.fullmatch(r"v(\d+)", lower)
    if verse_match:
        number = int(verse_match.group(1))
        return ("verse", number, stripped)

    if lower == "v":
        return ("verse", 1, stripped)

    slide_match = re.fullmatch(r"slide(\d+)", compact)
    if slide_match:
        number = int(slide_match.group(1))
        return ("verse", number, stripped)

    verse_number = _parse_number_suffix(compact, "verse")
    if verse_number is not None or compact == "verse":
        number = verse_number if verse_number is not None else 1
        return ("verse", number, stripped)

    chorus_number = _parse_number_suffix(compact, "chorus")
    if chorus_number is not None or compact == "chorus":
        return ("chorus", chorus_number, stripped)

    bridge_number = _parse_number_suffix(compact, "bridge")
    if bridge_number is not None or compact == "bridge":
        return ("bridge", bridge_number, stripped)

    if compact in {"pc", "prechorus"}:
        return ("pre_chorus", None, stripped)

    if compact in {"t", "tag", "ending"}:
        return ("tag", None, stripped)

    if chorus_match := re.fullmatch(r"c(\d*)", lower):
        number_str = chorus_match.group(1)
        number = int(number_str) if number_str else None
        return ("chorus", number, stripped)

    if bridge_match := re.fullmatch(r"b(\d*)", lower):
        number_str = bridge_match.group(1)
        number = int(number_str) if number_str else None
        return ("bridge", number, stripped)

    return None


def _looks_like_marker_candidate(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if "[" in line or "{" in line:
        return False
    if stripped.endswith(":"):
        stripped = stripped[:-1].strip()
    if not stripped or len(stripped) > 40:
        return False
    if not MARKER_CANDIDATE_LINE.fullmatch(stripped):
        return False
    cleaned = _clean_lyric_line(stripped)
    if not cleaned or len(cleaned) > 40:
        return False

    words = cleaned.split()
    if len(words) > 4:
        return False

    has_latin = bool(re.search(r"[A-Za-z]", stripped))
    has_cyrillic = bool(re.search(r"[\u0400-\u04FF]", stripped))

    if has_latin:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\s\-–—.:]*", stripped):
            return False
        if "-" in stripped:
            return True
        return len(words) == 1

    if has_cyrillic and not has_latin:
        return len(words) == 1

    return False


def _resolve_marker_line(
    line: str,
    marker_aliases: Mapping[str, str],
) -> tuple[str, int | None, str] | str | None:
    alias_key = marker_alias_key(line)
    alias_value = marker_aliases.get(alias_key)
    if alias_value is not None:
        if alias_value == "ignore_line":
            return "ignore_line"
        if alias_value == "not_a_marker":
            return "not_a_marker"
        if alias_value not in MARKER_ALIAS_SECTION_TYPES:
            raise ValueError(f"Invalid marker alias section type: {alias_value!r}")
        builtin = _parse_builtin_marker_line(line)
        if builtin is not None and builtin[0] == alias_value:
            return builtin
        stripped = line.strip()
        if stripped.endswith(":"):
            stripped = stripped[:-1].strip()
        return (alias_value, None, stripped)

    builtin = _parse_builtin_marker_line(line)
    if builtin is not None:
        return builtin

    if _looks_like_marker_candidate(line):
        return None

    return "not_a_marker"


def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if NOISE_LINE.match(stripped):
        return True
    if re.fullmatch(r"ccli\s+song\s*#\s*:\s*\d+", stripped, re.IGNORECASE):
        return True
    return False


def _collect_unknown_marker_keys(
    body_lines: list[str],
    marker_aliases: Mapping[str, str],
) -> frozenset[str]:
    unknown: set[str] = set()
    for line in body_lines:
        if _is_noise_line(line):
            continue
        alias_key = marker_alias_key(line)
        if alias_key in marker_aliases:
            continue
        if _parse_builtin_marker_line(line) is not None:
            continue
        if _looks_like_marker_candidate(line):
            unknown.add(alias_key)
    return frozenset(unknown)


def parse_song_text(
    raw_text: str,
    *,
    filename_stem: str,
    marker_aliases: Mapping[str, str] | None = None,
) -> ParsedSong:
    aliases = marker_aliases or {}
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

    unknown_markers = _collect_unknown_marker_keys(body_lines, aliases)

    sections: list[LyricSection] = []
    current: LyricSection | None = None

    for line in body_lines:
        if _is_noise_line(line):
            continue

        resolved = _resolve_marker_line(line, aliases)
        if resolved is None:
            continue
        if resolved == "ignore_line":
            continue
        if resolved == "not_a_marker":
            if current is None:
                continue
            current.lines.append(_clean_lyric_line(line))
            continue

        section_type, number, marker_text = resolved
        current = LyricSection(
            section_type=section_type,
            lines=[],
            number=number,
            marker=marker_text,
        )
        sections.append(current)

    return ParsedSong(
        title=title,
        author=author,
        sections=sections,
        raw_text=raw_text,
        unknown_markers=unknown_markers,
    )
