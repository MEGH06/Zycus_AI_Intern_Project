from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.schemas import KnowledgeDoc
from src.text_utils import extract_quote

# ── output model ──────────────────────────────────────────────────────────────

class RetrievalResult(BaseModel):
    doc_id: str
    path: str
    title: str
    score: float
    evidence_snippet: str
    product_area: str | None = None


# ── index ─────────────────────────────────────────────────────────────────────

class KnowledgeBaseIndex:
    def __init__(self, docs: list[KnowledgeDoc]) -> None:
        if not docs:
            raise ValueError("KnowledgeBaseIndex requires at least one document")
        self._docs = docs
        self._vectorizer = TfidfVectorizer(
            strip_accents="unicode",
            lowercase=True,
            ngram_range=(1, 2),
            max_df=0.95,
            min_df=1,
        )
        corpus = [f"{d.title} {d.text}" for d in docs]
        self._matrix = self._vectorizer.fit_transform(corpus)

    def search(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        q_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self._matrix)[0]
        query_terms = query.lower().split()

        results: list[RetrievalResult] = []
        for idx, score in enumerate(scores):
            doc = self._docs[idx]
            snippet = extract_quote(doc.text, query_terms, max_chars=180)
            results.append(RetrievalResult(
                doc_id=doc.doc_id,
                path=doc.path,
                title=doc.title,
                score=float(np.clip(score, 0.0, 1.0)),
                evidence_snippet=snippet,
                product_area=doc.product_area,
            ))

        results.sort(key=lambda r: (-r.score, r.path))
        return results[:top_k]


# ── classification primitives ─────────────────────────────────────────────────

_PRODUCT_AREA_KEYWORDS: dict[str, list[str]] = {
    "auth": ["login", "sso", "saml", "oauth", "password", "authentication", "sign in", "locked out", "ldap"],
    "billing": ["invoice", "charge", "payment", "subscription", "billing", "credit", "refund", "overcharge"],
    "analytics": ["dashboard", "report", "chart", "metrics", "analytics", "visualization"],
    "integrations": ["sync", "erp", "integration", "api", "webhook", "connector", "import", "export", "data sync"],
    "security": ["breach", "vulnerability", "exploit", "unauthorized", "data leak", "compromised"],
}

_ISSUE_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "authentication": ["login", "sso", "saml", "oauth", "password", "locked out", "sign in", "auth", "ldap"],
    "billing": ["invoice", "charge", "payment", "billing", "credit", "refund", "subscription", "billed"],
    "performance": ["slow", "timeout", "latency", "loading", "performance", "speed", "takes too long", "30 seconds"],
    "data_sync": ["sync", "data not", "not reflecting", "not updated", "out of sync", "records updated"],
    "integration": ["integration", "api", "webhook", "connector", "erp"],
    "security": ["breach", "vulnerability", "unauthorized", "data leak", "exploit", "compromised"],
    "usability": ["how to", "how-to", "where is", "documentation", "guide", "tutorial", "can you explain"],
}

_URGENCY_TIERS: list[tuple[str, list[str]]] = [
    ("P1", ["outage", "down", "all users", "production blocked", "data loss", "security breach",
            "entire team locked out", "service down", "critical failure", "complete outage",
            "cannot access at all"]),
    ("P2", ["major", "sso broken", "payment failure", "escalation", "cancel", "renewal risk",
            "final notice", "cancellation", "churn", "leadership", "evaluate alternative",
            "if this is not fixed", "locked out", "billing error", "twice"]),
    ("P3", ["degraded", "intermittent", "slow", "performance", "partial sync", "not updating",
            "integration issue", "taking longer", "30 seconds", "not reflecting"]),
    ("P4", ["how to", "how-to", "question", "cosmetic", "documentation", "feature request",
            "just wondering", "curious", "seems off", "look different"]),
]

_TEAM_MAP: dict[str, str] = {
    "auth": "Identity & Access",
    "billing": "Finance & Billing",
    "analytics": "Data & Analytics",
    "integrations": "Integrations",
    "security": "Security",
    "unknown": "Customer Success",
}


def detect_product_area(text: str, kb_results: list[RetrievalResult]) -> str:
    lower = text.lower()
    # Keyword scan first
    for area, kws in _PRODUCT_AREA_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            return area
    # Fall back to top KB result's product_area
    for r in kb_results:
        if r.product_area:
            return r.product_area
    return "unknown"


def detect_issue_category(text: str) -> str:
    lower = text.lower()
    for category, kws in _ISSUE_CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            return category
    return "unknown"


def detect_urgency(text: str) -> tuple[str, list[str]]:
    lower = text.lower()
    for tier, kws in _URGENCY_TIERS:
        matched = [kw for kw in kws if kw in lower]
        if matched:
            return tier, matched
    return "P3", []


def detect_team(product_area: str, issue_category: str, urgency: str) -> str:
    if urgency == "P1":
        return "On-Call Engineering"
    if issue_category == "billing":
        return _TEAM_MAP["billing"]
    if issue_category == "authentication":
        return _TEAM_MAP["auth"]
    if issue_category == "security":
        return _TEAM_MAP["security"]
    return _TEAM_MAP.get(product_area, _TEAM_MAP["unknown"])
