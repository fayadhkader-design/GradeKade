import sys
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/gradekade.db"
    storage_root: Path = Path("data/files")
    organization_id: UUID = UUID("00000000-0000-4000-8000-000000000001")
    ocr_provider: Literal["mock", "mathpix", "paddle"] = "mock"
    paddle_python: Path = Path(
        ".venv-paddle/Scripts/python.exe" if sys.platform == "win32" else ".venv-paddle/bin/python"
    )
    paddle_model_name: str = "PP-FormulaNet-S"
    paddle_model_dir: Path | None = None
    paddle_cache_root: Path = Path("data/paddle-cache")
    paddle_cpu_threads: int = Field(default=2, ge=1, le=16)
    paddle_initialization_timeout_seconds: float = Field(default=180, gt=0, le=900)
    paddle_inference_timeout_seconds: float = Field(default=20, gt=0, le=120)
    paddle_allow_experimental_auto_grade: bool = False
    paddle_min_agreeing_variants: int = Field(default=3, ge=2, le=3)
    mathpix_app_id: SecretStr = SecretStr("")
    mathpix_app_key: SecretStr = SecretStr("")
    auto_grade_confidence_threshold: float = Field(default=0.995, ge=0, le=1)
    auto_reject_confidence_threshold: float = Field(default=0.999, ge=0, le=1)
    alignment_minimum_confidence: float = Field(default=0.8, ge=0, le=1)
    crop_padding_pixels: int = Field(default=6, ge=0, le=40)
    ocr_variants: str = "color"
    ocr_timeout_seconds: float = Field(default=8, gt=0, le=25)
    ocr_retries: int = Field(default=1, ge=0, le=2)
    photo_blur_minimum: float = Field(default=3, ge=0)
    max_upload_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 20_000_000
    frontend_origin: str = "http://localhost:3000"


settings = Settings()
