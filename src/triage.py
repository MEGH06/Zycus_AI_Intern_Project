from __future__ import annotations

from typing import Any

from src.config import AppConfig
from src.data_loader import load_knowledge_base
from src.kb_index import (
    KnowledgeBaseIndex,
    detect_issue_category,
    detect_product_area,
    detect_team,
    detect_urgency,
)
from src.schemas import KnownIssueMatch, TriageOutput
from src.text_utils import clean_text
from src.visual_trace import build_triage_trace

_MIN_MATCH_SCORE = 0.15

_DRAFT_TEMPLATES: dict[str, str] = {
    "auth": (
        "Thank you for contacting our support team. We have received your report "
        "regarding an authentication or SSO issue affecting your users. We understand "
        "how critical access is to your daily operations, and we are treating this as "
        "a priority. To help us investigate the root cause, could you please share: "
        "(1) the identity provider (IdP) you are using, such as Okta or Azure AD; "
        "(2) the exact error message your users are seeing; and (3) whether this "
        "affects all users or a specific group? We will review and follow up promptly."
    ),
    "billing": (
        "Thank you for reaching out regarding a billing concern. We have logged your "
        "report and our Finance team will review the details. To expedite resolution, "
        "please confirm the invoice number or the transaction date in question, as "
        "well as the amount that appears incorrect. If you have a copy of the invoice "
        "or a billing statement showing the discrepancy, attaching it here will help "
        "us investigate more efficiently. We aim to respond with a concrete update "
        "within one business day and appreciate your patience."
    ),
    "analytics": (
        "Thank you for your report regarding the analytics dashboard. We have noted "
        "the performance issue and will investigate. To help us reproduce the "
        "problem accurately, could you provide: (1) the date range you were querying "
        "when the slowness occurred; (2) whether the issue affects all users in your "
        "organisation or just your account; and (3) the browser and version you are "
        "using? This information will allow our team to isolate the root cause more "
        "quickly. We will update you as soon as we have findings."
    ),
    "integrations": (
        "Thank you for contacting us about your integration or data sync issue. We "
        "have registered your ticket and are looking into it. To assist in the "
        "investigation, please share: (1) the name and version of the connected "
        "system or ERP; (2) the last date and time the sync ran successfully; and "
        "(3) any error codes or messages visible in your sync logs. The more detail "
        "you can provide, the faster we can identify the cause. We will follow up "
        "with an update as soon as possible."
    ),
    "security": (
        "Thank you for raising this security concern with us. We take reports of "
        "this nature very seriously and are treating this as a high-priority matter. "
        "Please avoid sharing any sensitive credentials or access tokens via this "
        "channel. Our security team has been alerted and will reach out through a "
        "verified secure channel shortly. In the meantime, we recommend reviewing "
        "recent access logs and revoking any suspicious sessions as a precaution. "
        "We will keep you informed of our findings and next steps throughout the "
        "investigation."
    ),
    "unknown": (
        "Thank you for reaching out to our support team. We have received your "
        "ticket and are reviewing the details to direct it to the right team. To "
        "help us triage this accurately, could you provide: (1) a brief description "
        "of the expected versus actual behaviour you are observing; and (2) which "
        "part of the product this relates to? If you are able to share any "
        "screenshots or error messages, those would also be very helpful. We will "
        "follow up as soon as we have reviewed your report and thank you for your "
        "patience."
    ),
}


def _parse_input(ticket_input: str | dict[str, Any]) -> tuple[str, str]:
    if isinstance(ticket_input, str):
        text = clean_text(ticket_input)
        if not text:
            raise ValueError("Ticket input is empty")
        return "", text

    if isinstance(ticket_input, dict):
        subject = clean_text(str(
            ticket_input.get("subject",
            ticket_input.get("title",
            ticket_input.get("summary", "")))
        ))
        body = clean_text(str(
            ticket_input.get("body",
            ticket_input.get("description",
            ticket_input.get("message",
            ticket_input.get("text",
            ticket_input.get("content", "")))))
        ))
        if not subject and not body:
            raise ValueError("Ticket input is empty")
        return subject, body

    raise TypeError(f"ticket_input must be str or dict, got {type(ticket_input).__name__}")


def _build_reasoning(
    subject: str,
    body: str,
    product_area: str,
    issue_category: str,
    urgency: str,
    urgency_kws: list[str],
    top_match_path: str | None,
) -> str:
    preview = (f"{subject} {body}".strip())[:100]
    parts = [
        f'The ticket ("{preview}…") indicates a {issue_category} issue in the {product_area} area.'
    ]
    if top_match_path:
        parts.append(f"The top KB match is {top_match_path}.")
    if urgency_kws:
        parts.append(
            f"Urgency set to {urgency} because the text contains: {', '.join(urgency_kws[:4])}."
        )
    else:
        parts.append(f"No strong urgency signals found; defaulted to {urgency}.")
    return " ".join(parts)


def triage_ticket(
    ticket_input: str | dict[str, Any],
    data_dir: str = "data",
    kb_dir: str = "knowledge-base",
    use_fixtures: bool = False,
) -> TriageOutput:
    subject, body = _parse_input(ticket_input)
    query = f"{subject} {body}".strip()

    config = AppConfig(data_dir=data_dir, kb_dir=kb_dir)
    docs = load_knowledge_base(config, use_fixtures=use_fixtures)
    index = KnowledgeBaseIndex(docs)
    results = index.search(query, top_k=3)

    product_area = detect_product_area(query, results)
    issue_category = detect_issue_category(query)
    urgency, urgency_kws = detect_urgency(query)
    team = detect_team(product_area, issue_category, urgency)

    top = results[0] if results else None
    known_issue_match: KnownIssueMatch | None = None
    if top and top.score >= _MIN_MATCH_SCORE:
        known_issue_match = KnownIssueMatch(
            doc_id=top.doc_id,
            path=top.path,
            title=top.title,
            score=round(top.score, 4),
            evidence_snippet=top.evidence_snippet,
        )

    reasoning = _build_reasoning(
        subject, body, product_area, issue_category,
        urgency, urgency_kws,
        top.path if top else None,
    )
    draft = _DRAFT_TEMPLATES.get(product_area, _DRAFT_TEMPLATES["unknown"])

    trace = build_triage_trace(
        subject=subject,
        body=body,
        product_area=product_area,
        issue_category=issue_category,
        urgency=urgency,
        urgency_kws=urgency_kws,
        team=team,
        retrieval_results=results,
    )

    return TriageOutput(
        product_area=product_area,
        issue_category=issue_category,
        urgency_tier=urgency,
        reasoning=reasoning,
        known_issue_match=known_issue_match,
        recommended_team=team,
        draft_first_response=draft,
        trace=trace,
    )
