from __future__ import annotations

from pathlib import Path

import duckdb

from quant.data.symbols import list_market_symbols


def connect_market(data_root: Path):
    """Open a DuckDB connection with a view per symbol parquet, plus spy_daily if present."""
    root = Path(data_root)
    con = duckdb.connect(database=":memory:")
    daily = root / "market" / "equities" / "US" / "daily"
    symbols = list_market_symbols(root)
    for symbol in symbols:
        parquet = daily / f"{symbol}.parquet"
        view = f"{symbol.lower().replace('.', '_').replace('-', '_')}_daily"
        con.execute(
            f"""
            CREATE OR REPLACE VIEW {view} AS
            SELECT * FROM read_parquet('{parquet.as_posix()}')
            """
        )
    spy = daily / "SPY.parquet"
    if spy.exists():
        con.execute(
            f"""
            CREATE OR REPLACE VIEW spy_daily AS
            SELECT * FROM read_parquet('{spy.as_posix()}')
            """
        )
    return con
