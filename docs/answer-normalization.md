# Numeric answer normalization and review gates

GradeKade compares elementary numeric answers using exact rational arithmetic. Integer, finite decimal and simple fraction answers are supported; there is no expression evaluation or approximate floating-point comparison.

## Accepted notation

- Leading zeros and integral decimals: 042 and 42.0 normalize to 42.
- Decimal shorthand and trailing zeros: .50 normalizes to 0.5.
- Simple fractions: 2/4 and 1 / 2 normalize to 1/2.
- Supported Unicode digits, minus signs and standalone vulgar fractions use the existing allowlist.
- One paired math wrapper may surround a supported numeric answer: $42$, $$42$$, \(42\), or \[42\]. Whitespace inside the pair is allowed. LaTeX fraction commands continue to support integer numerators and denominators.

Incomplete or mismatched delimiters such as $42, 42$, $$42$, or \(42\] are rejected. A wrapper never makes an expression, multiple answers, units, or ambiguous handwriting safe to auto-grade. Unsupported nested notation remains for human review.

## Raw OCR and candidate consistency

An OCR provider returns raw text and an optional normalized candidate. The grading engine independently normalizes the raw text before allowing that candidate to participate in agreement. Every supplied candidate must equal its canonical normalized value for that answer type.

For example, raw text 2/4 with candidate 1/2 is consistent. Raw text 47 with candidate 42 is inconsistent, even if every preprocessing variant supplies candidate 42. An invalid raw value cannot become valid solely because a provider supplied a clean candidate.

Contradictions route to human review with invalid_ocr_candidate and zero grading confidence. This applies to scored vendors and the experimental unscored Paddle agreement policy. The evidence includes candidate_raw_text_consistent; the original raw text, candidate and system prediction remain stored separately from a human final decision. Other blocking reasons such as provider errors, blank crops and poor photo quality retain priority.

Malformed raw text without a supplied candidate retains the existing invalid_answer routing reason. Correct and incorrect confidence thresholds, alignment checks, blank checks, and template review policies still apply to consistent answers.

## Scope and limitations

These checks apply when an answer is processed. Existing stored results are not rewritten. No provider score is treated as calibrated accuracy; valid syntax alone never establishes that OCR recovered the handwriting correctly. Real photographed handwriting evaluation is still required before trusting automation on student records.
