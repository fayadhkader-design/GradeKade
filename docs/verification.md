# Version 0.1 verification

Local verification completed on October 14, 2026:

- Python: 51 passed; 1 live PostgreSQL test skipped because `TEST_POSTGRES_URL` was unset. Non-failing upstream Starlette/PyMuPDF deprecation warnings.
- Frontend: 2 region-coordinate unit tests passed; TypeScript check passed; production Next.js build passed; Prettier/Ruff checks passed.
- Browser: 3 tests passed against an isolated database: manual 10-box template creation → student creation → upload → keyboard review → 9/10 final result; synthetic 20-answer demo → mixed automated/review decisions → 17/20 final result; narrow-screen layout without horizontal overflow.
- Alembic: empty SQLite database migration passed; PostgreSQL migration SQL compiled; schema drift check found no upgrade operations.
- Synthetic evaluation: 20 answers, 95% normalized OCR recovery, 100% automated grade-decision precision, 75% coverage, 25% human review. These are artificial fixture results, not handwriting reliability claims.
- Empty mock evaluation: 0% coverage, 100% review, undefined automated precision; blank actual response accounts for 5% OCR recovery.
- Live desktop browser inspection: dashboard and review crop/decision controls; narrow-screen review layout inspected.

Live Mathpix API calls and live local PostgreSQL were not tested. GitHub CI has now passed the backend suite with a disposable PostgreSQL service, including the complete 20-answer grading/review workflow (52 backend tests passed). CI also runs the browser suite with Chromium; see Actions for its final result.

## Real OCR / evaluation milestone — October 14, 2026

- Backend: **80 passed, 1 skipped** (optional local live PostgreSQL test); Ruff check/format passed. Migration upgrade and Alembic schema check passed.
- Frontend: **3 unit tests**, TypeScript, Prettier and production build passed.
- Browser: **7 passed** with isolated SQLite/production frontend. Includes desktop annotation, CSV/JSON/crop ZIP export, phone layout, filtered last-record navigation, existing booklet capture/draft/retry/review and keyboard workflows.
- Mathpix HTTP/provider contract and full-page pipeline were exercised with simulated HTTP responses. No live paid request was made; credentials and real photographed handwriting were deferred by the user.
- Synthetic fixture: 20/20 truth labels, raw and normalized OCR accuracy 19/20 (95%); grade prediction accuracy 18/19 (94.74%, excludes the blank abstention); automated precision 15/15 (100%), Wilson 95% CI 79.61–100%; coverage 15/20 (75%); review 5/20 (25%); false auto-correct/incorrect 0/0; OCR failures 0/20. Crop-only fixture alignment and review time are N/A.
- Real handwriting + live Mathpix: **0 evaluated answers**; all accuracy/precision claims remain N/A.
- The incorrect OCR interpretation for fixture Q7 is routed to review; blank Q20 abstains. These demonstrate routing only. Erasures/cross-outs, subtle glare, plausible wrong digits and photographed handwriting are unmeasured risks.
- Fresh functional UI review resolved its filtered-navigation finding and returned ship; the existing design remains unchanged.

## Paddle CPU infrastructure milestone — October 14, 2026

- Backend: **100 passed, 1 optional live PostgreSQL test skipped**. New Paddle tests use mocked output and a tiny fake package to exercise the actual worker protocol/lifecycle, with no model downloads.
- Frontend: **4 unit tests, 8 browser tests passed**; TypeScript, production build, formatting, Ruff and schema drift checks passed.
- CPU requirements resolve for CPython 3.12 on Apple Silicon. This is dependency resolution, not installation or live inference.
- A real FastAPI startup with Paddle selected and a missing runtime returned provider=paddle, status=degraded and a clear diagnostic. The smoke command returned nonzero, available=false and zero variants.
- Default synthetic evaluation remains 20 answers, 95% normalized OCR accuracy, 75% coverage, 15/15 correct automatic decisions. This is still fixture plumbing, unrelated to Paddle accuracy.
- **Real Paddle model inference speed/accuracy: N/A.** The user explicitly deferred model installation because disk space was insufficient. No fake-package timing is reported as a real benchmark.
- One local test setup hit a transient temporary-directory creation failure while resolving optional dependencies under disk pressure; after resolution ended, the full backend suite passed.


## Correction workflow milestone — October 15, 2026

- Backend: **107 passed, 1 optional local live PostgreSQL test skipped**. Includes repeated correction rounds, mixed auto/human decisions, unresolved-only processing, historical preservation, capture retry/retake, tenant isolation, one-open-round enforcement and already-correct assignment rejection.
- Frontend: **4 unit tests and 9 browser tests passed**; type check, production build and formatting passed.
- Browser correction scenario: 17/20 initial → 2 of 3 corrected → 1 of 1 corrected → 20/20 complete; phone capture/review/finalization, question history and mobile overflow checked.
- Migration 0004 upgrades legacy SQLite records without changing grades or evaluation annotations; PostgreSQL SQL compiles. Alembic reports no schema drift. Downgrade refuses to delete existing correction history.
- Local mock-only walkthrough created a completed booklet and verified original answer JSON unchanged. No artificial human review timing was recorded by the script.
- Screenshots are saved under ignored outputs/. These are synthetic/mock workflow demonstrations, not OCR accuracy evidence.
- Paddle/Mathpix adapters, grading thresholds and normalization were unchanged during this milestone.


## Correction recovery and ordering — October 16, 2026

- Backend: **108 passed, 1 optional local PostgreSQL test skipped**; Ruff passed. The new API regression deliberately stores correction slots in reverse order and checks both round and booklet workflow responses return pages in booklet order.
- Frontend: **4 unit tests**, TypeScript, production build and Prettier passed.
- Browser: all **9 existing scenarios passed**; the new recovery scenario passed in its final targeted run after selectors were scoped to the correction workspace. It checks phone-sized navigation/reload during server processing, a simulated HTTP 503, automatic recovery to review, hidden reprocessing/retake controls and polling cessation after processing finishes.
- Recovery uses simulated server states; the existing end-to-end correction scenario still exercises real local API processing with mock OCR. No live OCR or physical-phone validation was performed.
- No schema migration, OCR provider, normalization or grading threshold change.


## Upload rendering reliability — October 20, 2026

- Fixed PDF render rounding at the configured pixel cap: scale selection checks integer renderer bounds before raster allocation, preserving the existing 2x maximum render scale and first-page-only behavior.
- Transparent PNG backgrounds now flatten onto white after EXIF orientation. Dark handwriting and opaque colors remain intact; RGBA, grayscale-alpha and palette transparency are covered.
- Backend: **126 passed, 1 optional local PostgreSQL test skipped**; Ruff lint and formatting checks for changed Python files passed. New tests include PDF page sizes/aspect ratios, bounded output, first-page-only rendering, transparency, orientation, and stored template/submission image responses through the API.
- Frontend: **4 unit tests, 10 browser scenarios**, TypeScript and production build passed. Existing capture, correction, review and evaluation workflows continue to pass.
- Synthetic evaluation remains 20 answers, 95% normalized OCR recovery, 75% automated coverage and 15/15 correct automated decisions. These are fixture checks, not real handwriting accuracy measurements.
- No schema, OCR provider, confidence threshold or upload-limit changes; no model downloads or paid OCR calls.
