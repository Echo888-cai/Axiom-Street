from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from quant.data.ingest import prune_unreferenced_snapshots
from services.api.hashing import canonical_hash
from services.api.models import StrategyStatus
from services.api.status_machine import assert_client_status_transition


def test_canonical_hash_is_stable_under_key_order():
    a = canonical_hash({"b": 1, "a": 2})
    b = canonical_hash({"a": 2, "b": 1})
    assert a == b
    assert len(a) == 64


def test_canonical_hash_changes_with_value():
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


def test_client_cannot_set_validated():
    with pytest.raises(HTTPException) as exc:
        assert_client_status_transition(StrategyStatus.DRAFT, StrategyStatus.VALIDATED)
    assert exc.value.status_code == 409


def test_client_cannot_set_live():
    with pytest.raises(HTTPException) as exc:
        assert_client_status_transition(StrategyStatus.BACKTESTED, StrategyStatus.LIVE)
    assert exc.value.status_code == 409


def test_client_can_archive_draft():
    assert_client_status_transition(StrategyStatus.DRAFT, StrategyStatus.ARCHIVED)


def test_same_status_is_noop():
    assert_client_status_transition(StrategyStatus.VALIDATED, StrategyStatus.VALIDATED)


def test_prune_unreferenced_snapshots(tmp_path: Path):
    snaps = tmp_path / "snapshots"
    keep = snaps / "keep-me"
    drop = snaps / "drop-me"
    keep.mkdir(parents=True)
    drop.mkdir()
    (keep / "x").write_text("1")
    removed = prune_unreferenced_snapshots(tmp_path, {"keep-me"})
    assert "drop-me" in removed
    assert keep.exists()
    assert not drop.exists()
