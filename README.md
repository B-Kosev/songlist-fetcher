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

### Run the app

```bash
streamlit run app.py
```

On first load you see only the passcode prompt. Team passcode unlocks **Препоръка** and **Библиотека**; Admin passcode also unlocks **Импорт** and **Настройки**. Use **Изход** to return to the passcode screen.

### Tests

```bash
pytest
```

Passcode verification and role resolution are covered in `tests/test_auth.py`.
