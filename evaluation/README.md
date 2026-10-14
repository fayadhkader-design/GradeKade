# Evaluation dataset

`ground_truth.csv` records the actual student response separately from the answer key. `images/` contains original synthetic answer crops. `mock_predictions.json` contains SHA-256-bound simulated OCR observations, including an intentional recognition error. This is not real handwriting data and cannot establish real-world precision or coverage.

From `backend/`: `uv run python -m app.evaluation.run`. Default: explicitly labeled fixture provider. `--provider configured` uses the environment-selected OCR provider (Mathpix only with credentials, otherwise empty mock); `--dataset PATH` selects an independently collected dataset. Never generate production OCR predictions from ground truth. The fixture generator is only for these labeled synthetic samples.

Precision measures correct *grade decisions*, not merely whether the student answer was correct. No automated decisions means precision is undefined (N/A), not 100%. Blank normalized OCR matches blank actual response for OCR recovery, but blanks always route to review. Alignment is not measured here: these are already cropped answers; full-page registration has separate integration tests. Real held-out evaluation must include scan/alignment errors, demographic and handwriting variation, sufficient sample size, and confidence intervals.
