"""exp-20260606-007: SEC Item 2.03 credit absorption candidate pool.

This alpha search tests one replay-only/default-off paper candidate source:
SEC 8-K rows that include both Item 1.01 and Item 2.03, while excluding
Item 3.02 dilution rows. The hypothesis is that non-dilutive credit capacity
events become tradable only after same-day OHLCV absorption confirms demand.

No production adapter, live order path, shared policy, ranking, sizing, exits,
LLM/news path, or watchlist is changed. No JavaScript is used.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import exp_20260605_018_sec_operational_8k_absorption_candidate_pool as base  # noqa: E402


EXP_ID = "exp-20260606-007"
STEM = "sec_item203_credit_absorption_candidate_pool"
TRIAL_FAMILY = "sec_item203_non_dilutive_credit_absorption_candidate_pool"
TRIAL_VARIANT_ID = "sec_item203_credit_absorption_top1_delayed_entry_v1"
CHANGED_VARIABLE = "sec_item_203_non_dilutive_credit_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REQUIRED_ITEM_CODES = frozenset({"1.01", "2.03"})
EXCLUDED_ITEM_CODES = frozenset({"2.02", "3.02"})
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 30_000_000.0
MAX_SIGNAL_VOLUME_RATIO_20D = 3.00
MIN_SIGNAL_CLOSE_LOCATION = 0.60
MIN_SIGNAL_DAY_RETURN = 0.0
MIN_RET20_EXCESS_SPY = 0.0

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This runner changes no production code. It uses only historical "
        "PIT-safe SEC filing feature rows, first usable trading-day OHLCV "
        "available after the close, and a delayed next-open paper entry. A "
        "positive result would still require a separate shared default-off SEC "
        "filing-feature adapter and parity tests before any report queue, "
        "candidate priority, or order surface could change."
    ),
}

_BASE_BUILD_PAYLOAD = base.build_payload
_BASE_GATE4 = base._gate4


def _candidate_from_feature_row(
    row: dict[str, Any],
    *,
    frames: dict[str, Any],
    spy_frame: Any,
) -> tuple[dict[str, Any] | None, str]:
    ticker = str(row.get("ticker") or "").upper()
    usable = str(row.get("usable_trade_date") or "")[:10]
    window = base._window_name(usable)
    if not ticker or not usable or window is None:
        return None, "outside_window_or_missing_ticker"
    if "8-K" not in str(row.get("form_type") or "").upper():
        return None, "not_8k"

    codes = base._item_codes(row.get("eight_k_item_type"))
    if not REQUIRED_ITEM_CODES.issubset(codes):
        return None, "missing_required_101_203_item_pair"
    if codes.intersection(EXCLUDED_ITEM_CODES):
        return None, "excluded_dilution_or_earnings_item"

    frame = frames.get(ticker)
    if frame is None:
        return None, "missing_price_history"
    signal_pos = base._frame_pos_on_or_after(frame, usable)
    spy_pos = base._frame_pos_on_or_after(spy_frame, usable)
    if signal_pos is None or spy_pos is None:
        return None, "missing_signal_day"

    entry_pos = signal_pos + 1
    exit_pos = entry_pos + base.HOLD_DAYS
    if exit_pos >= len(frame):
        return None, "missing_exit_price"

    signal_date = str(frame.index[signal_pos].date())
    entry_date = str(frame.index[entry_pos].date())
    exit_date = str(frame.index[exit_pos].date())
    if not (base.WINDOWS[window]["start"] <= entry_date <= base.WINDOWS[window]["end"]):
        return None, "entry_outside_window"

    signal_close = base._float_or_none(frame["Close"].iloc[signal_pos])
    if signal_close is None or signal_close < MIN_PRICE:
        return None, "price_floor"

    adv20 = base._avg_dollar_volume(frame, signal_pos)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None, "adv20_floor"

    volume_ratio_20d = base._volume_ratio(frame, signal_pos)
    if volume_ratio_20d is None or volume_ratio_20d > MAX_SIGNAL_VOLUME_RATIO_20D:
        return None, "extreme_signal_volume"

    close_location = base._close_location(frame, signal_pos)
    if close_location is None or close_location < MIN_SIGNAL_CLOSE_LOCATION:
        return None, "weak_close_location"

    signal_day_return = base._ret(frame, signal_pos, 1)
    if signal_day_return is None or signal_day_return < MIN_SIGNAL_DAY_RETURN:
        return None, "negative_signal_day_return"

    ret20 = base._ret(frame, signal_pos, 20)
    spy_ret20 = base._ret(spy_frame, spy_pos, 20)
    if ret20 is None or spy_ret20 is None or ret20 - spy_ret20 < MIN_RET20_EXCESS_SPY:
        return None, "weak_ret20_excess_spy"

    entry_open = base._float_or_none(frame["Open"].iloc[entry_pos])
    exit_close = base._float_or_none(frame["Close"].iloc[exit_pos])
    if entry_open is None or exit_close is None or entry_open <= 0.0 or exit_close <= 0.0:
        return None, "missing_open_or_close"

    gross_return = exit_close / entry_open - 1.0
    net_return = gross_return - base.ROUND_TRIP_COST_PCT
    absorption_score = (
        2.0 * close_location
        + 5.0 * min(max(signal_day_return, 0.0), 0.10)
        + 2.0 * min(max(ret20 - spy_ret20, 0.0), 0.30)
        + min(volume_ratio_20d, MAX_SIGNAL_VOLUME_RATIO_20D) / MAX_SIGNAL_VOLUME_RATIO_20D
    )
    return {
        "ticker": ticker,
        "usable_trade_date": usable,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "window": window,
        "form_type": row.get("form_type"),
        "eight_k_item_type": row.get("eight_k_item_type"),
        "source_accession": row.get("source_accession"),
        "event_date": str(row.get("event_date") or "")[:10],
        "filing_date": str(row.get("filing_date") or "")[:10],
        "accepted_datetime": row.get("accepted_datetime"),
        "status": "price_ready",
        "strategy": STEM,
        "rule_version": RULE_VERSION,
        "required_item_codes": sorted(REQUIRED_ITEM_CODES),
        "excluded_item_codes": sorted(EXCLUDED_ITEM_CODES),
        "signal_close": round(signal_close, 6),
        "signal_day_return": round(signal_day_return, 6),
        "ret20": round(ret20, 6),
        "spy_ret20": round(spy_ret20, 6),
        "ret20_excess_spy": round(ret20 - spy_ret20, 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "volume_ratio_20d": round(volume_ratio_20d, 6),
        "close_location": round(close_location, 6),
        "candidate_selection_score": round(absorption_score, 6),
        "entry_open": round(entry_open, 6),
        "exit_close": round(exit_close, 6),
        "gross_return_pct": round(gross_return * 100.0, 6),
        "net_return_pct": round(net_return * 100.0, 6),
        "notional": base.PAPER_NOTIONAL,
        "shares": base.PAPER_NOTIONAL / entry_open,
        "pnl": round(base.PAPER_NOTIONAL * net_return, 2),
        "known_at": "usable_trade_date_close_before_next_open_delayed_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }, "candidate_ready"


def _gate4(
    aggregate_comparison: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    gate4 = _BASE_GATE4(aggregate_comparison, results, target_summary)
    if gate4["passed"]:
        gate4["decision"] = (
            "positive_replay_lead_not_promoted_requires_sec_item203_adapter"
        )
        gate4["status"] = "observed_only"
        gate4["rationale"] = (
            "The delayed-entry SEC Item 1.01+2.03 non-dilutive credit "
            "absorption source improved all canonical windows and passed "
            "sample, drawdown, survival, and concentration guards. It remains "
            "replay-only until a shared default-off adapter and parity tests "
            "are implemented."
        )
    else:
        gate4["decision"] = "rejected_sec_item203_credit_absorption_candidate_pool"
        gate4["status"] = "rejected"
        gate4["rationale"] = (
            "One or more Gate 4 checks failed, so this SEC Item 1.01+2.03 "
            "credit absorption source is not retained or promoted."
        )
    return gate4


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} SEC Item 2.03 Credit Absorption Candidate Pool",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        base._window_table(payload["results"]),
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in payload["gate4"]["gates"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Rule",
            "",
            (
                "Select PIT-safe SEC 8-K feature rows with both item codes "
                "1.01 and 2.03, exclude 2.02 and 3.02, require first usable "
                f"trading-day close-location >= {MIN_SIGNAL_CLOSE_LOCATION}, "
                f"volume_ratio_20d <= {MAX_SIGNAL_VOLUME_RATIO_20D}, "
                "nonnegative signal-day return, and nonnegative 20d excess "
                "return versus SPY. Entry is delayed to the next open after "
                "that close is known."
            ),
            "",
            "## Decision Rationale",
            "",
            payload["gate4"]["rationale"],
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260606_007_sec_item203_credit_absorption_candidate_pool.py"
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    base.ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    base.ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _patch_base() -> None:
    base.EXP_ID = EXP_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OUT_DIR = base.REPO_ROOT / "data" / "experiments" / EXP_ID
    base.OUT_JSON = base.OUT_DIR / f"exp_20260606_007_{STEM}.json"
    base.BEFORE_JSON = base.OUT_DIR / f"{STEM}_before_aggregate.json"
    base.AFTER_JSON = base.OUT_DIR / f"{STEM}_after_aggregate.json"
    base.LOG_JSON = base.REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
    base.TICKET_JSON = base.REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
    base.CARD_MD = base.REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
    base.ARTIFACT_MD = (
        base.REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
    )
    base.MANIFEST_JSON = base.REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
    base.INCLUDED_ITEM_CODES = REQUIRED_ITEM_CODES
    base.EXCLUDED_ITEM_PREFIXES = tuple(sorted(EXCLUDED_ITEM_CODES))
    base.MIN_PRICE = MIN_PRICE
    base.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    base.MAX_SIGNAL_VOLUME_RATIO_20D = MAX_SIGNAL_VOLUME_RATIO_20D
    base.MIN_SIGNAL_CLOSE_LOCATION = MIN_SIGNAL_CLOSE_LOCATION
    base.MIN_SIGNAL_DAY_RETURN = MIN_SIGNAL_DAY_RETURN
    base.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base._candidate_from_feature_row = _candidate_from_feature_row
    base._gate4 = _gate4
    base._write_artifact = _write_artifact


def build_payload() -> dict[str, Any]:
    _patch_base()
    payload = _BASE_BUILD_PAYLOAD()
    payload["experiment_id"] = EXP_ID
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = TRIAL_VARIANT_ID
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["rule_version"] = RULE_VERSION
    payload["preflight"] = {
        "alpha_hypothesis": (
            "SEC 8-K Item 1.01 plus 2.03 filings without Item 3.02 may "
            "identify non-dilutive credit capacity events that become "
            "tradable only when same-day OHLCV absorption confirms demand."
        ),
        "category": "entry_candidate_pool",
        "playbook_alignment": (
            "Uses a free, production-visible SEC feature layer and tests a "
            "candidate-pool source instead of LLM soft-ranking, Companyfacts "
            "peer retunes, FTD/FINRA retunes, post-earnings support stack "
            "retunes, or broad OHLCV-only pattern mining."
        ),
        "nearby_prior_experiments": {
            "exp-20260605-006": (
                "SEC EX-99 business-development text was aggregate positive "
                "but had concentration/window caveats."
            ),
            "exp-20260605-018": (
                "Operational 8-K absorption was rejected; this run uses a "
                "different SEC item-code financing mechanism."
            ),
            "exp-20260605-031": "SEC business-win inverse was rejected.",
            "exp-20260606-002": (
                "Strategic customer warrant alignment had zero target trades."
            ),
        },
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(base.WINDOWS.keys()),
            "aggregate_expected_value_delta": "> 0",
            "aggregate_pnl_delta": "> 0",
            "per_window_expected_value_delta": "3 of 3 windows > 0",
            "per_window_pnl_delta": "3 of 3 windows > 0",
            "minimum_target_trades": base.MIN_TARGET_TRADES,
            "minimum_target_windows": base.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": base.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": base.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": base.MAX_POSITIVE_HHI,
        },
    }
    payload["parameters"].update(
        {
            "required_item_codes": sorted(REQUIRED_ITEM_CODES),
            "excluded_item_codes": sorted(EXCLUDED_ITEM_CODES),
            "included_item_codes": sorted(REQUIRED_ITEM_CODES),
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "max_signal_volume_ratio_20d": MAX_SIGNAL_VOLUME_RATIO_20D,
            "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
            "min_signal_day_return": MIN_SIGNAL_DAY_RETURN,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "entry_policy": "next_open_after_first_usable_trading_day_close",
        }
    )
    payload["prediction"] = {
        "success_probability": 0.20,
        "expected_ev_delta": 0.10,
        "expected_pnl_delta": 1500.0,
        "main_failure_modes": [
            "window_regression",
            "drawdown_drift_too_high",
            "financing_false_positive",
            "concentration_failed",
        ],
        "confidence_reason": (
            "This uses a wider PIT SEC item-code field than recent sparse "
            "business-text/warrant scouts, but financing events are noisy and "
            "recent SEC candidate pools often failed old_thin or concentration."
        ),
        "recorded_at": "2026-06-06T05:06:11Z",
    }
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["llm_metrics"] = {
        "used_llm": False,
        "llm_change_scope": "none",
        "note": "LLM soft-ranking data was not used; this is deterministic free SEC/OHLCV data.",
    }
    payload["next_action"] = (
        "If positive, build a shared default-off SEC Item 1.01+2.03 "
        "filing-feature adapter with delayed-entry semantics and parity tests "
        "before promotion."
        if payload["gate4"]["passed"]
        else "Do not retune nearby SEC Item 2.03 absorption thresholds on this frozen sample; pivot to a different free-data candidate-pool mechanism or forward replacement rows."
    )
    return payload


def main() -> int:
    _patch_base()
    payload = build_payload()
    base.persist(payload)
    print(
        {
            "experiment_id": payload["experiment_id"],
            "decision": payload["gate4"]["decision"],
            "aggregate": payload["aggregate"]["comparison"],
            "target_summary": payload["target_summary"],
            "gate4": payload["gate4"],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
