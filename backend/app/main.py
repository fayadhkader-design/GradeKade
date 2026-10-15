import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.booklets import router as booklet_router
from app.api.evaluation import router as evaluation_router
from app.api.routes import ensure_demo_identity, router
from app.config import settings
from app.db import SessionLocal
from app.services.ocr import get_provider


@asynccontextmanager
async def lifespan(app):
    with SessionLocal() as db:
        ensure_demo_identity(db)
    provider = get_provider(settings)
    if provider.name == "paddle" and not provider.initialize():
        logging.getLogger(__name__).warning(provider.diagnostic)
    yield
    if provider.name == "paddle":
        provider.close()


app = FastAPI(title="GradeKade", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def upload_limit(request: Request, call_next):
    try:
        length = int(request.headers.get("content-length", "0"))
    except ValueError:
        return JSONResponse({"detail": "Invalid content length"}, status_code=400)
    if length > settings.max_upload_bytes + 65536:
        return JSONResponse({"detail": "Request exceeds the upload limit"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(router)

app.include_router(booklet_router)

app.include_router(evaluation_router)
