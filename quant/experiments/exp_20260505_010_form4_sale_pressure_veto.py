"""exp-20260505-010: Form 4 sale-pressure entry de-risk replay.

Alpha search. This tests one deterministic event-overlay variable:
whether recent large, non-10b5-1 open-market insider sale pressure should
reduce risk for otherwise valid long entries. It deliberately avoids LLM
soft-ranking and broad universe expansion because both are currently
sample/data limited in the experiment log.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import feature_layer as fl  # noqa: E402
import portfolio_engine as pe  # noqa: E402
import risk_engine as re  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-010"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "form4_sale_pressure_veto.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_form4_sale_pressure_veto.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

FORM4_PATH = REPO_ROOT / "data" / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"

SALE_LOOKBACK_DAYS = 20
SALE_VALUE_MIN_USD = 500_000

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("sale_pressure_0_00x", {"risk_multiplier": 0.0}),
    ("sale_pressure_0_25x", {"risk_multiplier": 0.25}),
])


def _round(value, digits=4):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _is_true(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _load_sale_pressure_events():
    raw_rows = 0
    qualified_rows = 0
    aggregates = {}
    roleless_rows = 0

    with FORM4_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            raw_rows += 1
            row = json.loads(line)
            ticker = str(row.get("ticker") or "").upper().strip()
            tx_date = _parse_date(row.get("usable_trade_date") or row.get("transaction_date"))
            value = row.get("transaction_value")
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = 0.0

            role_flag = any(
                _is_true(row.get(key))
                for key in ("is_officer", "is_director", "is_ten_percent_owner")
            )
            if not role_flag:
                roleless_rows += 1

            if (
                not ticker
                or tx_date is None
                or not _is_true(row.get("pit_safe_flag", True))
                or str(row.get("transaction_code") or "").upper() != "S"
                or str(row.get("acquired_disposed_code") or "").upper() != "D"
                or _is_true(row.get("10b5_1_flag"))
                or _is_true(row.get("option_exercise_flag"))
                or value < SALE_VALUE_MIN_USD
                or not role_flag
            ):
                continue

            qualified_rows += 1
            key = (ticker, tx_date)
            current = aggregates.setdefault(
                key,
                {
                    "ticker": ticker,
                    "date": tx_date,
                    "total_value_usd": 0.0,
                    "transaction_count": 0,
                    "owners": set(),
                    "officer_sale": False,
                    "director_sale": False,
                    "ten_percent_owner_sale": False,
                },
            )
            current["total_value_usd"] += value
            current["transaction_count"] += 1
            owner = str(row.get("owner_name") or row.get("reporting_owner") or "").strip()
            if owner:
                current["owners"].add(owner)
            current["officer_sale"] = current["officer_sale"] or _is_true(row.get("is_officer"))
            current["director_sale"] = current["director_sale"] or _is_true(row.get("is_director"))
            current["ten_percent_owner_sale"] = current["ten_percent_owner_sale"] or _is_true(
                row.get("is_ten_percent_owner")
            )

    by_ticker = defaultdict(list)
    for event in aggregates.values():
        by_ticker[event["ticker"]].append({
            **event,
            "owners": sorted(event["owners"]),
            "owner_count": len(event["owners"]),
        })
    for events in by_ticker.values():
        events.sort(key=lambda item: item["date"])

    summary = {
        "source": str(FORM4_PATH.relative_to(REPO_ROOT)),
        "raw_rows": raw_rows,
        "qualified_rows": qualified_rows,
        "aggregated_event_count": sum(len(events) for events in by_ticker.values()),
        "qualified_ticker_count": len(by_ticker),
        "roleless_rows": roleless_rows,
        "filters": {
            "transaction_code": "S",
            "acquired_disposed_code": "D",
            "pit_safe_flag": True,
            "10b5_1_flag": False,
            "option_exercise_flag": False,
            "transaction_value_min_usd": SALE_VALUE_MIN_USD,
            "role_required": "officer/director/10_percent_owner",
            "lookback_calendar_days": SALE_LOOKBACK_DAYS,
        },
    }
    return dict(by_ticker), summary


SALE_EVENTS_BY_TICKER, FORM4_SUMMARY = _load_sale_pressure_events()


def _events_in_window(ticker, as_of_date):
    if not ticker or as_of_date is None:
        return []
    start = as_of_date - timedelta(days=SALE_LOOKBACK_DAYS)
    events = []
    for event in SALE_EVENTS_BY_TICKER.get(str(ticker).upper(), []):
        event_date = event["date"]
        if start <= event_date <= as_of_date:
            events.append(event)
        if event_date > as_of_date:
            break
    return events


def _sale_pressure_payload(ticker, as_of_date):
    events = _events_in_window(ticker, as_of_date)
    if not events:
        return None
    total_value = sum(float(event["total_value_usd"]) for event in events)
    owners = sorted({owner for event in events for owner in event["owners"]})
    return {
        "lookback_days": SALE_LOOKBACK_DAYS,
        "event_count": len(events),
        "transaction_count": sum(int(event["transaction_count"]) for event in events),
        "owner_count": len(owners),
        "total_value_usd": round(total_value, 2),
        "latest_event_date": max(event["date"] for event in events).isoformat(),
        "officer_sale": any(event["officer_sale"] for event in events),
        "director_sale": any(event["director_sale"] for event in events),
        "ten_percent_owner_sale": any(event["ten_percent_owner_sale"] for event in events),
        "events": [
            {
                "date": event["date"].isoformat(),
                "total_value_usd": round(float(event["total_value_usd"]), 2),
                "transaction_count": event["transaction_count"],
                "owner_count": event["owner_count"],
            }
            for event in events
        ],
    }


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _make_compute_features(original_compute_features):
    def compute_features(ticker, ohlcv_data, earnings_data):
        features = original_compute_features(ticker, ohlcv_data, earnings_data)
        if features is None:
            return None
        if ohlcv_data is not None and not ohlcv_data.empty:
            features["as_of_date"] = ohlcv_data.index[-1].date().isoformat()
        return features

    return compute_features


def _make_enricher(original_enrich_signals):
    def enrich_signals(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich_signals(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        for sig in enriched:
            ticker = sig.get("ticker")
            features = features_dict.get(ticker) or {}
            as_of_date = _parse_date(features.get("as_of_date"))
            pressure = _sale_pressure_payload(ticker, as_of_date)
            if pressure:
                sig["form4_sale_pressure"] = pressure
        return enriched

    return enrich_signals


def _zero_sizing(original: dict, risk_multiplier: float) -> dict:
    zeroed = dict(original)
    zeroed["risk_pct"] = 0.0
    zeroed["risk_amount_usd"] = 0.0
    zeroed["shares_to_buy"] = 0
    zeroed["position_value_usd"] = 0.0
    zeroed["position_pct_of_portfolio"] = 0.0
    zeroed["form4_sale_pressure_risk_multiplier_applied"] = risk_multiplier
    return zeroed


def _make_variant_sizer(original_size_signals, risk_multiplier: float):
    def size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            if not sig.get("form4_sale_pressure"):
                continue
            sizing = sig.get("sizing") or {}
            if (sizing.get("shares_to_buy") or 0) <= 0:
                continue
            if risk_multiplier <= 0:
                sig["sizing"] = _zero_sizing(sizing, risk_multiplier)
                continue
            entry = sig.get("entry_price")
            stop = sig.get("stop_price")
            current_risk_pct = sizing.get("risk_pct")
            if not entry or not stop or current_risk_pct is None:
                continue
            new_sizing = pe.compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=float(current_risk_pct) * risk_multiplier,
                max_position_pct=sizing.get("max_position_pct_applied") or pe.MAX_POSITION_PCT,
            )
            if not new_sizing:
                continue
            for key, value in sizing.items():
                if key not in new_sizing:
                    new_sizing[key] = value
            new_sizing["risk_pct"] = float(current_risk_pct) * risk_multiplier
            new_sizing["form4_sale_pressure_risk_multiplier_applied"] = risk_multiplier
            sig["sizing"] = new_sizing
        return sized

    return size_signals


def _run_window(window: dict, variant: dict | None = None) -> dict:
    original_compute_features = fl.compute_features
    original_enrich_signals = re.enrich_signals
    original_size_signals = pe.size_signals
    fl.compute_features = _make_compute_features(original_compute_features)
    re.enrich_signals = _make_enricher(original_enrich_signals)
    if variant is not None:
        pe.size_signals = _make_variant_sizer(
            original_size_signals,
            variant["risk_multiplier"],
        )
    try:
        engine = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        )
        result = engine.run()
        result["form4_sale_pressure_source_summary"] = FORM4_SUMMARY
        return result
    finally:
        fl.compute_features = original_compute_features
        re.enrich_signals = original_enrich_signals
        pe.size_signals = original_size_signals


def _delta(before: dict, after: dict) -> dict:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
        "signals_generated",
        "signals_survived",
    )
    return {key: _round((after.get(key) or 0) - (before.get(key) or 0), 6) for key in keys}


def _sale_pressure_trade_attribution(result: dict) -> dict:
    rows = []
    for trade in result.get("trades") or []:
        sizing = trade.get("sizing_multipliers") or {}
        if sizing.get("form4_sale_pressure_risk_multiplier_applied") is not None:
            rows.append(trade)
    return {
        "trade_count": len(rows),
        "wins": sum(1 for row in rows if (row.get("pnl") or 0) > 0),
        "losses": sum(1 for row in rows if (row.get("pnl") or 0) <= 0),
        "total_pnl_usd": _round(sum(row.get("pnl") or 0 for row in rows), 2),
        "trades": [
            {
                "ticker": row.get("ticker"),
                "strategy": row.get("strategy"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "pnl": _round(row.get("pnl"), 2),
                "exit_reason": row.get("exit_reason"),
                "sizing_multipliers": row.get("sizing_multipliers") or {},
            }
            for row in rows
        ],
    }


def _sale_pressure_candidate_count(result: dict):
    # entry_audit is built before experiment-only signal annotations are
    # retained, so it cannot reliably count the touched candidate cohort.
    # The execution-level attribution below is the trustworthy sample count.
    return None


def _aggregate(rows: dict) -> dict:
    baseline_ev = sum(float(row["before"]["expected_value_score"] or 0) for row in rows.values())
    baseline_pnl = sum(float(row["before"]["total_pnl"] or 0) for row in rows.values())
    ev_delta = sum(float(row["delta"]["expected_value_score"] or 0) for row in rows.values())
    pnl_delta = sum(float(row["delta"]["total_pnl"] or 0) for row in rows.values())
    return {
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / baseline_ev if baseline_ev else 0, 6),
        "baseline_expected_value_score_sum": _round(baseline_ev, 6),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "baseline_total_pnl_sum": _round(baseline_pnl, 2),
        "total_pnl_delta_pct": _round(pnl_delta / baseline_pnl if baseline_pnl else 0, 6),
        "ev_windows_improved": sum(1 for row in rows.values() if row["delta"]["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for row in rows.values() if row["delta"]["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for row in rows.values() if row["delta"]["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for row in rows.values() if row["delta"]["total_pnl"] < 0),
        "max_drawdown_delta_max": _round(max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6),
        "trade_count_delta_sum": sum(row["delta"]["trade_count"] for row in rows.values()),
        "win_rate_delta_min": _round(min(row["delta"]["win_rate"] for row in rows.values()), 6),
        "sharpe_daily_delta_max": _round(max(row["delta"]["sharpe_daily"] for row in rows.values()), 6),
        "sale_pressure_candidates_before": None,
        "sale_pressure_candidate_audit_note": (
            "entry_audit does not retain experiment-only form4_sale_pressure "
            "annotations; use sale_pressure_trades_after for touched executed sample."
        ),
        "sale_pressure_trades_before": sum(
            row["sale_pressure_trade_attribution_before"]["trade_count"]
            for row in rows.values()
        ),
        "sale_pressure_trades_after": sum(
            row["sale_pressure_trade_attribution_after"]["trade_count"]
            for row in rows.values()
        ),
    }


def _gate4_passed(aggregate: dict) -> bool:
    material = (
        aggregate["expected_value_score_delta_pct"] > 0.10
        or aggregate["sharpe_daily_delta_max"] > 0.10
        or aggregate["max_drawdown_delta_max"] < -0.01
        or aggregate["total_pnl_delta_pct"] > 0.05
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    return (
        material
        and aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] == 0
    )


def _make_payload(baselines, variants, best_name, best, accepted, generated_at):
    decision = "accepted" if accepted else "rejected"
    rejection_reason = None
    if not accepted:
        rejection_reason = (
            "Form 4 sale-pressure de-risking did not clear three-window Gate 4. "
            "Either the touched cohort was too small, or the sale-pressure signal "
            "does not improve replacement-value quality under the current core stack."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "deterministic_event_overlay_entry_allocation",
        "mechanism_family": "form4_sale_pressure_long_entry_derisk",
        "hypothesis": (
            "Recent large, non-10b5-1, non-option-exercise Form 4 insider sale "
            "pressure may identify lower-quality long entries; reducing risk for "
            "those otherwise valid signals should improve EV without adding noisy tickers."
        ),
        "alpha_hypothesis": {
            "category": "entry / allocation",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking is production-sample limited, event-bundle promotion "
                "needs closed forward paper evidence, and broad watchlist expansion was "
                "rejected. Transaction-level Form 4 data is now PIT-safe and gives a "
                "non-OHLCV discriminator instead of simple ticker noise."
            ),
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260504-034/049/053": (
                    "Form 4 purchase and event-bundle overlays were tested as separate "
                    "satellite event sleeves; this test is the opposite sign, a sale-pressure "
                    "de-risk overlay on core A/B entries."
                ),
                "exp-20260505-009": (
                    "Broad historical watchlist expansion was rejected because it added "
                    "noise; this does not expand the universe and requires a transaction "
                    "event discriminator."
                ),
                "LLM soft-ranking runs": (
                    "Production-aligned sample is still too small, so this run avoids "
                    "that blocked direction instead of forcing another LLM experiment."
                ),
            },
            "why_not_simple_repeat": (
                "No recent record found for non-10b5 Form 4 sale pressure as a core "
                "long-entry risk reducer; prior Form 4 work focused on purchase-side "
                "event sleeves and forward attribution."
            ),
        },
        "parameters": {
            "single_causal_variable": "risk multiplier for core signals with recent Form 4 sale pressure",
            "baseline_behavior": "No Form 4 sale-pressure de-risking on core A/B candidate signals.",
            "fixed_sale_definition": FORM4_SUMMARY["filters"],
            "tested_variants": VARIANTS,
            "best_variant": best_name,
            "locked_variables": [
                "universe",
                "entries",
                "exits",
                "candidate ordering",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "sector rules",
                "earnings rules",
                "add-ons",
                "gap cancels",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "date_range": {label: f"{w['start']} -> {w['end']}" for label, w in WINDOWS.items()},
        "snapshots": {label: w["snapshot"] for label, w in WINDOWS.items()},
        "market_regime_summary": {label: w["state_note"] for label, w in WINDOWS.items()},
        "before_metrics": {label: row["before"] for label, row in best["rows"].items()},
        "after_metrics": {label: row["after"] for label, row in best["rows"].items()},
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in best["rows"].items()},
            **best["aggregate"],
        },
        "variants": variants,
        "best_variant": best_name,
        "gate4": {
            "passed": accepted,
            "basis": (
                "Gate4 requires >10% aggregate EV lift, >0.1 Sharpe lift, >1pp "
                "drawdown reduction, >5% PnL lift, or more trades without win-rate "
                "decline; accepted variants also need EV improvement in at least two "
                "fixed windows and no EV-regressed window."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If a future sale-pressure overlay passes, implement the event feature "
                "and risk multiplier through shared production/backtest policy and add "
                "parity tests before enabling it."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this run uses structured "
                "PIT Form 4 data instead of treating the LLM as the problem."
            ),
        },
        "form4_source_summary": FORM4_SUMMARY,
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "Do not retry simple Form 4 sale-pressure veto/de-risk variants without a larger touched cohort or forward sale-pressure replacement-value evidence.",
            "A valid retry needs an added discriminator such as cluster selling, CFO/CEO-only selling, or post-signal adverse price reaction, not just a nearby notional/lookback tweak.",
            "Any accepted retry must move to shared production/backtest policy before promotion.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260505_010_form4_sale_pressure_veto.py",
        ],
    }


def _write_artifact(payload):
    delta = payload["delta_metrics"]
    lines = [
        f"# {EXPERIMENT_ID} Form 4 sale-pressure de-risk",
        "",
        f"Status: {payload['decision']}",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Gate 4",
        "",
        f"- passed: {payload['gate4']['passed']}",
        f"- best_variant: {payload['best_variant']}",
        f"- aggregate_ev_delta_sum: {delta['expected_value_score_delta_sum']}",
        f"- aggregate_ev_delta_pct: {delta['expected_value_score_delta_pct']}",
        f"- aggregate_pnl_delta_sum: {delta['total_pnl_delta_sum']}",
        f"- touched_candidates: {delta['sale_pressure_candidates_before']} ({delta['sale_pressure_candidate_audit_note']})",
        f"- touched_trades_after: {delta['sale_pressure_trades_after']}",
        "",
        "## Fixed Windows",
        "",
    ]
    for label, row in payload["variants"][payload["best_variant"]]["rows"].items():
        lines.extend([
            f"### {label}",
            "",
            f"- before: {row['before']}",
            f"- after: {row['after']}",
            f"- delta: {row['delta']}",
            "",
        ])
    if payload["rejection_reason"]:
        lines.extend(["## Rejection Reason", "", payload["rejection_reason"], ""])
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _append_experiment_log(payload):
    record = {
        "experiment_id": payload["experiment_id"],
        "generated_at": payload["generated_at"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "hypothesis": payload["hypothesis"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["delta_metrics"]["expected_value_score_delta_sum"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "production_impact": payload["production_impact"],
        "related_files": payload["related_files"],
    }
    new_line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    existing = []
    if EXPERIMENT_LOG.exists():
        for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                existing.append(line)
                continue
            if parsed.get("experiment_id") == EXPERIMENT_ID:
                continue
            existing.append(line)
    existing.append(new_line)
    EXPERIMENT_LOG.write_text("\n".join(existing) + "\n", encoding="utf-8")


def _update_playbook(payload):
    marker = "## Recent mechanism insights"
    entry = (
        "\n"
        f"- `{EXPERIMENT_ID}` ({payload['decision']}): Form 4 sale-pressure "
        "de-risk was tested on the three canonical windows. "
        f"Best `{payload['best_variant']}` aggregate EV delta "
        f"{payload['delta_metrics']['expected_value_score_delta_sum']} "
        f"({payload['delta_metrics']['expected_value_score_delta_pct']:.2%}), "
        f"PnL delta ${payload['delta_metrics']['total_pnl_delta_sum']}. "
        "Do not retry simple sale-pressure veto/de-risk variants without a "
        "larger touched cohort or a new discriminator such as cluster selling, "
        "CEO/CFO-only selling, or adverse post-sale price reaction.\n"
    )
    text = PLAYBOOK.read_text(encoding="utf-8")
    if f"`{EXPERIMENT_ID}`" in text:
        return
    if marker in text:
        text = text.replace(marker, marker + entry, 1)
    else:
        text = text + "\n" + marker + "\n" + entry
    PLAYBOOK.write_text(text, encoding="utf-8")


def main() -> int:
    import backtester as bt

    if "form4_sale_pressure_risk_multiplier_applied" not in bt.SIZING_MULTIPLIER_KEYS:
        bt.SIZING_MULTIPLIER_KEYS = (
            *bt.SIZING_MULTIPLIER_KEYS,
            "form4_sale_pressure_risk_multiplier_applied",
        )

    baselines = OrderedDict()
    for label, window in WINDOWS.items():
        result = _run_window(window)
        baselines[label] = {"raw": result, "metrics": _metrics(result)}

    variants = OrderedDict()
    for name, variant in VARIANTS.items():
        rows = OrderedDict()
        for label, window in WINDOWS.items():
            after_result = _run_window(window, variant)
            before = baselines[label]["metrics"]
            after = _metrics(after_result)
            rows[label] = {
                "window": window,
                "before": before,
                "after": after,
                "delta": _delta(before, after),
                "sale_pressure_candidate_count_before": _sale_pressure_candidate_count(
                    baselines[label]["raw"]
                ),
                "sale_pressure_trade_attribution_before": _sale_pressure_trade_attribution(
                    baselines[label]["raw"]
                ),
                "sale_pressure_trade_attribution_after": _sale_pressure_trade_attribution(
                    after_result
                ),
            }
        aggregate = _aggregate(rows)
        variants[name] = {
            "parameters": variant,
            "rows": rows,
            "aggregate": aggregate,
            "gate4_passed": _gate4_passed(aggregate),
        }

    ranked = sorted(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
        reverse=True,
    )
    best_name, best = ranked[0]
    accepted = best["gate4_passed"]
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = _make_payload(baselines, variants, best_name, best, accepted, generated_at)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": payload["decision"],
        "decision": payload["decision"],
        "title": "Form 4 sale-pressure de-risk",
        "summary": f"Best {best_name}; Gate4={accepted}",
        "best_variant": best_name,
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_artifact(payload)
    _append_experiment_log(payload)
    _update_playbook(payload)

    print(f"{EXPERIMENT_ID} {payload['decision']} best={best_name}")
    print(json.dumps(ticket["delta_metrics"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
