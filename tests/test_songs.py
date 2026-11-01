from worship_song_selector.songs import build_song_row


def test_build_song_row_sets_normalized_title():
    row = build_song_row(
        title="  Велик!!! ",
        author="Автор",
        lyrics=[],
        raw_text="raw",
    )
    assert row["normalized_title"] == "велик"
    assert row["analysis_status"] == "pending"
