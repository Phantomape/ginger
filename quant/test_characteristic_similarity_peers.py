from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
QUANT_DIR = ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import characteristic_similarity_peers as csp


class FakeFundamentalIndex:
    def __init__(self, values: dict[str, dict[str, float]]) -> None:
        self.values = values

    def fundamental_context(self, ticker: str, signal_date: str) -> dict[str, Any]:
        row = self.values[ticker]
        return {
            "eps_yoy_growth": row["eps_yoy_growth"],
            "revenue_yoy_growth": row["revenue_yoy_growth"],
        }

    def operating_quality(self, ticker: str, signal_date: str) -> dict[str, Any]:
        return {"operating_margin_current": self.values[ticker]["operating_margin_current"]}

    def gross_margin_quality(self, ticker: str, signal_date: str) -> dict[str, Any]:
        return {"gross_margin": self.values[ticker]["gross_margin"]}

    def balance_sheet_quality(self, ticker: str, signal_date: str) -> dict[str, Any]:
        return {"liabilities_assets_ratio": self.values[ticker]["liabilities_assets_ratio"]}


def _rows(ticker: str, *, base: float, shock_day: int | None = None) -> list[dict[str, Any]]:
    start = date(2025, 1, 2)
    rows = []
    price = base
    for idx in range(90):
        day = start + timedelta(days=idx)
        ret = 0.001
        if shock_day is not None and idx == shock_day:
            ret = 0.065
        price *= 1.0 + ret
        rows.append(
            {
                "date": day.isoformat(),
                "open": round(price * 0.998, 4),
                "high": round(price * 1.015, 4),
                "low": round(price * 0.990, 4),
                "close": round(price, 4),
                "volume": 2_000_000 if ticker != "SPY" else 50_000_000,
            }
        )
    return rows


def test_similarity_uses_non_price_features() -> None:
    ohlcv = {
        "SPY": _rows("SPY", base=400),
        "AAA": _rows("AAA", base=100),
        "BBB": _rows("BBB", base=102),
        "CCC": _rows("CCC", base=104),
    }
    fundamentals = FakeFundamentalIndex(
        {
            "AAA": {
                "eps_yoy_growth": 0.20,
                "revenue_yoy_growth": 0.12,
                "operating_margin_current": 0.25,
                "gross_margin": 0.55,
                "liabilities_assets_ratio": 0.35,
            },
            "BBB": {
                "eps_yoy_growth": 0.21,
                "revenue_yoy_growth": 0.13,
                "operating_margin_current": 0.24,
                "gross_margin": 0.56,
                "liabilities_assets_ratio": 0.36,
            },
            "CCC": {
                "eps_yoy_growth": -0.20,
                "revenue_yoy_growth": -0.10,
                "operating_margin_current": -0.02,
                "gross_margin": 0.18,
                "liabilities_assets_ratio": 0.80,
            },
        }
    )
    sector_entries = {
        "AAA": {"sector": "Technology", "industry": "Software"},
        "BBB": {"sector": "Technology", "industry": "Software"},
        "CCC": {"sector": "Technology", "industry": "Hardware"},
    }
    provider = csp.CharacteristicSimilarityProvider(
        ohlcv_by_ticker=ohlcv,
        sector_entries=sector_entries,
        fundamental_index=fundamentals,
        config={"min_avg_dollar_volume_20d": 1.0},
    )

    similar = provider.similarity("AAA", "BBB", "2025-03-15")
    different = provider.similarity("AAA", "CCC", "2025-03-15")

    assert similar["score"] > different["score"]
    assert similar["fundamental_pair_feature_count"] == 5
    assert similar["non_price_pair_feature_count"] >= 5


def test_candidate_rows_exclude_accepted_rolling_corr_overlap() -> None:
    ohlcv = {
        "SPY": _rows("SPY", base=400),
        "AAA": _rows("AAA", base=100, shock_day=70),
        "BBB": _rows("BBB", base=101, shock_day=70),
    }
    fundamentals = FakeFundamentalIndex(
        {
            "AAA": {
                "eps_yoy_growth": 0.20,
                "revenue_yoy_growth": 0.12,
                "operating_margin_current": 0.25,
                "gross_margin": 0.55,
                "liabilities_assets_ratio": 0.35,
            },
            "BBB": {
                "eps_yoy_growth": 0.21,
                "revenue_yoy_growth": 0.13,
                "operating_margin_current": 0.24,
                "gross_margin": 0.56,
                "liabilities_assets_ratio": 0.36,
            },
        }
    )
    sector_entries = {
        "AAA": {"sector": "Technology", "industry": "Software"},
        "BBB": {"sector": "Technology", "industry": "Software"},
    }
    dates = [ohlcv["AAA"][70]["date"]]
    cfg = {
        "min_avg_dollar_volume_20d": 1.0,
        "min_peer_signal_return": 0.03,
        "min_peer_relative_vs_spy": 0.02,
        "min_peer_volume_ratio_20d": 0.0,
        "min_peer_ret20_excess_spy": -1.0,
        "min_candidate_signal_return": 0.0,
        "max_candidate_signal_return": 0.10,
        "min_candidate_close_location": 0.0,
        "min_candidate_ret5": -1.0,
        "max_candidate_ret5": 1.0,
        "min_candidate_ret20_excess_spy": -1.0,
        "min_candidate_ret60_excess_spy": -1.0,
        "max_candidate_realized_vol_20d": 1.0,
        "max_prior_return_correlation": -0.99,
    }

    candidates, _contexts, scan = csp.build_characteristic_similarity_candidate_rows(
        ohlcv_by_ticker=ohlcv,
        dates=dates,
        sector_entries=sector_entries,
        core_entries_by_date={dates[0]: [{"ticker": "SPY"}]},
        fundamental_index=fundamentals,
        config=cfg,
    )

    assert candidates == []
    assert scan["pairs_rejected_high_prior_corr"] > 0


def _write_ledger(path: Path, rows: list[dict[str, Any]]) -> None:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def test_coverage_index_reads_live_nonohlcv_ledger_and_asof_field(tmp_path: Path) -> None:
    # Regression: the loader used to only glob data/experiments/exp-*/ and only
    # accept an `asof_date` field, so the live data/non_ohlcv ledger (which keys
    # its date as `as_of_date`) was silently invisible -> 0 rows.
    data = tmp_path / "data"
    _write_ledger(
        data / "non_ohlcv" / "estimate_revision_ledger_20260630.jsonl",
        [
            {"ticker": "AAPL", "as_of_date": "2026-06-10", "estimate_revision_usable": True},
            {"ticker": "MSFT", "as_of_date": "2026-06-11", "analyst_count": 34},
        ],
    )
    idx, audit = csp.AnalystCoverageIndex.from_revision_ledgers(
        root=data / "experiments", max_asof="2026-06-30", tickers=["AAPL", "MSFT"]
    )
    assert audit["status"] == "ok"
    assert audit["row_count"] == 2
    assert audit["usable_coverage_rows"] == 2
    assert idx.coverage_count("AAPL", "2026-06-30") == 1.0   # presence proxy
    assert idx.coverage_count("MSFT", "2026-06-30") == 34.0  # explicit count


def test_coverage_index_reports_no_coverage_field_when_rows_lack_counts(tmp_path: Path) -> None:
    # Rows match ticker+asof but carry no coverage field and are not
    # estimate_revision_usable -> honest "no_coverage_field_in_source", not "empty".
    data = tmp_path / "data"
    _write_ledger(
        data / "non_ohlcv" / "estimate_revision_ledger_20260630.jsonl",
        [{"ticker": "AAPL", "as_of_date": "2026-06-10", "eps_estimate": 1.23}],
    )
    idx, audit = csp.AnalystCoverageIndex.from_revision_ledgers(
        root=data / "experiments", max_asof="2026-06-30", tickers=["AAPL"]
    )
    assert audit["row_count"] == 1
    assert audit["usable_coverage_rows"] == 0
    assert audit["status"] == "no_coverage_field_in_source"


def test_coverage_index_empty_when_no_rows_match(tmp_path: Path) -> None:
    data = tmp_path / "data"
    _write_ledger(
        data / "non_ohlcv" / "estimate_revision_ledger_20260630.jsonl",
        [{"ticker": "AAPL", "as_of_date": "2026-06-10", "estimate_revision_usable": True}],
    )
    idx, audit = csp.AnalystCoverageIndex.from_revision_ledgers(
        root=data / "experiments", max_asof="2026-06-30", tickers=["ZZZZ"]
    )
    assert audit["row_count"] == 0
    assert audit["status"] == "empty"
