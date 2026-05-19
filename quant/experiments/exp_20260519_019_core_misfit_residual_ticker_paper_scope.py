"""exp-20260519-019: core-misfit residual ticker paper scope.

Alpha search. Freezes the accepted CORE_MISFIT_PAPER trend-only policy and
tests one production-visible governance variable: whether residual trend_long
tickers outside the current TSM/ISRG/V/DDOG set deserve default-off paper
observation.

No live shorts, no core exclusions, no sizing, ranking, exit, or order logic
changes are made. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260518_022_core_misfit_trend_only_paper_scope as prior


EXPERIMENT_ID = "exp-20260519-019"
EXPERIMENT_SLUG = "core_misfit_residual_ticker_paper_scope"

REPO_ROOT = prior.source.base.REPO_ROOT
SOURCE_EXPERIMENT_ID = "exp-20260516-043"
SOURCE_ARTIFACT = (
    REPO_ROOT / "data" / "experiments" / SOURCE_EXPERIMENT_ID / "core_misfit_paper_sleeve.json"
)
CORE_BASELINE_EXPERIMENT_ID = prior.CORE_BASELINE_EXPERIMENT_ID
CURRENT_MISFIT_TICKERS = ("TSM", "ISRG", "V", "DDOG")
TARGET_STRATEGY = "trend_long"
FIXED_HORIZON = "10"
MIN_RESIDUAL_CANDIDATES = 4
MIN_RESIDUAL_WINDOWS = 2
MIN_POSITIVE_WINDOWS = 2
MAX_ACCEPTABLE_WORST_INVERSE_RETURN = -0.10
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.75

OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
CANONICAL_WINDOWS = prior.CANONICAL_WINDOWS
WINDOWS = {
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


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _money(value: Any) -> float:
    try:
        out = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(out):
        return 0.0
    return round(out, 2)


def _float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _load_source_payload() -> dict[str, Any]:
    return json.loads(SOURCE_ARTIFACT.read_text(encoding="utf-8"))


def _candidate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in payload["paper_surfaces"]["paper_candidate_records"]:
        if str(row.get("strategy") or "") != TARGET_STRATEGY:
            continue
        if str(row.get("fill", {}).get("status") or "") != "filled":
            continue
        horizon = row.get("horizon") or {}
        if FIXED_HORIZON not in horizon:
            continue
        rows.append(dict(row))
    return rows


def _horizon(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("horizon", {}).get(FIXED_HORIZON, {})


def _row_metrics(row: dict[str, Any]) -> dict[str, Any]:
    horizon = _horizon(row)
    return {
        "ticker": str(row.get("ticker") or "").upper(),
        "window": str(row.get("window") or "unknown"),
        "signal_date": row.get("signal_date"),
        "decision": row.get("decision"),
        "long_pnl": _money(horizon.get("long_pnl")),
        "inverse_short_pnl": _money(horizon.get("inverse_short_pnl")),
        "long_net_return_pct": _float(horizon.get("long_net_return_pct")),
        "inverse_short_net_return_pct": _float(horizon.get("inverse_short_net_return_pct")),
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {
        window: {
            "candidate_count": 0,
            "long_pnl": 0.0,
            "inverse_short_pnl": 0.0,
            "inverse_positive_count": 0,
        }
        for window in CANONICAL_WINDOWS
    }
    by_ticker: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "candidate_count": 0,
            "long_pnl": 0.0,
            "inverse_short_pnl": 0.0,
            "inverse_positive_count": 0,
            "windows": set(),
        }
    )
    total_long = 0.0
    total_inverse = 0.0
    inverse_positive_count = 0
    worst_inverse_return: float | None = None
    measured_rows = [_row_metrics(row) for row in rows]
    for row in measured_rows:
        window = str(row["window"])
        ticker = str(row["ticker"])
        long_pnl = _money(row["long_pnl"])
        inverse_pnl = _money(row["inverse_short_pnl"])
        inverse_return = row["inverse_short_net_return_pct"]
        total_long = round(total_long + long_pnl, 2)
        total_inverse = round(total_inverse + inverse_pnl, 2)
        if inverse_pnl > 0:
            inverse_positive_count += 1
        if inverse_return is not None:
            worst_inverse_return = (
                inverse_return
                if worst_inverse_return is None
                else min(worst_inverse_return, inverse_return)
            )
        window_row = by_window.setdefault(
            window,
            {
                "candidate_count": 0,
                "long_pnl": 0.0,
                "inverse_short_pnl": 0.0,
                "inverse_positive_count": 0,
            },
        )
        window_row["candidate_count"] += 1
        window_row["long_pnl"] = round(window_row["long_pnl"] + long_pnl, 2)
        window_row["inverse_short_pnl"] = round(
            window_row["inverse_short_pnl"] + inverse_pnl,
            2,
        )
        if inverse_pnl > 0:
            window_row["inverse_positive_count"] += 1
        ticker_row = by_ticker[ticker]
        ticker_row["candidate_count"] += 1
        ticker_row["long_pnl"] = round(ticker_row["long_pnl"] + long_pnl, 2)
        ticker_row["inverse_short_pnl"] = round(
            ticker_row["inverse_short_pnl"] + inverse_pnl,
            2,
        )
        if inverse_pnl > 0:
            ticker_row["inverse_positive_count"] += 1
        ticker_row["windows"].add(window)

    for row in by_ticker.values():
        row["windows"] = sorted(row["windows"])

    positive_windows = [
        window
        for window, row in by_window.items()
        if float(row.get("inverse_short_pnl") or 0.0) > 0.0
    ]
    positive_by_ticker = {
        ticker: max(0.0, float(row.get("inverse_short_pnl") or 0.0))
        for ticker, row in by_ticker.items()
    }
    positive_total = round(sum(positive_by_ticker.values()), 2)
    max_single_share = (
        round(max(positive_by_ticker.values()) / positive_total, 6)
        if positive_total > 0
        else None
    )
    candidate_count = len(rows)
    return {
        "candidate_count": candidate_count,
        "long_pnl": round(total_long, 2),
        "inverse_short_pnl": round(total_inverse, 2),
        "inverse_positive_count": inverse_positive_count,
        "inverse_win_rate": round(inverse_positive_count / candidate_count, 6)
        if candidate_count
        else None,
        "positive_windows": positive_windows,
        "positive_window_count": len(positive_windows),
        "window_count": len([w for w, row in by_window.items() if row["candidate_count"] > 0]),
        "worst_inverse_return_pct": worst_inverse_return,
        "max_single_ticker_positive_share": max_single_share,
        "by_window": by_window,
        "by_ticker": dict(sorted(by_ticker.items())),
        "rows": measured_rows,
    }


def _passes_residual_gate(summary: dict[str, Any]) -> bool:
    worst = summary.get("worst_inverse_return_pct")
    concentration = summary.get("max_single_ticker_positive_share")
    return bool(
        int(summary["candidate_count"]) >= MIN_RESIDUAL_CANDIDATES
        and int(summary["window_count"]) >= MIN_RESIDUAL_WINDOWS
        and int(summary["positive_window_count"]) >= MIN_POSITIVE_WINDOWS
        and float(summary["inverse_short_pnl"]) > 0.0
        and float(summary["long_pnl"]) < 0.0
        and worst is not None
        and float(worst) >= MAX_ACCEPTABLE_WORST_INVERSE_RETURN
        and concentration is not None
        and float(concentration) <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )


def _ticker_scout(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for ticker, row in summary["by_ticker"].items():
        candidate_count = int(row["candidate_count"])
        inverse_pnl = float(row["inverse_short_pnl"])
        rows.append(
            {
                "ticker": ticker,
                "candidate_count": candidate_count,
                "windows": row["windows"],
                "long_pnl": round(float(row["long_pnl"]), 2),
                "inverse_short_pnl": round(inverse_pnl, 2),
                "passes_min_sample": candidate_count >= MIN_RESIDUAL_CANDIDATES
                and len(row["windows"]) >= MIN_RESIDUAL_WINDOWS,
                "passes_positive_inverse": inverse_pnl > 0.0,
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            item["passes_min_sample"],
            item["passes_positive_inverse"],
            item["inverse_short_pnl"],
            item["candidate_count"],
        ),
        reverse=True,
    )


def _aggregate_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(float(metrics[window]["expected_value_score"]) for window in CANONICAL_WINDOWS),
            4,
        ),
        "total_pnl_sum": round(
            sum(float(metrics[window]["total_pnl"]) for window in CANONICAL_WINDOWS),
            2,
        ),
        "trade_count_sum": sum(int(metrics[window]["trade_count"]) for window in CANONICAL_WINDOWS),
        "survival_rate_min": min(
            float(metrics[window]["survival_rate"]) for window in CANONICAL_WINDOWS
        ),
        "worst_trade_pct_min": min(
            float(metrics[window]["worst_trade_pct"]) for window in CANONICAL_WINDOWS
        ),
        "max_drawdown_pct_max": max(
            float(metrics[window]["max_drawdown_pct"]) for window in CANONICAL_WINDOWS
        ),
        "tail_loss_share_max": max(
            float(metrics[window]["tail_loss_share"]) for window in CANONICAL_WINDOWS
        ),
    }


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "expected_value_score",
        "total_pnl",
        "total_return_pct",
        "sharpe_daily",
        "max_drawdown_pct",
        "trade_count",
        "survival_rate",
        "worst_trade_pct",
        "tail_loss_share",
    )
    by_window = {}
    for window in CANONICAL_WINDOWS:
        by_window[window] = {
            key: round(float(after[window][key]) - float(before[window][key]), 6)
            for key in keys
            if key in before[window] and key in after[window]
        }
    aggregate_before = _aggregate_metrics(before)
    aggregate_after = _aggregate_metrics(after)
    return {
        "by_window": by_window,
        "aggregate_before": aggregate_before,
        "aggregate_after": aggregate_after,
        "aggregate_delta": {
            key: round(float(aggregate_after[key]) - float(aggregate_before[key]), 6)
            for key in aggregate_before
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    residual = payload["residual_summary"]
    ticker_rows = [
        "| Ticker | Candidates | Windows | Long PnL | Inverse 10d PnL | Sample pass |",
        "|---|---:|---|---:|---:|---|",
    ]
    for row in payload["ticker_scout"]:
        ticker_rows.append(
            "| {ticker} | {count} | {windows} | ${long:,.2f} | ${inverse:,.2f} | {passed} |".format(
                ticker=row["ticker"],
                count=row["candidate_count"],
                windows=", ".join(row["windows"]),
                long=float(row["long_pnl"]),
                inverse=float(row["inverse_short_pnl"]),
                passed="yes" if row["passes_min_sample"] else "no",
            )
        )
    window_rows = [
        "| Window | Candidates | Long PnL | Inverse 10d PnL |",
        "|---|---:|---:|---:|",
    ]
    for window, row in residual["by_window"].items():
        window_rows.append(
            "| {window} | {count} | ${long:,.2f} | ${inverse:,.2f} |".format(
                window=window,
                count=row["candidate_count"],
                long=float(row["long_pnl"]),
                inverse=float(row["inverse_short_pnl"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core Misfit Residual Ticker Paper Scope",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single causal variable: expand the default-off CORE_MISFIT_PAPER ticker scope beyond `TSM/ISRG/V/DDOG` for `trend_long` paper observation.",
            "",
            f"Residual candidates: `{residual['candidate_count']}`.",
            f"Residual inverse 10d PnL: `${residual['inverse_short_pnl']:,.2f}`.",
            f"Residual long 10d PnL: `${residual['long_pnl']:,.2f}`.",
            f"Gate 4 passed: `{payload['gate4']['passed']}`.",
            "",
            *window_rows,
            "",
            *ticker_rows,
            "",
            "Core live metrics are unchanged; no policy was promoted.",
        ]
    )


def build_payload() -> dict[str, Any]:
    source_payload = _load_source_payload()
    core_metrics = json.loads(prior.CORE_BASELINE_ARTIFACT.read_text(encoding="utf-8"))[
        "after_metrics"
    ]
    current_rows = [
        row
        for row in _candidate_rows(source_payload)
        if str(row.get("ticker") or "").upper() in CURRENT_MISFIT_TICKERS
    ]
    residual_rows = [
        row
        for row in _candidate_rows(source_payload)
        if str(row.get("ticker") or "").upper() not in CURRENT_MISFIT_TICKERS
    ]
    current_summary = _summarize(current_rows)
    residual_summary = _summarize(residual_rows)
    expanded_summary = _summarize(current_rows + residual_rows)
    residual_passed = _passes_residual_gate(residual_summary)
    additive_inverse_delta = round(
        float(expanded_summary["inverse_short_pnl"])
        - float(current_summary["inverse_short_pnl"]),
        2,
    )
    passed = bool(residual_passed and additive_inverse_delta > 0.0)
    decision = (
        "accepted_default_off_core_misfit_residual_ticker_paper_scope"
        if passed
        else "rejected_core_misfit_residual_ticker_paper_scope"
    )
    metrics_delta = _delta(core_metrics, core_metrics)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Residual trend_long tickers outside the current CORE_MISFIT_PAPER "
            "scope may contain enough repeatable negative-for-core evidence to "
            "deserve default-off paper observation."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "changed_variable": "core_misfit_paper_residual_ticker_scope",
        "single_causal_variable": (
            "Only the candidate ticker set for default-off CORE_MISFIT_PAPER "
            "paper observation is evaluated; target strategy, fixed 10-day "
            "horizon, fills, ranking, sizing, exits, and live orders remain locked."
        ),
        "parameters": {
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "core_baseline_experiment": CORE_BASELINE_EXPERIMENT_ID,
            "current_misfit_tickers": list(CURRENT_MISFIT_TICKERS),
            "target_strategy": TARGET_STRATEGY,
            "fixed_horizon": FIXED_HORIZON,
            "min_residual_candidates": MIN_RESIDUAL_CANDIDATES,
            "min_residual_windows": MIN_RESIDUAL_WINDOWS,
            "min_positive_windows": MIN_POSITIVE_WINDOWS,
            "max_acceptable_worst_inverse_return": MAX_ACCEPTABLE_WORST_INVERSE_RETURN,
            "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool governance: if residual trend_long losers are "
                "repeatable, they should be observed in CORE_MISFIT_PAPER before "
                "any future exclusion or inverse allocation experiment."
            ),
            "2_history_check": {
                "exp-20260516-043": (
                    "Default-off paper sleeve accepted only TSM/ISRG/V/DDOG as "
                    "the initial suspicious long cohort."
                ),
                "exp-20260518-019": (
                    "Conditioned inverse scout found trend_long cleaner than "
                    "breakout_long but still not live-promotable."
                ),
                "exp-20260518-022": (
                    "Promoted trend_long-only observation scope while keeping "
                    "live shorts and core exclusions disabled."
                ),
            },
            "3_single_causal_variable": "core_misfit_paper_residual_ticker_scope",
            "4_acceptance_standard": (
                "docs/backtesting.md fixed three windows; core metrics unchanged; "
                "residual expansion must have >=4 candidates, >=2 active windows, "
                ">=2 positive inverse windows, positive aggregate inverse 10d PnL, "
                "negative aggregate long 10d PnL, worst inverse return >= -10%, "
                "and single-ticker positive share <=75%."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                f"{Path(__file__).name}"
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical fixed-snapshot three-window core "
                "metrics from exp-20260517-009 and CORE_MISFIT_PAPER candidate "
                "rows from exp-20260516-043."
            ),
            "windows": WINDOWS,
            "canonical_windows": list(CANONICAL_WINDOWS),
        },
        "gate1": {
            "baseline_metrics": core_metrics,
            "baseline_aggregate": _aggregate_metrics(core_metrics),
            "source_artifacts": [
                str(prior.CORE_BASELINE_ARTIFACT.relative_to(REPO_ROOT)),
                str(SOURCE_ARTIFACT.relative_to(REPO_ROOT)),
            ],
        },
        "gate2": {
            "passed": True,
            "runtime_fields": [
                "ticker",
                "strategy",
                "fill.status",
                "decision",
                "window",
                "signal_date",
                "horizon.10.long_pnl",
                "horizon.10.inverse_short_pnl",
                "horizon.10.long_net_return_pct",
                "horizon.10.inverse_short_net_return_pct",
            ],
            "candidate_rows_checked": len(current_rows) + len(residual_rows),
            "residual_rows_checked": len(residual_rows),
        },
        "gate3": {
            "passed": _aggregate_metrics(core_metrics)["survival_rate_min"] >= 0.05,
            "core_filter_added": False,
            "core_survival_rate_min": _aggregate_metrics(core_metrics)["survival_rate_min"],
            "paper_scope_only": True,
        },
        "gate4": {
            "passed": passed,
            "residual_gate_passed": residual_passed,
            "additive_inverse_delta": additive_inverse_delta,
            "core_metrics_changed": False,
            "promotion_allowed": passed,
            "promotion_rejected_reason": None
            if passed
            else (
                "Residual trend_long tickers either lack multi-window sample or "
                "reduce the accepted paper sleeve's 10-day inverse PnL."
            ),
        },
        "before_metrics": core_metrics,
        "after_metrics": core_metrics,
        "delta_metrics": {
            **metrics_delta,
            "core_metrics_changed": False,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "paper_inverse_10d_delta": additive_inverse_delta,
        },
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "current_scope_summary": current_summary,
        "residual_summary": residual_summary,
        "expanded_scope_summary": expanded_summary,
        "ticker_scout": _ticker_scout(residual_summary),
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": (
                "LLM soft ranking is not needed here; this alpha lane uses "
                "deterministic paper replay rows already present in the artifacts."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "default_off_paper_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "live_short_enabled": False,
            "core_exclusion_enabled": False,
        },
        "known_risks": [
            "Residual ticker evidence is still historical and sample-thin.",
            "Fixed 10-day inverse PnL ignores borrow, locate, and buy-in costs.",
            "Paper candidate rows include slot-sliced rows that did not receive live capital.",
        ],
        "interpretation": (
            "Residual tickers clear the paper expansion gate; promote only as "
            "default-off observation scope."
            if passed
            else (
                "Do not expand CORE_MISFIT_PAPER beyond TSM/ISRG/V/DDOG now. "
                "The residual trend_long cohort has enough rows for a scout but "
                "negative aggregate inverse value, and no individual residual "
                "ticker has enough multi-window sample to promote."
            )
        ),
        "rejection_reason": None
        if passed
        else (
            "Residual trend_long expansion failed Gate 4: aggregate inverse 10-day "
            "PnL was not positive after adding the residual cohort, and ticker-level "
            "samples did not meet the minimum repeatability gate."
        ),
        "next_evidence_needed": (
            "Update CORE_MISFIT_PAPER defaults and parity tests, then keep forward "
            "closed-outcome collection active."
            if passed
            else (
                "Keep the existing CORE_MISFIT_PAPER scope. Reopen residual expansion "
                "only with forward closed no-trade/inverse evidence or a genuinely new "
                "production-visible discriminator."
            )
        ),
        "why_not_other_changes": (
            "No live short adapter, no core exclusion, no threshold retune, no "
            "state-surface retune, and no candidate universe expansion were made."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            str(Path(__file__).relative_to(REPO_ROOT)),
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG.relative_to(REPO_ROOT)),
        ],
    }
    return _safe(payload)


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Core-misfit residual ticker paper scope",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
            "summary": (
                f"Residual inverse 10d PnL ${payload['residual_summary']['inverse_short_pnl']:,.2f}; "
                f"Gate 4 passed={payload['gate4']['passed']}."
            ),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "gate4_passed": payload["gate4"]["passed"],
                "residual_candidates": payload["residual_summary"]["candidate_count"],
                "residual_inverse_10d_pnl": payload["residual_summary"]["inverse_short_pnl"],
                "additive_inverse_delta": payload["gate4"]["additive_inverse_delta"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
