"""Provider-neutral adapter around a persistent, isolated local CPU predictor."""

import atexit
import base64
import json
import subprocess
from functools import lru_cache
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
from time import perf_counter

from app.services.normalization import normalize_answer
from app.services.ocr import OCRResult

PREFIX = "GRADEKADE_PADDLE:"
INSTALL_DIAGNOSTIC = "Paddle unavailable. Create backend/.venv-paddle with Python 3.12 and install requirements-paddle.txt; see README Free Local OCR."


class PaddleOCRProvider:
    name = "paddle"

    def __init__(
        self,
        python,
        model_name="PP-FormulaNet-S",
        model_dir=None,
        cache_root="data/paddle-cache",
        cpu_threads=2,
        initialization_timeout=180,
        inference_timeout=20,
    ):
        self.python, self.model_name, self.model_dir = python, model_name, model_dir
        self.cache_root, self.cpu_threads = cache_root, cpu_threads
        self.initialization_timeout, self.inference_timeout = initialization_timeout, inference_timeout
        self._lock = Lock()
        self._process = None
        self._messages = Queue()
        self.initialization_seconds = None
        self.diagnostic = None
        self.available = False

    def _reader(self, stream, messages):
        try:
            for line in iter(lambda: stream.readline(65536), ""):
                if line.startswith(PREFIX):
                    try:
                        messages.put(json.loads(line[len(PREFIX) :]))
                    except (ValueError, TypeError):
                        messages.put({"error": "paddle_invalid_response"})
        finally:
            messages.put({"error": "paddle_worker_exited"})

    def _receive(self, timeout):
        try:
            response = self._messages.get(timeout=timeout)
        except Empty:
            return {"error": "paddle_timeout"}
        return response if isinstance(response, dict) else {"error": "paddle_invalid_response"}

    def _stop(self):
        process, self._process = self._process, None
        self.available = False
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()

    def close(self):
        with self._lock:
            self._stop()

    def _initialize(self):
        if self.available and self._process is not None and self._process.poll() is None:
            return True
        if self.diagnostic:  # A failed model is retried explicitly after repairing installation.
            return False
        if not Path(self.python).is_file():
            self.diagnostic = INSTALL_DIAGNOSTIC
            return False
        command = [
            self.python,
            "-u",
            str(Path(__file__).with_name("paddle_worker.py")),
            "--model-name",
            self.model_name,
            "--cache-root",
            self.cache_root,
            "--cpu-threads",
            str(self.cpu_threads),
        ]
        if self.model_dir:
            command.extend(["--model-dir", self.model_dir])
        try:
            self._messages = Queue()
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            Thread(target=self._reader, args=(self._process.stdout, self._messages), daemon=True).start()
            ready = self._receive(self.initialization_timeout)
            if not ready.get("ready"):
                self.diagnostic = ready.get("diagnostic") or (
                    "Paddle initialization timed out or its worker exited. Check installation, model download/cache, CPU support and disk space; run paddle_smoke_test for verification."
                )
                self._stop()
                return False
            self.initialization_seconds = ready.get("initialization_seconds")
            self.available = True
            return True
        except OSError:
            self.diagnostic = INSTALL_DIAGNOSTIC
            self._stop()
            return False

    def initialize(self):
        with self._lock:
            return self._initialize()

    def recognize_answer(self, image, expected_answer_type, optional_context=None):
        started = perf_counter()
        with self._lock:
            if not self._initialize():
                return OCRResult(
                    "",
                    None,
                    error="paddle_initialization_failed",
                    provider_name=self.name,
                    provider_metadata={
                        "diagnostic": self.diagnostic,
                        "request_seconds": perf_counter() - started,
                    },
                )
            try:
                self._process.stdin.write(json.dumps({"image": base64.b64encode(image).decode()}) + "\n")
                self._process.stdin.flush()
                response = self._receive(self.inference_timeout)
            except (OSError, ValueError):
                response = {"error": "paddle_worker_exited"}
            if response.get("error") in {"paddle_timeout", "paddle_worker_exited", "paddle_invalid_response"}:
                self.diagnostic = "Paddle inference timed out or its CPU worker stopped. Restart the backend after checking the local runtime."
                self._stop()  # Never associate a late response with the next crop.
        return self.parse_result(response, expected_answer_type, perf_counter() - started)

    def parse_result(self, response, expected_answer_type, request_seconds=0):
        metadata = {
            "model": self.model_name,
            "device": "cpu",
            "cpu_threads": self.cpu_threads,
            "confidence_available": False,
            "confidence_calibrated": False,
            "request_seconds": request_seconds,
            "initialization_seconds": self.initialization_seconds,
        }
        seconds = response.get("inference_seconds")
        if isinstance(seconds, (int, float)) and seconds >= 0:
            import math

            if math.isfinite(seconds):
                metadata["inference_seconds"] = seconds
        if response.get("error"):
            return OCRResult(
                "",
                None,
                error="paddle_inference_failed",
                provider_metadata={**metadata, "failure_kind": response["error"]},
                provider_name=self.name,
            )
        raw = response.get("raw_text")
        if not isinstance(raw, str) or len(raw) > 1000:
            return OCRResult(
                "", None, error="paddle_invalid_output", provider_metadata=metadata, provider_name=self.name
            )
        try:
            candidate = normalize_answer(raw, expected_answer_type)
        except ValueError:
            candidate = None
        return OCRResult(
            raw,
            None,
            structured_math={"format": "latex", "latex": raw},
            normalized_candidate=candidate,
            provider_metadata=metadata,
            provider_name=self.name,
        )

    def recognize(self, image):
        return self.recognize_answer(image, "fraction")


@lru_cache(maxsize=4)
def cached_paddle_provider(*args):
    provider = PaddleOCRProvider(*args)
    atexit.register(provider.close)
    return provider
