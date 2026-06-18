# Prompts Changelog

## triage_v1 — initial release
- Urgency tiers P1–P4 with keyword examples.
- Requires JSON-only output.
- `known_issue_match` nulled when score < 0.1.
- Trace block includes `prompt_version`, `kb_results_used`, `urgency_keywords_matched`.

## account_brief_v1 — initial release
- Executive summary constrained to 3–5 sentences.
- Every risk flag requires a direct verbatim quote.
- Trace block includes `prompt_version`, `tickets_analyzed`, `health_score`.
