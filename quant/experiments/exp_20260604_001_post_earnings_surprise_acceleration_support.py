"""exp-20260604-001: post-earnings surprise-acceleration support scout.

This alpha search tests one production-visible earnings snapshot field on top
of the accepted default-off POST_EARNINGS_UNDERPRICED_DRIFT_PAPER stack:
already-selected candidates whose latest EPS surprise exceeds their historical
average surprise by at least 5 percentage points receive 1.05x paper notional.

The run compares against exp-20260603-022 after_metrics. It changes no live
orders, core entries, rankings, exits, watchlists, LLM/news authority, or
shared production adapter behavior. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

import exp_20260603_022_post_earnings_non_core_overlap_shared_support as parent


EXPERIMENT_ID = "exp-20260604-001"
STEM = "post_earnings_surprise_acceleration_support"
TRIAL_FAMILY = "post_earnings_underpriced_surprise_acceleration_support"
CHANGED_VARIABLE = "post_earnings_surprise_acceleration_support_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_001_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

BASELINE_RESULT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260603-022"
    / "exp_20260603_022_post_earnings_non_core_overlap_shared_support.json"
)

SURPRISE_ACCELERATION_MIN_DELTA_PCT = 5.0
SURPRISE_ACCELERATION_NOTIONAL_SCALAR = 1.05
BASE_NOTIONAL_USD = parent.parent.BASE_NOTIONAL_USD


def _framework() -> Any:
    return parent._framework()


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _surprise_acceleration_context(row: dict[str, Any]) -> dict[str, Any]:
    latest = _float_or_none(row.get("latest_surprise_pct"))
    historical = _float_or_none(row.get("avg_historical_surprise_pct"))
    if latest is None or historical is None:
        return {
            "surprise_acceleration_status": "missing_surprise_field",
            "surprise_acceleration_support": False,
        }
    delta = latest - historical
    return {
        "surprise_acceleration_status": "ok",
        "surprise_acceleration_latest_pct": round(latest, 6),
        "surprise_acceleration_historical_avg_pct": round(historical, 6),
        "surprise_acceleration_delta_pct": round(delta, 6),
        "surprise_acceleration_support": delta >= SURPRISE_ACCELERATION_MIN_DELTA_PCT,
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # Apply the shared exp022 non-core-overlap support first, then this run's
    # surprise-acceleration scalar. The exp022 wrapper patches exp021's
    # non-core context into the shared adapter, so exp021's candidate builder is
    # the accepted comparator stack before our change.
    candidates, audit = parent.parent._candidate_rows_for_window(
        snapshot,
        cfg,
        universe,
        before_result,
    )

    support_count = 0
    support_days: set[str] = set()
    support_tickers: set[str] = set()
    status_counts: Counter[str] = Counter()
    for row in candidates:
        context = _surprise_acceleration_context(row)
        row.update(context)
        status = str(context.get("surprise_acceleration_status") or "unknown")
        status_counts[status] += 1
        supported = bool(context.get("surprise_acceleration_support"))
        pre_notional = _float_or_none(row.get("intended_notional")) or BASE_NOTIONAL_USD
        scalar = SURPRISE_ACCELERATION_NOTIONAL_SCALAR if supported else 1.0
        row["surprise_acceleration_support_rule_version"] = RULE_VERSION
        row["surprise_acceleration_min_delta_pct"] = SURPRISE_ACCELERATION_MIN_DELTA_PCT
        row["surprise_acceleration_notional_scalar"] = scalar
        row["pre_surprise_acceleration_paper_notional_usd"] = round(pre_notional, 2)
        row["intended_notional"] = round(pre_notional * scalar, 2)
        row["trade_enabled"] = False
        row["alters_orders"] = False
        if supported:
            support_count += 1
            support_days.add(str(row.get("date") or ""))
            support_tickers.add(str(row.get("ticker") or "").upper())

    audit = dict(audit)
    audit["surprise_acceleration_support_rule_version"] = RULE_VERSION
    audit["surprise_acceleration_min_delta_pct"] = SURPRISE_ACCELERATION_MIN_DELTA_PCT
    audit["surprise_acceleration_notional_scalar"] = SURPRISE_ACCELERATION_NOTIONAL_SCALAR
    audit["surprise_acceleration_supported_raw_candidate_count"] = support_count
    audit["surprise_acceleration_supported_candidate_days"] = len(support_days)
    audit["surprise_acceleration_supported_unique_tickers"] = len(support_tickers)
    audit["surprise_acceleration_status_counts"] = dict(sorted(status_counts.items()))
    audit["support_changes_entries_or_filters"] = False
    return candidates, audit


def _paper_trade_from_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    trade = parent.parent._paper_trade_from_candidate(snapshot, candidate)
    if trade is None:
        return None
    for field in (
        "non_core_overlap_context_status",
        "same_day_ab_entry_count",
        "same_day_ab_overlap",
        "same_ticker_ab_overlap",
        "non_core_overlap_support",
        "non_core_overlap_support_rule_version",
        "non_core_overlap_notional_scalar",
        "pre_non_core_overlap_paper_notional_usd",
        "surprise_acceleration_status",
        "surprise_acceleration_latest_pct",
        "surprise_acceleration_historical_avg_pct",
        "surprise_acceleration_delta_pct",
        "surprise_acceleration_support",
        "surprise_acceleration_support_rule_version",
        "surprise_acceleration_min_delta_pct",
        "surprise_acceleration_notional_scalar",
        "pre_surprise_acceleration_paper_notional_usd",
    ):
        trade[field] = candidate.get(field)
    trade["trade_enabled"] = False
    trade["alters_orders"] = False
    return trade


def _select_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    for row in candidates:
        date_value = str(row.get("date") or "")
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[date_value] >= _framework().MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        trade = _paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[date_value] += 1
    return selected, filtered


def _accepted_baseline() -> dict[str, Any]:
    with BASELINE_RESULT_JSON.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _rebase_payload_to_accepted_baseline(payload: dict[str, Any]) -> dict[str, Any]:
    baseline = _accepted_baseline()
    before_metrics = {
        label: baseline["after_metrics"][label]
        for label in _framework().base.WINDOWS
    }
    window_rows: dict[str, dict[str, Any]] = {}
    delta_by_window: dict[str, dict[str, Any]] = {}
    for label in _framework().base.WINDOWS:
        before = before_metrics[label]
        after = payload["after_metrics"][label]
        delta = _framework().overlay_helper._delta(after, before)
        delta_by_window[label] = delta
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(payload["target_trades_by_window"][label]),
        }
    aggregate = _framework()._aggregate(window_rows)
    target_summary = _framework()._target_trade_summary(
        payload["target_trades_by_window"]
    )
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
    )
    gate4 = _framework()._gate4(aggregate, target_summary, min_survival)
    failed_reasons = list(gate4.get("failed_reasons") or [])
    for label, delta in delta_by_window.items():
        if float(delta.get("expected_value_score") or 0.0) <= 0:
            failed_reasons.append(f"{label}_ev_not_improved_vs_exp022")
        if float(delta.get("total_pnl") or 0.0) <= 0:
            failed_reasons.append(f"{label}_pnl_not_improved_vs_exp022")
    if failed_reasons:
        gate4["passed"] = False
        gate4["failed_reasons"] = sorted(set(failed_reasons))

    payload["incremental_baseline_experiment_id"] = "exp-20260603-022"
    payload["incremental_baseline_result_file"] = _framework().base._repo_rel(
        BASELINE_RESULT_JSON
    )
    payload["before_metrics"] = before_metrics
    payload["delta_metrics"] = {
        "by_window": delta_by_window,
        "aggregate": aggregate,
    }
    payload["target_trade_summary"] = target_summary
    payload["judge_before_aggregate"] = _framework()._aggregate_result_for_judge(
        before_metrics
    )
    payload["judge_after_aggregate"] = _framework()._aggregate_result_for_judge(
        payload["after_metrics"]
    )
    payload["gate4"] = gate4
    payload["expected_value_score_delta"] = aggregate["expected_value_score_delta_sum"]
    payload["total_pnl_delta"] = aggregate["total_pnl_delta_sum"]
    return payload


def _support_trade_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    incremental_by_ticker: Counter[str] = Counter()
    supported_rows: list[dict[str, Any]] = []
    for label, trades in target_trades_by_window.items():
        supported = [
            trade for trade in trades if trade.get("surprise_acceleration_support")
        ]
        supported_rows.extend(supported)
        incremental_pnl = 0.0
        for trade in supported:
            pre_notional = (
                _float_or_none(trade.get("pre_surprise_acceleration_paper_notional_usd"))
                or BASE_NOTIONAL_USD
            )
            pnl_pct_net = float(trade.get("pnl_pct_net") or 0.0)
            trade_incremental = (
                pnl_pct_net
                * pre_notional
                * (SURPRISE_ACCELERATION_NOTIONAL_SCALAR - 1.0)
            )
            incremental_pnl += trade_incremental
            incremental_by_ticker[str(trade.get("ticker") or "").upper()] += (
                trade_incremental
            )
        by_window[label] = {
            "adjusted_trade_count": len(supported),
            "adjusted_total_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in supported),
                2,
            ),
            "surprise_acceleration_incremental_pnl": round(incremental_pnl, 2),
        }
    positive = {ticker: pnl for ticker, pnl in incremental_by_ticker.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_share = (
        round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    hhi = (
        round(sum((pnl / positive_total) ** 2 for pnl in positive.values()), 6)
        if positive_total > 0 and positive
        else None
    )
    return {
        "adjusted_trade_count": len(supported_rows),
        "adjusted_windows": [
            label for label, row in by_window.items() if row["adjusted_trade_count"]
        ],
        "by_window": by_window,
        "positive_incremental_by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(positive.items())
        },
        "max_single_positive_incremental_pnl_share": max_share,
        "positive_incremental_pnl_hhi": hhi,
    }


def _patch_parent() -> None:
    parent.EXPERIMENT_ID = EXPERIMENT_ID
    parent.STEM = STEM
    parent.TRIAL_FAMILY = TRIAL_FAMILY
    parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    parent.OUT_DIR = OUT_DIR
    parent.OUT_JSON = OUT_JSON
    parent.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    parent.AFTER_AGG_JSON = AFTER_AGG_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.DOC_TICKET_JSON = DOC_TICKET_JSON
    parent.CARD_MD = CARD_MD
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.EXPERIMENT_LOG = EXPERIMENT_LOG
    parent.MANIFEST_JSON = MANIFEST_JSON
    parent._patch_parent()
    _framework()._candidate_rows_for_window = _candidate_rows_for_window
    _framework()._select_paper_trades = _select_paper_trades


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _rebase_payload_to_accepted_baseline(payload)
    gate4 = payload["gate4"]
    decision = (
        "accepted_post_earnings_surprise_acceleration_support"
        if gate4["passed"]
        else "rejected_post_earnings_surprise_acceleration_support"
    )
    support_summary = _support_trade_summary(payload["target_trades_by_window"])
    actual_success = 1 if gate4["passed"] else 0
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    prediction = {
        "success_probability": 0.18,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 100.0,
        "main_failure_modes": [
            "old_thin_regression",
            "mid_weak_regression",
            "post_earnings_support_stack_saturated",
            "thin_incremental_pnl",
        ],
        "confidence_reason": (
            "Precheck showed complete PIT earnings-snapshot coverage but "
            "negative old_thin and mid_weak incremental PnL. This is a narrow "
            "event-quality support test, not a post-earnings threshold retune."
        ),
        "recorded_at": "2026-06-04T00:13:37+00:00",
        "brier_score": round((0.18 - actual_success) ** 2, 6),
    }
    failed_reasons = gate4["failed_reasons"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": "completed",
            "decision": decision,
            "hypothesis": (
                "Already-selected post-earnings underpriced drift paper "
                "candidates whose latest EPS surprise exceeds their historical "
                "average surprise by at least 5pp may have cleaner continuation "
                "and deserve a small default-off paper support scalar."
            ),
            "change_type": "default_off_paper_adapter_event_quality_support",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "post_earnings_underpriced_drift",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260602-026",
                "exp-20260602-027",
                "exp-20260603-004",
                "exp-20260603-020",
                "exp-20260603-021",
                "exp-20260603-022",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "production_visible_earnings_snapshot_surprise_acceleration_field"
            ),
            "prediction": prediction,
            "calibration": {
                "actual_decision": decision,
                "actual_success": actual_success,
                "predicted_success_probability": prediction["success_probability"],
                "brier_score": prediction["brier_score"],
                "expected_ev_delta": prediction["expected_ev_delta"],
                "actual_ev_delta": payload["delta_metrics"]["aggregate"][
                    "expected_value_score_delta_sum"
                ],
                "expected_pnl_delta": prediction["expected_pnl_delta"],
                "actual_pnl_delta": payload["delta_metrics"]["aggregate"][
                    "total_pnl_delta_sum"
                ],
                "predicted_failure_modes": prediction["main_failure_modes"],
                "realized_failure_mode": None
                if gate4["passed"]
                else "; ".join(failed_reasons),
            },
            "parameters": {
                **payload.get("parameters", {}),
                "incremental_baseline_experiment_id": "exp-20260603-022",
                "support_field": (
                    "latest_surprise_pct - avg_historical_surprise_pct"
                ),
                "surprise_acceleration_min_delta_pct": (
                    SURPRISE_ACCELERATION_MIN_DELTA_PCT
                ),
                "surprise_acceleration_notional_scalar": (
                    SURPRISE_ACCELERATION_NOTIONAL_SCALAR
                ),
                "trade_enabled": False,
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "capital allocation / event-quality support: a latest EPS "
                    "surprise that materially beats the ticker's own historical "
                    "surprise average may indicate cleaner post-event drift."
                ),
                "2_history_check": {
                    "exp-20260602-026": "Accepted post-earnings underpriced drift adapter.",
                    "exp-20260602-027": "Accepted high-liquidity support; kept fixed here.",
                    "exp-20260603-004": "Accepted sector-residual support; kept fixed here.",
                    "exp-20260603-020": "Rejected participation support due mid_weak regression.",
                    "exp-20260603-021": "Replay lead for non-core overlap.",
                    "exp-20260603-022": "Accepted shared non-core overlap support; current baseline.",
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md canonical three windows; compare "
                    "against exp-20260603-022 after_metrics. Accept only if "
                    "aggregate EV/PnL improves, no EV/PnL window regresses, "
                    "drawdown drift stays inside guardrail, survival >=5%, "
                    "target concentration passes, and shared helper parity would "
                    "be required before retention."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260604_001_post_earnings_surprise_acceleration_support.py"
                ),
            },
            "gate1": {
                "baseline_metrics": payload["before_metrics"],
                "baseline_artifact": (
                    "data/experiments/exp-20260603-022/"
                    "exp_20260603_022_post_earnings_non_core_overlap_shared_support.json"
                    "#after_metrics"
                ),
                "passed": True,
            },
            "gate2": {
                **payload.get("gate2", {}),
                "support_field_check": {
                    "fields": [
                        "latest_surprise_pct",
                        "avg_historical_surprise_pct",
                        "surprise_acceleration_delta_pct",
                        "surprise_acceleration_support",
                    ],
                    "source": (
                        "PIT earnings_snapshot rows already consumed by the "
                        "post-earnings underpriced drift candidate builder"
                    ),
                    "decision_time": (
                        "known after actual EPS is published and before "
                        "next-open default-off paper entry"
                    ),
                    "coverage": _framework()._field_coverage(
                        all_target_trades,
                        [
                            "latest_surprise_pct",
                            "avg_historical_surprise_pct",
                            "surprise_acceleration_delta_pct",
                            "surprise_acceleration_support",
                        ],
                    ),
                    "passed": True,
                },
            },
            "gate3": {
                "new_core_filter_added": False,
                "candidate_pool_changed": False,
                "minimum_core_survival_rate": min(
                    float(row.get("survival_rate") or 0.0)
                    for row in payload["before_metrics"].values()
                ),
                "passed": True,
                "note": (
                    "No core filter or entry rule was added; this only changes "
                    "default-off paper notional for already selected candidates."
                ),
            },
            "support_trade_summary": support_summary,
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_signal_path_changed": False,
                "production_core_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exit_changed": False,
                "trade_enabled": False,
                "llm_or_news_changed": False,
                "retained_behavior": bool(gate4["passed"]),
            },
            "why_not_other_changes": (
                "Skipped LLM/event text support after exp022 selected rows had "
                "zero replayable event snapshot coverage. Skipped options/13F "
                "because canonical fixed-window PIT coverage was insufficient. "
                "Skipped consensus, FINRA, Companyfacts, Space, VCP, and "
                "post-earnings nearby support retunes already frozen or rejected "
                "on 2026-06-03."
            ),
            "interpretation": (
                "Accepted numerically, but would still need a shared default-off "
                "helper/parity promotion before any retained behavior."
                if gate4["passed"]
                else (
                    "Rejected. EPS surprise acceleration did not improve the "
                    "current accepted post-earnings paper stack across all "
                    "three canonical windows; do not retune adjacent surprise "
                    "thresholds or scalars on the frozen sample."
                )
            ),
            "acceptance_interpretation": (
                "Numeric Gate 4 passed; no retained shared behavior in this run."
                if gate4["passed"]
                else "Gate 4 failed; no shared adapter or production behavior changed."
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(failed_reasons),
            "related_files": [
                "quant/experiments/exp_20260604_001_post_earnings_surprise_acceleration_support.py",
                "data/experiments/exp-20260604-001/exp_20260604_001_post_earnings_surprise_acceleration_support.json",
                "experiments/logs/exp-20260604-001.json",
                "experiments/tickets/exp-20260604-001.json",
                "docs/experiments/tickets/exp-20260604-001.json",
                "experiments/cards/exp-20260604-001.md",
                "experiments/artifacts/exp-20260604-001_post_earnings_surprise_acceleration_support.md",
                "experiments/manifests/exp-20260604-001.json",
                "docs/experiment_log.jsonl",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Supported trades | Surprise dPnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    support = payload["support_trade_summary"]["by_window"]
    for label in _framework().base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        support_row = support[label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {supported} | ${support_dpnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                supported=support_row["adjusted_trade_count"],
                support_dpnl=support_row["surprise_acceleration_incremental_pnl"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Post-Earnings Surprise-Acceleration Support",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: already-selected "
                "`POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` candidates with "
                "`latest_surprise_pct - avg_historical_surprise_pct >= 5.0` "
                "receive `1.05x` paper notional."
            ),
            "",
            "Baseline: `exp-20260603-022` accepted after metrics.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- supported trades: `{payload['support_trade_summary']['adjusted_trade_count']}` across `{payload['support_trade_summary']['adjusted_windows']}`",
            f"- target max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- target positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            f"- supported max single positive incremental share: `{payload['support_trade_summary']['max_single_positive_incremental_pnl_share']}`",
            f"- supported positive incremental HHI: `{payload['support_trade_summary']['positive_incremental_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Replay-only default-off paper support scout. No shared helper, "
                "backtester adapter, run adapter, live/default orders, core "
                "ranking/sizing/exits, watchlists, LLM, or news behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base = _framework().base
    base._write_json(OUT_JSON, payload)
    base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    base._write_json(LOG_JSON, payload)
    ticket_payload: dict[str, Any] = {}
    if TICKET_JSON.exists():
        with TICKET_JSON.open("r", encoding="utf-8") as handle:
            ticket_payload = json.load(handle)
    lifecycle_status = "accepted" if payload["decision"].startswith("accepted") else "rejected"
    aggregate_delta = payload["delta_metrics"]["aggregate"]
    ticket_payload.update(
        {
            "status": lifecycle_status,
            "completed_at": payload["timestamp"],
            "result": {
                "decision": lifecycle_status,
                "gate4_decision": payload["decision"],
                "artifact": base._repo_rel(OUT_JSON),
                "log": base._repo_rel(LOG_JSON),
                "summary": payload["interpretation"],
                "before_result_file": base._repo_rel(BEFORE_AGG_JSON),
                "after_result_file": base._repo_rel(AFTER_AGG_JSON),
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "support_trade_summary": payload["support_trade_summary"],
                "production_impact": payload["production_impact"],
                "delta_metrics": {
                    "expected_value_score": aggregate_delta[
                        "expected_value_score_delta_sum"
                    ],
                    "total_pnl": aggregate_delta["total_pnl_delta_sum"],
                },
            },
        }
    )
    base._write_json(TICKET_JSON, ticket_payload)
    base._write_json(DOC_TICKET_JSON, ticket_payload)
    report = _build_report(payload)
    base._write_text(ARTIFACT_MD, report)
    base._write_text(CARD_MD, report)
    base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest()


def _write_manifest() -> None:
    base = _framework().base
    files = {
        "runner": base._repo_rel(Path(__file__)),
        "result": base._repo_rel(OUT_JSON),
        "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
        "log": base._repo_rel(LOG_JSON),
        "ticket": base._repo_rel(TICKET_JSON),
        "doc_ticket": base._repo_rel(DOC_TICKET_JSON),
        "card": base._repo_rel(CARD_MD),
        "artifact": base._repo_rel(ARTIFACT_MD),
        "manifest": base._repo_rel(MANIFEST_JSON),
        "experiment_log": base._repo_rel(EXPERIMENT_LOG),
        "baseline_result": base._repo_rel(BASELINE_RESULT_JSON),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    base._write_json(MANIFEST_JSON, manifest)


def main() -> int:
    _patch_parent()
    payload = _postprocess_payload(_framework()._build_payload())
    _persist(payload)
    print(
        json.dumps(
            _framework().base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "support_trade_summary": payload["support_trade_summary"],
                    "artifact": _framework().base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": _framework().base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": _framework().base._repo_rel(AFTER_AGG_JSON),
                    "production_impact": payload["production_impact"],
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
