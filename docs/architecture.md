# GradeKade 0.1 architecture

A local development application for arithmetic worksheets. Human review is a first-class outcome, not an error. Development/demo use only. Do not upload identifiable student educational records until production privacy/security controls are completed.

## Boundaries

- **Next.js / React / TypeScript / Tailwind**: internal dashboard, normalized-coordinate rectangle editor, uploads, results, keyboard review.
- **FastAPI**: typed REST API, organization-scoped resource lookup and local demo identity. No public deployment or production authentication in 0.1.
- **SQLAlchemy + PostgreSQL**: UUID entities, explicit relationships and constraints; SQLite is available for isolated tests and an optional zero-install demo. Docker Compose supplies PostgreSQL. Schema versioning through Alembic.
- **LocalStorage**: UUID keys; files served through organization-scoped resource routes, never arbitrary filesystem paths. Storage interface can be implemented for object storage later.
- **Ingestion**: bounded image/PDF validation and first-page rendering.
- **Alignment**: ORB matches + RANSAC homography with geometric and inlier checks. Unverified alignment requires a retake before cropping/grading; no silent high-confidence resize fallback.
- **Cropping**: normalized rectangles on the aligned image. Preprocessing is gentle; full-resolution color crops retained.
- **OCR**: provider protocol; mock is deliberately empty/uncertain for arbitrary uploads. A separately selected synthetic demo uses a fixture transcript bound to exact generated sample-pixel hashes. No answers are inferred from the answer key. Mathpix is opt-in; missing credentials fall back to clearly labeled mock, provider errors force review.
- **Normalization**: allowlisted numeric grammar and exact rational arithmetic. No evaluation of untrusted expressions, floating-point tolerance, or LLM decisions.
- **Grading/routing**: preserve system prediction, effective confidence, routing reason, and human decision. Vendor confidence is an uncalibrated input, gated by alignment, parse validity, template policy, and blank detection.
- **Review**: conditional updates prevent overwriting another review; score becomes final only when all answers have a final decision. Final decisions and recognized-text edits preserve original OCR.
- **Evaluation**: image manifest + separate ground truth. OCR fixture predictions are separate from truth. Report precision, coverage, review rate and exact normalized OCR recovery; synthetic results are plumbing tests, never handwriting accuracy claims.

## Data and lifecycle

Organization → User / Student / WorksheetTemplate → QuestionTemplate.
Student + WorksheetTemplate → WorksheetSubmission → QuestionSubmission.
All resource access is scoped to the configured local organization; this is not a user-selectable organization header. Demo admin/grader roles are represented in the schema; authenticated authorization is future work.

Submission: uploaded → processing → needs_review/completed, or failed. Explicit synchronous processing is intentional for a one-page local MVP. A database compare-and-set claims uploaded/failed submissions; repeated completed processing is a no-op; processing and review races are rejected. Retrying a failed submission replaces only its partial processing outputs. Template questions become immutable after first submission. Processing records OCR provider, alignment diagnostics, threshold and routing reasons for audit.

## Local runtime and future changes

Start PostgreSQL with Docker Compose, migrate and seed, then run FastAPI and Next.js. A dev script can use SQLite when Docker is unavailable. API runs on loopback; Next.js proxies API requests so storage and API URLs are same-origin. Uploads are limited to 10 MB and 20 megapixels; only decoded JPEG/PNG/PDF accepted. PDFs render the first page only, with bounded dimensions.

Before real records: authenticated sessions, enforced organization membership/roles and database RLS, private object storage, retention/deletion policies, consent/vendor review, encrypted transport/backups, rate limits, sandboxed ingestion, durable jobs, confidence calibration on held-out handwriting, monitoring and security review. No FERPA/COPPA claims.

## Real OCR / evaluation boundary (0.2 development milestone)

recognize_answer receives image bytes and answer type, never the answer key. OCRResult keeps raw text, nullable provider confidence, normalized candidate, allowlisted metadata and a safe error. HTTP retries are bounded; vendor errors never become incorrect answers. Missing credentials visibly fall back to MOCK, while configured CLI runs reject that fallback.

Full-color aligned regions are retained for human review. Padded color/grayscale/contrast debug variants are saved; selected OCR variants are configurable. All selected variants must normalize to the same answer, with no line errors/multiple lines. Grading uses the minimum known score and gates parsing, alignment, blank crops and template policy; it never multiplies/inflates confidence from correlated variants. Separate auto-correct/incorrect thresholds are uncalibrated rules.

The unchanged submission status enum is supplemented by persisted processing_metadata.stage. Severe photo failures or rejected geometry stop before OCR and require a retake. Individual provider failures produce PROCESSING_FAILED outcomes and retain usable crops for human decisions. AI raw text/system grade/rule evidence remain immutable after processing. Human final grades/timing and optional independent EvaluationAnnotation transcription/verified grade/source are separate.

Evaluation exports contain crops, IDs and observations, no student names or full pages. Original pages are available only through scoped local resource routes. Snapshot reports never call the provider. Accuracy excludes missing labels and reports denominators; coverage includes unlabeled records. Unique-page failures remain separate from answer accuracy. Source (real handwriting/synthetic/unknown) and provider (Mathpix/mock/fixture) are independent dimensions; exact supplied synthetic page pixels cannot be labeled real. Corrections should create new submissions later rather than overwrite these initial observations.

## Optional local Paddle runtime

OCR_PROVIDER=paddle uses PP-FormulaNet-S through PaddleOCR FormulaRecognition in a separate Python 3.12 CPU environment. A persistent subprocess receives in-memory answer crops via a bounded prefixed JSON protocol; serialized calls avoid sharing an unsafe native predictor across request threads. Worker timeouts terminate the process to prevent late predictions being assigned to another answer. The normal backend keeps its existing OpenCV package/version; PaddleX's conflicting cv2 distribution stays isolated.

Startup attempts initialization and reports unavailable/degraded status explicitly, with no mock fallback. Model downloads/cache are local setup steps. Raw LaTeX and null provider probability remain separate from normalized candidates. Optional experimental agreement-based automation is disabled by default and records its uncalibrated rule strategy independently. Paddle/Mathpix evaluation uses the same source/truth format; inference time, OCR wall time, attempted variants and missing timing denominators are preserved in exports.


## Assignment corrections

Booklet is the assignment instance; its completed status now requires all questions' latest finalized attempts to be correct. Existing page completed status remains grading-final, preserving old scan semantics. CorrectionRound snapshots unresolved initial QuestionSubmission IDs, CorrectionTarget stores those immutable memberships, and CorrectionPageSlot points to the current capture of an affected original page.

A corrected scan is a new WorksheetSubmission referencing its round/source. Only its snapshotted questions enter cropping/OCR/grading; each new QuestionSubmission links to the initial answer. Finalized rounds advance the assignment's resolved state. Explicit finalization requires every target to have a final decision. One open round per booklet is enforced by a partial unique index; capture/process mutations use round/slot locks and conditional updates.

Initial grades, human/AI decisions, evidence and evaluation annotations are preserved. Retakes of failed/unprocessed captures create new records; superseded captures cannot be processed. No correction inherits the initial synthetic fixture transcript. Evaluation exports retain attempt lineage. Correction counts/timings are groundwork only; OCR behavior and thresholds are unchanged.
