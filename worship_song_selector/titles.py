from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def normalize_title(title: str) -> str:
    folded = title.casefold().strip()
    chars: list[str] = []
    for char in folded:
        if char.isspace():
            chars.append(" ")
        elif unicodedata.category(char).startswith("L") or char.isdigit():
            chars.append(char)
    collapsed = re.sub(r"\s+", " ", "".join(chars)).strip()
    return collapsed
