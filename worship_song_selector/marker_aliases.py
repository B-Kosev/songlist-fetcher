from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from supabase import Client


def fetch_marker_aliases(client: Client) -> dict[str, str]:
    response = client.table("marker_aliases").select("raw_marker, section_type").execute()
    rows: list[dict[str, Any]] = list(response.data or [])
    return {str(row["raw_marker"]): str(row["section_type"]) for row in rows}


def upsert_marker_aliases(client: Client, aliases: Mapping[str, str]) -> None:
    if not aliases:
        return
    rows = [
        {"raw_marker": raw_marker, "section_type": section_type}
        for raw_marker, section_type in aliases.items()
    ]
    client.table("marker_aliases").upsert(rows).execute()
