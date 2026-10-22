# Free local OCR with PaddleOCR

GradeKade adds OCR_PROVIDER=paddle using FormulaRecognition with PP-FormulaNet-S and device=cpu. Mock and Mathpix remain available. No OCR API key is needed. This is a benchmark integration, not a production accuracy claim.

## Install and enable

Use **CPython 3.12, 64-bit**, for the documented path. GradeKade supports Python 3.12–3.13; the separate Paddle runtime pins PaddlePaddle 3.3.1, PaddleOCR 3.7.0 and PaddleX 3.7.2. Paddle publishes CPU wheels for Linux x86_64, Windows x86_64 and macOS Apple Silicon. Other architectures/Intel Mac configurations need a supported upstream wheel or separate validation. No CUDA/GPU dependency is requested.

From the repository root:

~~~bash
cd backend
uv venv --python 3.12 .venv-paddle
uv pip install --python .venv-paddle/bin/python -r requirements-paddle.txt
.venv-paddle/bin/python -c "import paddle; paddle.utils.run_check()"
~~~

On Windows use .venv-paddle/Scripts/python.exe, including PADDLE_PYTHON. Keep FastAPI in the normal backend/.venv; do not activate Paddle's environment to run it. Isolation avoids installing PaddleX's pinned opencv-contrib-python 4.10.0.84 over the existing alignment environment's opencv-python-headless, which shares the cv2 namespace.

Reserve at least **3 GB free** for wheels, extracted dependencies, weights and temporary downloads. The upstream model storage listing is about **224 MB**, not the total environment or RAM requirement. Internet is needed to install packages and initially download the public model; first initialization may take minutes. Artifacts default to backend/data/paddle-cache, ignored by Git.

For offline use, download once, then set PADDLE_MODEL_DIR to the complete PP-FormulaNet-S inference directory, typically data/paddle-cache/official_models/PP-FormulaNet-S. GradeKade disables the model-source connectivity probe. Verify offline operation with networking disabled on the target machine; complete compatible model/config/tokenizer files must already exist. Local inference sends no worksheet crops to an OCR API. This reduces third-party transmission without establishing legal compliance.

Add to backend/.env, preserving database settings:

~~~dotenv
OCR_PROVIDER=paddle
PADDLE_PYTHON=.venv-paddle/bin/python
PADDLE_MODEL_NAME=PP-FormulaNet-S
OCR_VARIANTS=color
~~~

Restart FastAPI from backend/. Startup initializes the persistent CPU worker, reused across crops. The banner shows **REAL OCR · PaddleOCR**. Failed initialization keeps Paddle selected with an explicit UNAVAILABLE diagnostic; it never silently switches to mock. Human review stays available.

Switch back with OCR_PROVIDER=mock, or OCR_PROVIDER=mathpix plus its existing credentials, and restart. Dependencies are optional and normal CI does not install them.

## First download / single-crop smoke test

~~~bash
cd backend
uv run python -m app.evaluation.paddle_smoke_test ../evaluation/images/answer-01.png --answer-type integer
uv run python -m app.evaluation.paddle_smoke_test /absolute/path/fraction.png --answer-type fraction --variants color,grayscale,contrast
~~~

Use an answer crop, not a full worksheet. JSON includes raw LaTeX, normalized candidate, null provider confidence, structured math, initialization time, per-variant inference time, request time and errors. It exits nonzero on initialization/inference failure. Expressions and unsupported/ambiguous math remain unnormalized for review.

PADDLE_CPU_THREADS defaults to 2. PADDLE_INITIALIZATION_TIMEOUT_SECONDS=180 bounds startup waiting; raise it deliberately for a slow first download. PADDLE_INFERENCE_TIMEOUT_SECONDS=20 bounds each crop. A timed-out/exited worker is stopped so a late response cannot attach to the next crop. Repair installation/model files, then restart the backend after fatal failure. The existing 110-second page OCR loop budget remains; later crops enter review when exhausted. Processing remains synchronous.

## Confidence / experimental automation

The supported FormulaRecognition output contains rec_formula, **no answer-level probability**. GradeKade preserves provider_confidence=null. By default Paddle supplies suggestions and all answers require review.

For an explicit benchmark of agreement-based automation:

~~~dotenv
OCR_VARIANTS=color,grayscale,contrast
PADDLE_ALLOW_EXPERIMENTAL_AUTO_GRADE=true
PADDLE_MIN_AGREEING_VARIANTS=3
~~~

The agreement rule score is min(agreeing_variant_count / required_variant_count, 1), provided every attempted result parses to the same numeric answer; disagreement scores zero. A minimum of two/three distinct configured variants is enforced even when numeric grading thresholds are lowered. Three is the default. Blank crops, failed/invalid outputs, poor alignment, template policy and disagreement still prevent automation.

A score of 1.0 means rule completion, **not 100% correctness probability**. The strategy and experimental flag are stored separately from null provider confidence. Color/grayscale/contrast are highly correlated, especially because the model also preprocesses inputs. Agreement can repeat the same mistake. No statistically calibrated reliability or production eligibility is established.

## Evaluation and timing

Every answer records OCR wall time, sum of observed per-variant inference time and attempted variant count. Inference includes crop decoding, preprocessing, prediction and response extraction, not just kernel execution. Page metadata includes total OCR time/average per answer, observed inference total/average per timed answer, and its denominator. Missing observations mean N/A.

Export annotated real handwriting from /evaluation and unzip privately. Compare both providers on the **same original dataset**, answer types and preprocessing:

~~~bash
cd backend
uv run python -m app.evaluation.run --dataset /absolute/private/dataset --provider paddle --variants color --output ../work/paddle-color --json
# Later, with Mathpix credentials:
uv run python -m app.evaluation.run --dataset /absolute/private/dataset --provider mathpix --variants color --output ../work/mathpix-color --json
# Replay frozen observations without loading either model:
uv run python -m app.evaluation.run --dataset ../work/paddle-color --provider recorded --require-real --json
~~~

--output stores records.json/report.json without overwriting an experiment. Output directories are snapshot-only; new inference must use the original exported dataset. Providers never receive the answer key. --require-real accepts real-handwriting records from Paddle or Mathpix and rejects fixture/mock-only data. Reports show provider/source cohorts, sample sizes, missing truth, OCR accuracy, auto precision/coverage, review rate, false grades, failures and mean observed inference time. Crop-only data without known registration cannot auto-grade.

## Verification and next experiment

Normal CI uses mocked results and a tiny fake paddleocr package to exercise the actual CPU worker protocol and persistent parent lifecycle without model downloads. Tests cover initialization, reuse, integer/fraction/LaTeX parsing, blank/invalid output, type mismatch, failures/timeouts, disagreement, opt-in automation, timing, whole-page processing and evaluation filtering.

**Local CPU installation was verified on Apple Silicon with Python 3.12 on October 22, 2026.** PaddlePaddle's CPU self-check and dependency compatibility check passed. The GradeKade worker loaded PP-FormulaNet-S and recognized the existing printed synthetic crops 42, 1.5 and 1/2. The three-crop persistent-worker run observed about 0.19, 0.09 and 0.09 seconds respectively; an earlier single-crop run observed 0.61 seconds. These tiny printed-crop observations are not a handwriting benchmark or a full-page latency estimate. The environment occupies about 1 GB and the cached model about 227 MB. **Real handwriting accuracy and photographed-page performance remain unmeasured.**

Next: smoke-test integer/decimal/fraction handwriting from five adults, and process one photographed page end-to-end. Start with automation off; independently label every answer. Compare color vs three variants for accuracy/latency before testing experimental automation on held-out handwriting. Watch for repeated wrong digits, faint decimal points/minus signs, fraction layout errors, erasures/cross-outs, hallucinated blank content, alignment failures and page-budget exhaustion.

Sources: [formula API/model size](https://www.paddleocr.ai/main/en/version3.x/module_usage/formula_recognition.html), [CPU platform wheels](https://www.paddlepaddle.org.cn/documentation/docs/en/install/Tables.html), [pinned FormulaRecognition wrapper](https://github.com/PaddlePaddle/PaddleOCR/blob/v3.7.0/paddleocr/_models/formula_recognition.py), [result fields](https://github.com/PaddlePaddle/PaddleX/blob/release/3.7/paddlex/inference/models/formula_recognition/predictor.py).


## Runtime isolation and troubleshooting

Keep PADDLE_PYTHON pointed at the virtual environment executable, including when it is a symlink. Resolving it to the base Python executable discards the virtual environment. The worker launches with Python's -P option so the adjacent GradeKade adapter paddle.py cannot shadow the installed Paddle package. Regression tests cover both cases without installing models in CI.

For a completed local download, point PADDLE_MODEL_DIR at data/paddle-cache/official_models/PP-FormulaNet-S and restart FastAPI. Run the smoke command again if the first download ends with an initialization error; verify cache completeness before trusting a partial download. The backend must return ocr_provider=paddle and ocr_available=true from /health, with experimental_auto_grade=false for the initial handwriting experiment.

The local .env, runtime, model files and smoke reports stay out of Git. With Paddle enabled in .env, run ordinary automated checks with OCR_PROVIDER=mock so tests and fixture evaluation remain independent of the model installation.
