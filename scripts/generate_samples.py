"""Original synthetic worksheet assets. Run from backend: uv run python ../scripts/generate_samples.py."""
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from PIL import Image, ImageDraw, ImageFont
from app.services.ingestion import image_digest, png_bytes
from app.services.alignment import align_submission_to_template
from app.services.cropping import crop_region

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sample_data"
EVAL = ROOT / "evaluation"
OUT.mkdir(exist_ok=True)
(EVAL / "images").mkdir(parents=True, exist_ok=True)
problems = [
    ("17 + 25", "42", "integer"), ("63 - 28", "35", "integer"), ("6 x 7", "42", "integer"),
    ("72 / 9", "8", "integer"), ("1.2 + 0.3", "1.5", "decimal"), ("3.5 - 1.25", "2.25", "decimal"),
    ("1/4 + 1/4", "1/2", "fraction"), ("3/4 - 1/4", "1/2", "fraction"), ("8 x 9", "72", "integer"),
    ("100 - 64", "36", "integer"), ("24 + 19", "43", "integer"), ("56 / 7", "8", "integer"),
    ("0.2 x 3", "0.6", "decimal"), ("9.6 / 4", "2.4", "decimal"), ("2/3 - 1/3", "1/3", "fraction"),
    ("1/8 + 3/8", "1/2", "fraction"), ("5 - 8", "-3", "integer"), ("12 x 4", "48", "integer"),
    ("81 / 9", "9", "integer"), ("0.75 + 0.25", "1", "decimal"),
]
# Printed synthetic responses, deliberately including mistakes and one blank.
actual = ["42", "35", "41", "8", "1.5", "2.25", "2/4", "1/2", "72", "36", "43", "9", "0.6", "2.4", "1/3", "2/4", "-3", "48", "9", ""]
font = ImageFont.load_default(size=27)
large = ImageFont.load_default(size=44)
answer_font = ImageFont.load_default(size=38)
blank = Image.new("RGB", (1200, 1600), "white")
draw = ImageDraw.Draw(blank)
draw.text((75, 65), "Arithmetic Practice A", font=large, fill="#172b28")
draw.text((75, 130), "Original GradeKade demo | 20 questions | GK-A-001", font=font, fill="black")
draw.text((75, 175), "Student: ____________________     Date: ______________", font=font, fill="black")
questions = []
for index, (problem, expected, kind) in enumerate(problems):
    col, row = divmod(index, 10)
    x, y = 75 + col * 565, 270 + row * 120
    draw.text((x, y + 15), f"{index + 1}.  {problem} =", font=font, fill="black")
    bx, by, bw, bh = x + 300, y, 170, 75
    draw.rectangle((bx - 3, by - 3, bx + bw + 3, by + bh + 3), outline="#999999", width=2)
    questions.append(dict(question_number=index + 1, x=bx / 1200, y=by / 1600, width=bw / 1200, height=bh / 1600,
                          expected_answer=expected, answer_type=kind, auto_grade_enabled=True))
draw.text((75, 1510), "Demo content only. Synthetic responses; no real student records.", font=font, fill="black")
completed = blank.copy()
draw = ImageDraw.Draw(completed)
for index, (q, value) in enumerate(zip(questions, actual)):
    if value:
        draw.text((round(q['x'] * 1200) + 16 + index % 7, round(q['y'] * 1600) + 14 + index % 5), value, font=answer_font, fill=(23 + index, 63, 138))
blank_bytes, completed_bytes = png_bytes(blank), png_bytes(completed)
(OUT / "blank.png").write_bytes(blank_bytes)
(OUT / "completed.png").write_bytes(completed_bytes)
blank.save(OUT / "blank.pdf", "PDF", resolution=144)
(OUT / "template.json").write_text(json.dumps({"name": "Arithmetic Practice A", "questions": questions}, indent=2))
(OUT / "manifest.json").write_text(json.dumps({"template_sha256": image_digest(blank_bytes), "submission_sha256": image_digest(completed_bytes)}, indent=2))
aligned = align_submission_to_template(blank, completed)
assert aligned.metadata['verified'], aligned.metadata
predictions, rows = {}, []
for index, (q, truth) in enumerate(zip(questions, actual)):
    crop = crop_region(aligned.image, q['x'], q['y'], q['width'], q['height'])
    data = png_bytes(crop)
    filename = f"answer-{index + 1:02}.png"
    (EVAL / "images" / filename).write_bytes(data)
    raw = "1/4" if index == 6 else truth  # Known OCR mistake at low confidence.
    confidence = .75 if index in {1, 6, 11, 14} else .999
    if not truth:
        confidence = 0
    predictions[image_digest(data)] = {"raw_text": raw, "confidence": confidence}
    rows.append(dict(image_file=f"images/{filename}", expected_answer=q['expected_answer'], student_actual_answer=truth, answer_type=q['answer_type']))
for path in [OUT / "ocr_predictions.json", EVAL / "mock_predictions.json"]:
    path.write_text(json.dumps(predictions, indent=2))
with (EVAL / "ground_truth.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
with (OUT / "answer_key.csv").open("w", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["question_number", "expected_answer", "answer_type"])
    writer.writerows((q['question_number'], q['expected_answer'], q['answer_type']) for q in questions)
print("Generated original 20-question worksheet, PDF, completed page and independent evaluation fixtures.")
