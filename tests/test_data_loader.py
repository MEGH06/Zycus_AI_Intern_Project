"""Tests for src/data_loader — all offline, no LLM calls."""
import json
import os
import tempfile

import pytest

from src.config import AppConfig
from src.data_loader import (
    DataAvailabilityError,
    DataFormatError,
    load_accounts,
    load_knowledge_base,
    load_tickets,
)

# ── fixture config (points at tests/fixtures/) ───────────────────────────────

FIXTURE_CONFIG = AppConfig()  # data_dir/kb_dir don't matter when use_fixtures=True


# ── fixture loading ───────────────────────────────────────────────────────────

def test_load_tickets_fixtures_succeeds():
    tickets = load_tickets(FIXTURE_CONFIG, use_fixtures=True)
    assert len(tickets) == 6


def test_load_accounts_fixtures_succeeds():
    accounts = load_accounts(FIXTURE_CONFIG, use_fixtures=True)
    assert len(accounts) == 2


def test_load_kb_fixtures_succeeds():
    docs = load_knowledge_base(FIXTURE_CONFIG, use_fixtures=True)
    assert len(docs) == 2


# ── stable IDs ────────────────────────────────────────────────────────────────

def test_ticket_ids_are_stable():
    t1 = load_tickets(FIXTURE_CONFIG, use_fixtures=True)
    t2 = load_tickets(FIXTURE_CONFIG, use_fixtures=True)
    assert [t.ticket_id for t in t1] == [t.ticket_id for t in t2]


def test_account_ids_are_stable():
    a1 = load_accounts(FIXTURE_CONFIG, use_fixtures=True)
    a2 = load_accounts(FIXTURE_CONFIG, use_fixtures=True)
    assert [a.account_id for a in a1] == [a.account_id for a in a2]


# ── real mode does NOT silently fall back to fixtures ─────────────────────────

def test_real_mode_fails_when_data_missing():
    cfg = AppConfig(data_dir="data")
    with pytest.raises(DataAvailabilityError):
        load_tickets(cfg, use_fixtures=False)


def test_real_mode_kb_fails_when_dir_missing():
    cfg = AppConfig(kb_dir="knowledge-base")
    with pytest.raises(DataAvailabilityError):
        load_knowledge_base(cfg, use_fixtures=False)


# ── empty JSON raises DataAvailabilityError ───────────────────────────────────

def test_empty_json_raises_data_availability_error():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write("")
        path = f.name
    try:
        cfg = AppConfig(data_dir=os.path.dirname(path))
        # Patch the path directly via a mini config
        from src.data_loader import _load_json
        with pytest.raises(DataAvailabilityError):
            _load_json(path, "Test file")
    finally:
        os.unlink(path)


# ── malformed JSON raises DataFormatError ────────────────────────────────────

def test_malformed_json_raises_data_format_error():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write("{not valid json")
        path = f.name
    try:
        from src.data_loader import _load_json
        with pytest.raises(DataFormatError):
            _load_json(path, "Test file")
    finally:
        os.unlink(path)


# ── empty KB dir raises DataAvailabilityError ─────────────────────────────────

def test_empty_kb_dir_raises_data_availability_error():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = AppConfig(kb_dir=tmp)
        with pytest.raises(DataAvailabilityError):
            load_knowledge_base(cfg, use_fixtures=False)


# ── normalization: dict root with known key ───────────────────────────────────

def test_normalization_handles_dict_root_with_tickets_key():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump({"tickets": [{"ticket_id": "X-1", "subject": "Test", "body": "Body"}]}, f)
        path = f.name
    try:
        cfg = AppConfig(data_dir=os.path.dirname(path))
        # Rename file to tickets.json inside a temp data dir
        dest = os.path.join(os.path.dirname(path), "tickets.json")
        os.rename(path, dest)
        tickets = load_tickets(cfg, use_fixtures=False)
        assert len(tickets) == 1
        assert tickets[0].ticket_id == "X-1"
    finally:
        if os.path.exists(dest):
            os.unlink(dest)
