from worship_song_selector.library_search import (
    build_song_search_text,
    filter_library_songs,
    fuzzy_query_matches_text,
    normalize_for_search,
)


def test_normalize_for_search_is_case_insensitive():
    assert normalize_for_search("Велик") == normalize_for_search("велик")


def test_normalize_for_search_strips_accents():
    assert normalize_for_search("café") == normalize_for_search("cafe")


def test_normalize_for_search_maps_bulgarian_confusables():
    assert normalize_for_search("май") == normalize_for_search("маи")
    assert normalize_for_search("сърце") == normalize_for_search("сарце")


def test_fuzzy_query_matches_subsequence_for_missing_letters():
    haystack = normalize_for_search("благословен")
    assert fuzzy_query_matches_text("блгословен", haystack)
    assert fuzzy_query_matches_text("благословен", haystack)


def test_fuzzy_query_matches_bulgarian_near_miss_in_phrase():
    text = normalize_for_search("Велик е Господ наш")
    assert fuzzy_query_matches_text("велик", text)
    assert fuzzy_query_matches_text("велк", text)


def test_build_song_search_text_includes_title_author_tags_and_lyrics():
    song = {
        "title": "Благословен",
        "author": "Автор",
        "tags": ["хваление"],
        "lyrics": [{"section_type": "verse", "number": 1, "lines": ["Първи ред"]}],
    }
    blob = build_song_search_text(song)
    assert "благословен" in blob
    assert "автор" in blob
    assert "хваление" in blob
    assert "парви" in blob


def test_filter_library_songs_empty_query_returns_all_sorted_by_title():
    songs = [
        {"id": "2", "title": "Б", "author": None, "energy": "fast", "tags": []},
        {"id": "1", "title": "А", "author": None, "energy": "slow", "tags": []},
    ]
    result = filter_library_songs(songs, query="", energy=None)
    assert [s["title"] for s in result] == ["А", "Б"]


def test_filter_library_songs_matches_title_author_tags_and_lyrics():
    songs = [
        {
            "id": "1",
            "title": "Едно",
            "author": "Иван",
            "energy": "medium",
            "tags": ["милост"],
            "lyrics": [{"section_type": "chorus", "lines": ["Христос е жив"]}],
        },
        {
            "id": "2",
            "title": "Друго",
            "author": "Петър",
            "energy": "fast",
            "tags": [],
            "lyrics": [],
        },
    ]
    assert len(filter_library_songs(songs, query="иван", energy=None)) == 1
    assert len(filter_library_songs(songs, query="милост", energy=None)) == 1
    assert len(filter_library_songs(songs, query="христос", energy=None)) == 1


def test_filter_library_songs_scales_to_full_library_size():
    template = {
        "author": "Автор",
        "energy": "medium",
        "tags": ["хваление"],
        "lyrics": [{"section_type": "verse", "lines": ["ред с текст"]}],
    }
    songs = [
        {**template, "id": str(index), "title": f"Песен {index:03d}"}
        for index in range(400)
    ]
    result = filter_library_songs(songs, query="песен 042", energy="medium")
    assert len(result) == 1
    assert result[0]["id"] == "42"


def test_filter_library_songs_energy_filter_combines_with_query():
    songs = [
        {
            "id": "1",
            "title": "Бърза песен",
            "author": None,
            "energy": "fast",
            "tags": ["хваление"],
            "lyrics": [],
        },
        {
            "id": "2",
            "title": "Бавна песен",
            "author": None,
            "energy": "slow",
            "tags": ["хваление"],
            "lyrics": [],
        },
    ]
    assert len(filter_library_songs(songs, query="хваление", energy="fast")) == 1
    assert filter_library_songs(songs, query="хваление", energy="fast")[0]["id"] == "1"
