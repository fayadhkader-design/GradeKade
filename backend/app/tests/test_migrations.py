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
    migrate("head")
    with sqlite3.connect(tmp_path / "legacy.db") as db:
        assert db.execute("SELECT status,booklet_id,page_number FROM worksheet_submissions").fetchone() == (
            "completed",
            None,
            None,
        )
        assert db.execute(
            "SELECT final_grade,raw_ocr_text,review_seconds FROM question_submissions"
        ).fetchone() == ("correct", "42", None)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
