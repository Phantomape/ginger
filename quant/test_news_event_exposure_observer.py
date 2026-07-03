import json

import pandas as pd

from news_event_exposure_observer import (
    build_exposure_rows,
    exposure_set_for_ticker,
    load_ledger,
    merge_rows,
    settle_rows,
    write_ledger,
)

EXPOSURE_MAP = {
    "sic_index": {
        "by_sic": {
            "7372": [
                {"ticker": "META", "cik": "1", "name": "M", "sic_description": ""},
                {"ticker": "CRWD", "cik": "2", "name": "C", "sic_description": ""},
                {"ticker": "SNOW", "cik": "3", "name": "S", "sic_description": ""},
            ]
        }
    },
    "overlay": {
        "overlay_version": "test_v1",
        "themes": [
            {
                "theme": "ai_software_platforms",
                "sic_codes": [],
                "name_keywords": [],
                "listed_peers": ["META", "PLTR", "NOW"],
            }
        ],
    },
    "ticker_sic": {"META": "7372", "CRWD": "7372", "SNOW": "7372"},
    "ticker_themes": {"META": ["ai_software_platforms"], "PLTR": ["ai_software_platforms"]},
}

EVENT = {
    "event_id": "ev-1",
    "event_date": "2026-06-30",
    "published_at": "2026-06-30T17:00:00+00:00",
    "ticker": "META",
    "relation_type": "customer_order_or_partnership",
    "relation_polarity": "negative",
    "rule_version": "daily_news_structured_event_ledger_v1",
}


def test_exposure_set_excludes_first_order_and_dedupes():
    edges = exposure_set_for_ticker("META", EXPOSURE_MAP)
    tickers = [e["exposure_ticker"] for e in edges]
    assert "META" not in tickers
    assert set(tickers) == {"CRWD", "SNOW", "PLTR", "NOW"}
    kinds = {e["exposure_ticker"]: e["relation_type"] for e in edges}
    assert kinds["CRWD"] == "sic_peer"
    assert kinds["PLTR"] == "theme_peer"


def test_sic_peer_cap():
    big_map = {
        "sic_index": {
            "by_sic": {
                "2836": [
                    {"ticker": f"T{i:03d}", "cik": str(i), "name": "", "sic_description": ""}
                    for i in range(40)
                ]
            }
        },
        "overlay": {"overlay_version": "v", "themes": []},
        "ticker_sic": {"T000": "2836"},
        "ticker_themes": {},
    }
    edges = exposure_set_for_ticker("T000", big_map)
    assert len(edges) == 14  # 15 cap minus the first-order ticker itself


def test_build_rows_carry_event_provenance():
    rows = build_exposure_rows([EVENT], EXPOSURE_MAP)
    assert len(rows) == 4
    row = rows[0]
    assert row["event_id"] == "ev-1"
    assert row["first_order_ticker"] == "META"
    assert row["event_polarity"] == "negative"
    assert row["outcome_status"] == "pending_forward_close"
    assert row["entry_date"] is None


def test_merge_rows_dedup():
    rows = build_exposure_rows([EVENT], EXPOSURE_MAP)
    merged, appended = merge_rows([], rows)
    assert appended == 4
    merged2, appended2 = merge_rows(merged, rows)
    assert appended2 == 0
    assert len(merged2) == 4


def _synthetic_frame(prices):
    idx = pd.bdate_range("2026-06-29", periods=len(prices))
    return pd.DataFrame(
        {
            "Open": prices,
            "High": prices,
            "Low": prices,
            "Close": prices,
            "Volume": [1e6] * len(prices),
        },
        index=idx,
    )


def test_settlement_math():
    rows = build_exposure_rows([EVENT], EXPOSURE_MAP)
    # exposure ticker rises 10% over 10 sessions, SPY flat -> excess ~ +10%
    frames = {
        t: _synthetic_frame([100.0 * (1.01**i) for i in range(15)])
        for t in ("CRWD", "SNOW", "PLTR", "NOW")
    }
    frames["SPY"] = _synthetic_frame([500.0] * 15)
    counts = settle_rows(rows, frames)
    assert counts["settled"] == 4
    row = rows[0]
    assert row["outcome_status"] == "closed"
    # event 06-30 -> entry next session 07-01 (index pos 2)
    assert row["entry_date"] == "2026-07-01"
    assert abs(row["excess_10d"] - ((1.01**9) - 1.0)) < 1e-5
    assert abs(row["excess_5d"] - ((1.01**4) - 1.0)) < 1e-5


def test_settlement_stays_pending_without_enough_bars():
    rows = build_exposure_rows([EVENT], EXPOSURE_MAP)
    frames = {
        t: _synthetic_frame([100.0] * 5) for t in ("CRWD", "SNOW", "PLTR", "NOW")
    }
    frames["SPY"] = _synthetic_frame([500.0] * 5)
    counts = settle_rows(rows, frames)
    assert counts["settled"] == 0
    assert counts["still_pending"] == 4


def test_write_and_reload_ledger(tmp_path):
    rows = build_exposure_rows([EVENT], EXPOSURE_MAP)
    manifest = write_ledger(rows, out_dir=tmp_path)
    assert manifest["rows"] == 4
    assert manifest["pending_rows"] == 4
    reloaded = load_ledger(tmp_path / "rows.jsonl")
    assert len(reloaded) == 4
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["rows"] == 4
