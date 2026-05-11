# Raumdeuter v2 (`Raumdeuterapp-v2`)

A web app for **football scouting and analytics** on player and team statistics (Wyscout-style data): profiles with radar and game-area views, scatter, rankings, screener, cross-league performance translation, potential estimates, team minutes, and tactical heatmaps on the player profile.

This is the successor to the legacy Streamlit app (**raumdeuterapp**): the same product direction with a performance-oriented stack and shared typing between the API and the front end.

## Stack

| Layer | Technology |
|--------|------------|
| Front end | [Next.js](https://nextjs.org/) 16 (App Router), React 19, TypeScript 5, Tailwind CSS 4, TanStack Query 5, Zustand |
| Visualization | Plotly (`react-plotly.js`), SVG (`d3-contour` for heatmap contours) |
| API | [FastAPI](https://fastapi.tiangolo.com/), Pydantic v2, DuckDB over Parquet files |
| Analytics | pandas, numpy, scipy, scikit-learn (e.g. similarity / potential where applicable) |
| Monorepo tooling | [pnpm](https://pnpm.io/) workspaces + [uv](https://docs.astral.sh/uv/) (Python 3.12) |
| API ↔ TS contract | FastAPI OpenAPI → types in `packages/shared-types` (`openapi-typescript`) |

## Repository layout

```
apps/web                 # Next.js (UI)
apps/api                 # FastAPI + domain in app/core/, thin HTTP routers
packages/shared-types    # Generated openapi.json + api.d.ts
docker-compose.yml       # API + web with volumes (API data read-only mount)
```

Player and team **Parquet files are not in Git**: provide a `data/` directory (often a symlink to the legacy repo where the data is produced) or set `RAUMDEUTER_DATA_DIR` to that path.

## Prerequisites

- **Node.js** compatible with the root `package.json` (recommended: current LTS) and **pnpm** (version pinned via the `packageManager` field).
- **Python 3.12+** and **uv** for the API (`apps/api`).
- A valid **`data/`** layout so the API can start (DuckDB views registered at startup).

## Install

From the monorepo root:

```bash
pnpm install
```

API:

```bash
cd apps/api
uv sync
```

Useful environment variables (see `apps/api/app/settings.py`):

- `RAUMDEUTER_DATA_DIR` — absolute path to the `data` directory (Parquet files). Uses `/data` in Docker.
- `RAUMDEUTER_CORS_ORIGINS` — JSON array of allowed origins (e.g. `["http://localhost:3000"]`).

Keep `.env` files local only (`*.env*` is `.gitignored`); do not commit secrets.

## Development

**Terminal 1 — API**

```bash
cd apps/api
uv run uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Web**

```bash
cd apps/web
pnpm dev
```

Defaults: front end at `http://localhost:3000`, API at `http://localhost:8000`. Ensure `NEXT_PUBLIC_API_URL` in the web app points at the API you run.

## Docker

From the repo root:

```bash
docker compose up --build
```

The API mounts `./data:/data:ro`. Without a populated local `data/`, DuckDB-backed endpoints fail until the expected Parquet files exist.

## Tests and quality

```bash
# API
cd apps/api && uv run pytest -q

# Web — types
cd apps/web && pnpm exec tsc --noEmit

# Web — lint
cd apps/web && pnpm lint
```

After changing Pydantic schemas in the API, regenerate OpenAPI and the TypeScript types (exact command with `openapi-typescript` is documented in **`AGENTS.md`** at the repo root).

## Contributing

**`AGENTS.md`** describes architecture conventions (`core/` vs `routers/`, SQL safety, response `LIMIT`s, dynamic Plotly imports, etc.). Read it before large changes.

## License and data

This repository ships **application code** only. **Wyscout-derived or vendor data** stays out of Git; comply with your data provider’s terms.

---

GitHub repository: **[Raumdeuterapp-v2](https://github.com/kikobobiano/Raumdeuterapp-v2)**.
