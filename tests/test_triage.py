"""Tests for Task 1 triage — all offline, no LLM calls."""
import pytest

from src.triage import triage_ticket
from src.schemas import TriageOutput

USE_FIXTURES = True


def _triage(subject: str, body: str) -> TriageOutput:
    return triage_ticket({"subject": subject, "body": body}, use_fixtures=USE_FIXTURES)


# 1. SSO/login ticket → authentication + P2 or P3
def test_sso_ticket_issue_category_authentication():
    result = _triage(
        subject="SSO login broken",
        body="Several enterprise users cannot sign in via SSO since this morning.",
    )
    assert result.issue_category == "authentication"
    assert result.urgency_tier in ("P2", "P3")


# 2. Outage wording → P1
def test_outage_ticket_urgency_p1():
    result = _triage(
        subject="Complete outage",
        body="The entire system is down and all users are blocked. Production is stopped.",
    )
    assert result.urgency_tier == "P1"


# 3. Billing ticket → billing team
def test_billing_ticket_routes_to_billing_team():
    result = _triage(
        subject="Incorrect invoice",
        body="We were billed twice for the Enterprise subscription in October.",
    )
    assert result.issue_category == "billing"
    assert "billing" in result.recommended_team.lower() or "finance" in result.recommended_team.lower()


# 4. Ambiguous short ticket → valid schema, category unknown or low-confidence
def test_ambiguous_ticket_returns_valid_schema():
    result = _triage(
        subject="Something seems off",
        body="Numbers look different.",
    )
    assert isinstance(result, TriageOutput)
    assert result.urgency_tier in ("P1", "P2", "P3", "P4")
    assert result.product_area
    assert result.recommended_team


# 5. KB match exists → known_issue_match has path/score/snippet
def test_sso_ticket_has_known_issue_match():
    result = _triage(
        subject="SAML SSO failure",
        body="Users get SAML assertion errors when trying to log in.",
    )
    assert result.known_issue_match is not None
    assert result.known_issue_match.path
    assert result.known_issue_match.score > 0
    assert result.known_issue_match.evidence_snippet


# 6. Empty input raises ValueError
def test_empty_input_raises_value_error():
    with pytest.raises(ValueError, match="empty"):
        triage_ticket("", use_fixtures=USE_FIXTURES)

    with pytest.raises(ValueError, match="empty"):
        triage_ticket({"subject": "", "body": ""}, use_fixtures=USE_FIXTURES)


# 7. String input accepted
def test_string_input_accepted():
    result = triage_ticket(
        "Dashboard loads very slowly for large date ranges.",
        use_fixtures=USE_FIXTURES,
    )
    assert isinstance(result, TriageOutput)


# 8. Output is deterministic for same input
def test_output_is_deterministic():
    r1 = _triage("SSO broken", "Cannot log in via SSO")
    r2 = _triage("SSO broken", "Cannot log in via SSO")
    assert r1.model_dump() == r2.model_dump()


# 9. Trace has required keys
def test_trace_has_required_keys():
    result = _triage("SSO broken", "Users cannot log in via SSO")
    trace = result.trace
    assert trace["trace_type"] == "ticket_triage"
    assert "input_summary" in trace
    assert "signals" in trace
    assert "retrieval" in trace
    assert "decisions" in trace


# 10. to_mermaid produces non-empty valid string
def test_to_mermaid_output():
    from src.visual_trace import to_mermaid
    result = _triage("SSO broken", "Users cannot log in via SSO")
    mermaid = to_mermaid(result.trace)
    assert mermaid.startswith("flowchart TD")
    assert "TriageOutput" in mermaid


# 11. Escalation/churn-risk ticket → P2
def test_churn_risk_ticket_urgency_p2():
    result = _triage(
        subject="Final notice before cancellation",
        body="If this is not fixed we will cancel. Our leadership is evaluating alternatives.",
    )
    assert result.urgency_tier in ("P1", "P2")
