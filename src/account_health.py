from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from src.config import AppConfig
from src.data_loader import load_accounts, load_tickets
from src.kb_index import detect_issue_category
from src.schemas import Account, AccountBrief, RiskFlag, Ticket
from src.text_utils import extract_quote
from src.visual_trace import build_account_trace

_NINETY_DAYS = timedelta(days=90)

_RISK_KEYWORDS: dict[str, list[str]] = {
    "churn_risk": ["churn", "cancel", "leaving", "competitor", "switch", "terminate", "not renew"],
    "executive_escalation": ["ceo", "cto", "vp", "executive", "escalated", "board"],
    "renewal_risk": ["renewal", "contract", "procurement", "qbr", "budget"],
    "severity_or_outage": ["outage", "down", "production blocked", "data loss", "all users"],
    "security_or_compliance": ["security", "breach", "compliance", "audit", "soc2", "gdpr", "pii"],
}

_SEVERITY: dict[str, str] = {
    "churn_risk": "high",
    "executive_escalation": "high",
    "severity_or_outage": "high",
    "security_or_compliance": "high",
    "renewal_risk": "medium",
    "repeated_issue": "medium",
}

_SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


# ── sorting ───────────────────────────────────────────────────────────────────

def _ticket_sort_key(t: Ticket) -> tuple:
    # None dates sort last; otherwise most-recent first
    ts = t.created_at.timestamp() if t.created_at else 0
    return (t.created_at is None, -ts, t.ticket_id)


def _ticket_date_key(ticket_id: str | None, by_id: dict[str, Ticket]) -> tuple:
    if ticket_id is None or ticket_id not in by_id:
        return (True, 0)
    t = by_id[ticket_id]
    ts = t.created_at.timestamp() if t.created_at else 0
    return (t.created_at is None, -ts)


# ── risk detection ────────────────────────────────────────────────────────────

def _detect_risk_flags(tickets: list[Ticket]) -> list[RiskFlag]:
    by_id = {t.ticket_id: t for t in tickets}
    flags: list[RiskFlag] = []
    seen: set[tuple[str, str]] = set()

    for ticket in tickets:
        text = f"{ticket.subject} {ticket.body}"
        lower = text.lower()
        for risk_type, keywords in _RISK_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    key = (risk_type, ticket.ticket_id)
                    if key not in seen:
                        seen.add(key)
                        quote = extract_quote(text, [kw], max_chars=150).strip()
                        flags.append(RiskFlag(
                            risk_type=risk_type,
                            severity=_SEVERITY.get(risk_type, "medium"),  # type: ignore[arg-type]
                            ticket_id=ticket.ticket_id,
                            quote=quote,
                            justification=f"Keyword '{kw}' in ticket {ticket.ticket_id}.",
                        ))
                    break  # one flag per risk_type per ticket

    # Repeated issue: 2+ tickets in the same issue_category
    category_groups: dict[str, list[Ticket]] = {}
    for t in tickets:
        cat = detect_issue_category(f"{t.subject} {t.body}")
        if cat != "unknown":
            category_groups.setdefault(cat, []).append(t)

    for cat, grp in sorted(category_groups.items()):
        if len(grp) >= 2:
            recent = sorted(grp, key=_ticket_sort_key)[0]
            quote = extract_quote(
                f"{recent.subject} {recent.body}", cat.split("_"), max_chars=150
            ).strip()
            key = ("repeated_issue", recent.ticket_id)
            if key not in seen:
                seen.add(key)
                flags.append(RiskFlag(
                    risk_type="repeated_issue",
                    severity="medium",
                    ticket_id=recent.ticket_id,
                    quote=quote,
                    justification=f"2+ tickets in category '{cat}' within 90 days.",
                ))

    # Sort: severity desc → ticket date desc → ticket ID asc
    flags.sort(key=lambda f: (
        _SEV_ORDER.get(f.severity, 3),
        _ticket_date_key(f.ticket_id, by_id),
        f.ticket_id or "",
    ))
    return flags


# ── summary generation ────────────────────────────────────────────────────────

def _top_areas(tickets: list[Ticket]) -> str:
    seen: list[str] = []
    for t in tickets:
        cat = detect_issue_category(f"{t.subject} {t.body}")
        if cat != "unknown" and cat not in seen:
            seen.append(cat)
    return ", ".join(seen[:3]) if seen else "various areas"


def _executive_summary(
    account: Account,
    tickets: list[Ticket],
    flags: list[RiskFlag],
    window_days: int,
) -> list[str]:
    sentences: list[str] = []

    # S1 — account overview
    plan = account.plan or "unspecified plan"
    if account.health_score is not None:
        if account.health_score >= 80:
            health_label = "healthy"
        elif account.health_score >= 60:
            health_label = "at moderate risk"
        else:
            health_label = "at elevated risk"
        sentences.append(
            f"{account.name} is a {plan}-tier account currently rated {health_label} "
            f"(health score: {account.health_score:.0f}/100)."
        )
    else:
        sentences.append(f"{account.name} is a {plan}-tier account with no health score on record.")

    # S2 — ticket volume
    n = len(tickets)
    if n == 0:
        sentences.append(f"No support tickets were recorded in the last {window_days} days.")
    else:
        sentences.append(
            f"Over the last {window_days} days, {n} support ticket{'s were' if n != 1 else ' was'} "
            f"raised, spanning: {_top_areas(tickets)}."
        )

    # S3 — risk summary
    high = [f for f in flags if f.severity == "high"]
    if high:
        risk_labels = list(dict.fromkeys(f.risk_type.replace("_", " ") for f in high))[:3]
        sentences.append(f"High-severity signals detected: {', '.join(risk_labels)}.")
    elif flags:
        sentences.append("No high-severity risks detected; medium-risk signals are present.")
    else:
        sentences.append("No risk flags were identified in the current ticket set.")

    # S4 — churn / renewal context
    if any(f.risk_type in ("churn_risk", "renewal_risk") for f in flags):
        sentences.append(
            "Churn or renewal risk signals require immediate TAM engagement before the next review cycle."
        )
    elif account.renewal_date:
        sentences.append(
            f"Account renewal is scheduled for {account.renewal_date.strftime('%B %Y')}; "
            "proactive outreach is recommended."
        )

    # S5 — closing recommendation (ensure minimum 3 sentences)
    if len(sentences) < 3:
        sentences.append(
            "Recommended action: schedule a TAM check-in to address open issues and reinforce value."
        )

    return sentences[:5]


def _renewal_date_str(account: Account) -> str | None:
    """Read renewal date from the model field or fall back to raw dict."""
    if account.renewal_date:
        return account.renewal_date.strftime("%B %Y")
    raw_val = account.raw.get("renewal_date")
    if raw_val:
        try:
            dt = datetime.fromisoformat(str(raw_val).replace("Z", "+00:00"))
            return dt.strftime("%B %Y")
        except (ValueError, TypeError):
            pass
    return None


def _talking_points(
    account: Account,
    tickets: list[Ticket],
    flags: list[RiskFlag],
) -> list[str]:
    points: list[str] = []
    seen_types: set[str] = set()

    _tp_map: dict[str, str] = {
        "churn_risk": "Address churn risk directly: acknowledge open issues and commit to a resolution timeline.",
        "executive_escalation": "Executive escalation is active — prepare a leadership-level response with status and next steps.",
        "renewal_risk": "Renewal is at risk — schedule a business review to reaffirm value and roadmap alignment.",
        "severity_or_outage": "Confirm the severity incident is fully resolved and deliver a root-cause analysis summary.",
        "security_or_compliance": "Security or compliance concern raised — coordinate with Security team for written assurance.",
        "repeated_issue": "Repeated issue pattern detected — escalate to Engineering for a permanent fix and share ETA.",
    }

    for f in flags:
        if f.risk_type not in seen_types and len(points) < 4:
            seen_types.add(f.risk_type)
            if f.risk_type in _tp_map:
                points.append(_tp_map[f.risk_type])

    if account.health_score is not None and account.health_score < 60:
        points.append(
            f"Health score is {account.health_score:.0f}/100 — co-create an improvement plan with clear milestones."
        )

    renewal = _renewal_date_str(account)
    if renewal:
        points.append(
            f"Renewal date: {renewal} — initiate conversation at least 60 days prior."
        )

    # Guarantee minimum 3 talking points with progressively generic fallbacks
    _fallbacks = [
        "Schedule a quarterly business review to surface value and collect product feedback.",
        "Review open tickets together and confirm resolution timelines with the customer.",
        "Reaffirm the platform roadmap and how upcoming features address the account's stated needs.",
    ]
    for fb in _fallbacks:
        if len(points) >= 3:
            break
        if fb not in points:
            points.append(fb)

    return points[:6]


# ── public API ────────────────────────────────────────────────────────────────

def generate_account_brief(
    account_id: str,
    data_dir: str = "data",
    kb_dir: str = "knowledge-base",
    use_fixtures: bool = False,
    as_of: datetime | None = None,
) -> AccountBrief:
    if not account_id or not account_id.strip():
        raise ValueError("account_id cannot be blank")

    config = AppConfig(data_dir=data_dir, kb_dir=kb_dir)
    all_accounts = load_accounts(config, use_fixtures=use_fixtures)
    all_tickets = load_tickets(config, use_fixtures=use_fixtures)

    account = next((a for a in all_accounts if a.account_id == account_id), None)
    if account is None:
        raise ValueError(f"Account not found: {account_id}")

    account_tickets = [t for t in all_tickets if t.account_id == account_id]

    # Reference time: as_of > max ticket date > now UTC
    if as_of is not None:
        ref_time = as_of
    else:
        dated = [t.created_at for t in account_tickets if t.created_at is not None]
        ref_time = max(dated) if dated else datetime.now(timezone.utc)

    # 90-day window; undated tickets are always included
    cutoff = ref_time - _NINETY_DAYS
    window_tickets: list[Ticket] = []
    for t in account_tickets:
        if t.created_at is None or t.created_at >= cutoff:
            window_tickets.append(t)

    window_tickets.sort(key=_ticket_sort_key)

    flags = _detect_risk_flags(window_tickets)
    summary = _executive_summary(account, window_tickets, flags, 90)
    tp = _talking_points(account, window_tickets, flags)
    trace = build_account_trace(account, window_tickets, flags)

    return AccountBrief(
        account_id=account_id,
        executive_summary=summary,
        open_risks_and_flagged_issues=flags,
        recommended_talking_points=tp,
        trace=trace,
    )
