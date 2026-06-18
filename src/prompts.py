from __future__ import annotations

import os

PROMPT_VERSIONS: dict[str, dict[str, str]] = {
    "triage": {
        "version": "triage_v1",
        "path": "prompts/triage_v1.md",
    },
    "account_brief": {
        "version": "account_brief_v1",
        "path": "prompts/account_brief_v1.md",
    },
}

_cache: dict[str, str] = {}


def get_prompt(name: str) -> str:
    if name not in PROMPT_VERSIONS:
        raise KeyError(f"Unknown prompt name '{name}'. Available: {list(PROMPT_VERSIONS)}")
    if name in _cache:
        return _cache[name]
    path = PROMPT_VERSIONS[name]["path"]
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file not found: '{path}'")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    _cache[name] = text
    return text


def get_prompt_version(name: str) -> str:
    if name not in PROMPT_VERSIONS:
        raise KeyError(f"Unknown prompt name '{name}'. Available: {list(PROMPT_VERSIONS)}")
    return PROMPT_VERSIONS[name]["version"]
