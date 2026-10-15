"""Image-based evaluation with independent truth; mock metrics are synthetic only."""

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from app.config import settings
from app.evaluation.report import report
from app.services.cropping import is_blank, prepare_variants
from app.services.grading import grade_answer
from app.services.ingestion import ingest, png_bytes
from app.services.normalization import answers_equivalent, normalize_answer
from app.services.ocr import REAL_OCR_PROVIDERS, FixtureOCRProvider, OCRProvider, get_provider

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
                alignment_verified=provider.name == "synthetic_fixture"
                or row.get("alignment_verified") == "True",
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


def evaluate_records(dataset, provider=None, threshold=0.995, variants=None):
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
            selected = variants or ["color"]
            if any(v not in {"color", "grayscale", "contrast"} for v in selected):
                raise ValueError("Unsupported preprocessing variant")
            prepared = prepare_variants(image, 0, 0, 1, 1, padding=0) if selected != ["color"] else None
            started = perf_counter()
            results = [
                provider.recognize_answer(png_bytes(prepared[v]) if prepared else content, row["answer_type"])
                for v in selected
            ]
            ocr_seconds = perf_counter() - started
            result = results[0]
            inference = [
                r.provider_metadata["inference_seconds"]
                for r in results
                if "inference_seconds" in r.provider_metadata
            ]
            from app.services.grading import grade_evidence

            decision, evidence = grade_evidence(
                results,
                row["expected_answer"],
                row["answer_type"],
                correct_threshold=threshold,
                incorrect_threshold=max(threshold, settings.auto_reject_confidence_threshold),
                alignment_verified=provider.name == "synthetic_fixture"
                or row.get("alignment_verified") == "True",
                blank=is_blank(image),
                allow_unscored_agreement=provider.name == "paddle"
                and settings.paddle_allow_experimental_auto_grade,
                min_agreeing_variants=settings.paddle_min_agreeing_variants,
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
                    "ocr_error": any(r.error for r in results),
                    "ocr_seconds": ocr_seconds,
                    "inference_seconds": sum(inference) if inference else None,
                    "variants_run": len(results),
                    "preprocessing_variants": selected,
                    "grading_strategy": evidence["strategy"],
                    "evidence": evidence,
                    "ocr_results": {
                        v: {
                            "raw_text": r.raw_text,
                            "normalized_candidate": r.normalized_candidate,
                            "provider_confidence": r.confidence,
                            "error": r.error,
                            "provider_metadata": r.provider_metadata,
                        }
                        for v, r in zip(selected, results)
                    },
                    # Crop-only evaluation cannot measure page alignment.
                    "alignment_verified": None,
                }
            )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument(
        "--provider", choices=["fixture", "configured", "recorded", "paddle", "mathpix"], default="fixture"
    )
    parser.add_argument("--threshold", type=float, default=settings.auto_grade_confidence_threshold)
    parser.add_argument("--require-real", action="store_true")
    parser.add_argument("--variants", default=settings.ocr_variants)
    parser.add_argument(
        "--output", type=Path, help="Save new observations as records.json for later comparison"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1:
        parser.error("threshold must be between 0 and 1")
    if args.output and (args.provider == "recorded" or (args.output / "records.json").exists()):
        parser.error("Choose a new output directory for new provider observations")
    provider = None
    if args.provider == "fixture":
        provider = FixtureOCRProvider(json.loads((args.dataset / "mock_predictions.json").read_text()))
    elif args.provider in {"configured", "paddle", "mathpix"}:
        config = (
            settings
            if args.provider == "configured"
            else settings.model_copy(update={"ocr_provider": args.provider})
        )
        provider = get_provider(config)
        if provider.name == "mock":
            parser.error("Configured real OCR is unavailable. Set OCR_PROVIDER and credentials first.")
        if provider.name == "paddle" and not provider.initialize():
            parser.error(provider.diagnostic)
    try:
        selected = list(dict.fromkeys(v.strip() for v in args.variants.split(",")))
        rows = evaluate_records(
            args.dataset, provider, args.threshold, ["color"] if args.provider == "fixture" else selected
        )
    except (ValueError, OSError) as error:
        parser.error(str(error))
    if args.require_real:
        rows = [
            r
            for r in rows
            if r.get("source") == "real_handwriting" and r.get("ocr_provider") in REAL_OCR_PROVIDERS
        ]
        if not rows:
            parser.error(
                "No real-handwriting records recognized by a real provider. Synthetic/mock results are ineligible."
            )
    if args.output:
        if args.provider == "recorded":
            parser.error("--output is for new observations, not recorded replay")
        args.output.mkdir(parents=True, exist_ok=True)
        target = args.output / "records.json"
        if target.exists():
            parser.error("Output records.json already exists; choose a new experiment directory")
        target.write_text(json.dumps(rows, indent=2))
    pages_path = args.dataset / "page_records.json"
    pages = (
        json.loads(pages_path.read_text()) if args.provider == "recorded" and pages_path.exists() else None
    )
    if pages is not None and args.require_real:
        eligible = {r["worksheet_id"] for r in rows}
        pages = [p for p in pages if p["worksheet_id"] in eligible]
    metrics = report(rows, pages)
    metrics["evaluation_mode"] = args.provider
    metrics["real_handwriting_real_ocr_answers"] = sum(
        r.get("source") == "real_handwriting" and r.get("ocr_provider") in REAL_OCR_PROVIDERS for r in rows
    )
    if args.output:
        (args.output / "report.json").write_text(json.dumps(metrics, indent=2))
    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print("RECORDED SNAPSHOTS" if provider is None else f"Provider: {provider.name}")
        if args.provider == "fixture":
            print("SYNTHETIC FIXTURE: pipeline validation only; not real handwriting evidence.")
        for key, value in metrics.items():
            if key not in {"by_answer_type", "by_confidence_bucket", "cohorts", "by_provider", "notes"}:
                print(f"{key}: {value if value is not None else 'N/A'}")
        print(
            json.dumps(
                {
                    k: metrics[k]
                    for k in ("by_answer_type", "by_confidence_bucket", "cohorts", "by_provider", "notes")
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
