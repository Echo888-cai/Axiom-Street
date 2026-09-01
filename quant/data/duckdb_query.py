from __future__ import annotations

from pathlib import Path

import duckdb


def connect_market(data_root: Path):
    """Open a DuckDB connection with a view over SPY parquet."""
    root = Path(data_root)
    con = duckdb.connect(database=":memory:")
    parquet = root / "market" / "equities" / "US" / "daily" / "SPY.parquet"
    if parquet.exists():
        con.execute(
            f"""
            CREATE OR REPLACE VIEW spy_daily AS
            SELECT * FROM read_parquet('{parquet.as_posix()}')
            """
        )
    return con
