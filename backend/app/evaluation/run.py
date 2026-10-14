"""Image-based evaluation with independent truth; mock metrics are synthetic only."""
import argparse
import csv
import json
from pathlib import Path
from dataclasses import dataclass
from app.config import settings
from app.services.ocr import OCRProvider, OCRResult, FixtureOCRProvider, get_provider
from app.services.normalization import normalize_answer, answers_equivalent
from app.services.grading import grade_answer
from app.services.ingestion import ingest
from app.services.cropping import is_blank

DEFAULT_DATA = Path(__file__).resolve().parents[3] / "evaluation"


@dataclass
class EvaluationMetrics:
    total: int
    ocr_matches: int
    automated: int
    correct_automated: int

    def summary(self):
        return {"total_answers": self.total,
                "ocr_accuracy": self.ocr_matches / self.total if self.total else None,
                "auto_grade_precision": self.correct_automated / self.automated if self.automated else None,
                "auto_grade_coverage": self.automated / self.total if self.total else None,
                "human_review_rate": 1 - self.automated / self.total if self.total else None}


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
            image_path = (dataset / row['image_file']).resolve()
            if not image_path.is_relative_to(dataset.resolve()):
                raise ValueError("Evaluation image must be inside the dataset directory")
            content = image_path.read_bytes()
            image = ingest(content, min_dimension=1)
            result = provider.recognize(content)
            total += 1
            recovered += same_normalized(result.raw_text, row['student_actual_answer'], row['answer_type'])
            decision = grade_answer(result.raw_text, row['expected_answer'], row['answer_type'], result.confidence,
                                    threshold, blank=is_blank(image))
            if decision.review_status == 'auto_accepted':
                automated += 1
                actual_grade = 'correct' if answers_equivalent(row['student_actual_answer'], row['expected_answer'], row['answer_type']) else 'incorrect'
                correct += decision.final_grade == actual_grade
    return EvaluationMetrics(total, recovered, automated, correct)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATA)
    parser.add_argument('--provider', choices=['fixture', 'configured'], default='fixture')
    parser.add_argument('--threshold', type=float, default=settings.auto_grade_confidence_threshold)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1:
        parser.error('threshold must be between 0 and 1')
    provider = FixtureOCRProvider(json.loads((args.dataset / 'mock_predictions.json').read_text())) if args.provider == 'fixture' else get_provider(settings)
    metrics = evaluate(args.dataset, provider, args.threshold).summary()
    if args.json:
        print(json.dumps({'provider': provider.name, 'synthetic': provider.name == 'synthetic_fixture', **metrics}, indent=2))
        return
    print(f"Provider: {provider.name}")
    if provider.name == 'synthetic_fixture':
        print('SYNTHETIC FIXTURE: pipeline validation only, not real handwriting accuracy.')
    print(f"Total answers: {metrics['total_answers']}")
    for title, key in [('OCR accuracy', 'ocr_accuracy'), ('Auto-grade precision', 'auto_grade_precision'),
                       ('Auto-grade coverage', 'auto_grade_coverage'), ('Human review rate', 'human_review_rate')]:
        value = metrics[key]
        print(f"{title}: {value:.2%}" if value is not None else f"{title}: N/A (no eligible decisions)")


if __name__ == '__main__':
    main()
