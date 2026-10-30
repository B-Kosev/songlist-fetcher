from __future__ import annotations

from supabase import Client, create_client

from worship_song_selector.config import SupabaseConfig


def create_supabase_client(config: SupabaseConfig) -> Client:
    return create_client(config.url, config.key)


def count_songs(client: Client) -> int:
    response = (
        client.table("songs")
        .select("id", count="exact", head=True)
        .execute()
    )
    if response.count is None:
        raise ValueError("Supabase did not return a row count")
    return int(response.count)
