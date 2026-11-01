from worship_song_selector.import_matching import (
    ImportActionKind,
    ImportMatchKind,
    batch_duplicate_normalized_titles,
    classify_against_existing,
    import_preview_label,
    lyrics_equal,
    plan_import_actions,
    resolve_import_action,
)
from worship_song_selector.titles import normalize_title


def test_normalize_title_equivalence_from_acceptance_criteria():
    assert normalize_title("Велик си Ти") == normalize_title("Велик Си Ти!")


def test_classify_new_when_no_existing_song():
    assert classify_against_existing([{"section_type": "verse", "lines": ["a"]}], None) == (
        ImportMatchKind.NEW
    )


def test_classify_identical_when_lyrics_match():
    lyrics = [{"section_type": "chorus", "lines": ["same"]}]
    existing = {"id": "1", "title": "T", "lyrics": lyrics, "raw_text": "x"}
    assert classify_against_existing(lyrics, existing) == ImportMatchKind.IDENTICAL


def test_classify_update_when_lyrics_differ():
    existing = {
        "id": "1",
        "title": "T",
        "lyrics": [{"section_type": "verse", "lines": ["old"]}],
        "raw_text": "x",
    }
    assert (
        classify_against_existing(
            [{"section_type": "verse", "lines": ["new"]}],
            existing,
        )
        == ImportMatchKind.UPDATE
    )


def test_lyrics_equal_compares_lyrics_payloads():
    left = [{"section_type": "verse", "number": 1, "lines": ["a", "b"]}]
    right = [{"section_type": "verse", "number": 1, "lines": ["a", "b"]}]
    assert lyrics_equal(left, right)


def test_batch_duplicate_normalized_titles():
    assert batch_duplicate_normalized_titles(["a", "b", "a"]) == frozenset({"a"})
    assert batch_duplicate_normalized_titles(["a", "b"]) == frozenset()


def test_resolve_import_action_auto_new_update_identical():
    existing = {
        "id": "song-1",
        "title": "Existing",
        "normalized_title": "existing",
        "lyrics": [{"section_type": "verse", "lines": ["x"]}],
        "raw_text": "raw",
    }
    by_norm = {"existing": existing}
    by_id = {"song-1": existing}

    action_new = resolve_import_action(
        lyrics=[{"section_type": "verse", "lines": ["y"]}],
        normalized_title="brand",
        existing_by_normalized=by_norm,
        existing_songs_by_id=by_id,
        override=None,
    )
    assert action_new.kind == ImportActionKind.INSERT

    action_update = resolve_import_action(
        lyrics=[{"section_type": "verse", "lines": ["changed"]}],
        normalized_title="existing",
        existing_by_normalized=by_norm,
        existing_songs_by_id=by_id,
        override=None,
    )
    assert action_update.kind == ImportActionKind.UPDATE
    assert action_update.song_id == "song-1"

    action_skip = resolve_import_action(
        lyrics=existing["lyrics"],
        normalized_title="existing",
        existing_by_normalized=by_norm,
        existing_songs_by_id=by_id,
        override=None,
    )
    assert action_skip.kind == ImportActionKind.SKIP


def test_resolve_import_action_override_new_and_other_song():
    existing = {
        "id": "song-1",
        "title": "A",
        "normalized_title": "a",
        "lyrics": [{"section_type": "verse", "lines": ["x"]}],
        "raw_text": "raw",
    }
    other = {
        "id": "song-2",
        "title": "B",
        "normalized_title": "b",
        "lyrics": [{"section_type": "verse", "lines": ["old"]}],
        "raw_text": "raw2",
    }
    by_norm = {"a": existing, "b": other}
    by_id = {"song-1": existing, "song-2": other}

    forced_new = resolve_import_action(
        lyrics=existing["lyrics"],
        normalized_title="a",
        existing_by_normalized=by_norm,
        existing_songs_by_id=by_id,
        override="new",
    )
    assert forced_new.kind == ImportActionKind.INSERT

    forced_other = resolve_import_action(
        lyrics=[{"section_type": "verse", "lines": ["fresh"]}],
        normalized_title="a",
        existing_by_normalized=by_norm,
        existing_songs_by_id=by_id,
        override="song-2",
    )
    assert forced_other.kind == ImportActionKind.UPDATE
    assert forced_other.song_id == "song-2"


def test_import_preview_label():
    assert import_preview_label(ImportMatchKind.NEW, None) == "Нова"
    assert import_preview_label(ImportMatchKind.UPDATE, "Great I Am") == (
        "Обновява: Great I Am"
    )
    assert import_preview_label(ImportMatchKind.IDENTICAL, "Great I Am") == (
        "Същата — пропуск"
    )


def test_plan_import_actions_skips_identical_and_inserts_new():
    drafts = [
        {
            "title": "New Song",
            "normalized_title": "new song",
            "author": None,
            "lyrics": [{"section_type": "verse", "lines": ["n"]}],
            "raw_text": "raw-n",
            "override": None,
        },
        {
            "title": "Same",
            "normalized_title": "same",
            "author": "A",
            "lyrics": [{"section_type": "verse", "lines": ["x"]}],
            "raw_text": "raw-s",
            "override": None,
        },
    ]
    existing_by_norm = {
        "same": {
            "id": "id-1",
            "title": "Same",
            "normalized_title": "same",
            "lyrics": [{"section_type": "verse", "lines": ["x"]}],
            "raw_text": "raw-s",
        },
    }
    existing_by_id = {"id-1": existing_by_norm["same"]}

    actions = plan_import_actions(
        drafts,
        existing_by_normalized=existing_by_norm,
        existing_songs_by_id=existing_by_id,
    )
    assert [a.kind for a in actions] == [ImportActionKind.INSERT, ImportActionKind.SKIP]
