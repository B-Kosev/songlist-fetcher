from __future__ import annotations

import re
import unicodedata
from typing import Any

from worship_song_selector.titles import normalize_title

_BULGARIAN_SEARCH_EQUIVALENTS = str.maketrans(
    {
        "й": "и",
        "ъ": "а",
    },
)


def normalize_for_search(text: str) -> str:
    folded = text.casefold()
    decomposed = unicodedata.normalize("NFKD", folded)
    without_marks = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    mapped = without_marks.translate(_BULGARIAN_SEARCH_EQUIVALENTS)
    collapsed = re.sub(r"\s+", " ", mapped).strip()
    return collapsed


def fuzzy_query_matches_text(query: str, normalized_haystack: str) -> bool:
    token = normalize_for_search(query)
    if not token:
        return True
    if token in normalized_haystack:
        return True
    index = 0
    for char in normalized_haystack:
        if char == token[index]:
            index += 1
            if index == len(token):
                return True
    return False


def build_song_search_text(song: dict[str, Any]) -> str:
    parts: list[str] = [
        song.get("title") or "",
        song.get("author") or "",
    ]
    tags = song.get("tags") or []
    if tags:
        parts.append(" ".join(str(tag) for tag in tags))
    for section in song.get("lyrics") or []:
        for line in section.get("lines") or []:
            parts.append(str(line))
    return normalize_for_search(" ".join(parts))


def song_matches_query(song: dict[str, Any], query: str) -> bool:
    normalized_query = normalize_for_search(query)
    if not normalized_query:
        return True
    haystack = build_song_search_text(song)
    for token in normalized_query.split():
        if not fuzzy_query_matches_text(token, haystack):
            return False
    return True


def song_matches_energy(song: dict[str, Any], energy: str | None) -> bool:
    if energy is None:
        return True
    return song.get("energy") == energy


def filter_library_songs(
    songs: list[dict[str, Any]],
    *,
    query: str,
    energy: str | None,
) -> list[dict[str, Any]]:
    filtered = [
        song
        for song in songs
        if song_matches_query(song, query) and song_matches_energy(song, energy)
    ]
    return sorted(filtered, key=lambda song: normalize_title(str(song.get("title") or "")))
