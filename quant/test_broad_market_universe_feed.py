from __future__ import annotations

import pandas as pd

from quant.broad_market_paper_sleeve import load_broad_market_candidate_universe
from quant.broad_market_universe_feed import generate_broad_market_paper_universe
from quant.industry_relative_laggard_repair_paper_sleeve import _resolve_sector_entries
from quant.ohlcv_warehouse import upsert_ohlcv_frames

AS_OF = "2026-06-10"


def _frame(end: str, days: int) -> pd.DataFrame:
    index = pd.bdate_range(end=end, periods=days)
    base = pd.Series(range(1, days + 1), index=index, dtype=float)
    return pd.DataFrame(
        {
            "Open": base + 10.0,
            "High": base + 11.0,
            "Low": base + 9.0,
            "Close": base + 10.5,
            "Volume": base * 1000.0,
        },
        index=index,
    )


def _sector_entries() -> dict[str, dict]:
    return {
        "FRESH": {"sector": "Technology", "industry": "Semiconductors", "status": "ok"},
        "STALE": {"sector": "Energy", "industry": "Oil & Gas", "status": "ok"},
        "THIN": {"sector": "Utilities", "industry": "Electric", "status": "ok"},
        "NOSEC": {"sector": None, "status": "ok"},
        "BADSTATUS": {"sector": "Healthcare", "status": "missing_info"},
    }


def _seed_warehouse(tmp_path):
    db = tmp_path / "warehouse.sqlite"
    upsert_ohlcv_frames(
        db,
        {
            "FRESH": _frame(AS_OF, 90),
            "STALE": _frame("2026-04-24", 90),
            "THIN": _frame(AS_OF, 10),
            "NOSEC": _frame(AS_OF, 90),
            "BADSTATUS": _frame(AS_OF, 90),
        },
        source="test_seed",
    )
    return db


def test_feed_includes_only_fresh_sector_covered_tickers(tmp_path) -> None:
    db = _seed_warehouse(tmp_path)
    out = tmp_path / "universe.json"

    payload = generate_broad_market_paper_universe(
        db_path=db,
        as_of=AS_OF,
        sector_entries=_sector_entries(),
        out_path=out,
    )

    assert payload["status"] == "generated"
    assert payload["tickers"] == ["FRESH"]
    assert payload["excluded_counts"] == {
        "missing_ohlcv": 0,
        "stale_ohlcv": 1,
        "thin_history": 1,
    }
    record = payload["records"]["FRESH"]
    assert record["sector"] == "Technology"
    assert record["sector_coverage_status"] == "ok"
    assert record["last_ohlcv_date"] == AS_OF
    assert out.exists()


def test_feed_round_trips_through_loader_and_sector_resolution(tmp_path) -> None:
    db = _seed_warehouse(tmp_path)
    out = tmp_path / "universe.json"
    generate_broad_market_paper_universe(
        db_path=db,
        as_of=AS_OF,
        sector_entries=_sector_entries(),
        out_path=out,
    )

    loaded = load_broad_market_candidate_universe(out)
    assert loaded["status"] == "loaded"
    assert loaded["tickers"] == ["FRESH"]

    rows_by_ticker = {"FRESH": [{"date": AS_OF, "close": 10.0}]}
    resolved = _resolve_sector_entries(
        sector_entries=None,
        candidate_universe=loaded,
        rows_by_ticker=rows_by_ticker,
    )
    assert resolved == {
        "FRESH": {
            "sector": "Technology",
            "industry": "Semiconductors",
            "sector_coverage_status": "ok",
        }
    }


def test_feed_dry_run_does_not_write(tmp_path) -> None:
    db = _seed_warehouse(tmp_path)
    out = tmp_path / "universe.json"
    payload = generate_broad_market_paper_universe(
        db_path=db,
        as_of=AS_OF,
        sector_entries=_sector_entries(),
        out_path=out,
        write=False,
    )
    assert payload["tickers"] == ["FRESH"]
    assert not out.exists()
