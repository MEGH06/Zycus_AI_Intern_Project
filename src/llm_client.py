from __future__ import annotations

from typing import Any


class LLMClient:
    """Base class for LLM backends. All subclasses must implement complete_json."""

    def complete_json(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class LocalHeuristicLLMClient(LLMClient):
    """Deterministic offline client. Uses classification primitives — no API calls.

    Used by tests and as the fallback when no LLM key is configured.
    """

    def complete_json(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        from src.kb_index import (
            detect_issue_category,
            detect_product_area,
            detect_team,
            detect_urgency,
        )
        from src.text_utils import extract_quote

        text = " ".join(str(v) for v in user_payload.values() if isinstance(v, str))
        product_area = detect_product_area(text, [])
        issue_category = detect_issue_category(text)
        urgency, matched_kws = detect_urgency(text)
        team = detect_team(product_area, issue_category, urgency)
        snippet = extract_quote(text, matched_kws or text.split()[:4], max_chars=120)

        return {
            "_mode": "local_heuristic",
            "product_area": product_area,
            "issue_category": issue_category,
            "urgency_tier": urgency,
            "reasoning": f"Local rules matched keywords: {matched_kws}",
            "recommended_team": team,
            "draft_first_response": (
                f"Thank you for reaching out. We have received your ticket and our "
                f"{team} team will review it as a {urgency} priority."
            ),
            "evidence_snippet": snippet,
        }


# TODO: GroqLLMClient and OpenAILLMClient — wired in Task 1/2 sessions.
# Both must pass temperature=0 and validate JSON output before returning.


def get_llm_client(config: Any) -> LLMClient:
    """Return the appropriate LLM client based on config."""
    provider = getattr(config, "llm_provider", "local")
    api_key = getattr(config, "active_api_key", None)

    if provider == "local" or not api_key:
        return LocalHeuristicLLMClient()

    # Groq and OpenAI clients will be added in Task 1 session.
    return LocalHeuristicLLMClient()
