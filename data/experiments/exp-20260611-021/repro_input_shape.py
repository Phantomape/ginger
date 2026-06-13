# exp-20260611-021 repro: daily sleeve adapter input-shape bugs.
#
# Reproduces the run.py daily call shape without touching production state:
# - OHLCV values are pandas DataFrames with a DatetimeIndex (get_ohlcv shape).
# - candidate_universe is the governance fallback feed: records carry
#   ticker/title/theme/status governance metadata and no sector fields.
#
# Usage:
#   .venv\Scripts\python.exe -B data\experiments\exp-20260611-021\repro_input_shape.py before.json
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "quant"))

import broad_market_sector_map
from industry_relative_laggard_repair_paper_sleeve import (
    build_industry_relative_laggard_repair_paper_sleeve_snapshot,
)
from industry_stable_core_flow_paper_sleeve import (
    build_industry_stable_core_flow_snapshot,
)
from rolling_corr_peer_shock_paper_sleeve import (
    build_rolling_corr_peer_shock_paper_sleeve_snapshot,
)

AS_OF = "2026-06-10"
DAYS = 90


def _frame(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range(end=AS_OF, periods=DAYS)
    close = 50.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.02, DAYS)))
    return pd.DataFrame(
        {
            "Open": close * (1 + rng.normal(0, 0.003, DAYS)),
            "High": close * (1 + np.abs(rng.normal(0, 0.008, DAYS))),
            "Low": close * (1 - np.abs(rng.normal(0, 0.008, DAYS))),
            "Close": close,
            "Volume": rng.integers(1_000_000, 9_000_000, DAYS).astype(float),
        },
        index=index,
    )


def main(out_path: str) -> None:
    cache = broad_market_sector_map.load_cache()
    cache_entries = cache.get("entries", {}) if isinstance(cache, dict) else {}
    covered = [
        ticker
        for ticker, meta in sorted(cache_entries.items())
        if isinstance(meta, dict)
        and meta.get("sector")
        and (meta.get("status") or "ok") == "ok"
        and "." not in ticker
        and "-" not in ticker
    ][:24]

    ohlcv = {ticker: _frame(i + 7) for i, ticker in enumerate(covered)}
    ohlcv["SPY"] = _frame(99)

    # Governance fallback feed shape: records have NO sector fields.
    universe = {
        "status": "universe_state_observation_feed",
        "tickers": sorted(covered),
        "records": {
            ticker: {
                "ticker": ticker,
                "title": f"{ticker} Inc",
                "status": "active",
                "theme": "space",
                "feed_rule_version": "universe_state_feed_v1",
            }
            for ticker in covered
        },
    }

    common = dict(
        as_of=AS_OF,
        candidate_universe=universe,
        core_entries=[],
        state={},
        persist=False,
    )
    rolling = build_rolling_corr_peer_shock_paper_sleeve_snapshot(
        ohlcv_by_ticker=ohlcv, **common
    )
    laggard = build_industry_relative_laggard_repair_paper_sleeve_snapshot(
        ohlcv_by_ticker=ohlcv, **common
    )
    stable = build_industry_stable_core_flow_snapshot(ohlcv_by_ticker=ohlcv, **common)

    summary = {
        "as_of": AS_OF,
        "universe_size": len(covered),
        "cache_covered_universe_tickers": len(covered),
        "sleeves": {
            "rolling_corr_peer_shock": {
                "error": rolling.get("error"),
                "candidate_count": rolling.get("candidate_count"),
                "raw_candidate_count": rolling.get("raw_candidate_count"),
            },
            "industry_relative_laggard_repair": {
                "error": laggard.get("error"),
                "candidate_count": laggard.get("candidate_count"),
                "sector_universe_count": laggard.get("sector_universe_count"),
            },
            "industry_stable_core_flow": {
                "error": stable.get("error"),
                "candidate_count": stable.get("candidate_count"),
                "sector_universe_count": stable.get("sector_universe_count"),
            },
        },
    }
    Path(out_path).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "repro_summary.json")
