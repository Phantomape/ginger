"""exp-20260608-005: industry stable-leadership tail guard scout.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: reuse the rejected-but-positive industry stable
leadership source, but block it only during broad risk-off / volatility-up
tail states.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import exp_20260608_004_industry_stable_leadership as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260608-005"
STEM = "industry_stable_tail_guard"
TRIAL_FAMILY = "industry_stable_tail_guard_candidate_pool"
TRIAL_VARIANT_ID = "industry_stable_spy_qqq_down_vixy_up_guard_top1_10d_v1"
CHANGED_VARIABLE = "industry_stable_leadership_tail_guard_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_005_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "edge_thinned_by_tail_guard",
        "drawdown_still_fails",
        "old_thin_regression",
        "broad_beta_relabel",
        "target_sample_too_small",
    ],
    "confidence_reason": (
        "exp-20260608-004 was positive in all windows but failed only on "
        "drawdown drift, while accepted exp-20260607-008 proves industry "
        "relations can work. The new evidence is an independent sign-based "
        "SPY/QQQ risk-off plus VIXY-up tail state, not an industry threshold "
        "retune."
    ),
    "recorded_at": "2026-06-08T04:04:17+00:00",
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
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter exposing the same industry "
        "stable-leadership source plus exact-date SPY/QQQ/VIXY tail-state "
        "guard in both replay and daily production before any report queue, "
        "paper ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}

BASE_CANDIDATE_ROWS_FOR_WINDOW = previous._candidate_rows_for_window
BASE_BUILD_PAYLOAD = previous._build_payload
BASE_PERSIST = previous.BASE_PERSIST
BASE_LOAD_WINDOW_SNAPSHOT = previous.BASE_LOAD_WINDOW_SNAPSHOT


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _market_tail_guard(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any]:
    required = {}
    for ticker in ("SPY", "QQQ", "VIXY"):
        rows = snapshot.get(ticker) or []
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < 5:
            return {
                "passed": False,
                "blocked": True,
                "block_reason": f"missing_{ticker}_tail_state",
                "signal_date": signal_date,
                "rule_version": RULE_VERSION,
                "known_at": "after_signal_day_close_before_next_open_paper_entry",
            }
        ret5 = framework._ret(rows, idx, 5)
        if ret5 is None:
            return {
                "passed": False,
                "blocked": True,
                "block_reason": f"missing_{ticker}_ret5",
                "signal_date": signal_date,
                "rule_version": RULE_VERSION,
                "known_at": "after_signal_day_close_before_next_open_paper_entry",
            }
        required[f"{ticker.lower()}_ret5"] = float(ret5)

    broad_risk_off_vol_up = (
        required["spy_ret5"] < 0.0
        and required["qqq_ret5"] < 0.0
        and required["vixy_ret5"] > 0.0
    )
    return {
        "passed": not broad_risk_off_vol_up,
        "blocked": broad_risk_off_vol_up,
        "block_reason": (
            "spy_qqq_5d_down_vixy_5d_up" if broad_risk_off_vol_up else "passed"
        ),
        "signal_date": signal_date,
        "spy_ret5": round(required["spy_ret5"], 6),
        "qqq_ret5": round(required["qqq_ret5"], 6),
        "vixy_ret5": round(required["vixy_ret5"], 6),
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    return BASE_LOAD_WINDOW_SNAPSHOT(
        cfg=cfg,
        eligible_tickers=set(eligible_tickers) | {"SPY", "QQQ", "VIXY"},
    )


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
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    guard_by_date: dict[str, dict[str, Any]] = {}
    filtered: list[dict[str, Any]] = []
    blocked_count = 0
    blocked_dates: set[str] = set()
    for row in candidates:
        signal_date = str(row["date"])
        guard = guard_by_date.get(signal_date)
        if guard is None:
            guard = _market_tail_guard(
                snapshot=snapshot,
                indices=indices,
                signal_date=signal_date,
            )
            guard_by_date[signal_date] = guard
        row["market_tail_guard"] = guard
        row["rule_version"] = RULE_VERSION
        if guard["passed"]:
            filtered.append(row)
        else:
            row["filter_reason"] = "market_tail_guard_failed"
            blocked_count += 1
            blocked_dates.add(signal_date)

    for context in contexts:
        signal_date = str(context.get("date") or "")
        guard = guard_by_date.get(signal_date)
        if guard is not None:
            context["market_tail_guard"] = guard
            if not guard["passed"]:
                context["raw_candidate_count_before_tail_guard"] = context.get(
                    "raw_candidate_count",
                    0,
                )
                context["raw_candidate_count"] = 0

    scan.update(
        {
            "rule_version": RULE_VERSION,
            "base_rule_version": previous.RULE_VERSION,
            "market_tail_guard_rule": "block_when_spy_ret5_lt_0_and_qqq_ret5_lt_0_and_vixy_ret5_gt_0",
            "tail_guard_blocked_raw_candidate_rows": blocked_count,
            "tail_guard_blocked_dates": len(blocked_dates),
            "tail_guard_context_dates": len(guard_by_date),
            "tail_guard_passed_dates": sum(
                1 for guard in guard_by_date.values() if guard["passed"]
            ),
        }
    )
    return filtered, contexts, scan


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
    gate["decision"] = (
        "positive_replay_lead_not_promoted_industry_stable_tail_guard"
        if gate["passed"]
        else "rejected_industry_stable_tail_guard_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    gate4 = payload["gate4"]
    aggregate = payload["delta_metrics"]["aggregate"]
    accepted = bool(gate4["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Industry stable leadership may retain its replacement-value "
                "edge if blocked only during broad risk-off / volatility-up "
                "tail states."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "free_ohlcv_market_tail_state",
            "nearby_prior_experiments": [
                "exp-20260608-004",
                "exp-20260607-008",
                "exp-20260607-009",
                "exp-20260607-010",
                "exp-20260607-012",
                "exp-20260607-014",
            ],
            "prior_trial_count": 1,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "decision": gate4["decision"],
            "status": "positive_replay_lead_not_promoted" if accepted else "rejected",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The tail-guarded industry stable-leadership source cleared "
                "Gate 4 as a replay-only/default-off lead, but no production "
                "surface was promoted."
                if accepted
                else (
                    "The tail-guarded industry stable-leadership source did "
                    "not clear Gate 4. Do not promote it or respond by tuning "
                    "the same industry thresholds or the sign-based tail guard "
                    "on these frozen windows."
                )
            ),
            "rejection_reason": None if accepted else "; ".join(gate4["failed_reasons"]),
            "negative_reflection": (
                "If rejected, the likely reason is that the prior industry "
                "stable-leadership edge was either not caused by broad "
                "risk-off/volatility-up dates, or the sign-based guard thinned "
                "winners faster than it removed crash-tail."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The source produced positive replacement value in all "
                    "three windows while the broad risk-off / VIXY-up guard "
                    "kept drawdown within the Gate 4 limit."
                    if accepted
                    else (
                        "The sign-based market tail guard did not produce a "
                        "robust enough fixed policy. That means the prior "
                        "drawdown drift was not isolated by simple SPY/QQQ "
                        "5-day weakness plus VIXY 5-day strength, or the guard "
                        "removed too many useful continuation rows."
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping SPY/QQQ/VIXY return lookbacks, "
                    "sign thresholds, industry ret20 strength, dispersion, "
                    "low-volatility, candidate lead, close-location, volume, "
                    "top-N, hold-day, cooldown, or paper notional on the "
                    "frozen windows."
                ),
                "new_evidence_required": (
                    "A retry requires materially new PIT relation/tail evidence "
                    "such as breadth participation, realized-vs-implied vol "
                    "compression, peer taxonomy quality, supplier/customer "
                    "links, industry earnings/revision propagation, or closed "
                    "forward replacement-value rows."
                ),
            },
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(EXPERIMENT_LOG),
                _repo_rel(REGISTRY_JSON),
            ],
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "base_candidate_source": previous.CHANGED_VARIABLE,
            "market_tail_guard_rule": (
                "block_when_spy_ret5_lt_0_and_qqq_ret5_lt_0_and_vixy_ret5_gt_0"
            ),
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date plus "
        "prior close history for the exp-20260608-004 industry stable "
        "leadership source and exact-date SPY/QQQ/VIXY 5-day tail-state "
        "returns. Paper entry is next available open with existing entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool with risk-tail boundary: stable leaders "
            "inside strong industries may work except during broad risk-off "
            "and volatility-up states."
        ),
        "2_history_check": {
            "exp-20260608-004": (
                "Rejected only because drawdown drift was too high despite "
                "positive EV/PnL in all windows and broad sample."
            ),
            "exp-20260607-008": (
                "Accepted shared industry-relative laggard repair proves an "
                "industry relation can work when it identifies a specific "
                "replacement edge."
            ),
            "exp-20260607-009/010/012/014": (
                "Rejected industry pullback, breadth repair, dispersion, and "
                "volume-breadth variants warn against retuning industry "
                "thresholds."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL "
            "must improve, no window may regress EV/PnL, target sample must be "
            ">=20 across all 3 windows, survival must stay >=5%, drawdown drift "
            "<=0.5pp, and concentration guard must pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_005_industry_stable_tail_guard.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    runtime_fields = payload.setdefault("gate2", {}).setdefault("runtime_fields", [])
    for field in (
        "SPY signal-date OHLCV and prior 5 trading days",
        "QQQ signal-date OHLCV and prior 5 trading days",
        "VIXY signal-date OHLCV and prior 5 trading days",
    ):
        if field not in runtime_fields:
            runtime_fields.append(field)
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Blocked dates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {blocked} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                blocked=scan.get("tail_guard_blocked_dates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry Stable Tail Guard",
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
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/"
            "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
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
                "tail_guard_blocked_dates": payload["context_scan_by_window"][
                    label
                ].get("tail_guard_blocked_dates"),
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
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
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


def persist(payload: dict[str, Any]) -> None:
    BASE_PERSIST(payload)
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
    framework._load_window_snapshot = _load_window_snapshot
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._write_manifest = _write_manifest
    framework.persist = persist


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
