"""exp-20260608-022: volatility-relief confirmed compression breakout.

Replay-only alpha search. This tests one fixed interaction between two accepted
production-visible paper mechanisms: admit accepted narrow-range compression
breakout candidates only on dates where the accepted VIXY/SPY/QQQ volatility
relief context has passed. Compression thresholds and VIXY relief thresholds
are locked; this is not a parameter retune.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import exp_20260608_012_narrow_range_compression_breakout as previous
import volatility_relief_stock_leadership_paper_sleeve as vrelief


framework = previous.framework

EXPERIMENT_ID = "exp-20260608-022"
STEM = "compression_volatility_relief_confirmation"
TRIAL_FAMILY = "narrow_range_compression_volatility_relief_confirmation"
TRIAL_VARIANT_ID = "compression_on_accepted_vixy_relief_top1_10d_v1"
CHANGED_VARIABLE = (
    "narrow_range_compression_volatility_relief_confirmed_candidate_source_v1"
)
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_022_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ACCEPTED_COMPRESSION_EXPERIMENT_ID = "exp-20260608-013"
ACCEPTED_COMPRESSION_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_COMPRESSION_EXPERIMENT_ID
    / "exp_20260608_013_narrow_range_compression_shared_adapter.json"
)

VOLATILITY_RELIEF_CONFIRMATION_REQUIRED = True

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sample_too_thin",
        "compression_winners_removed",
        "volatility_relief_overlap",
        "window_regression",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "exp-20260608-013 accepted the fixed narrow-range compression helper "
        "and exp-20260607-019 accepted the fixed VIXY volatility-relief helper. "
        "Recent compression confirmation overlays were sample-thin, so this "
        "only tests whether an orthogonal accepted market-state context improves "
        "replacement value without retuning either threshold set."
    ),
    "recorded_at": "2026-06-08T18:13:45+00:00",
}

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
    "live_realism_evaluated": False,
    "live_ready": False,
    "parity_note": (
        "This experiment changes no production code. A positive result is a "
        "replay lead only unless a shared default-off adapter exposes the same "
        "accepted narrow-range compression source, accepted VIXY/SPY/QQQ "
        "volatility-relief context, same-ticker core-overlap exclusion, "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, and "
        "concentration controls in both historical replay and daily production."
    ),
}

BASE_CANDIDATE_ROWS_FOR_WINDOW = previous._candidate_rows_for_window
BASE_BUILD_PAYLOAD = previous._build_payload


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _date(value: str) -> datetime:
    return datetime.strptime(str(value)[:10], "%Y-%m-%d")


def _load_context_ticker_rows(
    tickers: set[str],
    dates: set[str],
) -> dict[str, list[dict[str, Any]]]:
    if not tickers or not dates:
        return {}
    start = (_date(min(dates)) - timedelta(days=10)).date().isoformat()
    end = _date(max(dates)).date().isoformat()
    out: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    with sqlite3.connect(framework.WAREHOUSE) as con:
        placeholders = ",".join("?" for _ in sorted(tickers))
        sql = (
            "select ticker, date, open, high, low, close, volume "
            "from ohlcv "
            f"where ticker in ({placeholders}) and date >= ? and date <= ? "
            "order by ticker, date"
        )
        for row in con.execute(sql, [*sorted(tickers), start, end]):
            ticker, day, open_, high, low, close, volume = row
            out.setdefault(str(ticker).upper(), []).append(
                {
                    "Date": str(day)[:10],
                    "Open": float(open_),
                    "High": float(high),
                    "Low": float(low),
                    "Close": float(close),
                    "Volume": float(volume),
                }
            )
    return {ticker: rows for ticker, rows in out.items() if rows}


def _with_volatility_context_tickers(
    snapshot: dict[str, list[dict[str, Any]]],
    dates: set[str],
) -> dict[str, list[dict[str, Any]]]:
    out = dict(snapshot)
    missing = {"VIXY", "SPY", "QQQ"} - set(out)
    out.update(_load_context_ticker_rows(missing, dates))
    return out


def _volatility_contexts_for_snapshot(
    snapshot: dict[str, list[dict[str, Any]]],
    dates: set[str],
) -> dict[str, dict[str, Any]]:
    rows_by_ticker = vrelief.leader._normalise_ohlcv_by_ticker(
        _with_volatility_context_tickers(snapshot, dates)
    )
    indices = {
        ticker: vrelief.leader._row_index(rows)
        for ticker, rows in rows_by_ticker.items()
    }
    contexts: dict[str, dict[str, Any]] = {}
    for signal_date in sorted(dates):
        context = vrelief._volatility_relief_context_for_day(
            rows_by_ticker=rows_by_ticker,
            indices=indices,
            signal_date=signal_date,
        )
        if context is None:
            contexts[signal_date] = {
                "date": signal_date,
                "passed": False,
                "reason": "missing_accepted_volatility_relief_context",
                "rule_version": vrelief.SOURCE_RULE_VERSION,
                "known_at": "after_signal_day_close_before_next_open_paper_entry",
            }
        else:
            contexts[signal_date] = context
    return contexts


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, contexts, scan = BASE_CANDIDATE_ROWS_FOR_WINDOW(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )
    raw_count = len(candidates)
    candidate_dates = {str(row.get("date") or "")[:10] for row in candidates}
    volatility_contexts = _volatility_contexts_for_snapshot(snapshot, candidate_dates)
    passed_dates = {
        signal_date
        for signal_date, context in volatility_contexts.items()
        if context.get("passed")
    }

    filtered: list[dict[str, Any]] = []
    filtered_by_date: dict[str, list[dict[str, Any]]] = {}
    rejected_non_relief_count = 0
    missing_relief_count = 0

    for row in candidates:
        signal_date = str(row.get("date") or "")[:10]
        context = volatility_contexts.get(signal_date)
        if context is None:
            context = {
                "date": signal_date,
                "passed": False,
                "reason": "missing_accepted_volatility_relief_context",
                "rule_version": vrelief.SOURCE_RULE_VERSION,
                "known_at": "after_signal_day_close_before_next_open_paper_entry",
            }
        confirmation = {
            "required": VOLATILITY_RELIEF_CONFIRMATION_REQUIRED,
            "passed": bool(context.get("passed")),
            "reason": context.get("reason"),
            "accepted_rule_version": vrelief.SOURCE_RULE_VERSION,
            "known_at": "after_signal_day_close_before_next_open_paper_entry",
            "thresholds_locked": True,
            "rule_version": RULE_VERSION,
        }
        row["volatility_relief_confirmation"] = confirmation
        row["volatility_relief_context"] = context
        row["rule_version"] = RULE_VERSION
        if not context.get("passed"):
            row["filter_reason"] = "missing_accepted_volatility_relief_context"
            if context.get("reason") == "missing_accepted_volatility_relief_context":
                missing_relief_count += 1
            else:
                rejected_non_relief_count += 1
            continue
        filtered.append(row)
        filtered_by_date.setdefault(signal_date, []).append(row)

    for context in contexts:
        signal_date = str(context.get("date") or "")[:10]
        day_rows = filtered_by_date.get(signal_date, [])
        relief_context = volatility_contexts.get(signal_date) or {
            "date": signal_date,
            "passed": False,
            "reason": "missing_accepted_volatility_relief_context",
            "rule_version": vrelief.SOURCE_RULE_VERSION,
        }
        context["volatility_relief_confirmation_required"] = (
            VOLATILITY_RELIEF_CONFIRMATION_REQUIRED
        )
        context["accepted_volatility_relief_context"] = relief_context
        context["raw_candidate_count_before_volatility_relief_filter"] = context.get(
            "raw_candidate_count",
            0,
        )
        context["raw_candidate_count_after_volatility_relief_filter"] = len(day_rows)
        context["raw_candidate_count"] = len(day_rows)
        if day_rows:
            top = day_rows[0]
            context["top_candidate_after_volatility_relief"] = top["ticker"]
            context["top_score_after_volatility_relief"] = top["candidate_score"]
            context["top_range_expansion_after_volatility_relief"] = top[
                "candidate_range_expansion_ratio"
            ]

    scan.update(
        {
            "rule_version": RULE_VERSION,
            "base_rule_version": previous.RULE_VERSION,
            "accepted_volatility_relief_rule_version": vrelief.SOURCE_RULE_VERSION,
            "volatility_relief_confirmation_required": (
                VOLATILITY_RELIEF_CONFIRMATION_REQUIRED
            ),
            "volatility_relief_thresholds_locked": True,
            "raw_candidates_before_volatility_relief_filter": raw_count,
            "raw_candidate_dates_before_volatility_relief_filter": len(candidate_dates),
            "candidate_dates_with_accepted_volatility_relief": len(passed_dates),
            "raw_candidates_missing_volatility_relief_context": missing_relief_count,
            "raw_candidates_on_non_relief_dates": rejected_non_relief_count,
            "raw_candidates_after_volatility_relief_filter": len(filtered),
            "volatility_relief_confirmed_dates": len(filtered_by_date),
        }
    )
    return filtered, contexts, scan


def _accepted_compression_comparator() -> dict[str, Any]:
    if not ACCEPTED_COMPRESSION_ARTIFACT.exists():
        return {
            "available": False,
            "artifact": _repo_rel(ACCEPTED_COMPRESSION_ARTIFACT),
            "reason": "missing_accepted_compression_artifact",
        }
    payload = json.loads(ACCEPTED_COMPRESSION_ARTIFACT.read_text(encoding="utf-8"))
    aggregate = payload.get("delta_metrics", {}).get("aggregate", {})
    by_window = payload.get("delta_metrics", {}).get("by_window", {})
    out_by_window = {}
    for label in framework.WINDOWS:
        delta = by_window.get(label, {})
        out_by_window[label] = {
            "expected_value_score_delta": delta.get("expected_value_score"),
            "total_pnl_delta": delta.get("total_pnl"),
            "target_trade_count": len(payload.get("target_trades_by_window", {}).get(label, [])),
        }
    return {
        "available": True,
        "experiment_id": ACCEPTED_COMPRESSION_EXPERIMENT_ID,
        "artifact": _repo_rel(ACCEPTED_COMPRESSION_ARTIFACT),
        "decision": payload.get("decision"),
        "expected_value_score_delta_sum": aggregate.get("expected_value_score_delta_sum"),
        "total_pnl_delta_sum": aggregate.get("total_pnl_delta_sum"),
        "by_window": out_by_window,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = previous._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    comparator = _accepted_compression_comparator()
    if comparator.get("available"):
        comparator_ev = comparator.get("expected_value_score_delta_sum")
        comparator_pnl = comparator.get("total_pnl_delta_sum")
        if (
            comparator_ev is not None
            and aggregate["expected_value_score_delta_sum"] <= float(comparator_ev)
        ):
            gate["failed_reasons"].append("accepted_compression_ev_not_beaten")
        if (
            comparator_pnl is not None
            and aggregate["total_pnl_delta_sum"] <= float(comparator_pnl)
        ):
            gate["failed_reasons"].append("accepted_compression_pnl_not_beaten")
    else:
        gate["failed_reasons"].append("accepted_compression_comparator_missing")
    gate["accepted_compression_comparator"] = comparator
    gate["passed"] = not gate["failed_reasons"]
    gate["decision"] = (
        "positive_replay_lead_not_promoted_compression_volatility_relief_confirmed"
        if gate["passed"]
        else "rejected_compression_volatility_relief_confirmed_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Accepted VIXY volatility-relief state may identify when "
                "accepted narrow-range compression breakout candidates have "
                "cleaner next-open 10-day replacement value, without retuning "
                "either compression or VIXY thresholds."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_market_state_candidate_pool",
            "new_evidence_type": "cross_accepted_free_ohlcv_market_state_interaction",
            "nearby_prior_experiments": [
                "exp-20260608-013",
                "exp-20260608-020",
                "exp-20260607-019",
            ],
            "prior_trial_count": 3,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": gate4.get(
                "accepted_compression_comparator"
            ),
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that accepted volatility "
                "relief is either too sparse as a confirmation layer for the "
                "44-trade compression sample or it removes the independent "
                "compression winners rather than adding true market-state "
                "discrimination."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT volatility evidence, closed "
                "forward replacement-value rows from the accepted compression "
                "or VIXY helpers, or a shared-helper implementation with no "
                "production/backtest drift. Do not sweep VIXY, SPY, QQQ, "
                "compression, top-N, hold, cooldown, or notional thresholds on "
                "these frozen windows."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The accepted VIXY-relief overlay thinned the accepted "
                    "compression source from 44 trades to 4 trades, left "
                    "old_thin with zero rows, and selected a losing mid_weak "
                    "subset. The market-state intersection removed too much "
                    "independent compression edge instead of adding robust "
                    "replacement-value discrimination."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping VIXY return, VIXY close-location, "
                    "SPY/QQQ relief, compression range, volume, close-location, "
                    "ret5/ret20, top-N, hold-day, cooldown, or paper notional "
                    "thresholds on these frozen windows."
                ),
                "new_evidence_required": (
                    "Need forward replacement-value rows or materially new PIT "
                    "volatility/flow context before revisiting this interaction."
                ),
            },
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "Entry/candidate-pool interaction: fixed accepted compression "
            "breakouts may have higher replacement value when the fixed accepted "
            "VIXY/SPY/QQQ relief context passes. This follows the playbook's "
            "shared-paper/default-off direction but is intentionally replay-only "
            "because the intersection risk is high."
        ),
        "2_history_check": (
            "Related history: exp-20260608-013 accepted compression (+0.1608 EV, "
            "+$2,248.98, 44 trades, all three windows); exp-20260608-020 rejected "
            "a compression core-flow overlay as sample-thin (8 trades); "
            "exp-20260607-019 accepted VIXY relief (+0.5732 EV, +$11,934.79, "
            "88 trades)."
        ),
        "3_single_policy_bundle": (
            "Only one decision changes: require accepted volatility-relief context "
            "for accepted compression candidate rows. The runner, artifact, log, "
            "card, ticket, manifest, and comparator wiring only evaluate that "
            "fixed policy bundle."
        ),
        "4_acceptance_standard": (
            "Use docs/backtesting.md canonical 3 windows. Accept only if aggregate "
            "EV/PnL improve, no EV/PnL regression window, target sample >=20 "
            "across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
            "concentration passes, and the accepted compression comparator is "
            "beaten. Replay-only positive output still requires a shared "
            "default-off parity adapter before promotion."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_022_compression_volatility_relief_confirmation.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = gate4["decision"]
    payload["status"] = "accepted" if gate4["passed"] else "rejected"
    payload["interpretation"] = (
        "The accepted volatility-relief context improved the accepted compression "
        "source enough to qualify as a replay-only lead. Promotion still requires "
        "a shared default-off adapter and parity tests."
        if gate4["passed"]
        else (
            "The accepted volatility-relief context did not improve the accepted "
            "compression source enough for retention. Do not retune nearby VIXY "
            "or compression thresholds on these frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    )
    payload["expected_value_score_delta"] = aggregate["expected_value_score_delta_sum"]
    payload["total_pnl_delta"] = aggregate["total_pnl_delta_sum"]
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Relief raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=scan.get("raw_candidates_after_volatility_relief_filter", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload.get("accepted_compression_comparator") or {}
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Compression Volatility-Relief Confirmation",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Accepted compression comparator EV delta: `{}`".format(
                comparator.get("expected_value_score_delta_sum")
            ),
            "- Accepted compression comparator PnL delta: `${}`".format(
                comparator.get("total_pnl_delta_sum")
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_market_state_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "accepted_compression_comparator": payload.get("accepted_compression_comparator"),
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "volatility_relief_raw_candidates": payload["context_scan_by_window"][
                    label
                ].get("raw_candidates_after_volatility_relief_filter"),
                "volatility_relief_confirmed_dates": payload["context_scan_by_window"][
                    label
                ].get("volatility_relief_confirmed_dates"),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
            },
        }
    )
    framework._write_json(TICKET_JSON, ticket)

    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    for row in experiments:
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "completed_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
            }
        )
        break
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(
        json.dumps(framework._safe(registry), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4


def main() -> None:
    _patch_framework()
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
