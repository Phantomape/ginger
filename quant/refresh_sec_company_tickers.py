#!/usr/bin/env python3
from __future__ import annotations

import argparse

from sec_ticker_map import DEFAULT_CACHE_PATH, refresh_company_tickers


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh SEC CIK-to-ticker cache.")
    parser.add_argument("--output", default=str(DEFAULT_CACHE_PATH))
    parser.add_argument(
        "--user-agent",
        default="ginger-research/1.0 contact: research@example.com",
    )
    args = parser.parse_args()

    path = refresh_company_tickers(args.output, user_agent=args.user_agent)
    print(f"wrote: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
