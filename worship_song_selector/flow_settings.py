from __future__ import annotations

import re
from typing import Any

from supabase import Client

from worship_song_selector.recommendation import FlowSlot, default_flow_template

FLOW_TEMPLATE_KEY = "flow_template"
_ALLOWED_ENERGIES = frozenset({"fast", "medium", "slow"})
_ENERGY_PARTS_RE = re.compile(r"\s*/\s*")


class FlowTemplateValidationError(ValueError):
    pass


def _validation_message(code: str, slot_index: int) -> str:
    messages = {
        "count": "Шаблонът трябва да има точно 5 слота.",
        "slot": "Невалиден слот в шаблона.",
        "fields": "Невалидни полета в слот.",
        "empty_role": f"Празна роля в слот {slot_index}.",
        "empty_purpose": f"Празна цел в слот {slot_index}.",
        "invalid_energy": f"Невалидна енергия в слот {slot_index} (fast / medium / slow).",
    }
    return messages.get(code, "Невалиден шаблон за поток.")


def flow_template_to_json(slots: list[FlowSlot]) -> list[dict[str, str]]:
    return [
        {"role": slot.role, "energy": slot.energy, "purpose": slot.purpose} for slot in slots
    ]


def validate_flow_template(slots: list[FlowSlot]) -> None:
    if len(slots) != 5:
        raise FlowTemplateValidationError(_validation_message("count", 0))
    for index, slot in enumerate(slots, start=1):
        if not slot.role.strip():
            raise FlowTemplateValidationError(_validation_message("empty_role", index))
        if not slot.purpose.strip():
            raise FlowTemplateValidationError(_validation_message("empty_purpose", index))
        parts = _ENERGY_PARTS_RE.split(slot.energy.strip())
        if not parts or not parts[0] or len(parts) > 2:
            raise FlowTemplateValidationError(_validation_message("invalid_energy", index))
        for part in parts:
            if part not in _ALLOWED_ENERGIES:
                raise FlowTemplateValidationError(_validation_message("invalid_energy", index))


def parse_flow_template_value(raw: Any) -> list[FlowSlot]:
    if not isinstance(raw, list) or len(raw) != 5:
        raise FlowTemplateValidationError(_validation_message("count", 0))
    slots: list[FlowSlot] = []
    for item in raw:
        if not isinstance(item, dict):
            raise FlowTemplateValidationError(_validation_message("slot", 0))
        role = item.get("role")
        energy = item.get("energy")
        purpose = item.get("purpose")
        if not isinstance(role, str) or not isinstance(energy, str) or not isinstance(
            purpose,
            str,
        ):
            raise FlowTemplateValidationError(_validation_message("fields", 0))
        slots.append(
            FlowSlot(role=role.strip(), energy=energy.strip(), purpose=purpose.strip()),
        )
    validate_flow_template(slots)
    return slots


def _read_flow_template_row(client: Client) -> list[dict[str, Any]] | None:
    response = (
        client.table("settings")
        .select("value")
        .eq("key", FLOW_TEMPLATE_KEY)
        .limit(1)
        .execute()
    )
    rows: list[dict[str, Any]] = list(response.data or [])
    if not rows:
        return None
    value = rows[0].get("value")
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        nested = value.get("slots")
        if isinstance(nested, list):
            return nested
    return None


def _write_flow_template(client: Client, slots: list[FlowSlot]) -> None:
    validate_flow_template(slots)
    payload = flow_template_to_json(slots)
    client.table("settings").upsert(
        {"key": FLOW_TEMPLATE_KEY, "value": payload},
    ).execute()


def fetch_flow_template(client: Client) -> list[FlowSlot]:
    raw = _read_flow_template_row(client)
    if raw is None:
        default = default_flow_template()
        _write_flow_template(client, default)
        return default
    return parse_flow_template_value(raw)


def save_flow_template(client: Client, slots: list[FlowSlot]) -> None:
    _write_flow_template(client, slots)


def reset_flow_template(client: Client) -> list[FlowSlot]:
    default = default_flow_template()
    _write_flow_template(client, default)
    return default


def energies_from_slot_energy(energy: str) -> list[str]:
    return _ENERGY_PARTS_RE.split(energy.strip())


def slot_energy_from_energies(energies: list[str]) -> str:
    return " / ".join(energies)
