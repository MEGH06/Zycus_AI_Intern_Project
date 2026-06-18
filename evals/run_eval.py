"""Evaluation harness for Task 1 (triage) and Task 2 (account brief)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow running as `python evals/run_eval.py` from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

_EVALS_DIR = Path(__file__).parent
_PASS_THRESHOLD = 0.80


# ── Task 1 scorer ─────────────────────────────────────────────────────────────

def score_task1_case(case: dict, use_fixtures: bool = True) -> dict:
    from src.triage import triage_ticket

    case_id = case["case_id"]
    expected = case.get("expected", {})
    checks: list[dict] = []
    error = None
    output = None

    try:
        output = triage_ticket(case["input"], use_fixtures=use_fixtures)
    except Exception as exc:
        error = str(exc)

    if error:
        return {"case_id": case_id, "task": "task1", "passed": False,
                "score": 0.0, "checks": [], "error": error}

    # Build checks
    criteria = [k for k in expected if k != "must_have_known_issue" or True]

    if "issue_category_any_of" in expected:
        ok = output.issue_category in expected["issue_category_any_of"]
        checks.append({"name": "issue_category", "passed": ok, "points": 0.25,
                        "observed": output.issue_category})

    if "urgency_any_of" in expected:
        ok = output.urgency_tier in expected["urgency_any_of"]
        checks.append({"name": "urgency", "passed": ok, "points": 0.25,
                        "observed": output.urgency_tier})

    if expected.get("must_have_known_issue"):
        ok = output.known_issue_match is not None
        checks.append({"name": "known_issue_match", "passed": ok, "points": 0.25,
                        "observed": output.known_issue_match.path if output.known_issue_match else None})
    elif "must_have_known_issue" in expected and not expected["must_have_known_issue"]:
        # Optional: award points regardless (we don't penalise for a match)
        checks.append({"name": "known_issue_match_optional", "passed": True, "points": 0.25,
                        "observed": "n/a"})

    if "must_include_team_keyword_any_of" in expected:
        team_lower = output.recommended_team.lower()
        ok = any(kw in team_lower for kw in expected["must_include_team_keyword_any_of"])
        checks.append({"name": "recommended_team", "passed": ok, "points": 0.25,
                        "observed": output.recommended_team})

    return _finalise(case_id, "task1", checks)


# ── Task 2 scorer ─────────────────────────────────────────────────────────────

def score_task2_case(case: dict, use_fixtures: bool = True) -> dict:
    from src.account_health import generate_account_brief

    case_id = case["case_id"]
    expected = case.get("expected", {})

    # Adversarial: expect controlled error
    if expected.get("expect_error"):
        try:
            generate_account_brief(case["account_id"], use_fixtures=use_fixtures)
            return {"case_id": case_id, "task": "task2", "passed": False, "score": 0.0,
                    "checks": [{"name": "expect_error", "passed": False, "points": 1.0,
                                "observed": "no error raised"}], "error": None}
        except ValueError:
            return {"case_id": case_id, "task": "task2", "passed": True, "score": 1.0,
                    "checks": [{"name": "expect_error", "passed": True, "points": 1.0,
                                "observed": "ValueError raised correctly"}], "error": None}
        except Exception as exc:
            return {"case_id": case_id, "task": "task2", "passed": False, "score": 0.0,
                    "checks": [{"name": "expect_error", "passed": False, "points": 1.0,
                                "observed": f"unexpected error: {exc}"}], "error": str(exc)}

    checks: list[dict] = []
    error = None
    output = None

    try:
        output = generate_account_brief(case["account_id"], use_fixtures=use_fixtures)
    except Exception as exc:
        error = str(exc)

    if error:
        return {"case_id": case_id, "task": "task2", "passed": False,
                "score": 0.0, "checks": [], "error": error}

    s_min = expected.get("summary_sentence_min", 3)
    s_max = expected.get("summary_sentence_max", 5)
    n = len(output.executive_summary)
    ok = s_min <= n <= s_max
    checks.append({"name": "summary_sentences", "passed": ok, "points": 0.25,
                    "observed": n})

    risk_any = expected.get("risk_type_any_of")
    if risk_any:
        found = {f.risk_type for f in output.open_risks_and_flagged_issues}
        ok = bool(found & set(risk_any))
        checks.append({"name": "risk_type", "passed": ok, "points": 0.25,
                        "observed": sorted(found)})
    else:
        checks.append({"name": "risk_type_optional", "passed": True, "points": 0.25,
                        "observed": "n/a"})

    if expected.get("must_have_quote"):
        ok = all(f.quote for f in output.open_risks_and_flagged_issues)
        checks.append({"name": "quotes_present", "passed": ok, "points": 0.25,
                        "observed": len(output.open_risks_and_flagged_issues)})
    else:
        checks.append({"name": "quotes_optional", "passed": True, "points": 0.25,
                        "observed": "n/a"})

    tp_min = expected.get("talking_points_min", 3)
    ok = len(output.recommended_talking_points) >= tp_min
    checks.append({"name": "talking_points", "passed": ok, "points": 0.25,
                    "observed": len(output.recommended_talking_points)})

    return _finalise(case_id, "task2", checks)


# ── helpers ───────────────────────────────────────────────────────────────────

def _finalise(case_id: str, task: str, checks: list[dict]) -> dict:
    if not checks:
        return {"case_id": case_id, "task": task, "passed": False,
                "score": 0.0, "checks": [], "error": "no checks defined"}
    total_points = sum(c["points"] for c in checks)
    earned = sum(c["points"] for c in checks if c["passed"])
    score = round(earned / total_points, 3) if total_points else 0.0
    return {"case_id": case_id, "task": task, "passed": score >= _PASS_THRESHOLD,
            "score": score, "checks": checks, "error": None}


# ── run_all ───────────────────────────────────────────────────────────────────

def run_all(use_fixtures: bool = True) -> dict:
    with open(_EVALS_DIR / "cases_task1.json") as f:
        cases1: list[dict] = json.load(f)
    with open(_EVALS_DIR / "cases_task2.json") as f:
        cases2: list[dict] = json.load(f)

    results = []
    for c in cases1:
        results.append(score_task1_case(c, use_fixtures=use_fixtures))
    for c in cases2:
        results.append(score_task2_case(c, use_fixtures=use_fixtures))

    t1 = [r for r in results if r["task"] == "task1"]
    t2 = [r for r in results if r["task"] == "task2"]

    def avg(rs: list[dict]) -> float:
        return round(sum(r["score"] for r in rs) / len(rs), 3) if rs else 0.0

    return {
        "overall_score": avg(results),
        "task1_score": avg(t1),
        "task2_score": avg(t2),
        "total_cases": len(results),
        "passed_cases": sum(1 for r in results if r["passed"]),
        "run_at": datetime.now(timezone.utc).isoformat(),
        "mode": "fixtures" if use_fixtures else "real",
        "cases": results,
    }


# ── report writers ────────────────────────────────────────────────────────────

def write_reports(result: dict) -> None:
    _EVALS_DIR.mkdir(exist_ok=True)

    # JSON
    json_path = _EVALS_DIR / "eval_report.json"
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2)

    # Markdown
    md_path = _EVALS_DIR / "eval_report.md"
    lines = [
        "# Evaluation Report",
        "",
        f"**Run at:** {result['run_at']}  ",
        f"**Mode:** {result['mode']}  ",
        f"**Overall score:** {result['overall_score']}  ",
        f"**Passed:** {result['passed_cases']} / {result['total_cases']}  ",
        "",
        f"| Metric | Score |",
        f"|--------|-------|",
        f"| Task 1 (Triage) | {result['task1_score']} |",
        f"| Task 2 (Account Brief) | {result['task2_score']} |",
        f"| Overall | {result['overall_score']} |",
        "",
    ]

    for task_label, task_key in [("Task 1 – Triage", "task1"), ("Task 2 – Account Brief", "task2")]:
        cases = [r for r in result["cases"] if r["task"] == task_key]
        lines += [f"## {task_label}", "", "| Case ID | Score | Pass | Error |",
                  "|---------|-------|------|-------|"]
        for c in cases:
            status = "✅" if c["passed"] else "❌"
            err = c.get("error") or ""
            lines.append(f"| {c['case_id']} | {c['score']} | {status} | {err[:60]} |")
        lines.append("")

    failed_checks = [
        (r["case_id"], ch)
        for r in result["cases"]
        for ch in r.get("checks", [])
        if not ch["passed"]
    ]
    if failed_checks:
        lines += ["## Failed Checks", ""]
        for cid, ch in failed_checks:
            lines.append(f"- **{cid}** › `{ch['name']}`: observed `{ch['observed']}`")
        lines.append("")

    lines += [
        "> **Note:** This report was generated in fixture mode and is for harness validation only.",
        "> Run with real data (`--no-fixtures`) once `data/tickets.json` and `data/accounts.json` are populated.",
    ]

    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Reports written: {json_path}  {md_path}")


if __name__ == "__main__":
    r = run_all(use_fixtures=True)
    write_reports(r)
    print(f"Overall: {r['overall_score']}  Passed: {r['passed_cases']}/{r['total_cases']}")
