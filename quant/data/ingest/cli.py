from __future__ import annotations

import argparse
import json
from pathlib import Path

from quant.data.ingest import (
    data_status,
    ingest,
    load_symbols_file,
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest daily bars into an immutable snapshot.")
    parser.add_argument("symbols", nargs="*", default=None, help="Tickers; default SPY if omitted")
    parser.add_argument(
        "--symbols-file",
        default=None,
        help="text file with one ticker per line (# comments allowed)",
    )
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--provider", default="auto")
    parser.add_argument(
        "--mode",
        choices=("full", "incremental"),
        default="full",
        help="full = refetch history; incremental = append after last bar",
    )
    parser.add_argument(
        "--reconcile-with",
        default=None,
        help="optional secondary provider for dual-source reconciliation (e.g. yfinance)",
    )
    parser.add_argument("--no-lean", action="store_true")
    args = parser.parse_args()
    tickers = list(args.symbols or [])
    if args.symbols_file:
        tickers.extend(load_symbols_file(args.symbols_file))
    result = ingest(
        symbols=tickers or ["SPY"],
        start=args.start,
        end=args.end,
        provider=args.provider,
        convert_lean=not args.no_lean,
        mode=args.mode,
        reconcile_with=args.reconcile_with,
    )
    print(
        json.dumps(
            {k: str(v) if isinstance(v, Path) else v for k, v in result.items()},
            indent=2,
            default=str,
        )
    )
    print(data_status())
