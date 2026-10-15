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
