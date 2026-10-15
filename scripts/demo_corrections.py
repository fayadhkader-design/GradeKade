"""Create an explicit synthetic 17/20 -> 19/20 -> 20/20 local workflow example."""
import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    samples = Path(__file__).resolve().parents[1] / "sample_data"
    with httpx.Client(base_url=args.api, timeout=180) as client:
        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        def post(path, **kwargs):
            response = client.post(path, **kwargs)
            response.raise_for_status()
            return response.json()

        if get("/health")["ocr_provider"] != "mock":
            parser.error("Run this synthetic workflow example in MOCK mode; it must not call a real OCR provider")
        ids = post("/demo/setup")
        student = post("/students", json={"first_name": "Correction workflow demo"})
        booklet_id = str(uuid4())
        post("/booklets", json={"id":booklet_id, "student_id":student["id"], "page_count":1,
                                "capture_seconds":0, "synthetic_demo":True})
        initial_id = str(uuid4())
        post(f"/booklets/{booklet_id}/pages/{initial_id}", data={
            "template_id":ids["template_id"],"page_number":"1"},
            files={"file":("completed.png",(samples/"completed.png").read_bytes(),"image/png")})
        post(f"/submissions/{initial_id}/process")
        for answer in get(f"/review-queue?booklet_id={booklet_id}"):
            post(f"/question-submissions/{answer['id']}/review",
                 json={"grade":"incorrect" if answer["question_number"] in {12,20} else "correct"})
        original = get(f"/submissions/{initial_id}")["answers"]
        assert get(f"/booklets/{booklet_id}")["workflow"]["unresolved_count"] == 3
        rounds = []
        for number in (1,2):
            round_ = post(f"/booklets/{booklet_id}/correction-rounds")
            capture = post(f"/correction-rounds/{round_['id']}/pages/{initial_id}",files={
                "file":(f"correction-round-{number}.png",(samples/f"correction-round-{number}.png").read_bytes(),"image/png")})
            post(f"/submissions/{capture['id']}/process")
            for answer in get(f"/review-queue?correction_round_id={round_['id']}"):
                post(f"/question-submissions/{answer['id']}/review",
                     json={"grade":"incorrect" if number == 1 and answer["question_number"] == 20 else "correct"})
            rounds.append(post(f"/correction-rounds/{round_['id']}/finalize"))
        final = get(f"/booklets/{booklet_id}")
        assert final["status"] == "completed" and final["correct"] == 20
        preserved = get(f"/submissions/{initial_id}")["answers"] == original
        assert preserved
        print(json.dumps({"synthetic_workflow_only":True,"booklet_id":booklet_id,
                          "url":f"http://127.0.0.1:3000/booklets/{booklet_id}",
                          "initial_score":"17/20",
                          "rounds":[{"round_number":r["round_number"],"corrected":r["corrected"],
                                     "evaluated":r["unresolved_before"],"remaining":r["unresolved_after"]} for r in rounds],
                          "final_score":"20/20","original_answers_preserved":preserved,
                          "timing_note":"Scripted human decisions have no fabricated review durations."},indent=2))


if __name__ == "__main__":
    main()
