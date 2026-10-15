# Correction workflow implementation

Keep Booklet as the assignment instance. Initial pages and question decisions remain intact. CorrectionRound snapshots the unresolved initial-question IDs; each correction scan creates a new WorksheetSubmission and QuestionSubmission linked back to those IDs. A page slot identifies the current capture within a round; retakes preserve failed/uploaded captures. Template coordinates and keys are reused.

Booklet completion means every initial question's latest finalized attempt is correct, with no active correction round. A page's existing completed status continues to mean its grading decisions are final. Round finalization is explicit and requires every targeted answer to have a final decision. Failed processing and pending review cannot close a round.

Only unresolved questions are cropped/OCRed/graded. OCR provider behavior, thresholds and normalization are unchanged. The existing review queue gains round scope. Results show initial accuracy, current completion, rounds, labor counts and per-question history. Standalone pages can be attached to a one-page assignment without rescanning.

Migration 0004 is additive and preserves all existing grades. Development/demo identity remains unchanged. Concurrency guards and idempotent captures prevent duplicate active rounds or replacement of in-flight/graded pages.
