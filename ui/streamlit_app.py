"""Thin Streamlit demo — ticket triage + account brief with visual trust traces."""
import sys
from pathlib import Path

# Allow running from project root or ui/
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from src.prompts import get_prompt_version
from src.visual_trace import trace_to_markdown, trace_to_mermaid, trace_to_plotly_sankey

st.set_page_config(page_title="Zycus AI Support", layout="wide")

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Zycus AI Support")
    st.markdown("---")
    st.warning(
        "**Fixture mode** is for demo/testing only. "
        "Real submission should use the provided mock dataset when present."
    )
    st.markdown("**Prompt versions**")
    for name in ("triage", "account_brief"):
        try:
            st.caption(f"`{name}`: {get_prompt_version(name)}")
        except Exception:
            st.caption(f"`{name}`: unknown")

# ── tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["Ticket Triage", "Account Brief"])

# ── Tab 1: Ticket Triage ──────────────────────────────────────────────────────
with tab1:
    st.header("Ticket Triage")
    col_in, col_out = st.columns([1, 2])

    with col_in:
        subject = st.text_input("Subject", placeholder="e.g. SSO login broken")
        body = st.text_area("Body", height=150, placeholder="Describe the issue...")
        use_fixtures_t1 = st.checkbox("Use fixtures / demo data", value=True, key="fix_t1")
        run_triage = st.button("Run Triage", type="primary")

    with col_out:
        if run_triage:
            if not body.strip():
                st.error("Body is required.")
            else:
                with st.spinner("Triaging..."):
                    try:
                        from src.triage import triage_ticket
                        result = triage_ticket(
                            {"subject": subject, "body": body},
                            use_fixtures=use_fixtures_t1,
                        )
                    except Exception as exc:
                        st.error(f"Error: {exc}")
                        st.stop()

                # Metric cards
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Product Area", result.product_area)
                m2.metric("Category", result.issue_category)
                m3.metric("Urgency", result.urgency_tier)
                m4.metric("Team", result.recommended_team)

                # Known issue match
                if result.known_issue_match:
                    st.markdown("**Known Issue Match**")
                    km = result.known_issue_match
                    st.info(
                        f"📄 `{km.path}` — score **{km.score}**\n\n"
                        f"*{km.evidence_snippet[:200]}*"
                    )

                # Draft response
                st.markdown("**Draft First Response**")
                st.text_area("", value=result.draft_first_response, height=120, disabled=True, key="draft")

                # Visual trace
                st.markdown("**Evidence Trace**")
                try:
                    import plotly.graph_objects as go
                    data = trace_to_plotly_sankey(result.trace)
                    fig = go.Figure(go.Sankey(
                        node=dict(label=data["node"]["label"], color=data["node"]["color"], pad=15, thickness=20),
                        link=dict(source=data["link"]["source"], target=data["link"]["target"], value=data["link"]["value"]),
                    ))
                    fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    st.code(trace_to_mermaid(result.trace), language="text")

                st.markdown(trace_to_markdown(result.trace))

                with st.expander("Raw JSON"):
                    st.json(result.model_dump())

# ── Tab 2: Account Brief ──────────────────────────────────────────────────────
with tab2:
    st.header("Account Health Brief")
    col_in2, col_out2 = st.columns([1, 2])

    with col_in2:
        account_id = st.text_input("Account ID", placeholder="e.g. ACC-BETA")
        use_fixtures_t2 = st.checkbox("Use fixtures / demo data", value=True, key="fix_t2")
        run_brief = st.button("Generate Brief", type="primary")

    with col_out2:
        if run_brief:
            if not account_id.strip():
                st.error("Account ID is required.")
            else:
                with st.spinner("Generating brief..."):
                    try:
                        from src.account_health import generate_account_brief
                        brief = generate_account_brief(
                            account_id=account_id.strip(),
                            use_fixtures=use_fixtures_t2,
                        )
                    except ValueError as exc:
                        st.error(str(exc))
                        st.stop()
                    except Exception as exc:
                        st.error(f"Error: {exc}")
                        st.stop()

                # Executive summary
                st.markdown("**Executive Summary**")
                for sentence in brief.executive_summary:
                    st.markdown(f"- {sentence}")

                # Risk flags table
                if brief.open_risks_and_flagged_issues:
                    st.markdown("**Risk Flags**")
                    rows = [
                        {
                            "Risk Type": f.risk_type,
                            "Severity": f.severity,
                            "Ticket": f.ticket_id or "—",
                            "Quote": f.quote[:100],
                            "Justification": f.justification,
                        }
                        for f in brief.open_risks_and_flagged_issues
                    ]
                    st.dataframe(rows, use_container_width=True)
                else:
                    st.success("No risk flags detected.")

                # Talking points
                st.markdown("**Recommended Talking Points**")
                for tp in brief.recommended_talking_points:
                    st.markdown(f"- {tp}")

                # Visual trace
                st.markdown("**Evidence Trace**")
                try:
                    import plotly.graph_objects as go
                    data = trace_to_plotly_sankey(brief.trace)
                    fig = go.Figure(go.Sankey(
                        node=dict(label=data["node"]["label"], color=data["node"]["color"], pad=15, thickness=20),
                        link=dict(source=data["link"]["source"], target=data["link"]["target"], value=data["link"]["value"]),
                    ))
                    fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    st.code(trace_to_mermaid(brief.trace), language="text")

                st.markdown(trace_to_markdown(brief.trace))

                with st.expander("Raw JSON"):
                    st.json(brief.model_dump())
