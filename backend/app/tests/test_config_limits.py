import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize(
    "values",
    [
        {"max_upload_bytes": 0},
        {"max_upload_bytes": -1},
        {"max_image_pixels": 0},
        {"max_image_pixels": 9999},
        {"photo_blur_minimum": float("inf")},
        {"photo_blur_minimum": float("nan")},
        {"photo_blur_minimum": -1},
    ],
)
def test_invalid_resource_limits_fail_at_configuration(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_minimum_supported_limits_and_disabled_blur_gate():
    config = Settings(_env_file=None, max_upload_bytes=1, max_image_pixels=10_000, photo_blur_minimum=0)
    assert config.max_upload_bytes == 1
    assert config.max_image_pixels == 10_000
    assert config.photo_blur_minimum == 0
