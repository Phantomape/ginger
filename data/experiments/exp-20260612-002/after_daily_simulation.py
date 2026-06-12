# exp-20260612-002 after-artifact: simulate the run.py daily broad sleeve path
# on the real generated universe feed + warehouse frames. persist=False and
# state={} so no production state is touched.
import json
import sys
import time
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "quant"))

from broad_market_paper_sleeve import load_broad_market_candidate_universe
from industry_relative_laggard_repair_paper_sleeve import (
    build_industry_relative_laggard_repair_paper_sleeve_snapshot,
)
from industry_stable_core_flow_paper_sleeve import build_industry_stable_core_flow_snapshot
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH, load_warehouse_ohlcv_frames
from rolling_corr_peer_shock_paper_sleeve import (
    build_rolling_corr_peer_shock_paper_sleeve_snapshot,
)

universe = load_broad_market_candidate_universe()
tickers = sorted(set(universe.get("tickers") or []) | {"SPY"})
end = pd.Timestamp.utcnow().tz_localize(None).normalize()
start = end - pd.Timedelta(days=400)

t0 = time.monotonic()
frames = load_warehouse_ohlcv_frames(DEFAULT_WAREHOUSE_PATH, tickers, start=start, end=end)
load_seconds = round(time.monotonic() - t0, 2)
loaded = {t: f for t, f in frames.items() if f is not None and not f.empty}
as_of = max(str(f.index.max())[:10] for f in loaded.values())

common = dict(
    as_of=as_of,
    candidate_universe=universe,
    core_entries=[],
    state={},
    persist=False,
)
timings = {}
results = {}
for name, builder in [
    ("rolling_corr_peer_shock", build_rolling_corr_peer_shock_paper_sleeve_snapshot),
    ("industry_relative_laggard_repair", build_industry_relative_laggard_repair_paper_sleeve_snapshot),
    ("industry_stable_core_flow", build_industry_stable_core_flow_snapshot),
]:
    t0 = time.monotonic()
    snap = builder(ohlcv_by_ticker=loaded, **common)
    timings[name] = round(time.monotonic() - t0, 2)
    results[name] = {
        "error": snap.get("error"),
        "candidate_count": snap.get("candidate_count"),
        "raw_candidate_count": snap.get("raw_candidate_count"),
        "rejected_candidate_count": snap.get("rejected_candidate_count"),
    }

summary = {
    "as_of": as_of,
    "loader_status": universe.get("status"),
    "universe_ticker_count": len(universe.get("tickers") or []),
    "warehouse_frames_loaded": len(loaded),
    "warehouse_load_seconds": load_seconds,
    "sleeve_build_seconds": timings,
    "sleeves": results,
}
print(json.dumps(summary, indent=2))
