import json
import uuid

import pytest

from worship_song_selector.recommendation import (
    RecommendationValidationError,
    build_recommendation_messages,
    default_flow_template,
    parse_recommendation_response,
    recommend_set_with_completion,
)


def _song(
    *,
    title: str = "Песен",
    song_id: str | None = None,
) -> dict:
    return {
        "id": song_id or str(uuid.uuid4()),
        "title": title,
        "author": "Автор",
        "energy": "medium",
        "tags": ["хваление"],
        "scripture_refs": ["Пс 100"],
        "summary": "Кратко резюме.",
    }


def test_default_flow_template_has_five_prd_slots():
    slots = default_flow_template()
    assert len(slots) == 5
    assert slots[0].role == "Хваление"
    assert slots[0].energy == "fast"
    assert "celebratory" in slots[0].purpose.lower() or "gather" in slots[0].purpose.lower()


def test_build_recommendation_messages_include_theme_flow_and_songs():
    songs = [_song(title="А"), _song(title="Б")]
    messages = build_recommendation_messages(
        theme="Тема за неделя",
        flow_slots=default_flow_template(),
        songs=songs,
    )
    user = messages[1]["content"]
    assert "Тема за неделя" in user
    assert "Хваление" in user
    assert songs[0]["id"] in user
    assert songs[1]["title"] in user
    assert "summary" in user.lower() or "резюме" in user.lower() or songs[0]["summary"] in user


def test_parse_valid_recommendation_response():
    id_a = str(uuid.uuid4())
    id_b = str(uuid.uuid4())
    id_c = str(uuid.uuid4())
    id_d = str(uuid.uuid4())
    id_e = str(uuid.uuid4())
    valid_ids = {id_a, id_b, id_c, id_d, id_e}
    payload = {
        "picks": [
            {"song_id": id_a, "reason": "Причина 1."},
            {"song_id": id_b, "reason": "Причина 2."},
            {"song_id": id_c, "reason": "Причина 3."},
            {"song_id": id_d, "reason": "Причина 4."},
            {"song_id": id_e, "reason": "Причина 5."},
        ],
    }
    result = parse_recommendation_response(json.dumps(payload), valid_ids=valid_ids)
    assert len(result) == 5
    assert result[0].song_id == id_a
    assert result[0].reason == "Причина 1."


def test_parse_rejects_unknown_song_id():
    known_ids = [str(uuid.uuid4()) for _ in range(5)]
    unknown = str(uuid.uuid4())
    payload = {
        "picks": [
            {"song_id": unknown, "reason": "X."},
            *[{"song_id": sid, "reason": "Ok."} for sid in known_ids[1:]],
        ],
    }
    with pytest.raises(RecommendationValidationError):
        parse_recommendation_response(json.dumps(payload), valid_ids=set(known_ids))


def test_parse_rejects_duplicate_ids():
    ids = [str(uuid.uuid4()) for _ in range(4)]
    payload = {
        "picks": [
            {"song_id": ids[0], "reason": "A."},
            {"song_id": ids[0], "reason": "B."},
            {"song_id": ids[1], "reason": "C."},
            {"song_id": ids[2], "reason": "D."},
            {"song_id": ids[3], "reason": "E."},
        ],
    }
    with pytest.raises(RecommendationValidationError):
        parse_recommendation_response(json.dumps(payload), valid_ids=set(ids))


def test_recommend_set_retries_on_invalid_response():
    songs = [_song() for _ in range(5)]
    valid_ids = {s["id"] for s in songs}
    calls: list[int] = []

    def completion(messages):
        calls.append(1)
        if len(calls) == 1:
            return json.dumps({"picks": [{"song_id": "not-a-uuid", "reason": "x"}]})
        picks = [{"song_id": s["id"], "reason": f"R{i}."} for i, s in enumerate(songs, 1)]
        return json.dumps({"picks": picks})

    result = recommend_set_with_completion(
        completion,
        theme="Тема",
        flow_slots=default_flow_template(),
        songs=songs,
        valid_ids=valid_ids,
        max_attempts=2,
    )
    assert result is not None
    assert len(result) == 5
    assert len(calls) == 2


def test_recommend_set_returns_none_after_exhausted_retries():
    songs = [_song()]
    valid_ids = {songs[0]["id"]}

    def completion(messages):
        return json.dumps({"picks": []})

    result = recommend_set_with_completion(
        completion,
        theme="Тема",
        flow_slots=default_flow_template(),
        songs=songs,
        valid_ids=valid_ids,
        max_attempts=2,
    )
    assert result is None


def test_build_messages_include_locked_and_excluded_instructions():
    songs = [_song(title=f"S{i}") for i in range(6)]
    locked_id = songs[2]["id"]
    excluded_id = songs[5]["id"]
    messages = build_recommendation_messages(
        theme="Тема",
        flow_slots=default_flow_template(),
        songs=songs,
        locked_by_slot={1: locked_id},
        excluded_ids={excluded_id},
    )
    user = messages[1]["content"]
    assert locked_id in user
    assert excluded_id in user
    assert "заключ" in user.lower() or "locked" in user.lower() or "слот 2" in user.lower()
    assert excluded_id not in _catalog_ids_in_user_message(user)


def _catalog_ids_in_user_message(user: str) -> set[str]:
    marker = "Каталог на анализирани песни (JSON):"
    payload = user.split(marker, 1)[1].strip()
    catalog = json.loads(payload)
    return {entry["id"] for entry in catalog}


def test_parse_rejects_excluded_song_id():
    ids = [str(uuid.uuid4()) for _ in range(6)]
    excluded = ids[5]
    valid_ids = set(ids)
    payload = {
        "picks": [
            {"song_id": ids[0], "reason": "A."},
            {"song_id": ids[1], "reason": "B."},
            {"song_id": ids[2], "reason": "C."},
            {"song_id": ids[3], "reason": "D."},
            {"song_id": excluded, "reason": "E."},
        ],
    }
    with pytest.raises(RecommendationValidationError):
        parse_recommendation_response(
            json.dumps(payload),
            valid_ids=valid_ids,
            excluded_ids={excluded},
        )


def test_parse_rejects_locked_slot_change():
    ids = [str(uuid.uuid4()) for _ in range(5)]
    valid_ids = set(ids)
    payload = {
        "picks": [
            {"song_id": ids[0], "reason": "A."},
            {"song_id": ids[4], "reason": "B."},
            {"song_id": ids[2], "reason": "C."},
            {"song_id": ids[3], "reason": "D."},
            {"song_id": ids[4], "reason": "E."},
        ],
    }
    with pytest.raises(RecommendationValidationError):
        parse_recommendation_response(
            json.dumps(payload),
            valid_ids=valid_ids,
            locked_by_slot={1: ids[1]},
        )


def test_parse_replace_requires_other_slots_unchanged():
    ids = [str(uuid.uuid4()) for _ in range(6)]
    valid_ids = set(ids)
    replace_slot = 2
    rejected = ids[replace_slot]
    replacement = ids[5]
    payload = {
        "picks": [
            {"song_id": ids[0], "reason": "A."},
            {"song_id": ids[1], "reason": "B."},
            {"song_id": replacement, "reason": "C."},
            {"song_id": ids[3], "reason": "D."},
            {"song_id": ids[4], "reason": "E."},
        ],
    }
    result = parse_recommendation_response(
        json.dumps(payload),
        valid_ids=valid_ids,
        excluded_ids={rejected},
        required_by_slot={
            0: ids[0],
            1: ids[1],
            3: ids[3],
            4: ids[4],
        },
        replace_slot=replace_slot,
        replace_rejected_id=rejected,
    )
    assert result[replace_slot].song_id == replacement


def test_parse_replace_rejects_same_song():
    ids = [str(uuid.uuid4()) for _ in range(5)]
    valid_ids = set(ids)
    replace_slot = 2
    rejected = ids[replace_slot]
    payload = {
        "picks": [
            {"song_id": ids[0], "reason": "A."},
            {"song_id": ids[1], "reason": "B."},
            {"song_id": rejected, "reason": "C."},
            {"song_id": ids[3], "reason": "D."},
            {"song_id": ids[4], "reason": "E."},
        ],
    }
    with pytest.raises(RecommendationValidationError):
        parse_recommendation_response(
            json.dumps(payload),
            valid_ids=valid_ids,
            excluded_ids={rejected},
            required_by_slot={0: ids[0], 1: ids[1], 3: ids[3], 4: ids[4]},
            replace_slot=replace_slot,
            replace_rejected_id=rejected,
        )


def test_recommend_set_retries_when_locked_slot_violated():
    songs = [_song() for _ in range(6)]
    valid_ids = {s["id"] for s in songs}
    locked_slot = 0
    locked_id = songs[0]["id"]
    calls: list[int] = []

    def completion(messages):
        calls.append(1)
        if len(calls) == 1:
            picks = [{"song_id": s["id"], "reason": f"R{i}."} for i, s in enumerate(songs[:5], 1)]
            picks[locked_slot] = {"song_id": songs[5]["id"], "reason": "Bad."}
            return json.dumps({"picks": picks})
        picks = [{"song_id": s["id"], "reason": f"R{i}."} for i, s in enumerate(songs[:5], 1)]
        return json.dumps({"picks": picks})

    result = recommend_set_with_completion(
        completion,
        theme="Тема",
        flow_slots=default_flow_template(),
        songs=songs,
        valid_ids=valid_ids,
        locked_by_slot={locked_slot: locked_id},
        max_attempts=2,
    )
    assert result is not None
    assert result[locked_slot].song_id == locked_id
    assert len(calls) == 2


def test_recommend_set_retries_when_excluded_song_returned():
    songs = [_song() for _ in range(6)]
    valid_ids = {s["id"] for s in songs}
    excluded_id = songs[5]["id"]
    calls: list[int] = []

    def completion(messages):
        calls.append(1)
        if len(calls) == 1:
            picks = [{"song_id": s["id"], "reason": f"R{i}."} for i, s in enumerate(songs[:5], 1)]
            picks[3] = {"song_id": excluded_id, "reason": "Bad."}
            return json.dumps({"picks": picks})
        picks = [{"song_id": s["id"], "reason": f"R{i}."} for i, s in enumerate(songs[:5], 1)]
        return json.dumps({"picks": picks})

    result = recommend_set_with_completion(
        completion,
        theme="Тема",
        flow_slots=default_flow_template(),
        songs=songs,
        valid_ids=valid_ids,
        excluded_ids={excluded_id},
        max_attempts=2,
    )
    assert result is not None
    assert excluded_id not in {pick.song_id for pick in result}
    assert len(calls) == 2
