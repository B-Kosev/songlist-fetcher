-- Worship Song Selector — initial schema (PRD §3.1 songs table)

CREATE TABLE IF NOT EXISTS songs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL UNIQUE,
    author TEXT,
    lyrics JSONB,
    raw_text TEXT,
    energy TEXT CHECK (energy IN ('fast', 'medium', 'slow')),
    tags TEXT[] DEFAULT '{}',
    scripture_refs TEXT[] DEFAULT '{}',
    summary TEXT,
    tags_edited BOOLEAN NOT NULL DEFAULT FALSE,
    analysis_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (analysis_status IN ('pending', 'done', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS songs_normalized_title_idx ON songs (normalized_title);
