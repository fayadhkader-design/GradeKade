# Correction rounds

Booklet now represents the student's assignment across scans. Initial pages/answers never get replaced. A page's existing completed status means that scan's grades are final; a **booklet** is completed only when all questions are correct and no correction round remains open.

## Data and migration

Migration 0004 adds:
- correction_rounds: organization/booklet, sequential number, creation/finalization timestamps, unresolved-before/after counts. A partial unique index allows only one open round per booklet.
- correction_targets: immutable snapshot of the initial question-submission IDs still incorrect.
- correction_page_slots: one slot per original page containing targets, pointing to its current correction capture.
- worksheet_submissions.correction_round_id and source_submission_id.
- question_submissions.initial_question_submission_id.

Existing grades, confidence, review metadata and evaluation annotations are preserved. Correction scans are new submissions; already-correct questions are excluded before cropping/OCR. Reusing a template with repeated pages is safe because targets identify initial answer IDs, not just template/question numbers.

Run from backend:

~~~bash
uv run alembic upgrade head
uv run alembic check
~~~

SQLite migration temporarily disables foreign-key enforcement only on the migration connection, uses batch recreation for added foreign keys, restores checks and validates foreign keys afterward. PostgreSQL migrations use ordinary ALTER TABLE. Back up demo data before migration. Downgrade is refused while correction history exists, protecting original attempts and their links. Restore a pre-correction backup if you intentionally need to revert that schema.

## API

- POST /submissions/{id}/assignment: attach an existing standalone page to a one-page booklet; idempotent.
- GET /booklets/{id}: includes assignment status and workflow metrics/rounds.
- GET /booklets/{id}/corrections: correction state and unresolved page/question numbers.
- POST /booklets/{id}/correction-rounds: start/resume the current round after all initial grades/reviews are final.
- GET /correction-rounds/{id}: targets, required page slots, capture/progress/labor counts.
- POST /correction-rounds/{id}/pages/{source_page_id}: upload a corrected page; server reuses the original template/student. Same image retries return the same submission.
- POST /submissions/{id}/process: existing endpoint, with correction-target filtering and active-capture guards.
- GET /review-queue?correction_round_id={id}: only this round's uncertain answers; existing review endpoint saves decisions/timing.
- POST /correction-rounds/{id}/finalize: requires all targeted answers to have final grades; idempotent once finalized.
- GET /booklets/{id}/question-history: every question's original and subsequent attempts, provider/raw/system/confidence/final/human/timestamp evidence.

Booklet-scoped review includes the active corrections. Organization scope applies to every round, capture and history lookup. Initial question IDs and correction round/source IDs are also exported in evaluation CSV/JSON for later analysis.

## Workflow and completion

1. Finish initial grading and all uncertain-answer review.
2. If any final grades are incorrect, the booklet shows Needs correction and its unresolved question/page numbers.
3. Start a round. Only pages with unresolved questions need captures.
4. On /corrections/{id}, select/upload or use the phone's camera file picker. Process each required page.
5. Review uncertain correction answers through the same fast Correct/Incorrect controls and keyboard shortcuts.
6. Finalize the round. Correct answers resolve; incorrect answers remain open. The next round snapshots only those remaining.
7. Completion requires every initial question's latest finalized attempt to be correct. An open round stays in progress even if its scans have finished.

Finalized/processing/graded captures cannot be replaced. A failed or unprocessed capture may be retaken; the previous capture remains stored and cannot be processed after being superseded. Starting/finalizing rounds and capture slots use database locks/conditional updates and a unique open-round constraint.

Initial accuracy, initially incorrect count, current accuracy, correction rounds, answer-attempt count, completion timestamp/elapsed time are shown. Per-round auto decisions, human review count and measured review seconds remain available. Initial labor comparison remains explicitly initial-attempt only. No fabricated savings or time-to-mastery claims.

## Exact local manual test

Keep OCR_PROVIDER=mock for a workflow-only test. Paddle/Mathpix code and thresholds are unchanged.

1. Open /scan, choose Set up sample student & template, add one original demo page, and submit.
2. Open its booklet and review the five exceptions: Q2/Q7/Q15 Correct, Q12/Q20 Incorrect. Q3 is already automatically incorrect. Initial score is 17/20; three corrections remain.
3. Start correction round 1. Upload sample_data/correction-round-1.png (also GET /samples/correction-round-1.png). It visibly corrects Q3=42 and Q12=8 while Q20 remains blank.
4. Process page 1. In mock mode only Q3/Q12/Q20 enter review. Mark Q3/Q12 Correct and Q20 Incorrect.
5. Finalize round 1. Results show 2 of 3 corrected, 19/20 current score and one correction remaining.
6. Start round 2. Upload sample_data/correction-round-2.png, process, review only Q20 as Correct, and finalize.
7. Results show 20/20, 100%, Booklet complete. Expand Question attempt history: Q20 has Initial → Correction 1 → Correction 2; Q3/Q12 have two attempts; every originally correct question has one.
8. Try starting another round: the UI hides that action and the API rejects it. The original submission still shows 17/20.

You can create a completed example with:

~~~bash
cd backend
uv run python ../scripts/demo_corrections.py
~~~

The script refuses real-provider mode, uses original synthetic images, stores no invented review durations and prints the local booklet URL. Regenerate correction fixtures with uv run python ../scripts/generate_correction_samples.py. They are not handwriting evaluation data.

## Local pages and limitations

Inspect /booklets, /booklets/{id}, /corrections/{id} and the existing standalone Results action “Track correction rounds.” Phone capture uses the device file/camera picker; it is not a replacement camera redesign. A reload resumes acknowledged server captures, but an unuploaded selected file has no new IndexedDB draft support. If a captured page is still processing, the correction screen automatically refreshes every 1.5 seconds, including after reopening or reloading it. Temporary refresh failures show a retry action while automatic refresh continues; polling stops once no page is processing and no local action is running. This resumes observation of an existing job, not a new processing request. Required correction pages appear in the original booklet page order regardless of capture-slot insertion order.

Processing remains synchronous with existing quality/alignment/OCR gates and size limits. Wrong-template photos and low-quality captures may require a retake. No automatic page identification, partial credit, cancel/reopen-finalized-round UI, initial auto-grade amendment workflow, or correction capture labor timer was added. Large assignment/history queries are not optimized or paginated yet. OCR errors with usable crops enter human review; clear page failures cannot finalize a round.

This cycle proves workflow infrastructure using mock/synthetic inputs. It does not establish Paddle/Mathpix handwriting accuracy.
