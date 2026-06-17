from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Ticket(BaseModel):
    ticket_id: str
    account_id: str | None = None
    subject: str = ""
    body: str = ""
    created_at: datetime | None = None
    status: str | None = None
    product_area: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class Account(BaseModel):
    account_id: str
    name: str = "Unknown Account"
    plan: str | None = None
    segment: str | None = None
    renewal_date: datetime | None = None
    health_score: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDoc(BaseModel):
    doc_id: str
    path: str
    title: str
    product_area: str | None = None
    text: str


class KnownIssueMatch(BaseModel):
    doc_id: str
    path: str
    title: str
    score: float
    evidence_snippet: str


class TriageOutput(BaseModel):
    product_area: str
    issue_category: str
    urgency_tier: Literal["P1", "P2", "P3", "P4"]
    reasoning: str
    known_issue_match: KnownIssueMatch | None
    recommended_team: str
    draft_first_response: str
    trace: dict[str, Any]


class RiskFlag(BaseModel):
    risk_type: str
    severity: Literal["high", "medium", "low"]
    ticket_id: str | None = None
    quote: str
    justification: str


class AccountBrief(BaseModel):
    account_id: str
    executive_summary: list[str]
    open_risks_and_flagged_issues: list[RiskFlag]
    recommended_talking_points: list[str]
    trace: dict[str, Any]
