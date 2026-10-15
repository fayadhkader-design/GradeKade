# Real OCR and evaluation milestone

Priority: measured grade-decision precision on real photographed handwriting, not additional scanning UI. Existing capture and booklet flows stay in place.

Boundaries: provider-neutral typed OCR observations; configurable crop padding/preprocessing; measurable page/crop quality gates; deterministic numeric normalization; uncalibrated evidence-based grading rules; immutable system decisions plus separate human ground truth; de-identified dataset export; replayable CLI reports and a functional error-inspection screen.

Mathpix is the first real adapter, not a claim that it is the best or accurate enough. Missing credentials must remain visibly mock. All local HTTP contract tests use mock transports; no paid OCR or handwriting accuracy claim may be made before a real run. The user will configure credentials after implementation.

Data origins (`synthetic`, `real_handwriting`, `unknown`) and OCR modes (`synthetic`, `real`, `mock`) are independent. A real OCR call on a printed demo is still synthetic input. Evaluation requires human-verified labels; human grade decisions alone do not establish an exact handwriting transcription. Missing labels and unavailable alignment evidence must be reported, not scored as successes.

Default crop strategy preserves color with small configurable padding. Other variants are experiments, not independent statistical evidence: agreement can gate automation but must never inflate vendor confidence. Image quality failures, multiple answers, missing confidence, parse failures and disagreement force review or retake. No inference from the answer key is allowed inside the OCR provider.

Processing stages are observable while the page request runs. This milestone does not add a production job system, native app, curriculum features or correction cycles. System and ground-truth records remain separable so linked correction attempts can be added later.
