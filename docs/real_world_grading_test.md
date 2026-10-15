# Real-world handwriting experiment

Development/demo use only. Use adult volunteers and fictional learner identifiers; do not upload identifiable student educational records. Use only GradeKade's original Arithmetic Practice A assets. Do not use proprietary curriculum.

## First live smoke test

1. For free local OCR, first follow docs/paddle-ocr.md and set OCR_PROVIDER=paddle. For Mathpix, in backend/.env set OCR_PROVIDER=mathpix, MATHPIX_APP_ID and MATHPIX_APP_KEY. Keep this file out of Git. Restart the backend from backend/. The banner must say REAL OCR · Mathpix. Missing credentials produce an explicit MOCK fallback.
2. Print sample_data/blank.pdf. Have an adult write answers with a pen. Include one deliberately incorrect response, one decimal, one fraction and one blank.
3. In /scan select the sample template and a fictional learner. Leave synthetic OCR OFF. Photograph the entire flat page in good light. Submit.
4. Check the original/aligned images, padded crops and processing outcomes. Failed alignment/poor photos must say “Retake this page”; provider failures must have no automatic final grade.
5. In /evaluation choose Unclassified uploads. Transcribe answers independently before expanding OCR evidence. Mark their source Real photographed handwriting, set the actual human grade and save. The form rejects a grade inconsistent with a readable numeric transcription.
6. Inspect real-handwriting records, export, unzip privately, and run the recorded report below. Confirm provider=mathpix and source=real_handwriting. This is the first live end-to-end verification; it has NOT been performed on the implementation machine because keys/photos were deferred.

## Dataset target and protocol

Arithmetic Practice A has 20 questions: **25 completed sheets = 500 answers**, **50 = 1,000**. Twenty sheets yield 400 answers, not 1,000.

Recruit at least five adult volunteers, ideally ten. Use fictional identifiers; record a private participant/sheet split manifest outside Git. Include:
- pen and pencil, neat and deliberately messy answers;
- negative integers, leading zeros, small decimal points, .5/0.50 variants;
- simple fractions, equivalent unreduced fractions and uneven fraction bars;
- ambiguous 1/7, 3/8 and 5/6 shapes;
- erased attempts, overwritten digits, crossed-out answers and multiple competing answers;
- intentionally wrong answers and blanks;
- normal light, modest shadows, slight angles and different phone cameras;
- a small separately labeled stress set with extreme blur, darkness, glare or cropped-off pages.

Treat crossed-out/multiple answers as unreadable if the final intended answer is genuinely ambiguous. A human grade may still be recorded, but do not invent a numeric transcription. Make a written adjudication rule before collecting labels. Independently double-label ambiguous answers; reconcile differences before reporting accuracy. Do not let OCR output decide the ground truth.

Keep handwriting source, OCR provider, and ground-truth completeness distinct. The application recognizes exact supplied synthetic page pixels even with synthetic OCR switched off and prohibits relabeling those pages as real. Other rendered data must also be labeled honestly by the operator.

Split by participant/sheet, never randomly by crops from the same page. Reserve at least 20% as held-out test data; use a separate development subset for thresholds and preprocessing experiments. Keep all photos of the same handwriting in one split. Duplicating scans measures capture variation, not additional independent handwriting.

## Measure

From /evaluation select Verified real handwriting and download the ZIP. Inspect crops for names before sharing. Export excludes student names, student/reviewer IDs and full-page images; local UUIDs retain linkage, so it is not guaranteed anonymous. Keep export directories private and ignored by Git.

```bash
cd backend
uv run python -m app.evaluation.run --dataset /absolute/private/unzipped-dataset --provider recorded --require-real --json
```

Report total/verified/transcribed answers; raw exact and normalized OCR accuracy; grade decision accuracy and denominator; auto-grade precision and verified automated denominator; auto-grade coverage and review rate; false auto-correct/incorrect counts; OCR failures; unique-page alignment failure/poor-photo counts; and observed mean human review time. Include type/confidence bucket results and the Wilson 95% interval. Empty denominators mean N/A, never 100%.

Coverage includes unverified answers, but precision excludes them and shows how many are missing truth. Label **every** automated answer before making any precision claim; reviewing exceptions alone creates selection bias. Unreadable answers are excluded from OCR transcription accuracy, but verified grades still contribute to decision accuracy. Page failures are reported separately from answer denominators because no valid crops exist.

Raw metrics from a mixed source/provider cohort are not real OCR accuracy. --require-real requires both real handwriting and a real provider (Mathpix or Paddle); zero eligible rows is an error. Recorded mode uses frozen outputs and makes no paid calls. Fixture mode is plumbing validation only.

## Compare crop strategies

Color is the default OCR input, with 6 aligned-template pixels of padding. Grayscale and gentle contrast debug images are saved. Set OCR_VARIANTS=color,grayscale,contrast to recognize all three on new submissions (up to three times the requests/cost). Different outputs or missing scores force review; agreement never increases the minimum provider score. These correlated attempts are not independent evidence.

Use separate new submissions for experiments; do not overwrite the original AI prediction. Compare held-out precision and coverage per type before changing AUTO_GRADE_CONFIDENCE_THRESHOLD, AUTO_REJECT_CONFIDENCE_THRESHOLD, ALIGNMENT_MINIMUM_CONFIDENCE or CROP_PADDING_PIXELS. A .995 rule score does not establish 99.5% grade accuracy.

## Acceptance / next decision

Initially prioritize eliminating false automatic decisions over maximizing coverage. Record every false auto-correct and false auto-incorrect with page/crop, truth, OCR, evidence and preprocessing. At 15/15 correct synthetic automated decisions the 95% Wilson lower bound is only about 79.6%, and synthetic data says nothing about real handwriting.

Collect at least 500 independently verified real answers, then report measured failure modes and confidence intervals on the held-out set. Do not declare production readiness from a small or biased sample. If OCR is promising but latency dominates, the next infrastructure task is durable background processing; if false grades dominate, improve gates/crops and gather targeted handwriting examples first.
