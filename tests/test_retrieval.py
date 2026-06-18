"""Tests for KB index and classification primitives — all offline."""
import pytest

from src.config import AppConfig
from src.data_loader import load_knowledge_base
from src.kb_index import (
    KnowledgeBaseIndex,
    detect_issue_category,
    detect_product_area,
    detect_urgency,
)
from src.prompts import get_prompt, get_prompt_version
from src.schemas import KnowledgeDoc

FIXTURE_CONFIG = AppConfig()


# ── helpers ───────────────────────────────────────────────────────────────────

def _fixture_docs() -> list[KnowledgeDoc]:
    return load_knowledge_base(FIXTURE_CONFIG, use_fixtures=True)


def _fixture_index() -> KnowledgeBaseIndex:
    return KnowledgeBaseIndex(_fixture_docs())


# ── KB index ──────────────────────────────────────────────────────────────────

def test_kb_index_sso_query_returns_sso_doc_first():
    idx = _fixture_index()
    results = idx.search("SSO login failure SAML assertion", top_k=3)
    assert results, "Expected at least one result"
    assert "sso" in results[0].path.lower() or "sso" in results[0].title.lower()


def test_empty_kb_index_raises_value_error():
    with pytest.raises(ValueError, match="at least one document"):
        KnowledgeBaseIndex([])


def test_retrieval_result_has_evidence_snippet():
    idx = _fixture_index()
    results = idx.search("dashboard slow performance", top_k=2)
    for r in results:
        assert r.evidence_snippet, f"Missing evidence_snippet for {r.path}"


def test_retrieval_score_in_range():
    idx = _fixture_index()
    results = idx.search("password reset", top_k=2)
    for r in results:
        assert 0.0 <= r.score <= 1.0, f"Score {r.score} out of [0,1] for {r.path}"


def test_retrieval_is_deterministic():
    idx = _fixture_index()
    r1 = idx.search("sync integration failure", top_k=2)
    r2 = idx.search("sync integration failure", top_k=2)
    assert [r.doc_id for r in r1] == [r.doc_id for r in r2]


def test_retrieval_sorted_descending_by_score():
    idx = _fixture_index()
    results = idx.search("SAML certificate expired authentication", top_k=3)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


# ── classification primitives ─────────────────────────────────────────────────

def test_detect_urgency_p1_for_outage_wording():
    tier, kws = detect_urgency("The entire system is down, all users are locked out, production blocked.")
    assert tier == "P1"
    assert kws


def test_detect_urgency_p4_for_howto_wording():
    tier, kws = detect_urgency("How to export data to CSV? Just wondering.")
    assert tier == "P4"


def test_detect_urgency_p2_for_churn_wording():
    tier, _ = detect_urgency("If this is not fixed we will cancel our subscription.")
    assert tier == "P2"


def test_detect_issue_category_authentication():
    assert detect_issue_category("cannot log in via SSO SAML") == "authentication"


def test_detect_issue_category_billing():
    assert detect_issue_category("We were billed twice for the subscription.") == "billing"


def test_detect_product_area_auth_from_text():
    area = detect_product_area("SAML SSO login is broken for our users", [])
    assert area == "auth"


# ── prompt registry ───────────────────────────────────────────────────────────

def test_prompt_version_triage():
    assert get_prompt_version("triage") == "triage_v1"


def test_prompt_version_account_brief():
    assert get_prompt_version("account_brief") == "account_brief_v1"


def test_get_prompt_triage_contains_version_string():
    text = get_prompt("triage")
    assert "triage_v1" in text


def test_get_prompt_account_brief_contains_version_string():
    text = get_prompt("account_brief")
    assert "account_brief_v1" in text


def test_get_prompt_unknown_raises_key_error():
    with pytest.raises(KeyError):
        get_prompt("nonexistent_prompt")
