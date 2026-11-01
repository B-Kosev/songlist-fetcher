import json

import pytest

from worship_song_selector.song_analysis import (
    AnalysisValidationError,
    SongAnalysis,
    analyze_song_with_completion,
    build_analysis_messages,
    parse_analysis_response,
)


def test_build_analysis_messages_include_song_metadata_and_lyrics():
    messages = build_analysis_messages(
        title="Велик си Ти",
        author="Автор",
        lyrics_plain="[verse 1]\nРед един",
    )
    assert messages[0]["role"] == "system"
    assert "български" in messages[0]["content"].lower()
    user = messages[1]["content"]
    assert "Велик си Ти" in user
    assert "Автор" in user
    assert "Ред един" in user


def test_parse_valid_analysis():
    payload = {
        "tags": ["хваление", "кръст"],
        "scripture_refs": ["Пс 103:1"],
        "energy": "fast",
        "summary": "Радостна песен за Божията величие.",
    }
    result = parse_analysis_response(json.dumps(payload))
    assert result == SongAnalysis(
        tags=["хваление", "кръст"],
        scripture_refs=["Пс 103:1"],
        energy="fast",
        summary="Радостна песен за Божията величие.",
    )


def test_parse_rejects_invalid_energy():
    payload = {
        "tags": ["хваление"],
        "scripture_refs": [],
        "energy": "upbeat",
        "summary": "Кратко резюме.",
    }
    with pytest.raises(AnalysisValidationError):
        parse_analysis_response(json.dumps(payload))


def test_parse_rejects_empty_summary():
    payload = {
        "tags": ["хваление"],
        "scripture_refs": [],
        "energy": "medium",
        "summary": "   ",
    }
    with pytest.raises(AnalysisValidationError):
        parse_analysis_response(json.dumps(payload))


def test_analyze_song_retries_once_on_invalid_response():
    calls: list[str] = []

    def completion(messages):
        calls.append(messages[-1]["content"])
        if len(calls) == 1:
            return json.dumps(
                {
                    "tags": ["тема"],
                    "scripture_refs": [],
                    "energy": "invalid",
                    "summary": "Резюме.",
                },
            )
        return json.dumps(
            {
                "tags": ["тема"],
                "scripture_refs": ["Ин 3:16"],
                "energy": "slow",
                "summary": "Поклонение към Бога.",
            },
        )

    result = analyze_song_with_completion(
        completion,
        model="gpt-4o-mini",
        title="Заглавие",
        author=None,
        lyrics_plain="текст",
    )
    assert result is not None
    assert result.energy == "slow"
    assert len(calls) == 2


def test_analyze_song_returns_none_after_two_invalid_responses():
    def completion(_messages):
        return json.dumps(
            {
                "tags": [],
                "scripture_refs": [],
                "energy": "fast",
                "summary": "",
            },
        )

    result = analyze_song_with_completion(
        completion,
        model="gpt-4o-mini",
        title="Заглавие",
        author="Автор",
        lyrics_plain="текст",
    )
    assert result is None
