"""Tests for visual_trace functions — all offline."""
from src.account_health import generate_account_brief
from src.triage import triage_ticket
from src.visual_trace import trace_to_markdown, trace_to_mermaid, trace_to_plotly_sankey


def _triage_trace() -> dict:
    r = triage_ticket(
        {"subject": "SSO login broken", "body": "Users cannot sign in via SSO."},
        use_fixtures=True,
    )
    return r.trace


def _account_trace() -> dict:
    b = generate_account_brief("ACC-BETA", use_fixtures=True)
    return b.trace


# 1. Triage trace → Mermaid contains "flowchart TD"
def test_triage_mermaid_contains_flowchart():
    mermaid = trace_to_mermaid(_triage_trace())
    assert mermaid.startswith("flowchart TD")


# 2. Account trace → Mermaid contains "flowchart TD"
def test_account_mermaid_contains_flowchart():
    mermaid = trace_to_mermaid(_account_trace())
    assert mermaid.startswith("flowchart TD")


# 3. Sankey data has "node" and "link" keys
def test_triage_sankey_has_node_and_link():
    data = trace_to_plotly_sankey(_triage_trace())
    assert "node" in data
    assert "link" in data


def test_account_sankey_has_node_and_link():
    data = trace_to_plotly_sankey(_account_trace())
    assert "node" in data
    assert "link" in data


# 4. Sankey sources/targets same length
def test_sankey_link_lengths_match():
    for trace in (_triage_trace(), _account_trace()):
        data = trace_to_plotly_sankey(trace)
        assert len(data["link"]["source"]) == len(data["link"]["target"])
        assert len(data["link"]["source"]) == len(data["link"]["value"])


# 5. Account trace markdown contains risk flag quote
def test_account_markdown_contains_quote():
    md = trace_to_markdown(_account_trace())
    assert "cancel" in md.lower() or "churn" in md.lower() or "|" in md


# 6. Triage trace markdown contains evidence table
def test_triage_markdown_contains_decisions():
    md = trace_to_markdown(_triage_trace())
    assert "product_area" in md or "Evidence" in md


# 7. Mermaid node IDs are alphanumeric only
def test_mermaid_node_ids_alphanumeric():
    import re
    for trace in (_triage_trace(), _account_trace()):
        mermaid = trace_to_mermaid(trace)
        # Extract node definitions: lines like "    X[..." or "    XY[..."
        node_ids = re.findall(r'^\s+([A-Z][A-Z0-9_]*)\[', mermaid, re.MULTILINE)
        for nid in node_ids:
            assert re.fullmatch(r'[A-Z][A-Z0-9_]*', nid), f"Invalid node ID: {nid}"
