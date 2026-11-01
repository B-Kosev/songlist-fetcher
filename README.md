# Worship Song Selector

Private Bulgarian-language Streamlit app for worship song recommendations. See [docs/PRD.md](docs/PRD.md) for product requirements.

## Local setup

### Requirements

- Python **3.11+**
- A [Supabase](https://supabase.com/) project (free tier)

### Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Streamlit secrets

The app reads credentials from Streamlit secrets (not environment variables).

1. Copy the example file:

   ```bash
   mkdir -p .streamlit
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

2. Set **passcode hashes** (plain passcodes are never stored in the repo). Generate a SHA-256 hex digest:

   ```bash
   python -c "import hashlib; print(hashlib.sha256(b'YOUR_PASSCODE').hexdigest())"
   ```

   Put the Team digest in `team_passcode_hash` and the Admin digest in `admin_passcode_hash`.

3. Set **Supabase** credentials under `[supabase]`:

   - `url` — Project URL from Supabase → Settings → API
   - `key` — `anon` key for local dev (or service role if you prefer; keep it out of git)

`.streamlit/secrets.toml` is gitignored. Do not commit real secrets.

### Database schema

Apply the migration in your Supabase SQL editor (or via the CLI):

- File: [`supabase/migrations/001_songs.sql`](supabase/migrations/001_songs.sql)

This creates the `songs` table described in PRD §3.1. Later tickets may add columns or related tables.

For marker alias persistence (import preview), also apply:

- File: [`supabase/migrations/002_marker_aliases.sql`](supabase/migrations/002_marker_aliases.sql)

For the editable flow template (Settings tab), also apply:

- File: [`supabase/migrations/003_settings.sql`](supabase/migrations/003_settings.sql)

### Run the app

```bash
streamlit run app.py
```

On first load you see only the passcode prompt. Team passcode unlocks **Препоръка** and **Библиотека**; Admin passcode also unlocks **Импорт** and **Настройки**. Use **Изход** to return to the passcode screen.

### Tests

```bash
pytest
```

Passcode verification and role resolution are covered in `tests/test_auth.py`. The lyric parser (Worship Tools `v1` / `Verse 1`, ProPresenter `slide1`, chord and `{comment}` stripping, unknown-marker detection, and saved marker aliases) and title normalization have fixture tests in `tests/test_parser.py` and `tests/test_songs.py`.

## Production deployment checklist

Issue **02** — complete these steps on your accounts. The repo includes [`.github/workflows/supabase-keepalive.yml`](.github/workflows/supabase-keepalive.yml) and [`scripts/supabase_keepalive.py`](scripts/supabase_keepalive.py); you wire up the cloud services and secrets.

### 1. Supabase (production)

1. Create a Supabase project (or designate your existing production project).
2. In the SQL editor, run [`supabase/migrations/001_songs.sql`](supabase/migrations/001_songs.sql).
3. Note **Project URL** and the **anon** key (for the Streamlit app). For GitHub keep-alive, prefer the **service role** key so the scheduled query is not blocked by future RLS policies.

### 2. Streamlit Community Cloud

1. Push this repository to GitHub (if not already).
2. Open [Streamlit Community Cloud](https://share.streamlit.io/) → **Create app** → connect the repo.
3. Set **Main file path** to `app.py` and Python **3.11**.
4. Under **Advanced settings → Secrets**, paste TOML matching [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example):

   - `team_passcode_hash` / `admin_passcode_hash` — SHA-256 hex digests of your production passcodes (same generator as local setup).
   - `[supabase]` — production `url` and `key` (anon key is typical for the app).
   - `[openai]` — see step 3 below.

5. Deploy and open the public URL. Confirm the passcode gate, then **Библиотека** shows a song count (e.g. `0 songs` on an empty table).

### 3. OpenAI (for later tickets)

1. In the [OpenAI dashboard](https://platform.openai.com/), create an API key for this app.
2. Set a **hard monthly spend limit** (PRD suggests e.g. **$5**).
3. Add the key to Streamlit Cloud secrets under `[openai]` → `api_key`. The walking skeleton does not call OpenAI yet; this avoids redeploying when LLM features land.

### 4. GitHub Actions keep-alive

1. In the GitHub repo → **Settings → Secrets and variables → Actions**, add:

   | Secret | Value |
   |--------|--------|
   | `SUPABASE_URL` | Production project URL |
   | `SUPABASE_KEY` | Service role key (recommended) or anon key if reads are allowed |

2. Push the workflow to the default branch so Actions can run it.
3. **Actions → Supabase keep-alive → Run workflow** (manual). The job should print `keepalive ok: songs count=…`.
4. In Supabase → **Logs** (or API logs), confirm a `GET`/`HEAD` against `songs` around that time.

The workflow also runs on a cron schedule (~every three days) so the free-tier project is not paused for inactivity.
