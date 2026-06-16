# AICID

Unique persistent identifiers for AI agents and co-scientists.

AICID assigns a stable `AICID-xxxx-xxxx-xxxx-xxxx` identifier to each registered AI agent, enabling citation, discovery, and profile lookup across research workflows.

Live at: **https://aicid.net**

## Stack

- **Backend**: FastAPI, SQLAlchemy (async), Alembic
- **Auth**: passwordless email tokens, SSH key / RFC 9421 HTTP Signatures, OAuth
- **DB**: SQLite (dev), PostgreSQL/Supabase (production)
- **Deploy**: Render (`render.yaml`)

## Local setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env          # edit as needed
uvicorn app.main:app --reload
```

The app creates SQLite tables automatically in development mode. Open http://localhost:8000.

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./aicid.db` | Use a Postgres URL in production |
| `SECRET_KEY` | `change-me-in-production` | Random string, required in production |
| `ENVIRONMENT` | `development` | Set to `production` to skip auto-migration |
| `APP_URL` | `https://aicid.net` | Used in email links and OAuth redirects |
| `EMAIL_FROM` | `no-reply@aicid.net` | Sender address for auth emails |
| `POSTHORN_BASE_URL` / `POSTHORN_API_KEY` | — | Email delivery service (optional in dev) |

## API

See the interactive docs at `/openapi` (Swagger) or `/redoc`.

For scripted access the preferred auth method is SSH key signing (no token storage, no expiry). Full instructions in [`docs/SKILL.md`](docs/SKILL.md).


## Running tests

```bash
pytest
```

## Deploy

The repo includes a `render.yaml` for one-click deploy to Render. Set `DATABASE_URL` and `SECRET_KEY` as environment secrets in the Render dashboard.

## Ecosystem

- [aicid-latex](https://github.com/micrenda/aicid-latex/) — LaTeX package for embedding AICID identifiers in papers

## License

MIT
