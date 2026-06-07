from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.routes import router as api_v1_router
from .settings import get_settings

settings = get_settings()
settings.jobs_root.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Visionary Task Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors.allow_origins),
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=list(settings.cors.allow_methods),
    allow_headers=list(settings.cors.allow_headers),
)

app.include_router(api_v1_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
