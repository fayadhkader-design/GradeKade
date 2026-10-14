from io import BytesIO
import warnings
import pymupdf as fitz
from PIL import Image, ImageOps, UnidentifiedImageError


def png_bytes(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def ingest(content: bytes, max_pixels: int = 20_000_000) -> Image.Image:
    """Decode actual file contents, not filename or caller-supplied MIME."""
    if not content:
        raise ValueError("Choose a nonempty JPG, PNG, or PDF file")
    try:
        if content.startswith(b"%PDF-"):
            with fitz.open(stream=content, filetype="pdf") as document:
                if document.is_encrypted or document.page_count < 1:
                    raise ValueError("PDF must have an accessible first page")
                page = document[0]
                if page.rect.width <= 0 or page.rect.height <= 0:
                    raise ValueError("Invalid PDF page dimensions")
                scale = min(2, (max_pixels / (page.rect.width * page.rect.height)) ** .5)
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as source:
                    if source.format not in {"JPEG", "PNG"}:
                        raise ValueError("Only JPG, PNG, and PDF are supported")
                    if source.width * source.height > max_pixels:
                        raise ValueError("Image exceeds the pixel limit")
                    source.load()
                    image = ImageOps.exif_transpose(source).convert("RGB")
        if image.width * image.height > max_pixels or min(image.size) < 100:
            raise ValueError("Page must be at least 100px on each side and within the pixel limit")
        return image
    except (UnidentifiedImageError, OSError, RuntimeError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise ValueError("File could not be decoded as a safe JPG, PNG, or PDF") from None
