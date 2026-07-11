#!/usr/bin/env python3
"""Refresh the separate intraday triage counterfactual scorecard."""

from __future__ import annotations

import argparse
import json

try:
    from intraday_backtester import render_scorecard, run_intraday_backtest
except ImportError:  # pragma: no cover - package-style imports
    from quant.intraday_backtester import render_scorecard, run_intraday_backtest


def main(as_of: str | None = None, *, no_fetch: bool = False) -> int:
    result = run_intraday_backtest(as_of, fetch_prices=not no_fetch)
    print(render_scorecard(result["scorecard"]))
    print(json.dumps(result["paths"], indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", help="YYYY-MM-DD; defaults to current ET date")
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="do not query OpenD; useful for zero-row readiness smoke tests",
    )
    args = parser.parse_args()
    raise SystemExit(main(args.as_of, no_fetch=args.no_fetch))
