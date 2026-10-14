from pathlib import Path
from uuid import UUID
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/gradekade.db"
    storage_root: Path = Path("data/files")
    organization_id: UUID = UUID("00000000-0000-4000-8000-000000000001")
    ocr_provider: str = "mock"
    mathpix_app_id: SecretStr = SecretStr("")
    mathpix_app_key: SecretStr = SecretStr("")
    auto_grade_confidence_threshold: float = Field(default=0.995, ge=0, le=1)
    max_upload_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 20_000_000
    frontend_origin: str = "http://localhost:3000"


settings = Settings()
