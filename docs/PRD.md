# Worship Song Selector — Product Requirements

## 1. Overview

A private, Bulgarian-language web app for one church. A worship leader types a free-text service theme and gets back an ordered list of 5 songs from the church's own library. The leader then builds the service chart in Worship Tools Planning; this app never writes to Worship Tools.

**Library size:** ~310 songs today, growing by ~20–40 per year.

**Language:** Bulgarian only — songs, themes, UI, and AI output.

## 2. Users and access

| Role | Passcode | Can do |
|---|---|---|
| Team | Team passcode | Browse library, view lyrics, generate and refine sets |
| Admin | Admin passcode | Everything Team can, plus import, edit metadata/tags, delete, re-analyse, edit flow template, manage marker aliases |

- No user accounts, no sign-up. Passcodes are stored as hashes in Streamlit secrets.
- Role is held in Streamlit session state; admin-only screens are hidden for Team.
- One person (the admin) does nearly all imports and edits.

## 3. Architecture

| Concern | Choice |
|---|---|
| Language / UI | Python 3.11+, Streamlit |
| Hosting | Streamlit Community Cloud (free tier) |
| Persistence | Supabase Postgres (free tier) |
| Keep-alive | Scheduled GitHub Actions workflow issuing a trivial query every ~3 days so the Supabase project is not paused |
| LLM | OpenAI, model name configurable; default `gpt-4o-mini` |
| Cost guard | Hard monthly spend limit set in the OpenAI dashboard |

The app container's local disk is not used for persistence (it is wiped on restart/redeploy).

### 3.1 Data model

- **songs**: `id`, `title`, `normalized_title` (unique), `author`, `lyrics` (sections with normalized labels), `raw_text` (original file content, for re-parsing), `energy` (`fast` / `medium` / `slow`), `tags` (themes), `scripture_refs`, `summary`, `tags_edited` (bool — set when admin edits AI fields by hand), `analysis_status` (`pending` / `done` / `failed`), timestamps.
- **marker_aliases**: `raw_marker` (normalized) → `section_type` (`verse` / `pre_chorus` / `chorus` / `bridge` / `tag` / `ignore_line` / `not_a_marker`).
- **settings**: the 5-slot flow template.

No usage history, no saved sets.

## 4. Functional requirements

### FR-1 Authentication

- App shows a passcode prompt before anything else.
- Entering the Team or Admin passcode sets the role for the session.

### FR-2 Import (Admin)

1. Multi-file upload of `.txt` files. One song per file.
2. **Deterministic parser** (no AI touches lyrics):
   - Strips chords in `[...]` and comments in `{...}`.
   - Recognises section markers from several formats (e.g. `v1`, `Verse1`, ProPresenter `slide1`) and normalizes them to a section type.
   - Title comes from the file's title line / metadata if present, otherwise the filename.
3. **Import preview** — nothing is saved until the admin confirms:
   - Each file is shown as **New**, **Updates existing: \<title\>**, or **Identical — skip**, matched on normalized title (lowercase, punctuation stripped, whitespace collapsed). The admin can override any match.
   - Any unrecognised marker is surfaced; the admin maps it to a section type. Mappings are saved to `marker_aliases` and applied to all future imports.
   - Flagged files show the parsed result next to the raw text.
   - Title and author can be corrected in the preview.
4. On confirm, songs are saved, then analysed (FR-3). An update replaces lyrics and re-runs analysis, but preserves AI fields the admin edited by hand unless the admin opts to overwrite them.

### FR-3 Song analysis

- Run once per song after save (and on re-analyse). Produces: theme tags, scripture references, energy, one-line summary — all in Bulgarian, kept short to limit tokens.
- Bulk import runs analysis concurrently with a progress bar. Failed songs are marked `failed` and can be retried via "Analyse pending/failed".
- Admin can **Re-analyse** a single song or **Re-analyse all** (e.g. after the analysis prompt changes).

### FR-4 Library

- One search box matching title, author, lyrics, and tags; case- and accent-insensitive, tolerant of near-miss spellings.
- Filter by energy.
- List columns: title, author, energy, tags.
- Song detail: read-only lyrics with section labels, AI summary, tags, scripture refs.
- Admin on detail: edit title, author, energy, tags/summary/scripture refs; Re-analyse; Delete (with confirmation, hard delete).
- Lyrics are **not** editable in the app; change them by re-uploading the file.

### FR-5 Recommendation

**Input:** a single free-text field (theme, passage, or notes).

**Optional:** "Exclude songs" multi-select.

**Process:**
- Prompt contains the summaries/tags/energy of **all** songs (no embeddings at this library size), the flow template, the theme, plus locked and excluded songs.
- The model must return song IDs. The app rejects any ID not in the library, duplicates, or excluded songs, and retries.

**Output** — an ordered list of 5 lines, each showing:
- number, title, author
- slot role, energy
- a one-line reason (small text below the title)

**Actions:**
- **Lock** a line (kept on regenerate).
- **Replace** a single line (rejected song is excluded for the rest of the session).
- **Regenerate** all unlocked lines.
- **Copy titles** — copies the numbered title list to the clipboard.

All refinement state lives in the session only.

### FR-6 Flow template (Admin)

Five slots, each with a Bulgarian role name, target energy, and a one-sentence purpose given to the model. Default:

| # | Role | Energy | Purpose |
|---|---|---|---|
| 1 | Хваление | fast | Opening, celebratory, invites the church to gather |
| 2 | Хваление | fast / medium | Sustains energy, starts moving toward the theme |
| 3 | Преход | medium | Bridges into reflection, closest to the theme |
| 4 | Поклонение | slow | Intimate, focused on God's character as it relates to the theme |
| 5 | Отговор | medium / slow | Response: commitment, sending, consecration |

## 5. Non-functional requirements

- **Cost:** entire stack on free tiers; LLM spend capped by the OpenAI hard limit. Per-song analysis is one-off; each recommendation is a single call.
- **Latency:** parsing < 3 s per file; set generation within 5–10 s.
- **Usability:** minimal tabbed UI (Recommend · Library · Import · Settings, the last two admin-only). Workflow: type theme → get 5 songs → copy titles.

## 6. Out of scope

- Embeddings / vector retrieval (revisit beyond ~1000 songs).
- AI-based lyric cleanup or parsing.
- Editing lyrics in the app.
- Usage history, rotation, "active/inactive" flags, saved sets.
- Bible API lookup or structured scripture input.
- PDF/print export; any integration with Worship Tools.
- Multi-language support.

## 7. Risks and open items

- **Bulgarian quality of `gpt-4o-mini`:** evaluate analysis and recommendations on 10–20 real songs before the bulk import; switch model via config if needed.
- **Token volume:** Cyrillic is ~2× tokens vs English; ~400 compact summaries ≈ 40–50k input tokens per query. Confirm the 5–10 s latency target holds.
- **Export formats:** collect real sample files (Worship Tools, ProPresenter, others) to pin parser rules and fixture tests.
- **Copyright:** confirm storing full lyrics in a private app is covered by the church's CCLI licence.
- **Free-tier policies** (Supabase pausing, Streamlit Cloud limits) can change; re-check at build time.
