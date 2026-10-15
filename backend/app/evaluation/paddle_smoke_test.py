"""Run one local answer crop through Paddle; no API keys or answer key involved."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from app.config import settings
from app.services.cropping import prepare_variants
from app.services.ingestion import ingest, png_bytes
from app.services.ocr import get_provider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--answer-type", choices=["integer", "decimal", "fraction"], default="integer")
    parser.add_argument("--variants", default=settings.ocr_variants)
    args = parser.parse_args()
    variants = list(dict.fromkeys(v.strip() for v in args.variants.split(",")))
    if not variants or any(v not in {"color", "grayscale", "contrast"} for v in variants):
        parser.error("variants must be color,grayscale,contrast or a subset")
    try:
        if args.image.stat().st_size > settings.max_upload_bytes:
            raise ValueError("Crop exceeds upload size limit")
        image = ingest(args.image.read_bytes(), settings.max_image_pixels, min_dimension=4)
        prepared = prepare_variants(image, 0, 0, 1, 1, padding=0)
    except (OSError, ValueError):
        parser.error("Provide a readable PNG/JPG answer crop (4px minimum; upload limits apply)")
    provider = get_provider(settings.model_copy(update={"ocr_provider": "paddle"}))
    started = perf_counter()
    try:
        ready = provider.initialize()
        results = {}
        if ready:
            results = {
                v: asdict(provider.recognize_answer(png_bytes(prepared[v]), args.answer_type))
                for v in variants
            }
        print(
            json.dumps(
                {
                    "provider": "paddle",
                    "model": settings.paddle_model_name,
                    "device": "cpu",
                    "available": ready,
                    "diagnostic": provider.diagnostic,
                    "initialization_seconds": provider.initialization_seconds,
                    "total_seconds": perf_counter() - started,
                    "variants_run": len(results),
                    "results": results,
                    "note": "Confidence is unavailable; variant agreement is not calibrated accuracy.",
                },
                indent=2,
            )
        )
        return 0 if ready and not any(r["error"] for r in results.values()) else 1
    finally:
        provider.close()


if __name__ == "__main__":
    raise SystemExit(main())
