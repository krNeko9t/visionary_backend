from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .http.routes_jobs import router as jobs_router
from .settings import get_settings

settings = get_settings()
settings.jobs_root.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Visionary Task Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
