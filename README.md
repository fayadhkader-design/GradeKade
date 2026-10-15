# GradeKade 0.1

An internal, AI-assisted arithmetic worksheet grading MVP. Configure a blank template once, upload a completed paper worksheet, auto-grade eligible answers, and rapidly review exceptions. Humans retain the final decision on uncertain answers.

**Development/demo use only. Do not upload identifiable student educational records until production privacy/security controls are completed.**

## Mobile scanning preview

The local mobile-first milestone is at `/scan`: guided camera capture, persistent drafts, ordered booklet batches, upload retry, phone exception review and observed workflow timings. See the [mobile walkthrough and limitations](docs/mobile-workflow.md). Severe photo-quality checks and an internal handwriting evaluation workspace are now available; live-provider verification awaits credentials and real photographed handwriting.

## What works

- Dashboard: worksheet/answer counts, auto-grade coverage, historical human-review rate, current queue size.
- Template manager: upload PNG/JPG/PDF, draw answer rectangles or enter normalized coordinates, number questions, set integer/decimal/fraction answer keys and per-question auto-grade policy. Used templates are locked.
- Students: minimal first-name/display-identifier and optional external identifier.
- Submission workflow: bounded uploads, first PDF page rendering, gentle grayscale preprocessing for ORB registration, full-resolution alignment and cropping, swappable OCR, exact numeric normalization and deterministic comparison.
- Results: original/aligned page, answer crops, expected/OCR/edited text, system confidence, auto/human decisions, final score after every answer is decided.
- Human review: exception-only queue, **C** correct, **I** incorrect, **E** edit. Shortcuts are suppressed in text inputs. Each decision advances automatically; decisions are blocked until the current crop loads. Original predictions and human overrides are retained.
- Internal /evaluation workspace: independent human transcription/verified grades, full-page/crop/variant inspection, immutable AI outputs, scoped CSV/JSON/PNG ZIP export.
- Evaluation CLI: exact/normalized OCR, decision accuracy, verified auto-grade precision and Wilson interval, coverage/review rate, false automatic grades, OCR/page failures and type/confidence/provider cohorts.
- Original 20-question synthetic worksheet, blank PNG/PDF, completed PNG, answer key and template JSON. No proprietary curriculum imagery or content.

## Correction and regrading workflow

Booklets now track an assignment across correction rounds. After initial grades/reviews are final, incorrect answers appear as corrections remaining. Start a round, capture only affected pages, process only the unresolved answer regions, review exceptions and finalize. Repeat until every question is correct. A graded scan can still have mistakes; the booklet is complete only at 100%.

Results preserve initial accuracy, current completion, round counts and every question's OCR/system/human attempt history. Standalone worksheet results can be attached to a one-page assignment. Failed/unprocessed correction captures can be retaken without deleting earlier captures.

~~~bash
cd backend
uv run alembic upgrade head
# With both local servers running in mock mode:
uv run python ../scripts/demo_corrections.py
~~~

The script creates an explicitly synthetic 17/20 → 19/20 → 20/20 example and prints its local URL. No paid/live OCR is used. See [correction APIs, migration details and exact manual procedure](docs/correction-workflow.md). Original correction sample PNGs are included in sample_data and the /samples allowlist. OCR implementations and thresholds were not changed.

## Repository

```text
frontend/
  src/app/                 Next.js workspace + bounded API proxy
  src/components/          TemplateEditor, ReviewDesk, Results
  src/lib/                 Typed API client and region utilities/tests
  e2e/                     Browser workflow tests
backend/
  app/api/                 Organization-scoped REST endpoints
  app/models.py            SQLAlchemy UUID entities and constraints
  app/schemas.py           Validated API inputs
  app/services/
    ingestion/ alignment/ cropping/ ocr/
    normalization/ grading/ quality/ storage/ pipeline.py
  app/evaluation/          Crop evaluation + recorded-dataset reports
  app/tests/               Unit, API, migration and integration tests
  migrations/              Immutable Alembic schema migration
sample_data/               Original worksheet assets and template
evaluation/               Ground truth, crop images, synthetic predictions
scripts/                   Dev launcher, checks, sample generator
docs/                      Architecture and production privacy gaps
```

## Start locally

Requires **Python 3.12 or 3.13**, **uv**, **Node.js 22+**, and npm. Python 3.14 is not supported by this project's pinned range. Commands below start in the repository root.

### Zero-install database demo

No keys or environment files are required:

```bash
cd backend
uv sync --python 3.12
uv run alembic upgrade head
cd ../frontend
npm ci
cd ..
./scripts/dev.sh
```

Open **http://localhost:3000**. API documentation: **http://127.0.0.1:8000/docs**. The launcher runs both servers on loopback; stop it with Ctrl+C. It preserves local data across restarts. SQLite data lives in `backend/data/`; uploaded pages are private to the local backend's scoped resource routes and are ignored by Git.

### PostgreSQL (primary database)

```bash
docker compose up -d --wait
cp backend/.env.example backend/.env
# This .env selects the local PostgreSQL instance on port 5433.
cd backend
uv sync --python 3.12
uv run alembic upgrade head
cd ../frontend
npm ci
cd ..
./scripts/dev.sh
```

The included database credentials are for a loopback-only local demo. An existing PostgreSQL database can be used through `DATABASE_URL`. Supabase is not required, and no Supabase project has been created. SQLite and PostgreSQL use the same models/migration; PostgreSQL SQL generation and a live PostgreSQL grading/review integration test pass in GitHub CI; the implementation machine uses SQLite because its Docker daemon was unavailable. Concurrent workloads should use PostgreSQL rather than SQLite.

To run the services separately:

```bash
# Terminal 1
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2
cd frontend
npm run dev
```

## Try the workflow

**Fast synthetic demo:** click “Prepare demo”, download the completed sample on the upload screen, choose that file and keep synthetic OCR enabled. The seeded template has 20 answer boxes. Processing yields 15 auto-accepted answers and 5 exceptions (Q2, Q7, Q12, Q15, Q20). Review Q2/Q7/Q15 as correct and Q12/Q20 as incorrect; the result finalizes at **17/20 (85%)**. Q3 is a deliberately incorrect answer that the synthetic provider recognizes confidently.

**Manual template setup:** download `sample_data/blank.png` (also linked in Templates), create a named template, drag boxes around at least ten answer regions, select each box, and enter its correct answer/type from `sample_data/answer_key.csv`. Save the key. Add a fictional student on Upload, select the template, and upload `sample_data/completed.png` or your own generic practice page. Leave synthetic OCR off for arbitrary images. Mock mode routes every answer to review, where the crop and answer key are sufficient to make a decision.

Synthetic mode accepts only the exact supplied blank/completed PNGs. Its transcript is bound to decoded-pixel crop hashes; moving boxes changes the crops and causes unmatched answers to require review. PDF/JPEG transformations do not preserve synthetic hashes. Sample answers are **printed synthetic responses**, not real handwriting. The sample is a workflow fixture, not an OCR benchmark.

## OCR modes

| Mode | Behavior |
| --- | --- |
| `OCR_PROVIDER=mock` (default) | Returns empty text and confidence 0 for arbitrary uploads; no fabricated handwriting recognition. All answers require review. |
| Explicit “Use synthetic OCR” on upload | Uses Decoded-pixel SHA-256-bound observations for the supplied original sample only. Separate from the answer key. Includes wrong, ambiguous and blank responses. |
| `OCR_PROVIDER=mathpix` plus both credentials | Sends answer crops to Mathpix `/v3/text` and uses returned text/confidence. No keys in source or browser. Provider errors route to review. |
| OCR_PROVIDER=paddle | Local PP-FormulaNet-S CPU inference; null provider confidence, review by default, optional experimental variant agreement. |
| Mathpix selected but credentials missing | Falls back to empty mock mode. UI and result metadata show the actual provider. |

The Mathpix adapter follows the [official image OCR API](https://docs.mathpix.com/reference/post-v3-text). Its full-page integration and HTTP contract are tested with simulated provider responses; live paid OCR has **not** been exercised. Requests set metadata.improve_mathpix=false; account-level vendor settings can override this flag. See the [official privacy documentation](https://docs.mathpix.com/concepts/privacy). Enabling it transmits worksheet crops to that vendor; review vendor privacy/retention terms before using real records.

### Configure real OCR later

Create backend/.env without copying the PostgreSQL example if you want to keep the existing SQLite demo:

```dotenv
OCR_PROVIDER=mathpix
MATHPIX_APP_ID=your-app-id
MATHPIX_APP_KEY=your-app-key
```

Restart FastAPI from backend/. The global banner must say **REAL OCR · Mathpix**. Leave synthetic OCR off for photographs. Set OCR_PROVIDER=mock and restart to return to mock mode. Keys stay backend-only and ignored by Git. Missing either key visibly falls back to MOCK; the evaluation CLI refuses that fallback for configured real runs.

## Free Local OCR with PaddleOCR

PP-FormulaNet-S recognizes answer crops locally on CPU, with no paid API key. Install into a separate **Python 3.12** environment to avoid conflicting OpenCV distributions:

~~~bash
cd backend
uv venv --python 3.12 .venv-paddle
uv pip install --python .venv-paddle/bin/python -r requirements-paddle.txt
# First invocation downloads the model:
uv run python -m app.evaluation.paddle_smoke_test ../evaluation/images/answer-01.png --answer-type integer
~~~

Set OCR_PROVIDER=paddle in backend/.env and restart FastAPI from backend/. The UI shows REAL OCR · PaddleOCR, or a visible UNAVAILABLE diagnostic if initialization fails. No API credentials are needed. The normal backend remains in backend/.venv; the local model runs in a persistent isolated CPU process.

Allow at least 3 GB free. Published model storage is about 224 MB; packages and extracted caches need additional space. Internet is required for installation/initial model download. An explicit PADDLE_MODEL_DIR supports cached/offline operation. Windows uses .venv-paddle/Scripts/python.exe. Linux x86_64 and macOS Apple Silicon have upstream CPU wheels; verify the pinned combination on the target platform.

The formula API exposes no answer-level probability: provider confidence stays null and automatic grading is off by default. For a deliberate agreement-based benchmark, set OCR_VARIANTS=color,grayscale,contrast and PADDLE_ALLOW_EXPERIMENTAL_AUTO_GRADE=true (three agreeing variants required by default). The rule score is not calibrated probability. These correlated variants may repeat the same mistake.

CPU inference time/variant count are stored per answer and aggregated per worksheet; no live speed is claimed yet. Installation and model loading were deferred by the user due to disk space. Switch back with OCR_PROVIDER=mock, or OCR_PROVIDER=mathpix plus its credentials, then restart.

~~~bash
uv run python -m app.evaluation.run --dataset /absolute/private/dataset --provider paddle --output ../work/paddle-run --json
uv run python -m app.evaluation.run --dataset ../work/paddle-run --provider recorded --require-real --json
~~~

See [Paddle installation, offline operation, confidence policy and comparison protocol](docs/paddle-ocr.md) for settings, known failure modes and the next handwriting experiment.

## Environment variables

Backend reads `backend/.env` when launched from `backend/`:

| Variable | Default / purpose |
| --- | --- |
| `DATABASE_URL` | `sqlite:///./data/gradekade.db`; `.env.example` selects PostgreSQL. Use `postgresql+psycopg://...` for PostgreSQL. |
| `STORAGE_ROOT` | `data/files`; UUID-named normalized PNGs. |
| `ORGANIZATION_ID` | Fixed local demo organization UUID `00000000-0000-4000-8000-000000000001`. No user-selectable organization header. |
| `OCR_PROVIDER` | `mock`, `mathpix` (credentials), or `paddle` (local CPU environment). |
| `MATHPIX_APP_ID`, `MATHPIX_APP_KEY` | Empty; required only for real Mathpix OCR. |
| `AUTO_GRADE_CONFIDENCE_THRESHOLD` | `0.995`; auto-correct threshold, **not calibrated accuracy**. |
| `AUTO_REJECT_CONFIDENCE_THRESHOLD` | `0.999`; auto-incorrect threshold. |
| `ALIGNMENT_MINIMUM_CONFIDENCE` | `0.8`; geometric evidence gate, not probability. |
| `CROP_PADDING_PIXELS` | `6`; aligned-template pixels, clipped to page bounds. |
| `OCR_VARIANTS` | `color`; comma-separated color/grayscale/contrast. Each selected variant adds paid requests; disagreement forces review. |
| `OCR_TIMEOUT_SECONDS`, `OCR_RETRIES` | `8`, `1`; transient failure retry, bounded per request. |
| `PHOTO_BLUR_MINIMUM` | `3`; Laplacian variance after resizing to max 1200px; experimental heuristic. |
| `MAX_UPLOAD_BYTES` | `10485760` (10 MB); frontend proxy has a matching hard limit. |
| `MAX_IMAGE_PIXELS` | `20000000` (20 MP). |
| `FRONTEND_ORIGIN` | `http://localhost:3000`; direct API CORS allowlist. |

Frontend server reads `API_BASE_URL` (default `http://127.0.0.1:8000`). Copy `frontend/.env.example` to `.env.local` only to customize it. Requests go through a same-origin, size-bounded server proxy; no browser secrets are needed.

## Verification and evaluation

```bash
./scripts/check.sh
# Or independently:
cd backend
uv run ruff check app migrations
uv run pytest -q
uv run python -m app.evaluation.run
uv run python -m app.evaluation.run --provider configured
uv run alembic check
cd ../frontend
npm run typecheck
npm test
npm run format:check
npm run build
npm run test:e2e
```

Browser tests use installed Google Chrome by default, start isolated backend/production frontend servers on ports 8001/3001 and create a unique SQLite database/storage directory under ignored `work/`. To use a supported bundled Chromium instead, set `PLAYWRIGHT_CHANNEL=chromium` after `npx playwright install chromium`. Build the frontend before the browser tests. Normal local demo records are not touched.

`evaluation/ground_truth.csv` fields: `image_file,expected_answer,student_actual_answer,answer_type`. Use `--dataset PATH` for another dataset, `--threshold NUMBER` to inspect routing, and `--json` for machine-readable results. Precision is undefined (N/A) when no answers are automated. The default evaluation runs a **synthetic fixture** and yields:

```text
Total answers:       20
OCR accuracy:        95.00%
Auto-grade precision:100.00%
Auto-grade coverage: 75.00%
Human review rate:   25.00%
```

These figures establish plumbing correctness only. They are not evidence of production precision or workload reduction. With ordinary empty mock OCR, coverage is 0%, review rate 100%, and precision N/A. Fixture evaluation uses already cropped images, so alignment is N/A. Application exports include unique-page failure records; recorded reports measure their alignment failures separately from answer accuracy.

**Real evaluation:** use /evaluation to label Unclassified uploads as real handwriting and verify actual answers/grades, then export the Verified real handwriting cohort. Unzip privately and run:

```bash
cd backend
uv run python -m app.evaluation.run --dataset /absolute/private/dataset --provider recorded --require-real --json
```

Recorded mode makes no paid requests and preserves the original routing thresholds. Accuracy denominators exclude missing human truth and show the missing counts. `--provider configured` explicitly performs new OCR; it errors when real-provider credentials are unavailable, and crop-only datasets without alignment verification cannot auto-grade. Do not use exception-only labels to claim automatic precision. See [the real-world test protocol](docs/real_world_grading_test.md) for the 500–1,000-answer collection plan.

Regenerate original assets with `cd backend && uv run python ../scripts/generate_samples.py`. OpenCV registration/crop hashes may differ across library/platform versions; regenerate fixtures together if synthetic predictions no longer match. Do not use the fixture generator to create predictions for a real evaluation dataset.

## API overview

`POST/GET /students`; `POST/GET /templates`; `GET /templates/{id}`; `POST /templates/{id}/questions` (atomically replaces the draft answer key); `POST/GET /submissions`; `GET /submissions/{id}`; `POST /submissions/{id}/process`; `GET /review-queue`; `POST /question-submissions/{id}/review`; `GET /metrics`. Scoped image endpoints serve template/page/crop images without exposing filesystem keys. `/demo/setup` seeds fictional data idempotently. `/samples/{filename}` serves an explicit allowlist of original assets.

## Known limitations and next steps

- Local single-center demo identity; **no authentication or production role enforcement**. Run on loopback only. Not a secure SaaS deployment.
- One page per upload, manual template selection, exact answers only, no partial credit.
- ORB registration requires a flat, feature-rich page. Failed geometry retains a diagnostic preview and **requires a retake before grading**; severe blur/darkness/empty or low-resolution photos are also rejected. Moderate glare, erasures, crossed-out answers and confidently wrong single-digit OCR remain unvalidated risks. Plausible feature matches are not proof that the right template was selected.
- Grading confidence is a gated vendor score, not a learned or calibrated probability. Blank detection and conservative parsing are heuristics. No real-world error/coverage claims.
- Processing is synchronous and sequential with persisted Aligning/Cropping/Recognizing/Grading stages, transient provider retry/backoff and a 110-second OCR loop budget (an in-flight request can run longer). Remaining crops after the budget enter review as processing failures. No durable jobs, cancellation or crash recovery for stuck `processing`; jobs must replace this before sustained use. Automatic retries may duplicate vendor billing.
- Image limits and private resource lookups are foundations only. Retention/deletion, sandboxed PDF decoding, storage encryption, rate limits, TLS, backups, audit administration and production authorization remain work. Reprocessing can leave orphaned local images.
- Review queue returns up to 200 items and dashboard lists the latest 100 worksheets; metrics/query optimization, pagination and multi-grader review assignment are future work.
- Versioned migrations preserve legacy grades and add booklet/evaluation records; revised templates must be created separately. No template cloning or unsaved-edit recovery yet.

Next five highest-value engineering steps:

1. Collect permissioned, de-identified handwriting/scan data and measure grade-decision precision with confidence intervals on a held-out set.
2. Exercise and harden a live OCR integration; calibrate conservative thresholds and add stronger blank/ambiguity detection.
3. Add durable processing jobs, idempotent retries, crash recovery and provider backoff.
4. Implement authenticated organization membership, grader authorization, private object storage and retention/deletion controls; complete privacy/security review before real records.
5. Improve registration diagnostics, template revision/clone tools, and queue pagination/assignment for multi-grader centers.

See [architecture](docs/architecture.md), [privacy foundations](docs/privacy.md), and [verification results](docs/verification.md).
