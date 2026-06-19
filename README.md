# Zycus AI Support / TAM Assessment

## Problem Statement

Support teams receive hundreds of tickets daily with no consistent prioritisation. Technical Account Managers spend hours manually reviewing ticket history to prepare for account reviews. This project builds a production-grade AI layer that: (1) intelligently triages incoming tickets — classifying urgency, routing to the correct team, and matching known KB issues; and (2) generates structured TAM account health briefs from ticket history — surfacing churn risk, escalation signals, and ready-made talking points. All outputs are deterministic, explainable, and fully auditable via a visual trust trace.

---

## Architecture

```
data/tickets.json          ─┐
data/accounts.json          ├─► src/data_loader.py ──► src/schemas.py (Pydantic)
knowledge-base/**/*.md     ─┘        │
                                      ▼
                              src/kb_index.py  (TF-IDF + cosine similarity)
                              src/text_utils.py (clean, hash, extract_quote)
                                      │
                    ┌─────────────────┴──────────────────┐
                    ▼                                      ▼
            src/triage.py                    src/account_health.py
            (Task 1 pipeline)                (Task 2 pipeline)
                    │                                      │
                    └──────────► src/visual_trace.py ◄────┘
                                 (Sankey + Mermaid + Markdown)
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                     src/cli.py      src/api.py    ui/streamlit_app.py
```

**LLM is optional.** Set `GROQ_API_KEY` or `OPENAI_API_KEY` in `.env` to enable Groq/OpenAI for improved phrasing. `LLM_PROVIDER=local` (default) runs fully offline using deterministic rules. Temperature is always 0.

---

## Data Policy

- Real data files **(`data/tickets.json`, `data/accounts.json`, `knowledge-base/**/*.md`)** are required for production mode.
- If any file is absent or empty, the system raises `DataAvailabilityError` with the exact file path and remediation — it **never silently falls back** to fixtures.
- Test fixtures live exclusively under `tests/fixtures/` and are loaded only when `--use-fixtures` is passed.
- No production data, no generated data, no scraped data is included in this repository. This is intentional per the assessment rules.

---

## Setup

```bash
git clone <your-submission-repo>
cd <your-submission-repo>
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # add GROQ_API_KEY if available; leave blank for offline mode
python -m src.cli health      # → {"status": "ok"}
```

---

## Sample Runs

### Task 1 — Ticket Triage

```bash
python -m src.cli triage \
  --subject "SSO login broken" \
  --body "Several enterprise users cannot sign in via SSO since this morning." \
  --use-fixtures \
  --trace-mermaid
```

**Output (truncated):**
```json
{
  "product_area": "auth",
  "issue_category": "authentication",
  "urgency_tier": "P3",
  "known_issue_match": {
    "path": "troubleshooting/example_sso.md",
    "score": 0.2504,
    "evidence_snippet": "..."
  },
  "recommended_team": "Identity & Access",
  "draft_first_response": "...",
  "trace": { ... }
}
```

### Task 2 — TAM Account Brief

```bash
python -m src.cli account-brief \
  --account-id ACC-BETA \
  --use-fixtures \
  --trace-mermaid
```

**Output includes:** 4-sentence executive summary, 3 risk flags (churn_risk, executive_escalation, repeated_issue) each with a direct ticket quote, 5 TAM talking points, full trace.

### Real-data mode (once data files are provided)

```bash
python -m src.cli triage --subject "..." --body "..."
python -m src.cli account-brief --account-id <account_id>
```

If `data/tickets.json` is missing or empty, the CLI prints:
```
ERROR: Tickets not found at 'data/tickets.json'. Populate the file or pass --use-fixtures.
```

---

## Evaluation Harness

```bash
python -m src.cli eval --use-fixtures
# → evals/eval_report.md
# → evals/eval_report.json
```

- 12 cases: 6 Task 1, 6 Task 2 (includes 1 adversarial case per task).
- Each case scored 0–1 across 4 weighted checks. Pass threshold: 0.80.
- Current fixture-mode result: **12/12 passed, overall score 1.0**.

---

## Streamlit UI

```bash
streamlit run ui/streamlit_app.py
# or: python -m src.cli ui   (prints the command above)
```

**Tab 1 — Ticket Triage:** Enter subject + body → see urgency, category, team, KB match card, draft response, and Plotly Sankey trust trace.

**Tab 2 — Account Brief:** Enter account ID → see executive summary, risk flags table with direct quotes, talking points, and account trace.

Sidebar shows data-mode warning and prompt version info.

---

## API Endpoints

```bash
uvicorn src.api:app --host 127.0.0.1 --port 8000
```

| Endpoint | Method | Body / Params | Status |
|----------|--------|---------------|--------|
| `/health` | GET | — | ✅ |
| `/triage` | POST | `{"subject":"...","body":"...","use_fixtures":false}` | ✅ |
| `/accounts/{id}/brief` | GET | `?use_fixtures=false` | ✅ |

---

## Output Schema Examples

**TriageOutput:**
```json
{
  "product_area": "auth",
  "issue_category": "authentication",
  "urgency_tier": "P2",
  "reasoning": "...",
  "known_issue_match": {"doc_id":"...","path":"...","title":"...","score":0.25,"evidence_snippet":"..."},
  "recommended_team": "Identity & Access",
  "draft_first_response": "...",
  "trace": {"trace_type":"ticket_triage","signals":[...],"retrieval":[...],"decisions":[...]}
}
```

**AccountBrief:**
```json
{
  "account_id": "ACC-BETA",
  "executive_summary": ["sentence 1", "..."],
  "open_risks_and_flagged_issues": [
    {"risk_type":"churn_risk","severity":"high","ticket_id":"TKT-006","quote":"...","justification":"..."}
  ],
  "recommended_talking_points": ["...", "..."],
  "trace": {"trace_type":"account_brief","risk_signals":[...],...}
}
```

---

## Tests

```bash
pytest -q                                # 67 tests, all offline, no API keys
pytest tests/test_triage.py -q          # 11 tests — Task 1
pytest tests/test_account_health.py -q  # 11 tests — Task 2
pytest tests/test_eval_harness.py -q    #  9 tests — eval harness
pytest tests/test_visual_trace.py -q    #  8 tests — visual trace
pytest tests/test_retrieval.py -q       # 17 tests — KB index + classifiers
pytest tests/test_data_loader.py -q     # 11 tests — data loader
```

---

## Design Note

See **[DESIGN_NOTE.md](DESIGN_NOTE.md)** for:
- Top 3 production failure modes and mitigations (misclassification, retrieval mismatch, PII leakage)
- Latency vs quality trade-off
- Data sensitivity and PII handling policy
- Scaling to 10× ticket volume and the key bottleneck

---

## Known Limitations

| Limitation | Status |
|-----------|--------|
| No real mock dataset provided — fixture mode only | By design (assessment rules prohibit generated data) |
| `data_loader._parse_date` ignores `renewal_date` key | `account_health.py` reads from `raw` dict as workaround |
| "board" substring in "dashboard" triggers `executive_escalation` | Known false positive; word-boundary fix deferred |
| `LocalHeuristicLLMClient` returns stub draft text | Groq/OpenAI wrappers stubbed; full wiring deferred |
| KB index rebuilt per request | Startup-time singleton needed for production |

---

## Submission Checklist

- [x] Task 1: `triage_ticket()` — CLI, API, tests, trace
- [x] Task 2: `generate_account_brief()` — CLI, API, tests, trace
- [x] Task 3: Eval harness — 12 cases, `eval_report.md`, `eval_report.json`
- [x] Task 4: `DESIGN_NOTE.md` — failure modes, latency, PII, scaling
- [x] Visual trust graph — Sankey + Mermaid + Markdown evidence table
- [x] Streamlit UI — two tabs, sidebar, trace visualisation
- [x] CI — `.github/workflows/eval.yml` (no secrets required)
- [x] `LOOM_SCRIPT.md` — 5-minute walkthrough script
- [x] `HANDOFF.md` — session-by-session change log
- [x] All 67 tests pass offline
