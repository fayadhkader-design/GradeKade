import asyncio

import pytest
from fastapi import HTTPException
from PIL import Image

from app.api import routes
from app.services.ingestion import png_bytes


class InterruptedUpload:
    closed = False

    async def read(self, size):
        assert size == routes.settings.max_upload_bytes + 1
        raise OSError("Interrupted upload")

    async def close(self):
        self.closed = True


def test_failed_read_still_closes_upload():
    upload = InterruptedUpload()
    with pytest.raises(OSError, match="Interrupted upload"):
        asyncio.run(routes.read_page(upload))
    assert upload.closed


@pytest.mark.parametrize("kind,status", [("valid", None), ("invalid", 422), ("oversized", 413)])
def test_upload_is_closed_on_success_and_validation_rejection(monkeypatch, kind, status):
    monkeypatch.setattr(routes.settings, "max_upload_bytes", 4096)

    class Upload(InterruptedUpload):
        async def read(self, size):
            assert size == 4097
            return {
                "valid": png_bytes(Image.new("RGB", (100, 100), "white")),
                "invalid": b"not an image",
                "oversized": b"x" * 4097,
            }[kind]

    upload = Upload()
    if status:
        with pytest.raises(HTTPException) as error:
            asyncio.run(routes.read_page(upload))
        assert error.value.status_code == status
    else:
        assert asyncio.run(routes.read_page(upload)).size == (100, 100)
    assert upload.closed
