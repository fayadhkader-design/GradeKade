import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

BACKEND = Path(__file__).resolve().parents[2]


def test_migrate_empty_sqlite_database(tmp_path):
    url = f"sqlite:///{tmp_path / 'new' / 'schema.db'}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    assert {
        "organizations",
        "users",
        "students",
        "worksheet_templates",
        "question_templates",
        "worksheet_submissions",
        "question_submissions",
    } <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_postgresql_migration_sql_compiles_without_database():
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": "postgresql+psycopg://demo:demo@localhost/gradekade"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE worksheet_submissions" in result.stdout
    assert "UUID" in result.stdout and "TIMESTAMP WITH TIME ZONE" in result.stdout


def test_booklet_migration_preserves_existing_grades(tmp_path):
    import sqlite3

    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    env = {**os.environ, "DATABASE_URL": url}

    def migrate(target):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", target],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    migrate("0001")
    with sqlite3.connect(tmp_path / "legacy.db") as db:
        stamp = "2026-10-14 12:00:00"
        ids = [f"{i:032x}" for i in range(1, 7)]
        db.execute(
            "INSERT INTO organizations (id,name,created_at) VALUES (?,?,?)", (ids[0], "Legacy demo", stamp)
        )
        db.execute(
            "INSERT INTO students (id,organization_id,first_name,created_at) VALUES (?,?,?,?)",
            (ids[1], ids[0], "Demo", stamp),
        )
        db.execute(
            "INSERT INTO worksheet_templates (id,organization_id,name,version,template_image_path,width,height,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (ids[2], ids[0], "Legacy template", 1, "demo.png", 1200, 1600, stamp),
        )
        db.execute(
            "INSERT INTO question_templates (id,worksheet_template_id,question_number,x,y,width,height,expected_answer,answer_type,auto_grade_enabled,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ids[3], ids[2], 1, 0.1, 0.1, 0.2, 0.1, "42", "integer", 1, stamp),
        )
        db.execute(
            "INSERT INTO worksheet_submissions (id,organization_id,student_id,worksheet_template_id,uploaded_file_path,status,created_at) VALUES (?,?,?,?,?,?,?)",
            (ids[4], ids[0], ids[1], ids[2], "scan.png", "completed", stamp),
        )
        db.execute(
            "INSERT INTO question_submissions (id,worksheet_submission_id,question_template_id,crop_image_path,raw_ocr_text,expected_answer,ocr_confidence,grading_confidence,system_grade,final_grade,review_status,human_override,routing_reason,ocr_provider,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ids[5],
                ids[4],
                ids[3],
                "crop.png",
                "42",
                "42",
                1,
                1,
                "correct",
                "correct",
                "auto_accepted",
                0,
                "high_confidence",
                "mock",
                stamp,
            ),
        )
    migrate("0003")
    with sqlite3.connect(tmp_path / "legacy.db") as db:
        db.execute(
            "INSERT INTO evaluation_annotations (id,created_at,question_submission_id,actual_answer,transcription_status,verified_grade,source,annotation_seconds,verified_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (f"{7:032x}", stamp, ids[5], "42", "readable", "correct", "synthetic", 1.2, stamp),
        )
        prior_answer = db.execute("SELECT * FROM question_submissions").fetchone()
        prior_annotation = db.execute("SELECT * FROM evaluation_annotations").fetchone()
    migrate("head")
    with sqlite3.connect(tmp_path / "legacy.db") as db:
        assert db.execute("SELECT * FROM question_submissions").fetchone()[:-1] == prior_answer
        assert db.execute("SELECT * FROM evaluation_annotations").fetchone() == prior_annotation
        assert db.execute("SELECT initial_question_submission_id FROM question_submissions").fetchone() == (
            None,
        )
        assert db.execute("SELECT COUNT(*) FROM correction_rounds").fetchone() == (0,)

        assert db.execute("SELECT status,booklet_id,page_number FROM worksheet_submissions").fetchone() == (
            "completed",
            None,
            None,
        )
        assert db.execute(
            "SELECT final_grade,raw_ocr_text,review_seconds FROM question_submissions"
        ).fetchone() == ("correct", "42", None)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_correction_downgrade_refuses_to_discard_attempt_history(tmp_path):
    from sqlalchemy.orm import Session

    from app.db import Base
    from app.models import Booklet, CorrectionRound, Organization, Student

    url = f"sqlite:///{tmp_path / 'history.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        org = Organization(name="Migration demo")
        db.add(org)
        db.flush()
        student = Student(organization_id=org.id, first_name="Demo")
        db.add(student)
        db.flush()
        booklet = Booklet(organization_id=org.id, student_id=student.id, page_count=1)
        db.add(booklet)
        db.flush()
        db.add(
            CorrectionRound(
                organization_id=org.id, booklet_id=booklet.id, round_number=1, unresolved_before=1
            )
        )
        db.commit()
    engine.dispose()
    env = {**os.environ, "DATABASE_URL": url}
    stamped = subprocess.run(
        [sys.executable, "-m", "alembic", "stamp", "head"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert stamped.returncode == 0, stamped.stderr
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0003"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 and "Cannot downgrade while correction history exists" in result.stderr
    import sqlite3

    with sqlite3.connect(tmp_path / "history.db") as db:
        assert db.execute("SELECT COUNT(*) FROM correction_rounds").fetchone() == (1,)
