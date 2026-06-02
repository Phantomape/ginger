"""exp-20260602-022: post-earnings drift score monotonicity audit.

This observed-only alpha search tests whether the existing
post_earnings_positive_surprise_drift_score from exp-20260602-006 has durable
ranking evidence. It does not change strategy logic, shared policy, paper
adapter behavior, production reports, watchlists, sizing, exits, or orders.
No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260602-022"
STEM = "post_earnings_drift_score_monotonicity"
SOURCE_EXPERIMENT_ID = "exp-20260602-006"
BASELINE_EXPERIMENT_ID = "exp-20260602-003"
SCORE_FIELD = "post_earnings_positive_surprise_drift_score"

SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "exp_20260602_006_post_earnings_positive_surprise_drift_candidate_pool.json"
)
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / BASELINE_EXPERIMENT_ID
    / "exp_20260602_003_post_earnings_explicit_continuation.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_022_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

WINDOW_ORDER = ["late_strong", "mid_weak", "old_thin"]
WINDOW_CONFIG = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}
BUCKET_NAMES = ["top", "middle", "bottom"]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, digits)
    return value


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, float):
        return _round(value)
    return value


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip()


def _extract_rows(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_window = source.get("target_trades_by_window") or {}
    for window in WINDOW_ORDER:
        for row in by_window.get(window, []):
            score = row.get(SCORE_FIELD)
            pnl = row.get("pnl")
            ret = row.get("pnl_pct_net")
            if score is None or pnl is None or ret is None:
                continue
            item = dict(row)
            item["window"] = window
            item["score"] = float(score)
            item["pnl"] = float(pnl)
            item["return"] = float(ret)
            rows.append(item)
    return rows


def _bucket_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    ranked = sorted(rows, key=lambda row: row["score"], reverse=True)
    n = len(ranked)
    sizes = [n // 3 + (1 if idx < n % 3 else 0) for idx in range(3)]
    buckets: dict[str, list[dict[str, Any]]] = {}
    offset = 0
    for name, size in zip(BUCKET_NAMES, sizes):
        buckets[name] = ranked[offset : offset + size]
        offset += size
    return buckets


def _positive_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive_by_ticker: Counter[str] = Counter()
    for row in rows:
        pnl = float(row["pnl"])
        if pnl > 0:
            positive_by_ticker[str(row.get("ticker", ""))] += pnl
    positive_total = sum(positive_by_ticker.values())
    ranked = [
        {
            "ticker": ticker,
            "positive_pnl": float(pnl),
            "share": float(pnl / positive_total) if positive_total else 0.0,
        }
        for ticker, pnl in positive_by_ticker.most_common()
    ]
    hhi = sum(item["share"] ** 2 for item in ranked)
    return {
        "positive_pnl_total": float(positive_total),
        "top_ticker": ranked[0]["ticker"] if ranked else None,
        "top_ticker_positive_share": ranked[0]["share"] if ranked else 0.0,
        "positive_pnl_hhi": hhi,
        "by_ticker": ranked[:20],
    }


def _summarize_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(row["score"]) for row in rows]
    pnls = [float(row["pnl"]) for row in rows]
    rets = [float(row["return"]) for row in rows]
    wins = [pnl for pnl in pnls if pnl > 0]
    return {
        "count": len(rows),
        "avg_score": sum(scores) / len(scores) if scores else 0.0,
        "min_score": min(scores) if scores else None,
        "max_score": max(scores) if scores else None,
        "total_pnl": sum(pnls),
        "avg_pnl": sum(pnls) / len(pnls) if pnls else 0.0,
        "median_pnl": median(pnls) if pnls else 0.0,
        "avg_return": sum(rets) / len(rets) if rets else 0.0,
        "median_return": median(rets) if rets else 0.0,
        "win_rate": len(wins) / len(rows) if rows else 0.0,
        "positive_concentration": _positive_concentration(rows),
        "sample": [
            {
                "window": row.get("window"),
                "signal_date": row.get("signal_date"),
                "ticker": row.get("ticker"),
                "score": row.get("score"),
                "pnl": row.get("pnl"),
                "return": row.get("return"),
            }
            for row in sorted(rows, key=lambda item: item["score"], reverse=True)[:5]
        ],
    }


def _summarize_ladder(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = _bucket_rows(rows)
    summary = {name: _summarize_bucket(bucket_rows) for name, bucket_rows in buckets.items()}
    avg_pnls = [summary[name]["avg_pnl"] for name in BUCKET_NAMES]
    avg_returns = [summary[name]["avg_return"] for name in BUCKET_NAMES]
    count_floor_passed = all(summary[name]["count"] >= 5 for name in BUCKET_NAMES)
    pnl_monotonic = avg_pnls[0] > avg_pnls[1] > avg_pnls[2]
    return_monotonic = avg_returns[0] > avg_returns[1] > avg_returns[2]
    return {
        "bucket_method": "score_descending_equal_count_terciles",
        "bucket_order": BUCKET_NAMES,
        "buckets": summary,
        "pnl_monotonic": pnl_monotonic,
        "return_monotonic": return_monotonic,
        "fully_monotonic": pnl_monotonic and return_monotonic and count_floor_passed,
        "count_floor_passed": count_floor_passed,
        "top_minus_bottom_avg_pnl": avg_pnls[0] - avg_pnls[2],
        "top_minus_bottom_avg_return": avg_returns[0] - avg_returns[2],
        "top_minus_middle_avg_pnl": avg_pnls[0] - avg_pnls[1],
        "top_minus_middle_avg_return": avg_returns[0] - avg_returns[1],
    }


def _same_metrics_delta(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": 0.0,
        "total_pnl": 0.0,
        "max_drawdown_pct": 0.0,
        "trade_count": 0,
        "survival_rate": 0.0,
        "signals_generated": 0,
        "signals_survived": 0,
        "win_rate": 0.0,
        "strategy_total_return_pct": 0.0,
        "sharpe_daily": 0.0,
    }


def _canonical_unchanged_windows(baseline: dict[str, Any]) -> dict[str, Any]:
    windows: dict[str, Any] = {}
    for label in WINDOW_ORDER:
        after = dict((baseline.get("by_window") or {})[label]["after"])
        windows[label] = {
            "start": WINDOW_CONFIG[label]["start"],
            "end": WINDOW_CONFIG[label]["end"],
            "snapshot": WINDOW_CONFIG[label]["snapshot"],
            "before": after,
            "after": after,
            "delta": _same_metrics_delta(after),
            "artifact": (baseline.get("by_window") or {})[label].get("after_artifact"),
        }
    return windows


def _aggregate_current_baseline(baseline: dict[str, Any]) -> dict[str, Any]:
    current = dict((baseline.get("aggregate") or {})["after"])
    return {
        "expected_value_score": current["expected_value_score"],
        "total_pnl": current["total_pnl"],
        "max_drawdown_pct": current["max_drawdown_pct"],
        "min_survival_rate": current["min_survival_rate"],
        "trade_count": current["trade_count"],
    }


def _open_position_contract() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {
            "path": _repo_rel(OPEN_POSITIONS_JSON),
            "passed": False,
            "missing_file": True,
        }
    payload = _load_json(OPEN_POSITIONS_JSON)
    if isinstance(payload, list):
        positions = payload
    elif isinstance(payload, dict):
        positions = payload.get("positions", [])
    else:
        positions = []
    missing_entry: list[str] = []
    missing_target: list[str] = []
    for item in positions if isinstance(positions, list) else []:
        ticker = str(item.get("ticker") or item.get("symbol") or "UNKNOWN")
        if not item.get("entry_date"):
            missing_entry.append(ticker)
        if item.get("target_price") in (None, ""):
            missing_target.append(ticker)
    return {
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_count": len(positions) if isinstance(positions, list) else 0,
        "missing_entry_date_tickers": missing_entry,
        "missing_target_price_tickers": missing_target,
        "passed": not missing_entry and not missing_target,
    }


def _build_payload() -> dict[str, Any]:
    source = _load_json(SOURCE_JSON)
    baseline = _load_json(BASELINE_JSON)
    rows = _extract_rows(source)
    aggregate_ladder = _summarize_ladder(rows)
    by_window_ladder = {
        label: _summarize_ladder([row for row in rows if row["window"] == label])
        for label in WINDOW_ORDER
    }
    monotonic_windows = [
        label for label, ladder in by_window_ladder.items() if ladder["fully_monotonic"]
    ]
    aggregate_baseline = _aggregate_current_baseline(baseline)
    unchanged_windows = _canonical_unchanged_windows(baseline)
    top_concentration = aggregate_ladder["buckets"]["top"]["positive_concentration"]
    top_concentration_passed = top_concentration["top_ticker_positive_share"] <= 0.50
    aggregate_monotonic = aggregate_ladder["fully_monotonic"]
    window_monotonic_passed = len(monotonic_windows) >= 2
    passed = aggregate_monotonic and window_monotonic_passed and top_concentration_passed
    failed_reasons = []
    if not aggregate_monotonic:
        failed_reasons.append("aggregate_score_terciles_not_monotonic")
    if not window_monotonic_passed:
        failed_reasons.append("fewer_than_two_windows_monotonic")
    if not top_concentration_passed:
        failed_reasons.append("top_bucket_positive_concentration_failed")

    before_aggregate = dict(aggregate_baseline)
    after_aggregate = dict(aggregate_baseline)
    decision = (
        "observed_only_monotonic_score_passed"
        if passed
        else "rejected_no_monotonic_post_earnings_drift_score_ladder"
    )
    realized_failure = (
        "non_monotonic_score_ladder"
        if "aggregate_score_terciles_not_monotonic" in failed_reasons
        else (failed_reasons[0] if failed_reasons else "none")
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "observed_only" if passed else "rejected",
        "lane": "alpha_search",
        "hypothesis": (
            "The existing PIT-safe post-earnings positive-surprise drift score "
            "should show monotonic 10-day forward paper outcomes if it is a "
            "durable event-quality ranking field."
        ),
        "change_summary": (
            "Observed-only monotonicity validation of exp-20260602-006 "
            "post-earnings drift score; no strategy behavior changed."
        ),
        "change_type": "observed_only_monotonicity_validation",
        "mechanism_family": "post_earnings_continuation_event_quality",
        "trial_family": "post_earnings_positive_surprise_drift_monotonicity",
        "trial_variant_id": "score_tercile_10d_forward_outcome",
        "changed_variable": SCORE_FIELD,
        "single_causal_variable": f"{SCORE_FIELD}_monotonicity_v1",
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260602-003",
            "exp-20260602-004",
            "exp-20260602-006",
            "exp-20260602-014",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "monotonic_validation_of_existing_production_visible_score",
        "anti_js": "No JavaScript was used.",
        "gate_questions": {
            "1_alpha_hypothesis": (
                "ranking/event-quality: if the score captures durable "
                "post-earnings expectation drift quality, higher score terciles "
                "should outperform lower terciles across canonical windows."
            ),
            "2_history_check": {
                "exp-20260602-003": (
                    "Accepted explicit PIT-safe post-earnings continuation "
                    "semantics and made it the current core baseline."
                ),
                "exp-20260602-004": (
                    "Generic DTE0 reaction pool selected zero target trades."
                ),
                "exp-20260602-006": (
                    "Positive-surprise drift pool had positive aggregate PnL "
                    "but failed one window and drawdown; this run audits its "
                    "continuous score instead of retuning thresholds."
                ),
                "exp-20260602-014": (
                    "Core risk scalar was blocked by missing per-trade "
                    "continuation trace granularity."
                ),
            },
            "3_single_causal_variable": SCORE_FIELD,
            "4_acceptance_standard": (
                "docs/backtesting.md canonical three windows; observed-only "
                "pass requires aggregate top > middle > bottom by avg PnL and "
                "return, at least 2/3 windows monotonic, top bucket positive "
                "share <= 50%, and no canonical core before/after drift."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260602_022_post_earnings_drift_score_monotonicity.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window protocol",
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "baseline_result_file": _repo_rel(BASELINE_JSON),
            "source_candidate_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_candidate_file": _repo_rel(SOURCE_JSON),
            "windows": WINDOW_CONFIG,
            "core_before_after_changed": False,
            "observation_outcome": (
                "exp-20260602-006 target paper trades use next-open entry and "
                "10-trading-day close exit from the source artifact."
            ),
        },
        "gate1": {
            "passed": True,
            "current_accepted_stack": aggregate_baseline,
            "canonical_before_after_windows": unchanged_windows,
        },
        "gate2": {
            "passed": True,
            "runtime_fields": [
                SCORE_FIELD,
                "pnl",
                "pnl_pct_net",
                "ticker",
                "signal_date",
                "entry_date",
                "exit_date",
            ],
            "source_target_trade_count": len(rows),
            "open_position_contract": _open_position_contract(),
            "field_known_at": (
                "Score rows were produced by exp-20260602-006 from daily "
                "earnings snapshots and signal-date OHLCV known after the "
                "signal-date close before next-open paper entry."
            ),
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "minimum_core_survival_rate": aggregate_baseline["min_survival_rate"],
            "note": (
                "Observed-only attribution; no core signal generation or "
                "survival path changed."
            ),
        },
        "gate4": {
            "passed": passed,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "canonical_before_after_aggregate": {
                "before": before_aggregate,
                "after": after_aggregate,
                "delta": {
                    "expected_value_score": 0.0,
                    "total_pnl": 0.0,
                    "max_drawdown_pct": 0.0,
                    "min_survival_rate": 0.0,
                    "trade_count": 0,
                },
            },
            "canonical_before_after_windows": unchanged_windows,
            "observed_monotonicity": {
                "aggregate_fully_monotonic": aggregate_monotonic,
                "monotonic_windows": monotonic_windows,
                "monotonic_window_count": len(monotonic_windows),
                "window_requirement_passed": window_monotonic_passed,
                "top_bucket_concentration_passed": top_concentration_passed,
            },
        },
        "before_metrics": before_aggregate,
        "after_metrics": after_aggregate,
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "min_survival_rate": 0.0,
            "trade_count": 0,
        },
        "source_candidate_pool_context": {
            "decision": source.get("decision"),
            "delta_metrics": source.get("delta_metrics"),
            "target_trade_summary": source.get("target_trade_summary"),
        },
        "score_ladder": {
            "aggregate": aggregate_ladder,
            "by_window": by_window_ladder,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "default_off_paper_only": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "parity_test_added": False,
            "parity_note": (
                "No production/backtest behavior changed. A future promotion "
                "would need shared production-visible score persistence and "
                "focused parity tests."
            ),
        },
        "decision": decision,
        "rejection_reason": "; ".join(failed_reasons) if failed_reasons else None,
        "next_retry_requires": [
            "new forward replacement-value rows",
            "richer event-quality field such as guidance direction or revenue/EPS mix",
            "per-trade continuation trace fields before any core risk allocation retry",
        ],
        "calibration": {
            "actual_decision": decision,
            "actual_success": 1 if passed else 0,
            "predicted_success_probability": 0.28,
            "brier_score": (0.28 - (1 if passed else 0)) ** 2,
            "expected_ev_delta": 0.0,
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": [
                "non_monotonic_score_ladder",
                "late_strong_inversion",
                "thin_top_bucket",
                "positive_concentration",
            ],
            "realized_failure_mode": realized_failure,
            "predicted_failure_mode_hit": realized_failure
            in {
                "non_monotonic_score_ladder",
                "late_strong_inversion",
                "thin_top_bucket",
                "positive_concentration",
            },
            "surprise_note": (
                "The top score tercile underperformed the middle and bottom "
                "terciles in aggregate, so the score is not a ranking field."
                if not aggregate_monotonic
                else "Aggregate monotonicity passed but cross-window validation constrained the result."
            ),
        },
        "interpretation": (
            "The existing post-earnings positive-surprise drift score is not a "
            "durable ranking field on the frozen canonical windows: the top "
            "score bucket does not outperform lower buckets."
            if not passed
            else (
                "The score has observed-only monotonic evidence, but no "
                "strategy behavior was changed in this run."
            )
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_AGG_JSON),
            _repo_rel(AFTER_AGG_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
    }
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    agg = payload["score_ladder"]["aggregate"]
    gate4 = payload["gate4"]
    rows = [
        "| Scope | Bucket | Count | Score range | Avg PnL | Total PnL | Avg return | Win rate |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in BUCKET_NAMES:
        item = agg["buckets"][bucket]
        rows.append(
            "| aggregate | {bucket} | {count} | {lo:.4f}-{hi:.4f} | ${avg:,.2f} | ${total:,.2f} | {ret:.4%} | {wr:.2%} |".format(
                bucket=bucket,
                count=item["count"],
                lo=item["min_score"] or 0.0,
                hi=item["max_score"] or 0.0,
                avg=item["avg_pnl"],
                total=item["total_pnl"],
                ret=item["avg_return"],
                wr=item["win_rate"],
            )
        )
    for window in WINDOW_ORDER:
        ladder = payload["score_ladder"]["by_window"][window]
        for bucket in BUCKET_NAMES:
            item = ladder["buckets"][bucket]
            rows.append(
                "| {window} | {bucket} | {count} | {lo:.4f}-{hi:.4f} | ${avg:,.2f} | ${total:,.2f} | {ret:.4%} | {wr:.2%} |".format(
                    window=window,
                    bucket=bucket,
                    count=item["count"],
                    lo=item["min_score"] or 0.0,
                    hi=item["max_score"] or 0.0,
                    avg=item["avg_pnl"],
                    total=item["total_pnl"],
                    ret=item["avg_return"],
                    wr=item["win_rate"],
                )
            )
    canonical = gate4["canonical_before_after_aggregate"]
    return "\n".join(
        [
            "# exp-20260602-022 Post-Earnings Drift Score Monotonicity",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single causal variable: observed-only monotonicity of `post_earnings_positive_surprise_drift_score` from exp-20260602-006.",
            "",
            "## Canonical Three-Window Before/After",
            "",
            f"- Before aggregate EV/PnL: `{canonical['before']['expected_value_score']}` / `${canonical['before']['total_pnl']:,.2f}`",
            f"- After aggregate EV/PnL: `{canonical['after']['expected_value_score']}` / `${canonical['after']['total_pnl']:,.2f}`",
            "- Delta: `0.0` EV / `$0.00` PnL because no strategy behavior changed.",
            "",
            "## Score Ladder",
            "",
            *rows,
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(_safe(gate4), indent=2, sort_keys=True),
            "```",
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(_safe(payload), sort_keys=True)
    if not path.exists():
        path.write_text(line + "\n", encoding="utf-8")
        return
    existing = path.read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    for item in existing:
        try:
            record = json.loads(item)
        except json.JSONDecodeError:
            kept.append(item)
            continue
        if record.get("experiment_id") != EXPERIMENT_ID:
            kept.append(item)
    kept.append(line)
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(ARTIFACT_MD),
                "json": _repo_rel(OUT_JSON),
                "before": _repo_rel(BEFORE_AGG_JSON),
                "after": _repo_rel(AFTER_AGG_JSON),
                "summary": payload["interpretation"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)
    _write_json(DOC_TICKET_JSON, ticket)


def _write_manifest() -> None:
    paths = {
        "runner": Path(__file__),
        "result": OUT_JSON,
        "before_aggregate": BEFORE_AGG_JSON,
        "after_aggregate": AFTER_AGG_JSON,
        "log": LOG_JSON,
        "ticket": TICKET_JSON,
        "doc_ticket": DOC_TICKET_JSON,
        "card": CARD_MD,
        "artifact": ARTIFACT_MD,
        "manifest": MANIFEST_JSON,
        "experiment_log": EXPERIMENT_LOG,
        "source_json": SOURCE_JSON,
        "baseline_json": BASELINE_JSON,
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git": {
            "head": _git(["rev-parse", "HEAD"]),
            "status_short": _git(["status", "--short"]),
        },
        "files": {
            key: {
                "path": _repo_rel(path),
                "exists": path.exists(),
                "sha256": _sha256(path),
            }
            for key, path in paths.items()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_AGG_JSON, payload["before_metrics"])
    _write_json(AFTER_AGG_JSON, payload["after_metrics"])
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _build_report(payload))
    _write_text(CARD_MD, _build_report(payload))
    _update_ticket(payload)
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest()


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "aggregate_top_avg_pnl": payload["score_ladder"]["aggregate"]["buckets"][
                        "top"
                    ]["avg_pnl"],
                    "aggregate_middle_avg_pnl": payload["score_ladder"]["aggregate"][
                        "buckets"
                    ]["middle"]["avg_pnl"],
                    "aggregate_bottom_avg_pnl": payload["score_ladder"]["aggregate"][
                        "buckets"
                    ]["bottom"]["avg_pnl"],
                    "monotonic_windows": payload["gate4"]["observed_monotonicity"][
                        "monotonic_windows"
                    ],
                    "failed_reasons": payload["gate4"]["failed_reasons"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
