"""Image-based evaluation with independent truth; mock metrics are synthetic only."""

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.services.cropping import is_blank
from app.services.grading import grade_answer
from app.services.ingestion import ingest
from app.services.normalization import answers_equivalent, normalize_answer
from app.services.ocr import FixtureOCRProvider, OCRProvider, get_provider
from app.evaluation.report import report

DEFAULT_DATA = Path(__file__).resolve().parents[3] / "evaluation"


@dataclass
class EvaluationMetrics:
    total: int
    ocr_matches: int
    automated: int
    correct_automated: int

    def summary(self):
        return {
            "total_answers": self.total,
            "ocr_accuracy": self.ocr_matches / self.total if self.total else None,
            "auto_grade_precision": self.correct_automated / self.automated if self.automated else None,
            "auto_grade_coverage": self.automated / self.total if self.total else None,
            "human_review_rate": 1 - self.automated / self.total if self.total else None,
        }


def same_normalized(raw, actual, kind):
    if not raw.strip() or not actual.strip():
        return not raw.strip() and not actual.strip()
    try:
        return normalize_answer(raw, kind) == normalize_answer(actual, kind)
    except ValueError:
        return False


def evaluate(dataset: Path, provider: OCRProvider, threshold: float) -> EvaluationMetrics:
    total = recovered = automated = correct = 0
    with (dataset / "ground_truth.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            image_path = (dataset / row["image_file"]).resolve()
            if not image_path.is_relative_to(dataset.resolve()):
                raise ValueError("Evaluation image must be inside the dataset directory")
            content = image_path.read_bytes()
            image = ingest(content, min_dimension=1)
            result = provider.recognize(content)
            total += 1
            recovered += same_normalized(result.raw_text, row["student_actual_answer"], row["answer_type"])
            decision = grade_answer(
                result.raw_text,
                row["expected_answer"],
                row["answer_type"],
                result.confidence,
                threshold,
                blank=is_blank(image),
            )
            if decision.review_status == "auto_accepted":
                automated += 1
                actual_grade = (
                    "correct"
                    if answers_equivalent(
                        row["student_actual_answer"], row["expected_answer"], row["answer_type"]
                    )
                    else "incorrect"
                )
                correct += decision.final_grade == actual_grade
    return EvaluationMetrics(total, recovered, automated, correct)


def evaluate_records(dataset, provider=None, threshold=0.995):
    """Replay exported snapshots by default; explicit providers perform new OCR."""
    json_file = dataset / "records.json"
    if provider is None:
        if not json_file.exists():
            raise ValueError("Recorded evaluation needs records.json from the application export")
        rows = json.loads(json_file.read_text())
        if not isinstance(rows, list):
            raise ValueError("Invalid records dataset")
        return rows
    rows = []
    with (dataset / "ground_truth.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            image_path = (dataset / row["image_file"]).resolve()
            if not image_path.is_relative_to(dataset.resolve()):
                raise ValueError("Evaluation image must be inside the dataset")
            content = image_path.read_bytes()
            image = ingest(content, min_dimension=1)
            result = provider.recognize_answer(content, row["answer_type"])
            from app.services.grading import grade_evidence

            decision, evidence = grade_evidence(
                [result],
                row["expected_answer"],
                row["answer_type"],
                correct_threshold=threshold,
                incorrect_threshold=max(threshold, settings.auto_reject_confidence_threshold),
                blank=is_blank(image),
            )
            actual = row["student_actual_answer"]
            status = row.get("transcription_status") or ("readable" if actual.strip() else "blank")
            verified = row.get("verified_grade")
            if not verified and status in {"readable", "blank"}:
                verified = (
                    "correct"
                    if answers_equivalent(actual, row["expected_answer"], row["answer_type"])
                    else "incorrect"
                )
            rows.append(
                {
                    **row,
                    "raw_ocr_text": result.raw_text,
                    "grading_confidence": decision.grading_confidence,
                    "ocr_confidence": result.confidence,
                    "system_grade": decision.system_grade,
                    "automated": decision.review_status == "auto_accepted",
                    "decision": evidence["outcome"],
                    "verified_grade": verified,
                    "transcription_status": status,
                    "source": "synthetic"
                    if provider.name == "synthetic_fixture"
                    else row.get("source", "unknown"),
                    "ocr_provider": provider.name,
                    "ocr_error": result.error,
                    # Crop-only evaluation cannot measure page alignment.
                    "alignment_verified": None,
                }
            )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--provider", choices=["fixture", "configured", "recorded"], default="fixture")
    parser.add_argument("--threshold", type=float, default=settings.auto_grade_confidence_threshold)
    parser.add_argument("--require-real", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1:
        parser.error("threshold must be between 0 and 1")
    provider = None
    if args.provider == "fixture":
        provider = FixtureOCRProvider(json.loads((args.dataset / "mock_predictions.json").read_text()))
    elif args.provider == "configured":
        provider = get_provider(settings)
        if provider.name == "mock":
            parser.error("Configured real OCR is unavailable. Set OCR_PROVIDER and credentials first.")
    try:
        rows = evaluate_records(args.dataset, provider, args.threshold)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    if args.require_real:
        rows = [
            r for r in rows if r.get("source") == "real_handwriting" and r.get("ocr_provider") == "mathpix"
        ]
        if not rows:
            parser.error(
                "No real-handwriting records recognized by a real provider. Synthetic/mock results are ineligible."
            )
    metrics = report(rows)
    metrics["evaluation_mode"] = args.provider
    metrics["real_handwriting_real_ocr_answers"] = sum(
        r.get("source") == "real_handwriting" and r.get("ocr_provider") == "mathpix" for r in rows
    )
    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print("RECORDED SNAPSHOTS" if provider is None else f"Provider: {provider.name}")
        if args.provider == "fixture":
            print("SYNTHETIC FIXTURE: pipeline validation only; not real handwriting evidence.")
        for key, value in metrics.items():
            if key not in {"by_answer_type", "by_confidence_bucket", "cohorts", "notes"}:
                print(f"{key}: {value if value is not None else 'N/A'}")
        print(
            json.dumps(
                {k: metrics[k] for k in ("by_answer_type", "by_confidence_bucket", "cohorts", "notes")},
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
