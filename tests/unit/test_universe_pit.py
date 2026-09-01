from __future__ import annotations

from datetime import date

import pytest

from quant.data.universe import (
    LEAN_OPEN_ENDED,
    Membership,
    constituents_as_of,
    constituents_overlapping,
    infer_effective_to_from_bars,
    lean_map_file_text,
    validate_memberships,
    write_lean_map_files,
)


def _m(symbol: str, start: str, end: str | None = None) -> Membership:
    return Membership(
        symbol=symbol,
        effective_from=date.fromisoformat(start),
        effective_to=date.fromisoformat(end) if end else None,
    )


def test_contains_inclusive_bounds():
    member = _m("BBBY", "2010-01-04", "2018-03-23")
    assert member.contains(date(2010, 1, 4))
    assert member.contains(date(2018, 3, 23))
    assert not member.contains(date(2018, 3, 24))
    assert not member.contains(date(2009, 12, 31))


def test_open_ended_membership_stays_active():
    member = _m("SPY", "2010-01-04")
    assert member.contains(date(2026, 8, 31))


def test_delisted_symbol_absent_after_effective_to():
    members = [_m("SPY", "2010-01-01"), _m("BBBY", "2010-01-01", "2018-03-23")]
    assert constituents_as_of(members, date(2018, 3, 23)) == ["SPY", "BBBY"]
    assert constituents_as_of(members, date(2018, 3, 24)) == ["SPY"]


def test_overlapping_window_includes_delisted_during_window():
    members = [_m("SPY", "2010-01-01"), _m("BBBY", "2010-01-01", "2018-03-23")]
    assert constituents_overlapping(members, date(2018, 1, 1), date(2020, 12, 31)) == [
        "SPY",
        "BBBY",
    ]
    assert constituents_overlapping(members, date(2019, 1, 1), date(2020, 12, 31)) == ["SPY"]


def test_validate_rejects_inverted_dates():
    with pytest.raises(ValueError, match="早于"):
        validate_memberships([_m("X", "2020-01-02", "2020-01-01")])


def test_validate_rejects_overlapping_same_symbol():
    with pytest.raises(ValueError, match="重叠"):
        validate_memberships(
            [_m("X", "2010-01-01", "2015-12-31"), _m("X", "2015-06-01", "2020-01-01")]
        )


def test_adjacent_intervals_are_allowed():
    validate_memberships([_m("X", "2010-01-01", "2015-12-31"), _m("X", "2016-01-01", "2020-01-01")])


def test_lean_map_file_uses_inclusive_end():
    text = lean_map_file_text(_m("BBBY", "2010-01-04", "2018-03-23"))
    assert text == "20100104,bbby\n20180323,bbby\n"
    open_ended = lean_map_file_text(_m("SPY", "2010-01-04"))
    assert f"{LEAN_OPEN_ENDED.strftime('%Y%m%d')},spy" in open_ended


def test_write_lean_map_files(tmp_path):
    write_lean_map_files(tmp_path, [_m("QQQ", "2012-01-03")])
    assert (tmp_path / "qqq.csv").read_text(encoding="utf-8").startswith("20120103,qqq")


def test_infer_effective_to_when_stale():
    assert infer_effective_to_from_bars(date(2018, 3, 23), as_of=date(2026, 9, 1)) == date(
        2018, 3, 23
    )
    assert infer_effective_to_from_bars(date(2026, 8, 31), as_of=date(2026, 9, 1)) is None


def test_docker_volume_overlay_shadows_snapshot_map_files(tmp_path):
    from quant.engine.lean import docker_volume_args

    lean_data = tmp_path / "snapshot" / "lean"
    overlay = tmp_path / "jobs" / "bt" / "map_files"
    lean_data.mkdir(parents=True)
    overlay.mkdir(parents=True)
    args = docker_volume_args(
        config_path=tmp_path / "config.json",
        algo_dir=tmp_path / "algo",
        lean_data=lean_data,
        results_dir=tmp_path / "results",
        map_overlay=overlay,
    )
    data_mount = f"{lean_data.resolve()}:/Data:ro"
    overlay_mount = f"{overlay.resolve()}:/Data/equity/usa/map_files:ro"
    assert args.index("-v") < args.index(data_mount)
    assert args.index(data_mount) < args.index(overlay_mount)
    assert str(tmp_path / "snapshot") not in overlay_mount
