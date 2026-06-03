"""exp-20260603-024: alpha-score market-regime VIX context scout.

Alpha search. This keeps the accepted exp-20260531-021 alpha-score
market-regime paper source fixed, then tests one new free external macro
context variable: signal-day VIX daily close must be <= 25.

Core signal generation, alpha_score weights, market-gate inputs, ranking,
exits, LLM/news replay, watchlists, and live/default orders are unchanged.
No JavaScript is used.
"""

from __future__ import annotations

import csv
import json
import math
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional as source


framework = source.framework

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260603-024"
STEM = "alpha_score_vix_regime_support"
TRIAL_FAMILY = "alpha_score_market_regime_external_macro_context"
CHANGED_VARIABLE = "alpha_score_market_regime_vix_below_25_support_v1"
RULE_VERSION = "alpha_score_market_regime_fred_vix_lte_25_v1"

FRED_VIX_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"
YAHOO_VIX_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
    "?period1=1727827200&period2=1776902400&interval=1d"
)
VIX_THRESHOLD = 25.0

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_024_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
VIX_CACHE_FILE = OUT_DIR / "vix_daily_close_source.txt"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260531-021"
    / "exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional.json"
)

_VIX_BY_DATE: dict[str, float] | None = None
_VIX_SOURCE_STATUS: dict[str, Any] = {}


def _patch_framework() -> None:
    source._patch_framework()
    for module in (source, source.source, getattr(source.source, "source", None), framework):
        if module is None:
            continue
        module.EXPERIMENT_ID = EXPERIMENT_ID
        module.STEM = STEM
        module.TRIAL_FAMILY = TRIAL_FAMILY
        module.CHANGED_VARIABLE = CHANGED_VARIABLE
        module.RULE_VERSION = RULE_VERSION
        module.OUT_DIR = OUT_DIR
        module.OUT_JSON = OUT_JSON
        module.BEFORE_AGG_JSON = BEFORE_AGG_JSON
        module.AFTER_AGG_JSON = AFTER_AGG_JSON
        module.LOG_JSON = LOG_JSON
        module.TICKET_JSON = TICKET_JSON
        module.CARD_MD = CARD_MD
        module.ARTIFACT_MD = ARTIFACT_MD
        module.EXPERIMENT_LOG = EXPERIMENT_LOG

    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _parse_vix_csv(raw_text: str) -> tuple[dict[str, float], str]:
    values: dict[str, float] = {}
    reader = csv.DictReader(raw_text.splitlines())
    fieldnames = {str(name) for name in (reader.fieldnames or [])}
    if {"observation_date", "VIXCLS"}.issubset(fieldnames):
        date_field = "observation_date"
        value_field = "VIXCLS"
        source_name = "FRED:VIXCLS"
    elif {"Date", "Close"}.issubset(fieldnames):
        date_field = "Date"
        value_field = "Close"
        source_name = "Stooq:^VIX"
    else:
        raise RuntimeError(f"Unrecognized VIX CSV columns: {sorted(fieldnames)}")

    for row in reader:
        date = str(row.get(date_field) or "")
        value = row.get(value_field)
        if not date or value in (None, "", "."):
            continue
        try:
            values[date] = float(value)
        except ValueError:
            continue
    if not values:
        raise RuntimeError("VIX daily close load produced no usable rows")
    return values, source_name


def _parse_yahoo_vix_json(raw_text: str) -> tuple[dict[str, float], str]:
    payload = json.loads(raw_text)
    result = (((payload.get("chart") or {}).get("result") or []) + [None])[0]
    if not isinstance(result, dict):
        raise RuntimeError("Yahoo VIX chart response missing result")
    timestamps = result.get("timestamp") or []
    quote = ((((result.get("indicators") or {}).get("quote") or []) + [None])[0]) or {}
    closes = quote.get("close") or []
    values: dict[str, float] = {}
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        date = datetime.fromtimestamp(float(ts), timezone.utc).date().isoformat()
        values[date] = float(close)
    if not values:
        raise RuntimeError("Yahoo VIX chart response produced no usable rows")
    return values, "Yahoo:^VIX"


def _parse_vix_payload(raw_text: str) -> tuple[dict[str, float], str]:
    stripped = raw_text.lstrip()
    if stripped.startswith("{"):
        return _parse_yahoo_vix_json(raw_text)
    return _parse_vix_csv(raw_text)


def _download_text(url: str, timeout: int) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 alpha-search-vix-scout"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _load_vix_by_date() -> dict[str, float]:
    global _VIX_BY_DATE
    if _VIX_BY_DATE is not None:
        return _VIX_BY_DATE

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_status = "downloaded"
    source_name = ""
    source_url = ""
    errors: list[str] = []
    if VIX_CACHE_FILE.exists():
        raw_text = VIX_CACHE_FILE.read_text(encoding="utf-8")
        values, source_name = _parse_vix_payload(raw_text)
        source_status = "cache"
        source_url = "cache"
    else:
        raw_text = ""
        for name, url, timeout, parser in (
            ("FRED:VIXCLS", FRED_VIX_URL, 12, _parse_vix_csv),
            ("Yahoo:^VIX", YAHOO_VIX_URL, 30, _parse_yahoo_vix_json),
        ):
            try:
                raw_text = _download_text(url, timeout)
                values, source_name = parser(raw_text)
                source_url = url
                break
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        else:
            raise RuntimeError(
                "Unable to fetch free VIX daily close from primary or fallback: "
                + "; ".join(errors)
            )
        VIX_CACHE_FILE.write_text(raw_text, encoding="utf-8")

    _VIX_SOURCE_STATUS.update(
        {
            "url": source_url,
            "source_name": source_name,
            "primary_url": FRED_VIX_URL,
            "fallback_url": YAHOO_VIX_URL,
            "cache_file": framework.base._repo_rel(VIX_CACHE_FILE),
            "status": source_status,
            "usable_rows": len(values),
            "min_date": min(values),
            "max_date": max(values),
            "fetch_errors": errors,
            "known_at": "signal_day_close_before_next_open_paper_entry",
        }
    )
    _VIX_BY_DATE = values
    return values


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, audit = source._candidate_rows_for_window(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    vix_by_date = _load_vix_by_date()
    filtered: list[dict[str, Any]] = []
    reject_counts: dict[str, int] = {
        "missing_vixcls": 0,
        "vix_above_threshold": 0,
    }
    kept_by_bucket: dict[str, int] = {
        "vix_lte_25": 0,
    }

    for row in candidates:
        date_value = str(row.get("date") or row.get("signal_date") or "")
        vix_value = vix_by_date.get(date_value)
        if vix_value is None:
            reject_counts["missing_vixcls"] += 1
            continue
        if vix_value > VIX_THRESHOLD:
            reject_counts["vix_above_threshold"] += 1
            continue
        kept_by_bucket["vix_lte_25"] += 1
        filtered.append(
            {
                **row,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "vix_context_rule_version": RULE_VERSION,
                "vix_daily_close": framework.base._round(vix_value, 4),
                "vix_threshold_max": VIX_THRESHOLD,
                "vix_regime_bucket": "vix_lte_25",
                "vix_known_at": "signal_day_close_before_next_open_paper_entry",
                "vix_data_source": _VIX_SOURCE_STATUS.get("source_name"),
                "macro_context_alters_orders": False,
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    return filtered, {
        **audit,
        "rule_version": RULE_VERSION,
        "source_rule_version": source.RULE_VERSION,
        "source_experiment_id": "exp-20260531-021",
        "vix_threshold_max": VIX_THRESHOLD,
        "vix_data_source": dict(_VIX_SOURCE_STATUS),
        "vix_reject_counts": reject_counts,
        "vix_kept_counts": kept_by_bucket,
        "candidate_count_before_vix_filter": len(candidates),
        "candidate_count_after_vix_filter": len(filtered),
    }


def _accepted_comparator(payload: dict[str, Any]) -> dict[str, Any]:
    accepted = json.loads(ACCEPTED_SOURCE_JSON.read_text(encoding="utf-8"))
    accepted_aggregate = accepted["delta_metrics"]["aggregate"]
    current_aggregate = payload["delta_metrics"]["aggregate"]
    accepted_after_ev = float(accepted_aggregate["after_expected_value_score_sum"])
    accepted_after_pnl = float(accepted_aggregate["after_total_pnl_sum"])
    current_after_ev = float(current_aggregate["after_expected_value_score_sum"])
    current_after_pnl = float(current_aggregate["after_total_pnl_sum"])
    return {
        "comparator_experiment_id": "exp-20260531-021",
        "comparator_artifact": framework.base._repo_rel(ACCEPTED_SOURCE_JSON),
        "accepted_after_expected_value_score": framework.base._round(accepted_after_ev, 6),
        "current_after_expected_value_score": framework.base._round(current_after_ev, 6),
        "delta_vs_accepted_expected_value_score": framework.base._round(
            current_after_ev - accepted_after_ev,
            6,
        ),
        "accepted_after_total_pnl": framework.base._round(accepted_after_pnl, 2),
        "current_after_total_pnl": framework.base._round(current_after_pnl, 2),
        "delta_vs_accepted_total_pnl": framework.base._round(
            current_after_pnl - accepted_after_pnl,
            2,
        ),
        "passed": current_after_ev > accepted_after_ev and current_after_pnl > accepted_after_pnl,
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = source._postprocess_payload(payload)
    comparator = _accepted_comparator(payload)
    gate4 = payload["gate4"]
    if not comparator["passed"]:
        gate4["passed"] = False
        if "accepted_comparator_underperformed" not in gate4["failed_reasons"]:
            gate4["failed_reasons"].append("accepted_comparator_underperformed")
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "positive_replay_lead_requires_shared_vix_adapter"
        if gate4["passed"]
        else "rejected_alpha_score_vix_regime_support"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Alpha-score market-regime paper candidates may have cleaner "
                "replacement value when a free external macro stress field, "
                "free VIX daily close, is not elevated on the signal date."
            ),
            "change_type": "default_off_paper_macro_context_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260531-021",
                "exp-20260531-024",
                "exp-20260601-020",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "free_external_macro_regime_field",
            "accepted_comparator": comparator,
            "prediction": {
                "success_probability": 0.27,
                "expected_ev_delta": 0.15,
                "expected_pnl_delta": 4000.0,
                "main_failure_modes": [
                    "late_strong_regression",
                    "drawdown_drift",
                    "thin_macro_overlap",
                    "production_ingestion_missing",
                    "accepted_comparator_underperformed",
                ],
                "confidence_reason": (
                    "VIX is an orthogonal free macro context, but alpha-score "
                    "already uses SPY/IWM risk appetite and prior source "
                    "composition refinements failed."
                ),
                "recorded_at": "2026-06-03T21:12:47+00:00",
                "brier_score": round((0.27 - actual_success) ** 2, 6),
            },
            "parameters": {
                **payload.get("parameters", {}),
                "vix_source": dict(_VIX_SOURCE_STATUS),
                "vix_threshold_max": VIX_THRESHOLD,
                "single_causal_variable": CHANGED_VARIABLE,
                "acceptance": {
                    "aggregate_ev_delta_gt": 0,
                    "aggregate_pnl_delta_gt": 0,
                    "ev_improved_windows": 3,
                    "pnl_improved_windows": 3,
                    "max_drawdown_worse": 0.005,
                    "min_target_trades": 20,
                    "min_target_windows": 3,
                    "must_beat_accepted_exp_20260531_021": True,
                    "promotion_requires_shared_vix_ingestion_adapter": True,
                },
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "entry / risk allocation: adding one free external VIX "
                    "stress context to the accepted alpha-score market-regime "
                    "paper source may avoid weak macro-stress candidates."
                ),
                "2_history_check": {
                    "exp-20260531-021": (
                        "Accepted replay lead for alpha-score market-regime "
                        "safe notional; this is the required comparator."
                    ),
                    "exp-20260531-024": (
                        "Accepted source-consensus support; do not retune source sets."
                    ),
                    "exp-20260601-020": (
                        "Rejected alpha/fundamental pair due drawdown, concentration, "
                        "and baseline caveat."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "docs/backtesting.md three fixed windows; positive aggregate "
                    "EV/PnL; all windows improve; drawdown drift <=0.5pp; "
                    "target trades >=20 across all windows; concentration passes; "
                    "must beat accepted exp-20260531-021 before any retention."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260603_024_alpha_score_vix_regime_support.py"
                ),
            },
            "production_impact": {
                "alters_candidate_ranking": False,
                "alters_exits": False,
                "alters_orders": False,
                "alters_signal_generation": False,
                "alters_sizing": False,
                "backtester_adapter_changed": False,
                "default_off_paper_only": True,
                "llm_or_news_changed": False,
                "production_orders_changed": False,
                "production_signal_path_changed": False,
                "production_watchlist_changed": False,
                "replay_only": True,
                "run_adapter_changed": False,
                "shared_policy_changed": False,
                "trade_enabled": False,
                "promotion_blocker": "No shared production/backtest FRED VIX ingestion adapter exists.",
            },
            "production_parity": {
                "positive_change_retained": gate4["passed"],
                "shared_vix_ingestion_adapter_exists": False,
                "production_order_path_changed": False,
                "trade_enabled": False,
                "promotion_allowed": False,
                "note": (
                    "A positive result would remain replay-only until daily VIX "
                    "ingestion is shared by production and backtest paths."
                ),
            },
            "interpretation": (
                "VIX filtering passed the replay gates and beat the accepted "
                "alpha-score comparator, but it remains unpromoted until shared "
                "VIX ingestion/parity exists."
                if gate4["passed"]
                else (
                    "Do not promote VIX filtering. It either failed Gate 4 or "
                    "underperformed the accepted alpha-score market-regime paper "
                    "source."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If revisiting macro context, first add shared production/backtest "
                "VIX ingestion and only then test forward replacement rows. Do not "
                "retune VIX thresholds on this frozen sample."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate2"]["target_trade_field_coverage"] = framework._field_coverage(
        all_target_trades,
        [
            "ticker",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "paper_notional_usd",
            "known_at",
            "alpha_score",
            "rank_score_validity_regime_bucket",
            "vix_daily_close",
            "vix_threshold_max",
            "vix_regime_bucket",
            "vix_known_at",
        ],
    )
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
        framework.base._repo_rel(OUT_JSON),
        framework.base._repo_rel(BEFORE_AGG_JSON),
        framework.base._repo_rel(AFTER_AGG_JSON),
        framework.base._repo_rel(VIX_CACHE_FILE),
        framework.base._repo_rel(LOG_JSON),
        framework.base._repo_rel(TICKET_JSON),
        framework.base._repo_rel(CARD_MD),
        framework.base._repo_rel(ARTIFACT_MD),
        framework.base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates after VIX |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["candidate_audits"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=audit.get("candidate_count_after_vix_filter"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    comparator = payload["accepted_comparator"]
    return "\n".join(
        [
            "# exp-20260603-024 Alpha-Score VIX Regime Support",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: keep exp-20260531-021 alpha-score market-regime source fixed, but admit paper candidates only when free daily `VIX <= 25` on the signal date.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta vs core baseline: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta vs core baseline: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Accepted Comparator",
            "",
            "```json",
            json.dumps(comparator, indent=2, sort_keys=True),
            "```",
            "",
            "## VIX Source",
            "",
            "```json",
            json.dumps(payload["parameters"]["vix_source"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result would still need shared FRED VIX ingestion and parity tests before activation.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Alpha-score VIX regime support",
        "status": payload["status"],
        "decision": payload["decision"],
        "json": framework.base._repo_rel(OUT_JSON),
        "card": framework.base._repo_rel(CARD_MD),
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "before_aggregate": payload["judge_before_aggregate"],
        "after_aggregate": payload["judge_after_aggregate"],
        "summary": payload["interpretation"],
        "completed_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "failed_reasons": payload["gate4"]["failed_reasons"],
            "result_file": framework.base._repo_rel(OUT_JSON),
            "card_file": framework.base._repo_rel(CARD_MD),
            "artifact_file": framework.base._repo_rel(ARTIFACT_MD),
            "gate4_passed": payload["gate4"]["passed"],
            "delta_metrics": {
                "expected_value_score": payload["expected_value_score_delta"],
                "total_pnl": payload["total_pnl_delta"],
                "max_drawdown_pct": payload["delta_metrics"]["aggregate"][
                    "max_drawdown_delta_max"
                ],
            },
        },
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    report = _build_report(payload)
    framework.base._write_text(CARD_MD, report)
    framework.base._write_text(ARTIFACT_MD, report)
    framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _patch_framework()
    payload = _postprocess_payload(framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "accepted_comparator": payload["accepted_comparator"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "card": framework.base._repo_rel(CARD_MD),
                    "artifact": framework.base._repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
