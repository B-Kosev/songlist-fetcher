import pytest

from worship_song_selector.flow_settings import (
    FlowTemplateValidationError,
    flow_template_to_json,
    parse_flow_template_value,
    slot_energy_from_energies,
    validate_flow_template,
)
from worship_song_selector.recommendation import FlowSlot, default_flow_template


def test_default_flow_template_passes_validation():
    validate_flow_template(default_flow_template())


def test_flow_template_to_json_round_trip():
    slots = default_flow_template()
    restored = parse_flow_template_value(flow_template_to_json(slots))
    assert restored == slots


def test_validate_rejects_empty_role():
    base = default_flow_template()
    slots = [
        FlowSlot(role="  ", energy=base[0].energy, purpose=base[0].purpose),
        *base[1:],
    ]
    with pytest.raises(FlowTemplateValidationError, match="Празна роля"):
        validate_flow_template(slots)


def test_validate_rejects_invalid_energy():
    base = default_flow_template()
    slots = [
        FlowSlot(role=base[0].role, energy="lively", purpose=base[0].purpose),
        *base[1:],
    ]
    with pytest.raises(FlowTemplateValidationError, match="Невалидна енергия"):
        validate_flow_template(slots)


def test_slot_energy_from_energies():
    assert slot_energy_from_energies(["fast", "medium"]) == "fast / medium"
