from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import options_onclickmedia as options


def _fake_fetch_json(*, params, **kwargs):
    if params.get("list") == "expiration":
        return {
            "call expirations for TSLA on 2025-01-13": [
                "2025-01-17",
                "2025-01-24",
            ]
        }
    if params.get("data") == "greeks":
        call_put = params["type"]
        return [
            {
                "expiration": params["expiration"],
                "strike": 290.0,
                "type": call_put,
                "last": 22.0,
                "bid": 21.5,
                "ask": 22.5,
                "mark": 22.0,
                "volume": 125,
                "open_interest": 800,
                "greeks": {
                    "implied_volatility": 0.72,
                    "delta": 0.55 if call_put == "call" else -0.45,
                    "gamma": 0.02,
                    "theta": -0.10,
                    "vega": 0.30,
                    "rho": 0.01,
                },
            },
            {
                "expiration": params["expiration"],
                "strike": 310.0,
                "type": call_put,
                "last": 11.0,
                "bid": 0.0,
                "ask": 0.25,
                "mark": 0.125,
                "volume": 0,
                "open_interest": 10,
                "greeks": {
                    "implied_volatility": 0.95,
                    "delta": 0.25 if call_put == "call" else -0.75,
                },
            },
        ]
    raise AssertionError(f"unexpected params: {params}")


def test_build_ticker_date_rows_normalizes_schema_and_pit_flags():
    rows, stats = options.build_ticker_date_rows(
        ticker="tsla",
        quote_date=date(2025, 1, 13),
        underlying_price=300.0,
        max_expirations=1,
        max_strikes_per_side=0,
        collection_mode="historical_backfill",
        fetch_json=_fake_fetch_json,
    )

    assert stats["expiration_count"] == 1
    assert stats["rows_written"] == 4
    row = rows[0]
    assert row["ticker"] == "TSLA"
    assert row["date"] == "2025-01-13"
    assert row["expiry"] == "2025-01-17"
    assert row["call_put"] == "call"
    assert row["mid"] == 22.0
    assert row["implied_vol"] == 0.72
    assert row["delta"] == 0.55
    assert row["usable_trade_date"] == "2025-01-14"
    assert row["pit_safe"] is False
    assert row["pit_safe_flag"] == "historical_backfill_vendor_asof_missing"
    assert row["option_liquidity_score"] >= 0.75
    assert row["option_liquidity_pass"] is True


def test_run_options_backfill_writes_jsonl_and_summary(tmp_path):
    output = tmp_path / "chain.jsonl"
    summary_output = tmp_path / "summary.json"

    summary = options.run_options_backfill(
        tickers=["TSLA"],
        start=date(2025, 1, 13),
        end=date(2025, 1, 13),
        output=output,
        summary_output=summary_output,
        cache_dir=tmp_path / "cache",
        max_expirations=1,
        max_strikes_per_side=0,
        collection_mode="historical_backfill",
        fetch_json=_fake_fetch_json,
    )

    assert summary["rows_written"] == 4
    assert summary["pit_safe_rows"] == 0
    assert summary["option_liquidity_pass_rows"] == 2
    assert output.exists()
    assert summary_output.exists()
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert {row["call_put"] for row in rows} == {"call", "put"}


def test_persist_daily_options_snapshot_marks_forward_rows_pit_safe(tmp_path):
    summary = options.persist_daily_options_snapshot(
        as_of="2025-01-13",
        tickers=["TSLA"],
        underlying_prices={"TSLA": 300.0},
        data_dir=tmp_path,
        max_expirations=1,
        max_strikes_per_side=0,
        fetch_json=_fake_fetch_json,
    )

    assert summary["status"] == "ok"
    assert summary["rows_written"] == 4
    assert summary["pit_safe_rows"] == 4
    rows_path = Path(summary["output_path"])
    if not rows_path.is_absolute():
        rows_path = options.REPO_ROOT / rows_path
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]
    assert all(row["collection_mode"] == "forward_daily" for row in rows)
    assert all(row["pit_safe"] is True for row in rows)
