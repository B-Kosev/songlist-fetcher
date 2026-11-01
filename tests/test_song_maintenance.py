import pytest

from worship_song_selector.song_maintenance import (
    AdminSongFields,
    InvalidEnergyError,
    ai_fields_changed,
    analysis_result_may_overwrite_hand_edits,
    import_update_preserves_hand_edits,
    normalized_title_clash,
    parse_comma_separated_list,
    parse_energy_value,
    should_set_tags_edited,
)


def test_parse_comma_separated_list():
    assert parse_comma_separated_list("a, b , ,c") == ["a", "b", "c"]
    assert parse_comma_separated_list("") == []


def test_parse_energy_value():
    assert parse_energy_value("fast") == "fast"
    assert parse_energy_value("") is None
    with pytest.raises(InvalidEnergyError):
        parse_energy_value("upbeat")


def test_ai_fields_changed_detects_summary_and_tags():
    existing = {
        "energy": "fast",
        "tags": ["хваление"],
        "summary": "Старо.",
        "scripture_refs": [],
    }
    assert not ai_fields_changed(
        existing,
        energy="fast",
        tags=["хваление"],
        summary="Старо.",
        scripture_refs=[],
    )
    assert ai_fields_changed(
        existing,
        energy="fast",
        tags=["хваление", "кръст"],
        summary="Старо.",
        scripture_refs=[],
    )


def test_should_set_tags_edited_when_ai_field_changes():
    existing = {
        "tags_edited": False,
        "energy": "medium",
        "tags": ["тема"],
        "summary": "Резюме.",
        "scripture_refs": [],
    }
    fields = AdminSongFields(
        title="T",
        author=None,
        energy="medium",
        tags=["тема", "ново"],
        summary="Резюме.",
        scripture_refs=[],
    )
    assert should_set_tags_edited(existing, fields)


def test_should_set_tags_edited_stays_true():
    existing = {"tags_edited": True, "energy": "fast", "tags": [], "summary": None, "scripture_refs": []}
    fields = AdminSongFields(
        title="T",
        author=None,
        energy="fast",
        tags=[],
        summary=None,
        scripture_refs=[],
    )
    assert should_set_tags_edited(existing, fields)


def test_normalized_title_clash():
    by_norm = {"same": {"id": "1", "title": "Same"}}
    assert normalized_title_clash("same", songs_by_normalized=by_norm, exclude_song_id="1") is False
    assert normalized_title_clash("same", songs_by_normalized=by_norm, exclude_song_id="2") is True
    assert normalized_title_clash("other", songs_by_normalized=by_norm, exclude_song_id=None) is False


def test_import_update_preserves_hand_edits():
    assert import_update_preserves_hand_edits(tags_edited=True, overwrite_hand_edits=False)
    assert not import_update_preserves_hand_edits(tags_edited=True, overwrite_hand_edits=True)
    assert not import_update_preserves_hand_edits(tags_edited=False, overwrite_hand_edits=False)


def test_analysis_result_may_overwrite_hand_edits():
    assert analysis_result_may_overwrite_hand_edits(tags_edited=False, overwrite_hand_edits=False)
    assert not analysis_result_may_overwrite_hand_edits(tags_edited=True, overwrite_hand_edits=False)
    assert analysis_result_may_overwrite_hand_edits(tags_edited=True, overwrite_hand_edits=True)
