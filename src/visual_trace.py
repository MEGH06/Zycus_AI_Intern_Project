from __future__ import annotations

from typing import Any

from src.kb_index import RetrievalResult


# ── triage trace ──────────────────────────────────────────────────────────────

def build_triage_trace(
    subject: str,
    body: str,
    product_area: str,
    issue_category: str,
    urgency: str,
    urgency_kws: list[str],
    team: str,
    retrieval_results: list[RetrievalResult],
) -> dict[str, Any]:
    text = f"{subject} {body}".strip()
    signals: list[str] = list(urgency_kws[:4])
    lower = text.lower()
    for kw in ("sso", "saml", "invoice", "sync", "dashboard", "login", "cancel", "outage"):
        if kw in lower and kw not in signals:
            signals.append(kw)

    return {
        "trace_type": "ticket_triage",
        "input_summary": text[:100] + ("…" if len(text) > 100 else ""),
        "signals": signals[:8],
        "retrieval": [
            {"path": r.path, "score": round(r.score, 4), "snippet": r.evidence_snippet[:100]}
            for r in retrieval_results
        ],
        "decisions": [
            {"name": "product_area", "value": product_area, "evidence": "keyword match in ticket text"},
            {"name": "issue_category", "value": issue_category, "evidence": "keyword match in ticket text"},
            {
                "name": "urgency_tier",
                "value": urgency,
                "evidence": f"matched: {urgency_kws[:3]}" if urgency_kws else "default rule",
            },
            {
                "name": "recommended_team",
                "value": team,
                "evidence": f"mapped from product_area={product_area}, issue_category={issue_category}",
            },
        ],
    }


# ── account brief trace ───────────────────────────────────────────────────────

def build_account_trace(account: Any, tickets: list[Any], flags: list[Any]) -> dict[str, Any]:
    undated = sum(1 for t in tickets if t.created_at is None)
    return {
        "trace_type": "account_brief",
        "account_id": account.account_id,
        "account_snapshot": {
            "name": account.name,
            "plan": account.plan,
            "health_score": account.health_score,
        },
        "ticket_window": {
            "days": 90,
            "ticket_count": len(tickets),
            "undated_count": undated,
        },
        "risk_signals": [
            {
                "risk_type": f.risk_type,
                "ticket_id": f.ticket_id,
                "quote": f.quote[:100],
                "trigger": f.justification[:80],
            }
            for f in flags
        ],
        "sections_generated": [
            "executive_summary",
            "open_risks_and_flagged_issues",
            "recommended_talking_points",
        ],
    }


# ── mermaid renderer ──────────────────────────────────────────────────────────

def to_mermaid(trace: dict[str, Any]) -> str:
    if trace.get("trace_type") == "account_brief":
        return _account_mermaid(trace)
    return _triage_mermaid(trace)


def _triage_mermaid(trace: dict[str, Any]) -> str:
    lines = ["flowchart TD"]
    lines.append(f'    A["Input: {_esc(trace.get("input_summary", "")[:55])}"]')

    retrieval = trace.get("retrieval", [])
    if retrieval:
        top = retrieval[0]
        lines.append(f'    B["KB: {_esc(top["path"])} score={top["score"]}"]')
    else:
        lines.append('    B["KB: no match"]')
    lines.append("    A --> B")

    prev = "B"
    for i, decision in enumerate(trace.get("decisions", [])):
        node = "CDEFGHIJ"[i] if i < 8 else f"N{i}"
        lines.append(f'    {node}["{decision["name"]}: {_esc(str(decision["value"]))}"]')
        lines.append(f"    {prev} --> {node}")
        prev = node

    lines.append('    Z[/"TriageOutput"/]')
    lines.append(f"    {prev} --> Z")
    return "\n".join(lines)


def _account_mermaid(trace: dict[str, Any]) -> str:
    lines = ["flowchart TD"]
    snap = trace.get("account_snapshot", {})
    acct_id = _esc(trace.get("account_id", ""))
    lines.append(f'    A["Account: {acct_id} | plan={_esc(str(snap.get("plan","?")))} | health={snap.get("health_score","?")}"]')

    tw = trace.get("ticket_window", {})
    lines.append(f'    B["Ticket window: {tw.get("ticket_count",0)} tickets / 90 days ({tw.get("undated_count",0)} undated)"]')
    lines.append("    A --> B")

    risk_signals = trace.get("risk_signals", [])
    if risk_signals:
        lines.append(f'    C["Risk signals: {len(risk_signals)} flag(s) detected"]')
        lines.append("    B --> C")
        prev = "C"
    else:
        lines.append('    C["Risk signals: none"]')
        lines.append("    B --> C")
        prev = "C"

    sections = trace.get("sections_generated", [])
    node_letters = "DEFGHIJ"
    for i, section in enumerate(sections):
        node = node_letters[i] if i < len(node_letters) else f"S{i}"
        lines.append(f'    {node}["{_esc(section)}"]')
        lines.append(f"    {prev} --> {node}")
        prev = node

    lines.append('    Z[/"AccountBrief"/]')
    lines.append(f"    {prev} --> Z")
    return "\n".join(lines)


def _esc(s: str) -> str:
    return s.replace('"', "'").replace("\n", " ")


# ── public alias with sanitised IDs ──────────────────────────────────────────
# Node IDs are single letters (A-Z) — already alphanumeric, no sanitisation needed.

def trace_to_mermaid(trace: dict[str, Any]) -> str:
    """Return Mermaid flowchart text. Node IDs are alphanumeric/underscore only."""
    return to_mermaid(trace)


# ── Plotly Sankey data (no Plotly import here) ────────────────────────────────

def trace_to_plotly_sankey(trace: dict[str, Any]) -> dict[str, Any]:
    """Return Plotly Sankey figure data dict with 'node' and 'link' keys."""
    if trace.get("trace_type") == "ticket_triage":
        decisions = trace.get("decisions", [])
        retrieval = trace.get("retrieval", [])
        kb_label = retrieval[0]["path"] if retrieval else "no KB match"

        labels = (
            ["Input"]
            + [f"KB: {kb_label[:30]}"]
            + [f"{d['name']}: {d['value']}" for d in decisions]
            + ["TriageOutput"]
        )
        n = len(labels)
        colors = (
            ["#4C78A8", "#F28E2B"]
            + ["#72B7B2"] * len(decisions)
            + ["#54A24B"]
        )
    else:
        snap = trace.get("account_snapshot", {})
        tw = trace.get("ticket_window", {})
        risk_signals = trace.get("risk_signals", [])
        sections = trace.get("sections_generated", [])

        labels = (
            [f"Account: {trace.get('account_id','')}"]
            + [f"Tickets ({tw.get('ticket_count',0)})"]
            + [f"Risk signals ({len(risk_signals)})"]
            + [s.replace("_", " ") for s in sections]
            + ["AccountBrief"]
        )
        n = len(labels)
        colors = (
            ["#4C78A8", "#72B7B2", "#F58518"]
            + ["#54A24B"] * len(sections)
            + ["#B07AA1"]
        )

    sources = list(range(n - 1))
    targets = list(range(1, n))
    return {
        "node": {"label": labels, "color": colors[:n]},
        "link": {"source": sources, "target": targets, "value": [1] * (n - 1)},
    }


# ── Markdown evidence table ───────────────────────────────────────────────────

def trace_to_markdown(trace: dict[str, Any]) -> str:
    """Return readable evidence table markdown."""
    lines: list[str] = []

    if trace.get("trace_type") == "ticket_triage":
        lines += [
            "### Evidence Trace",
            f"\n**Input:** {trace.get('input_summary', '')}",
            "",
        ]
        signals = trace.get("signals", [])
        if signals:
            lines.append(f"**Signals:** {', '.join(signals)}\n")

        retrieval = trace.get("retrieval", [])
        if retrieval:
            lines += ["**KB Retrieval**", "", "| Document | Score | Snippet |", "|----------|-------|---------|"]
            for r in retrieval:
                lines.append(f"| `{r['path']}` | {r['score']} | {r.get('snippet','')[:70].replace(chr(10),' ')} |")
            lines.append("")

        decisions = trace.get("decisions", [])
        if decisions:
            lines += ["**Decisions**", "", "| Field | Value | Evidence |", "|-------|-------|----------|"]
            for d in decisions:
                lines.append(f"| {d['name']} | **{d['value']}** | {d['evidence']} |")

    else:  # account_brief
        snap = trace.get("account_snapshot", {})
        tw = trace.get("ticket_window", {})
        lines += [
            "### Account Evidence Trace",
            f"\n**Account:** {trace.get('account_id','')} | Plan: {snap.get('plan','?')} | Health: {snap.get('health_score','?')}",
            f"**Ticket window:** {tw.get('ticket_count',0)} tickets / {tw.get('days',90)} days ({tw.get('undated_count',0)} undated)\n",
        ]
        risk_signals = trace.get("risk_signals", [])
        if risk_signals:
            lines += ["**Risk Signals**", "", "| Risk Type | Ticket | Quote |", "|-----------|--------|-------|"]
            for r in risk_signals:
                quote = r.get("quote", "")[:70].replace("\n", " ")
                lines.append(f"| {r['risk_type']} | {r.get('ticket_id','?')} | {quote} |")

    return "\n".join(lines)
