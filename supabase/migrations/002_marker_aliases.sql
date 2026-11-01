-- Worship Song Selector — marker alias mappings (PRD §3.1)

CREATE TABLE IF NOT EXISTS marker_aliases (
    raw_marker TEXT PRIMARY KEY,
    section_type TEXT NOT NULL CHECK (
        section_type IN (
            'verse',
            'pre_chorus',
            'chorus',
            'bridge',
            'tag',
            'ignore_line',
            'not_a_marker'
        )
    )
);
