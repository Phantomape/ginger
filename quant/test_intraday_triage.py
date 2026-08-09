from datetime import date

import pandas as pd

from intraday_moomoo import derive_metrics, quote_from_ticker_payload
from intraday_triage import (
    build_decision_template,
    build_machine_triage,
    finalize_decision_payload,
    persist_final_decision,
)


def _position_payload(ticker="NVDA"):
    return {
        "portfolio_value_usd": 100_000,
        "cash_usd": 30_000,
        "positions": [{
            "ticker": ticker,
            "shares": 10,
            "avg_cost": 100,
            "target_price": 150,
            "stop_price": 90,
        }],
    }


def _metrics(price=120.0, vwap=115.0):
    return {
        "reference_price": price,
        "rth_vwap": vwap,
        "ema8": 112.0,
        "sma20": 110.0,
        "rth_high": 121.0,
        "rth_low": 108.0,
        "rth_range_location": 0.92,
        "atr_pct": 0.04,
        "technical_context_complete": True,
    }


def _opend(ticker="NVDA", phase="RTH", metrics=None):
    return {
        "status": "ok",
        "market_phase": phase,
        "tickers": {
            ticker: {"metrics": metrics or _metrics()},
            "SMH": {"metrics": _metrics(300, 295)},
            "QQQ": {"metrics": _metrics(700, 695)},
            "SPY": {"metrics": _metrics(750, 745)},
        },
    }


def _review(ticker="NVDA", status="OK", **overrides):
    row = {
        "ticker": ticker,
        "status": status,
        "quote": {"price": 120},
        "distance_to_target_pct": 0.10,
    }
    row.update(overrides)
    return [row]


def _triage(ticker="NVDA", status="OK", phase="RTH", opend=None):
    return build_machine_triage(
        _position_payload(ticker),
        _review(ticker, status),
        opend or _opend(ticker, phase),
        portfolio_heat={"portfolio_heat_pct": 0.04, "max_heat_pct": 0.08},
        accounting={"portfolio_value_usd": 100_000, "cash_usd": 30_000},
    )


def test_all_confirmations_only_open_add_small_for_review():
    result = _triage()
    row = result["rows"][0]
    assert row["machine_state"] == "ADD_REVIEW_ELIGIBLE"
    assert row["default_action"] == "WAIT"
    assert "ADD_SMALL" in row["allowed_actions"]
    assert row["max_add_pct_existing_position"] == 0.20
    assert result["add_review_eligible"] == ["NVDA"]


def test_existing_exit_breach_overrides_every_add_condition():
    row = _triage(status="BREACHED")["rows"][0]
    assert row["machine_state"] == "RISK_ACTION_REQUIRED"
    assert row["default_action"] == "REDUCE_RISK"
    assert row["allowed_actions"] == ["REDUCE_RISK"]
    assert row["max_add_pct_existing_position"] == 0.0


def test_review_only_rule_does_not_force_reduce_but_blocks_add():
    result = build_machine_triage(
        _position_payload(),
        _review(
            status="BREACHED",
            primary_advisory_shadow_action={"shadow_action": "REVIEW"},
        ),
        _opend(),
        portfolio_heat={"portfolio_heat_pct": 0.04, "max_heat_pct": 0.08},
        accounting={"portfolio_value_usd": 100_000, "cash_usd": 30_000},
    )
    row = result["rows"][0]
    assert row["machine_state"] == "RULE_REVIEW_REQUIRED"
    assert row["default_action"] == "HOLD_ONLY"
    assert row["allowed_actions"] == ["HOLD_ONLY", "REDUCE_RISK"]


def test_near_stop_or_pending_reduce_blocks_add_review():
    result = build_machine_triage(
        _position_payload(),
        _review(proximity_flags=["NEAR_HARD_STOP"]),
        _opend(),
        portfolio_heat={"portfolio_heat_pct": 0.04, "max_heat_pct": 0.08},
        accounting={"portfolio_value_usd": 100_000, "cash_usd": 30_000},
        pending_actions=[{"ticker": "NVDA", "action": "REDUCE"}],
    )
    row = result["rows"][0]
    assert "ADD_SMALL" not in row["allowed_actions"]
    assert "near_existing_stop" in row["risk_blocks"]
    assert "pending_risk_action_open" in row["risk_blocks"]
    assert row["pending_risk_actions"] == ["REDUCE"]


def test_outside_rth_blocks_add_review():
    row = _triage(phase="AFTER_HOURS")["rows"][0]
    assert row["default_action"] == "WAIT"
    assert "ADD_SMALL" not in row["allowed_actions"]
    assert "outside_rth" in row["blockers"]


def test_stale_position_quote_blocks_add_review():
    result = build_machine_triage(
        _position_payload(),
        _review(quote={"price": 120, "is_stale": True}),
        _opend(),
        portfolio_heat={"portfolio_heat_pct": 0.04, "max_heat_pct": 0.08},
        accounting={"portfolio_value_usd": 100_000, "cash_usd": 30_000},
    )
    row = result["rows"][0]
    assert "ADD_SMALL" not in row["allowed_actions"]
    assert "stale_position_quote" in row["blockers"]


def test_leveraged_product_requires_underlying_confirmation():
    opend = _opend("MUU")
    opend["tickers"]["MU"] = {"metrics": _metrics(95, 100)}
    result = _triage("MUU", opend=opend)
    row = result["rows"][0]
    assert "ADD_SMALL" not in row["allowed_actions"]
    assert "underlying_above_rth_vwap_not_confirmed" in row["blockers"]


def test_decision_template_uses_safe_machine_default():
    machine = _triage()
    payload = build_decision_template(
        machine,
        timestamp_et="2026-07-10 13:00 ET",
        raw_snapshot_ref="snapshot.json",
    )
    row = payload["rows"][0]
    assert row["action_label"] == "WAIT"
    assert "ADD_SMALL" in row["allowed_actions"]
    assert row["raw_snapshot_ref"] == "snapshot.json"
    assert payload["trade_enabled"] is False


def test_finalize_decision_rejects_action_outside_machine_allowed_set():
    template = build_decision_template(
        _triage(phase="AFTER_HOURS"),
        timestamp_et="2026-07-10 19:00 ET",
        raw_snapshot_ref="snapshot.json",
    )
    response = {
        "decisions": [{
            "ticker": "NVDA",
            "action_label": "ADD_SMALL",
            "confidence": 0.8,
            "news_refs": ["https://example.com/news"],
            "reason": "invalid override",
        }]
    }
    try:
        finalize_decision_payload(template, response)
    except ValueError as exc:
        assert "not in allowed_actions" in str(exc)
    else:
        raise AssertionError("invalid ADD_SMALL override was accepted")


def test_finalize_and_persist_valid_decision_exclusively(tmp_path):
    template = build_decision_template(
        _triage(),
        timestamp_et="2026-07-10 13:00 ET",
        raw_snapshot_ref="snapshot.json",
    )
    response = {
        "portfolio_summary": "Machine constraints respected.",
        "decisions": [{
            "ticker": "NVDA",
            "action_label": "ADD_SMALL",
            "confidence": 0.7,
            "news_veto": False,
            "news_refs": ["https://example.com/verified"],
            "reason": "Eligible after verified news review.",
        }],
    }
    finalized = finalize_decision_payload(template, response)
    first = persist_final_decision(finalized, tmp_path)
    second = persist_final_decision(finalized, tmp_path)
    assert first != second
    assert first.exists() and second.exists()
    assert finalized["rows"][0]["action_label"] == "ADD_SMALL"
    execution = finalized["rows"][0]["paper_execution"]
    assert execution["action_direction"] == 1
    assert execution["action_fraction_existing_position"] == 0.20
    assert execution["paper_notional_usd"] == 240.0
    assert execution["entry_rule"] == "next_eligible_5m_open_strictly_after_decision"


def test_derive_metrics_uses_completed_daily_history_and_rth_vwap():
    daily_dates = pd.bdate_range(end="2026-07-09", periods=60)
    daily_rows = []
    for i, ts in enumerate(daily_dates):
        close = 100.0 + i
        daily_rows.append({
            "time_key": str(ts.date()),
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000,
            "turnover": close * 1_000_000,
        })
    intraday_rows = [
        {
            "time_key": f"2026-07-10 09:{minute:02d}:00",
            "open": 160.0,
            "high": 161.0,
            "low": 159.0,
            "close": 160.0 + index,
            "volume": 100,
            "turnover": (160.0 + index) * 100,
        }
        for index, minute in enumerate((30, 35, 40, 45))
    ]
    metrics = derive_metrics(
        {
            "last_price": 163.0,
            "prev_close_price": 159.0,
            "open_price": 160.0,
            "high_price": 164.0,
            "low_price": 159.0,
            "avg_price": 161.5,
            "volume_ratio": 1.2,
            "update_time": "2026-07-10 09:45:00",
        },
        daily_rows,
        intraday_rows,
        asof_date=date(2026, 7, 10),
        phase="RTH",
    )
    assert metrics["reference_price"] == 163.0
    assert metrics["rth_vwap"] == 161.5
    assert metrics["rth_bar_count"] == 4
    assert metrics["atr_pct"] is not None
    assert metrics["rsi14"] is not None
    assert metrics["technical_context_complete"] is True


def test_opend_quote_marks_prior_date_snapshot_stale():
    quote = quote_from_ticker_payload(
        {
            "ticker": "NVDA",
            "metrics": {
                "reference_price": 120.0,
                "reference_price_source": "moomoo_opend_last",
                "update_time": "2026-07-09 16:00:00",
            },
        },
        "2026-07-10 13:00 ET",
    )
    assert quote["is_stale"] is True
