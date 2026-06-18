"""Tests for the evaluation harness — all offline."""
import json
from pathlib import Path

import pytest

from evals.run_eval import run_all, write_reports

_EVALS_DIR = Path(__file__).parent.parent / "evals"


def _result():
    return run_all(use_fixtures=True)


# 1. run_all returns at least 10 cases
def test_run_all_returns_at_least_10_cases():
    r = _result()
    assert r["total_cases"] >= 10


# 2. Every case score is in [0, 1]
def test_all_scores_in_range():
    r = _result()
    for c in r["cases"]:
        assert 0.0 <= c["score"] <= 1.0, f"{c['case_id']} score={c['score']}"


# 3. At least one adversarial case per task in case files
def test_adversarial_cases_exist_task1():
    with open(_EVALS_DIR / "cases_task1.json") as f:
        cases = json.load(f)
    assert any(c.get("adversarial") for c in cases)


def test_adversarial_cases_exist_task2():
    with open(_EVALS_DIR / "cases_task2.json") as f:
        cases = json.load(f)
    assert any(c.get("adversarial") for c in cases)


# 4. Report files are written after write_reports
def test_report_files_written(tmp_path, monkeypatch):
    import evals.run_eval as run_eval_mod
    orig_dir = run_eval_mod._EVALS_DIR
    monkeypatch.setattr(run_eval_mod, "_EVALS_DIR", tmp_path)
    (tmp_path / "cases_task1.json").write_text(
        (orig_dir / "cases_task1.json").read_text()
    )
    (tmp_path / "cases_task2.json").write_text(
        (orig_dir / "cases_task2.json").read_text()
    )
    r = run_eval_mod.run_all(use_fixtures=True)
    run_eval_mod.write_reports(r)
    assert (tmp_path / "eval_report.json").exists()
    assert (tmp_path / "eval_report.md").exists()


# 5. JSON report has expected top-level keys
def test_json_report_schema():
    r = _result()
    for key in ("overall_score", "task1_score", "task2_score", "total_cases", "passed_cases", "cases"):
        assert key in r, f"Missing key: {key}"


# 6. At least 5 Task 1 cases and 5 Task 2 cases
def test_minimum_cases_per_task():
    r = _result()
    t1 = [c for c in r["cases"] if c["task"] == "task1"]
    t2 = [c for c in r["cases"] if c["task"] == "task2"]
    assert len(t1) >= 5
    assert len(t2) >= 5


# 7. Adversarial unknown-account case passes (controlled failure)
def test_adversarial_unknown_account_passes():
    r = _result()
    adv = next((c for c in r["cases"] if c["case_id"] == "T2_ADV_001"), None)
    assert adv is not None
    assert adv["passed"] is True


# 8. each case result has required fields
def test_case_result_fields():
    r = _result()
    required = {"case_id", "task", "passed", "score", "checks", "error"}
    for c in r["cases"]:
        assert required <= c.keys(), f"{c['case_id']} missing fields"
