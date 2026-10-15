"""Original correction fixtures for manual workflow testing, never an OCR benchmark."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from PIL import Image, ImageDraw, ImageFont
from app.services.ingestion import image_digest, png_bytes

root = Path(__file__).resolve().parents[1] / "sample_data"
questions = json.loads((root / "template.json").read_text())["questions"]
image = Image.open(root / "completed.png").convert("RGB")
font = ImageFont.load_default(size=38)


def write_answer(number):
    q = questions[number-1]
    x, y = round(q["x"]*image.width), round(q["y"]*image.height)
    width, height = round(q["width"]*image.width), round(q["height"]*image.height)
    draw = ImageDraw.Draw(image)
    draw.rectangle((x,y,x+width-1,y+height-1),fill="white")
    draw.text((x+18,y+16),q["expected_answer"],font=font,fill=(25,63,138))


write_answer(3)
write_answer(12)
first = png_bytes(image)
(root / "correction-round-1.png").write_bytes(first)
write_answer(20)
second = png_bytes(image)
(root / "correction-round-2.png").write_bytes(second)
manifest = json.loads((root / "manifest.json").read_text())
manifest["correction_sha256"] = [image_digest(first),image_digest(second)]
(root / "manifest.json").write_text(json.dumps(manifest))
print("Generated synthetic correction pages: two corrected, then the final remaining answer.")
