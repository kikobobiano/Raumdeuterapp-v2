from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.duckdb_pool import duckdb_session
from app.routers import (
    bar,
    bar_ranking,
    heatmap,
    meta,
    players,
    potential,
    profile,
    progression,
    rankings,
    replacement,
    scatter,
    screener,
    team_minutes,
    team_squad_value,
    teams,
    translation,
)
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    with duckdb_session():
        pass  # eager init: register parquet views before accepting traffic
    yield


app = FastAPI(title="Raumdeuter API", version="0.0.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(players.router)
app.include_router(profile.router)
app.include_router(scatter.router)
app.include_router(screener.router)
app.include_router(progression.router)
app.include_router(replacement.router)
app.include_router(rankings.router)
app.include_router(bar.router)
app.include_router(bar_ranking.router)
app.include_router(translation.router)
app.include_router(teams.router)
app.include_router(team_minutes.router)
app.include_router(team_squad_value.router)
app.include_router(potential.router)
app.include_router(heatmap.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
