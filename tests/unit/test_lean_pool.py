from __future__ import annotations

from pathlib import Path

from quant.engine.pool import build_lean_view


def test_build_lean_view_overlays_map_files_without_touching_snapshot(tmp_path: Path):
    snapshot = tmp_path / "snap" / "lean"
    daily = snapshot / "equity" / "usa" / "daily"
    maps = snapshot / "equity" / "usa" / "map_files"
    daily.mkdir(parents=True)
    maps.mkdir(parents=True)
    (daily / "spy.zip").write_text("price", encoding="utf-8")
    (maps / "spy.csv").write_text("20000101,spy\n", encoding="utf-8")
    (snapshot / "market-hours").mkdir()
    (snapshot / "market-hours" / "db.json").write_text("{}", encoding="utf-8")

    overlay = tmp_path / "job" / "map_files"
    overlay.mkdir(parents=True)
    (overlay / "spy.csv").write_text("20180101,spy\n", encoding="utf-8")

    view = build_lean_view(tmp_path / "job", snapshot, overlay)
    assert (view / "equity" / "usa" / "daily" / "spy.zip").resolve() == (daily / "spy.zip").resolve()
    assert (view / "equity" / "usa" / "map_files" / "spy.csv").read_text(encoding="utf-8") == "20180101,spy\n"
    assert (maps / "spy.csv").read_text(encoding="utf-8") == "20000101,spy\n"
    assert (view / "market-hours" / "db.json").resolve() == (snapshot / "market-hours" / "db.json").resolve()
