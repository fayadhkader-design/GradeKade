# Version 0.1 verification

Local verification completed on October 14, 2026:

- Python: 50 passed; 1 live PostgreSQL test skipped because `TEST_POSTGRES_URL` was unset. Non-failing upstream Starlette/PyMuPDF deprecation warnings.
- Frontend: 2 region-coordinate unit tests passed; TypeScript check passed; production Next.js build passed; Prettier/Ruff checks passed.
- Browser: 3 tests passed against an isolated database: manual 10-box template creation → student creation → upload → keyboard review → 9/10 final result; synthetic 20-answer demo → mixed automated/review decisions → 17/20 final result; narrow-screen layout without horizontal overflow.
- Alembic: empty SQLite database migration passed; PostgreSQL migration SQL compiled; schema drift check found no upgrade operations.
- Synthetic evaluation: 20 answers, 95% normalized OCR recovery, 100% automated grade-decision precision, 75% coverage, 25% human review. These are artificial fixture results, not handwriting reliability claims.
- Empty mock evaluation: 0% coverage, 100% review, undefined automated precision; blank actual response accounts for 5% OCR recovery.
- Live desktop browser inspection: dashboard and review crop/decision controls; narrow-screen review layout inspected.

Real Mathpix API calls and live local PostgreSQL were not tested. GitHub CI includes a disposable PostgreSQL service and an optional live-database workflow test; see Actions for its actual result. CI also runs the browser suite with Chromium.
