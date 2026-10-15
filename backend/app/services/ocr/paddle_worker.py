"""Isolated CPU runtime. No imports from the main backend environment.

Stdout is a prefixed JSON protocol; third-party progress is suppressed by the parent.
Never print worksheet content except in the explicit response to the local parent.
"""

import argparse
import base64
import json
import os
import sys
from io import BytesIO
from time import perf_counter

PREFIX = "GRADEKADE_PADDLE:"


def send(value):
    sys.stdout.write(PREFIX + json.dumps(value, allow_nan=False) + "\n")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--model-dir")
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--cpu-threads", type=int, required=True)
    args = parser.parse_args()
    os.environ["PADDLE_PDX_CACHE_HOME"] = args.cache_root
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    os.environ.setdefault("HF_HOME", os.path.join(args.cache_root, "huggingface"))
    os.environ.setdefault("MODELSCOPE_CACHE", os.path.join(args.cache_root, "modelscope"))
    started = perf_counter()
    try:
        import numpy as np
        from paddleocr import FormulaRecognition
        from PIL import Image

        options = {
            "model_name": args.model_name,
            "device": "cpu",
            "cpu_threads": args.cpu_threads,
            "enable_mkldnn": False,
        }
        if args.model_dir:
            options["model_dir"] = args.model_dir
        model = FormulaRecognition(**options)
    except Exception:  # noqa: BLE001 -- Isolate arbitrary third-party model failures.
        # Native initialization/import failures must not disclose paths or credentials.
        send(
            {
                "error": "paddle_initialization_failed",
                "diagnostic": "Paddle could not initialize. Install backend/requirements-paddle.txt in .venv-paddle; check model files, CPU compatibility, disk space and download connectivity.",
            }
        )
        return 1
    send({"ready": True, "initialization_seconds": perf_counter() - started})
    for line in sys.stdin:
        started = perf_counter()
        try:
            payload = json.loads(line)
            image = Image.open(BytesIO(base64.b64decode(payload["image"], validate=True))).convert("RGB")
            # PaddleX ndarray inputs follow OpenCV BGR conventions; paths are not needed.
            bgr = np.asarray(image)[:, :, ::-1].copy()
            outputs = iter(model.predict(input=bgr, batch_size=1))
            first = next(outputs, None)
            if first is None or next(outputs, None) is not None:
                raise ValueError("Expected one answer-crop result")
            data = first.json
            if isinstance(data, str):
                data = json.loads(data)
            if not isinstance(data, dict):
                raise TypeError("Invalid prediction")
            result = data.get("res", data)
            raw = result.get("rec_formula")
            if not isinstance(raw, str) or len(raw) > 1000:
                raise ValueError("Invalid formula")
            send({"raw_text": raw, "inference_seconds": perf_counter() - started})
        except Exception:  # noqa: BLE001 -- Isolate arbitrary third-party model failures.
            send({"error": "paddle_inference_failed", "inference_seconds": perf_counter() - started})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
