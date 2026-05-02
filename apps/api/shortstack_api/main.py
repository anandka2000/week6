from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import costs, metrics, niches, trends, videos

app = FastAPI(title="ShortStack API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(niches.router)
app.include_router(trends.router)
app.include_router(videos.router)
app.include_router(costs.router)
app.include_router(metrics.router)
