import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

BACKEND = Path(__file__).resolve().parents[2]


def test_migrate_empty_sqlite_database(tmp_path):
    url = f"sqlite:///{tmp_path / 'schema.db'}"
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
