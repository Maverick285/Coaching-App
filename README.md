# Buddy

Personal AI companion. Markdown-based memory, calibrated persona, two-tier LLM routing, nightly consolidation with auto-apply / require-review tiering.

- **Phase 0** (backend, this repo's `src/buddy`) — FastAPI + SQLite + sqlite-vec + APScheduler + Anthropic. CLI-accessible.
- **Phase 1** (Android client, `android/`) — Kotlin + Jetpack Compose. Chat, voice input, settings.

See [`android/README.md`](android/README.md) for the phone client.

## What works in Phase 0

- FastAPI service with bearer-token auth (16 endpoints).
- Memory lives in a git-versioned directory of plain Markdown files. The user can read, edit, and clone everything.
- SQLite index over the memory directory with **BM25** (FTS5) + **vector** (sqlite-vec) hybrid retrieval, fused with reciprocal rank.
- Two-tier model routing (`FAST` / `REASONING`) resolved by tier, not by version string. Latest models live in `src/buddy/llm/model_registry.json`; pin via env if you need stability.
- Persona calibration intake (10 questions → reasoning-tier synthesis → `PERSONA.md` + `MEMORY.md`).
- `/converse` endpoint that loads always-loaded files, today + yesterday day files, retrieved chunks, and active patterns into the persona system prompt.
- Nightly consolidation pass that reads the day's conversations and proposes memory updates with **auto-apply / require-review tiering**.
- `DREAMS.md` mirror file plus a DB-backed proposal queue, both reviewable from the CLI.
- Monthly budget envelope: `$50` soft (alert), `$100` hard (503).
- `buddy` CLI for chat, intake, memory edit, search, dreams review, usage, history, clone instructions.

## Quick start (local dev)

```bash
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY, OPENAI_API_KEY, BUDDY_AUTH_TOKEN.

python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,cli]"

# Bring schema up to current.
alembic upgrade head

# Run the backend.
uvicorn buddy.main:app --reload

# In another shell, point the CLI at the local backend.
export BUDDY_BACKEND_URL=http://localhost:8000
export BUDDY_AUTH_TOKEN="<value from .env>"

buddy intake          # run the persona calibration
buddy chat            # talk to it
buddy memory list     # see what it knows
buddy dreams          # process pending memory proposals
buddy usage           # check API spend
```

## Production deploy (Hetzner CX22)

```bash
docker compose up -d --build
```

The `Caddyfile` will automatically issue Let's Encrypt TLS for `${BUDDY_PUBLIC_HOST}`. Memory + DB live on the `buddy_data` volume; nightly the consolidation pass writes to `MEMORY.md` / `PATTERNS.md` / `DREAMS.md`, then a backup push fires to `BUDDY_GIT_REMOTE` if configured.

## Endpoint summary

| Method | Path                          | Purpose |
|--------|-------------------------------|---------|
| GET    | `/health`                     | Liveness + resolved models |
| POST   | `/intake/start`               | Begin persona calibration |
| POST   | `/intake/turn`                | Submit answer, get next question |
| POST   | `/intake/finalize`            | Synthesize PERSONA.md + MEMORY.md |
| POST   | `/converse`                   | Send a message, get a response |
| GET    | `/memory/files`               | List all memory files |
| GET    | `/memory/file/{path}`         | Read a memory file |
| PUT    | `/memory/file/{path}`         | Replace a memory file |
| POST   | `/memory/search`              | Hybrid search over memory |
| GET    | `/memory/dreams`              | View proposals + recent auto-applied |
| POST   | `/memory/dreams`              | Approve / reject / edit a proposal |
| POST   | `/memory/explain`             | What memory was used for this response? |
| GET    | `/memory/clone-instructions`  | How to clone the memory repo locally |
| GET    | `/conversations`              | List recent sessions |
| GET    | `/conversations/{session_id}` | Full session history |
| GET    | `/usage`                      | API usage and cost |

## Layout

```
buddy/
├── src/buddy/
│   ├── api/        — FastAPI routers
│   ├── llm/        — model resolver + Anthropic/OpenAI clients + prompts
│   ├── memory/     — markdown store, indexer, search, retrieval, consolidation, dreams
│   ├── services/   — budget enforcement
│   ├── auth.py     — bearer-token dep
│   ├── config.py   — pydantic-settings
│   ├── db.py       — SQLAlchemy async + sqlite-vec loader
│   ├── main.py     — FastAPI app entrypoint with lifespan
│   ├── models.py   — ORM models
│   ├── schemas.py  — Pydantic request/response models
│   └── scheduler.py
└── cli/buddy_cli/  — terminal client
```

## Acceptance criteria

See `Phase 0 Specification §14`. Tracked in repo under the `claude/initial-setup-18KJY` branch.
