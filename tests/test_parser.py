import time
from pathlib import Path

import pytest

from worship_song_selector.parser import parse_song_text, strip_chord_brackets, strip_curly_brace_comments
from worship_song_selector.titles import normalize_title

FIXTURES = Path(__file__).parent / "fixtures"


def test_strip_chord_brackets_preserves_cyrillic_and_punctuation():
    line = "Духът [G] мъдрост, [Am7] днес!"
    assert strip_chord_brackets(line) == "Духът мъдрост, днес!"


def test_normalize_title_collapses_whitespace_and_strips_punctuation():
    assert normalize_title("  Велик е Бог!!!  ") == "велик е бог"


def test_parse_worshiptools_verse1_fixture():
    raw = (FIXTURES / "worshiptools_verse1_sample.txt").read_text(encoding="utf-8")
    parsed = parse_song_text(raw, filename_stem="fallback-name")

    assert parsed.title == "Благословен Бог"
    assert parsed.author == "Тестов автор"
    assert [s.section_type for s in parsed.sections] == [
        "verse",
        "chorus",
        "bridge",
    ]
    assert parsed.sections[0].number == 1
    assert parsed.sections[0].lines == [
        "Първи ред с акорд",
        "Втори ред",
    ]
    assert parsed.sections[1].lines == ["Припев един", "Припев два"]
    lyric_blob = "\n".join(line for s in parsed.sections for line in s.lines)
    assert "{" not in lyric_blob
    assert "WorshipTools" not in lyric_blob
    assert "CCLI" not in lyric_blob


def test_parse_propresenter_slide_fixture():
    raw = (FIXTURES / "propresenter_slide_sample.txt").read_text(encoding="utf-8")
    parsed = parse_song_text(raw, filename_stem="fallback-name")

    assert parsed.title == "Свят свят свят"
    assert parsed.author == "Тестов автор"
    assert [s.section_type for s in parsed.sections] == [
        "verse",
        "chorus",
        "verse",
    ]
    assert parsed.sections[0].number == 1
    assert parsed.sections[2].number == 2
    assert parsed.sections[0].lines == [
        "Свят, свят, свят",
        "Господ Бог всемогъщ",
    ]
    lyric_blob = "\n".join(line for s in parsed.sections for line in s.lines)
    assert "{" not in lyric_blob
    assert "ProPresenter" not in lyric_blob
    assert "Arrangement" not in lyric_blob


def test_parse_tracer_fixture():
    raw = (FIXTURES / "tracer_sample.txt").read_text(encoding="utf-8")
    parsed = parse_song_text(raw, filename_stem="fallback-name")

    assert parsed.title == "Велик е нашият Бог"
    assert parsed.author == "Неизвестен автор"
    assert len(parsed.sections) == 2

    verse = parsed.sections[0]
    assert verse.section_type == "verse"
    assert verse.number == 1
    assert verse.lines == [
        "Духът мъдрост дава",
        "И сила за пътя",
    ]

    chorus = parsed.sections[1]
    assert chorus.section_type == "chorus"
    assert chorus.lines == [
        "Велик е нашият Бог",
        "Велик е нашият Бог",
    ]


def test_parse_uses_filename_when_no_title_line():
    raw = "v1\nСамо текст\n"
    parsed = parse_song_text(raw, filename_stem="Моя песен")
    assert parsed.title == "Моя песен"
    assert parsed.author is None


def test_parse_bridge_and_pre_chorus_markers():
    raw = "pc\nПреход\nb\nМост\n"
    parsed = parse_song_text(raw, filename_stem="x")
    assert [s.section_type for s in parsed.sections] == ["pre_chorus", "bridge"]


@pytest.mark.parametrize(
    ("marker", "section_type", "number"),
    [
        ("v2", "verse", 2),
        ("Verse1", "verse", 1),
        ("Verse 1", "verse", 1),
        ("slide1", "verse", 1),
        ("slide 2", "verse", 2),
        ("c", "chorus", None),
        ("Chorus", "chorus", None),
        ("t", "tag", None),
        ("Ending", "tag", None),
    ],
)
def test_marker_normalization(marker, section_type, number):
    raw = f"{marker}\nРед\n"
    parsed = parse_song_text(raw, filename_stem="x")
    section = parsed.sections[0]
    assert section.section_type == section_type
    assert section.number == number


def test_strip_curly_brace_comments_from_line():
    assert strip_curly_brace_comments("Ред{бележка} край") == "Ред край"


def test_parse_large_file_under_three_seconds():
    body = "v1\n" + "Ред с [G] акорд\n" * 5000
    started = time.perf_counter()
    parse_song_text(body, filename_stem="x")
    assert time.perf_counter() - started < 3.0
