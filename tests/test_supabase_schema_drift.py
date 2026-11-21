"""supabase_schema_drift：migration 解析與缺表判定。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import supabase_schema_drift as d  # noqa: E402


def test_repo_migrations_include_aivi_tables():
    tables = d.expected_tables()
    assert tables["aivi_runs"] == "20260830000000_aivi_tracking.sql"
    assert "brands" in tables


def test_parse_create_drop_and_comments(tmp_path):
    (tmp_path / "001.sql").write_text(
        "CREATE TABLE IF NOT EXISTS public.a (id int);\n"
        "-- CREATE TABLE commented_out (id int);\n"
        "create table \"b\" (id int);\n",
        encoding="utf-8",
    )
    (tmp_path / "002.sql").write_text("DROP TABLE IF EXISTS b;\nCREATE TABLE c(id int);", encoding="utf-8")
    assert d.expected_tables(tmp_path) == {"a": "001.sql", "c": "002.sql"}


def test_missing_table_fails(monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setattr(d, "expected_tables", lambda: {"aivi_runs": "m.sql", "brands": "i.sql"})
    monkeypatch.setattr(d, "live_tables", lambda u, k: {"brands"})
    assert d.main() == 1
    assert "aivi_runs" in capsys.readouterr().err


def test_no_drift_passes(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setattr(d, "expected_tables", lambda: {"brands": "i.sql"})
    monkeypatch.setattr(d, "live_tables", lambda u, k: {"brands", "extra_view"})
    assert d.main() == 0
