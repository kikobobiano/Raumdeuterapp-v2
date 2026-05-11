# Raumdeuter v2 (`Raumdeuterapp-v2`)

Aplicação web de **scout e analytics** sobre estatísticas de jogadores e equipas (dados tipo Wyscout): perfis com radar e áreas de jogo, scatter, rankings, screener, tradução de performance entre ligas, potencial previsto, minutos por equipa e heatmaps tácticos no perfil.

É a evolução da app legacy em Streamlit (**raumdeuterapp**): mesma linha de produto com stack moderna orientada à performance e tipagem partilhada entre API e front-end.

## Stack

| Camada | Tecnologia |
|--------|------------|
| Front-end | [Next.js](https://nextjs.org/) 16 (App Router), React 19, TypeScript 5, Tailwind CSS 4, TanStack Query 5, Zustand |
| Visualização | Plotly (`react-plotly.js`), SVG (`d3-contour` nos contornos do heatmap) |
| API | [FastAPI](https://fastapi.tiangolo.com/), Pydantic v2, DuckDB sobre ficheiros Parquet |
| Dados analytics | pandas, numpy, scipy, scikit-learn (ex.: similarity / potencial onde aplicável) |
| Tooling monorepo | [pnpm](https://pnpm.io/) workspaces + [uv](https://docs.astral.sh/uv/) (Python 3.12) |
| Contrato API ↔ TS | OpenAPI gerado pela FastAPI → tipos em `packages/shared-types` (`openapi-typescript`) |

## Layout do repositório

```
apps/web                 # Next.js (UI)
apps/api                 # FastAPI + domínio em app/core/, routers HTTP finos
packages/shared-types    # openapi.json + api.d.ts gerados
docker-compose.yml       # API + web com volumes (data read-only na API)
```

Os **Parquets de jogadores e equipas** não vêm no Git: espera-se um directório `data/` (por exemplo symlink para o repositório legacy onde já geraste os dados) ou `RAUMDEUTER_DATA_DIR` apontando para esses ficheiros.

## Pré-requisitos

- **Node.js** compatível com o `package.json` (recomendado: LTS atual) e **pnpm** (versão definida em `package.json` → campo `packageManager`).
- **Python 3.12+** e **uv** para dependências da API (`apps/api`).
- Pasta **`data/`** válida para a API arrancar (views DuckDB registadas no startup).

## Instalação

Na raiz do monorepo:

```bash
pnpm install
```

API:

```bash
cd apps/api
uv sync
```

Variáveis úteis (ver `apps/api/app/settings.py`):

- `RAUMDEUTER_DATA_DIR` — caminho absoluto para a pasta `data` (Parquets). Em Docker usa-se `/data`.
- `RAUMDEUTER_CORS_ORIGINS` — JSON array de origins permitidas (ex.: `["http://localhost:3000"]`).

Copia `.env` apenas localmente (`/.env*` está no `.gitignore`); não comites secrets.

## Correr em desenvolvimento

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

Por omissão: front em `http://localhost:3000`, API em `http://localhost:8000`. Garante que `NEXT_PUBLIC_API_URL` na web aponta para a API que estás a correr.

## Docker

Na raiz:

```bash
docker compose up --build
```

A API monta `./data:/data:ro`. Sem `data/` local preenchido, os endpoints que leem DuckDB falham até existirem os Parquets esperados.

## Testes e qualidade

```bash
# API
cd apps/api && uv run pytest -q

# Web — types
cd apps/web && pnpm exec tsc --noEmit

# Web — lint
cd apps/web && pnpm lint
```

Depois de alterares schemas Pydantic na API, regera OpenAPI e os tipos TS (ver `AGENTS.md` na raiz para o comando exacto com `openapi-typescript`).

## Documentação para contribuir

O ficheiro **`AGENTS.md`** descreve convenções de arquitectura (limites `core/` vs `routers/`, segurança SQL, limites de `LIMIT`, Plotly dinâmico, etc.). Lê esse ficheiro antes de alterações grandes.

## Licença e dados

Este repositório contém **código** da aplicação. Os **dados Wyscout ou derivados** mantêm-se fora do Git; cada utilizador/fornecedor deve respeitar os termos da fonte dos dados.

---

*Nome do repositório no GitHub: **Raumdeuterapp-v2**.*
