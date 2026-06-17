from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import AppConfig
from src.schemas import Account, KnowledgeDoc, Ticket
from src.text_utils import clean_text, stable_hash


class DataAvailabilityError(Exception):
    pass


class DataFormatError(Exception):
    pass


# ── internal helpers ──────────────────────────────────────────────────────────

def _first(d: dict, keys: list[str], default: Any = None) -> Any:
    for k in keys:
        if k in d:
            return d[k]
    return default


def _extract_ticket_id(raw: dict, subject: str, body: str) -> str:
    for k in ("ticket_id", "id", "case_id"):
        val = raw.get(k)
        if val is not None and str(val).strip():
            return str(val)
    return stable_hash(subject + body, "TKT")


def _extract_account_id(raw: dict) -> str | None:
    for k in ("account_id", "customer_id", "id"):
        val = raw.get(k)
        if val is not None and str(val).strip():
            return str(val)
    nested = raw.get("account")
    if isinstance(nested, dict):
        name = nested.get("name")
        if name:
            return stable_hash(str(name), "ACC")
    return None


def _parse_date(raw: dict) -> datetime | None:
    for k in ("created_at", "created", "timestamp", "date"):
        val = raw.get(k)
        if val:
            try:
                return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
    return None


def _normalize_list(data: Any, list_keys: tuple[str, ...] = ("tickets", "data", "items")) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in list_keys:
            if k in data and isinstance(data[k], list):
                return data[k]
        return [data]  # single-object — valid only in fixture contexts
    raise DataFormatError(f"Unsupported root JSON structure: {type(data).__name__}")


def _load_json(path: str, label: str) -> Any:
    if not os.path.exists(path):
        raise DataAvailabilityError(
            f"{label} not found at '{path}'. "
            "Populate the file or pass use_fixtures=True for test data."
        )
    if os.stat(path).st_size == 0:
        raise DataAvailabilityError(
            f"{label} exists but is empty at '{path}'. Add real data to proceed."
        )
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise DataFormatError(f"{label} at '{path}' is not valid JSON: {exc}") from exc


# ── public loaders ────────────────────────────────────────────────────────────

def load_tickets(config: AppConfig, use_fixtures: bool = False) -> list[Ticket]:
    if use_fixtures:
        path = str(Path(__file__).parent.parent / "tests" / "fixtures" / "tickets_fixture.json")
        label = "Fixture tickets"
    else:
        path = os.path.join(config.data_dir, "tickets.json")
        label = "Tickets"

    rows = _normalize_list(_load_json(path, label), ("tickets", "data", "items"))
    tickets: list[Ticket] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        subject = clean_text(str(_first(row, ["subject", "title", "summary"], "")))
        body = clean_text(str(_first(row, ["body", "description", "message", "text", "content"], "")))
        if not subject and not body:
            body = json.dumps(row, separators=(",", ":"))
        tickets.append(Ticket(
            ticket_id=_extract_ticket_id(row, subject, body),
            account_id=_extract_account_id(row),
            subject=subject,
            body=body,
            created_at=_parse_date(row),
            status=row.get("status"),
            product_area=row.get("product_area"),
            raw=row,
        ))
    return tickets


def load_accounts(config: AppConfig, use_fixtures: bool = False) -> list[Account]:
    if use_fixtures:
        path = str(Path(__file__).parent.parent / "tests" / "fixtures" / "accounts_fixture.json")
        label = "Fixture accounts"
    else:
        path = os.path.join(config.data_dir, "accounts.json")
        label = "Accounts"

    rows = _normalize_list(_load_json(path, label), ("accounts", "data", "items"))
    accounts: list[Account] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        acc_id = _extract_account_id(row) or stable_hash(
            json.dumps(row, sort_keys=True), "ACC"
        )
        health = row.get("health_score")
        try:
            health = float(health) if health is not None else None
        except (ValueError, TypeError):
            health = None
        accounts.append(Account(
            account_id=acc_id,
            name=str(row.get("name", row.get("account_name", "Unknown Account"))),
            plan=row.get("plan"),
            segment=row.get("segment"),
            renewal_date=_parse_date(row),
            health_score=health,
            raw=row,
        ))
    return accounts


def load_knowledge_base(config: AppConfig, use_fixtures: bool = False) -> list[KnowledgeDoc]:
    if use_fixtures:
        kb_dir = str(
            Path(__file__).parent.parent / "tests" / "fixtures" / "knowledge-base-fixture"
        )
        label = "Fixture KB"
    else:
        kb_dir = config.kb_dir
        label = "Knowledge base"

    if not os.path.isdir(kb_dir):
        raise DataAvailabilityError(
            f"{label} directory not found at '{kb_dir}'. "
            "Create 'knowledge-base/' with .md files or pass use_fixtures=True."
        )

    docs: list[KnowledgeDoc] = []
    for root, _, files in os.walk(kb_dir):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            if os.stat(fpath).st_size == 0:
                continue
            with open(fpath, encoding="utf-8") as f:
                text = f.read().strip()
            if not text:
                continue
            lines = text.splitlines()
            title = fname.replace(".md", "").replace("_", " ").title()
            for line in lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            rel = os.path.relpath(fpath, kb_dir).replace("\\", "/")
            parts = rel.split("/")
            product_area = parts[0] if len(parts) > 1 else None
            docs.append(KnowledgeDoc(
                doc_id=stable_hash(rel, "KB"),
                path=rel,
                title=title,
                product_area=product_area,
                text=text,
            ))

    if not docs:
        raise DataAvailabilityError(
            f"{label} at '{kb_dir}' has no non-empty .md files. "
            "Add articles or pass use_fixtures=True."
        )
    return docs
