#!/usr/bin/env python3
"""Trivial Supabase read for scheduled keep-alive (free-tier inactivity)."""

from __future__ import annotations

import os
import sys

from worship_song_selector.config import SupabaseConfig
from worship_song_selector.songs import count_songs, create_supabase_client


def main() -> int:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_KEY must be set", file=sys.stderr)
        return 1

    client = create_supabase_client(SupabaseConfig(url=url, key=key))
    try:
        total = count_songs(client)
    except Exception as exc:
        print(f"keepalive failed: {exc}", file=sys.stderr)
        return 1

    print(f"keepalive ok: songs count={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
