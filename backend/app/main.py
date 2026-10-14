from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.db import SessionLocal
from app.api.routes import router, ensure_demo_identity


@asynccontextmanager
async def lifespan(app):
    with SessionLocal() as db:
        ensure_demo_identity(db)
    yield


app = FastAPI(title="GradeKade", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


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
