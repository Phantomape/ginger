"""exp-20260528-025: Fundamental Growth + RS monotonic rank validation.

This read-only alpha experiment validates whether the accepted
FUNDAMENTAL_GROWTH_RS_PAPER candidate pool behaves like a durable continuous
ranking surface. It does not add a feature, scalar, gate, adapter, ranking rule,
exit rule, LLM prompt, or live/default order path.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260528-025"
STEM = "fundamental_growth_rs_monotonic_rank_validation"
TRIAL_FAMILY = "fundamental_growth_rs_monotonic_rank_validation"
CHANGED_VARIABLE = "fundamental_growth_rs_score_v1_tercile_monotonicity"
RULE_VERSION = "fundamental_growth_rs_score_monotonic_validation_v1"

SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260528-017"
    / "fundamental_growth_rs_low_liability_support.json"
)
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

PRIMARY_SCORE_FIELD = "fundamental_growth_rs_score_v1"
BUCKET_ORDER = ["top_tercile", "middle_tercile", "bottom_tercile"]


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_jsonl_if_missing(path: Path, payload: dict[str, Any]) -> None:
    experiment_id = str(payload.get("experiment_id") or EXPERIMENT_ID)
    found = False
    if path.exists():
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for existing in handle:
                if experiment_id not in existing:
                    continue
                try:
                    row = json.loads(existing)
                except json.JSONDecodeError:
                    continue
                if row.get("experiment_id") == experiment_id:
                    found = True
                    break
    if found:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True) + "\n")


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _money(value: Any) -> float:
    parsed = _as_float(value)
    return parsed if parsed is not None else 0.0


def _round(value: Any, digits: int = 6) -> float | None:
    parsed = _as_float(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def _load_source() -> dict[str, Any]:
    if not SOURCE_ARTIFACT.exists():
        raise FileNotFoundError(f"Missing source artifact: {SOURCE_ARTIFACT}")
    return _read_json(SOURCE_ARTIFACT)


def _flatten_target_trades(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    trades_by_window = source.get("target_trades_by_window") or {}
    if not isinstance(trades_by_window, dict):
        raise ValueError("source artifact missing target_trades_by_window")
    for window in WINDOWS:
        window_rows = trades_by_window.get(window) or []
        for index, row in enumerate(window_rows):
            if not isinstance(row, dict):
                continue
            score = _as_float(row.get(PRIMARY_SCORE_FIELD))
            pnl = _money(row.get("pnl"))
            notional = _money(row.get("paper_notional_usd"))
            rows.append(
                {
                    **row,
                    "window": window,
                    "source_row_index": index,
                    "score": score,
                    "pnl": pnl,
                    "pnl_pct": pnl / notional if notional else None,
                    "paper_notional_usd": notional,
                    "ticker": str(row.get("ticker") or ""),
                }
            )
    return rows


def assign_score_terciles(
    rows: list[dict[str, Any]],
    *,
    score_field: str = "score",
) -> list[dict[str, Any]]:
    """Return rows with descending score tercile labels.

    The split is count-based to avoid adding an arbitrary threshold. Rows with
    missing scores are kept and labelled `missing_score`.
    """

    scored = [
        (idx, _as_float(row.get(score_field)))
        for idx, row in enumerate(rows)
        if _as_float(row.get(score_field)) is not None
    ]
    sorted_scored = sorted(scored, key=lambda item: (-float(item[1]), item[0]))
    total = len(sorted_scored)
    labels_by_index: dict[int, str] = {}
    if total:
        first_cut = math.ceil(total / 3)
        second_cut = math.ceil((2 * total) / 3)
        for rank, (idx, _score) in enumerate(sorted_scored, start=1):
            if rank <= first_cut:
                label = "top_tercile"
            elif rank <= second_cut:
                label = "middle_tercile"
            else:
                label = "bottom_tercile"
            labels_by_index[idx] = label

    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        out.append(
            {
                **row,
                "score_bucket": labels_by_index.get(idx, "missing_score"),
                "score_rank_desc": (
                    sorted(labels_by_index).index(idx) + 1
                    if idx in labels_by_index
                    else None
                ),
            }
        )
    return out


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    pnls = [_money(row.get("pnl")) for row in rows]
    positive_pnls = [value for value in pnls if value > 0]
    scores = [
        float(row["score"])
        for row in rows
        if isinstance(row.get("score"), (int, float)) and math.isfinite(float(row["score"]))
    ]
    pnl_pct = [
        float(row["pnl_pct"])
        for row in rows
        if isinstance(row.get("pnl_pct"), (int, float))
        and math.isfinite(float(row["pnl_pct"]))
    ]
    tickers: dict[str, int] = {}
    positive_by_ticker: dict[str, float] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "")
        tickers[ticker] = tickers.get(ticker, 0) + 1
        pnl = _money(row.get("pnl"))
        if pnl > 0:
            positive_by_ticker[ticker] = positive_by_ticker.get(ticker, 0.0) + pnl
    positive_total = sum(positive_by_ticker.values())
    max_single_positive_share = (
        max(positive_by_ticker.values()) / positive_total
        if positive_total > 0 and positive_by_ticker
        else None
    )
    return {
        "trade_count": count,
        "total_pnl": round(sum(pnls), 2),
        "avg_pnl": round(sum(pnls) / count, 2) if count else None,
        "median_pnl": round(median(pnls), 2) if pnls else None,
        "win_rate": round(len(positive_pnls) / count, 6) if count else None,
        "avg_pnl_pct": round(sum(pnl_pct) / len(pnl_pct), 6) if pnl_pct else None,
        "avg_score": round(sum(scores) / len(scores), 6) if scores else None,
        "min_score": round(min(scores), 6) if scores else None,
        "max_score": round(max(scores), 6) if scores else None,
        "ticker_count": len(tickers),
        "max_single_positive_pnl_share": (
            round(max_single_positive_share, 6)
            if max_single_positive_share is not None
            else None
        ),
        "top_ticker_counts": dict(
            sorted(tickers.items(), key=lambda item: (-item[1], item[0]))[:10]
        ),
    }


def summarize_score_buckets(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bucketed = assign_score_terciles(rows)
    out: dict[str, Any] = OrderedDict()
    for bucket in BUCKET_ORDER + ["missing_score"]:
        subset = [row for row in bucketed if row.get("score_bucket") == bucket]
        if subset:
            out[bucket] = _summarize(subset)
    return out


def _window_summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = OrderedDict()
    for window in WINDOWS:
        subset = [row for row in rows if row.get("window") == window]
        out[window] = summarize_score_buckets(subset)
    return out


def _bucket_avg(summary: dict[str, Any], bucket: str) -> float | None:
    row = summary.get(bucket)
    if not isinstance(row, dict):
        return None
    return _as_float(row.get("avg_pnl"))


def _strictly_monotonic(summary: dict[str, Any]) -> bool:
    values = [_bucket_avg(summary, bucket) for bucket in BUCKET_ORDER]
    if any(value is None for value in values):
        return False
    return bool(values[0] > values[1] > values[2])


def _top_beats_bottom(summary: dict[str, Any]) -> bool:
    top = _bucket_avg(summary, "top_tercile")
    bottom = _bucket_avg(summary, "bottom_tercile")
    if top is None or bottom is None:
        return False
    return top > bottom


def monotonicity_report(
    overall_summary: dict[str, Any],
    window_summaries: dict[str, Any],
) -> dict[str, Any]:
    monotonic_windows = [
        window
        for window, summary in window_summaries.items()
        if _strictly_monotonic(summary)
    ]
    top_beats_bottom_windows = [
        window
        for window, summary in window_summaries.items()
        if _top_beats_bottom(summary)
    ]
    top_positive_windows = [
        window
        for window, summary in window_summaries.items()
        if _money((summary.get("top_tercile") or {}).get("total_pnl")) > 0
    ]
    overall_strict = _strictly_monotonic(overall_summary)
    overall_top_beats_bottom = _top_beats_bottom(overall_summary)
    passed = (
        overall_strict
        and len(monotonic_windows) >= 2
        and len(top_beats_bottom_windows) == len(WINDOWS)
    )
    if passed:
        status = "observed_only_monotonic_rank_evidence_needs_forward"
        reason = (
            "The accepted candidate-pool score is monotonic overall, monotonic in "
            "at least two windows, and top tercile beats bottom tercile in every "
            "standard window. This is validation evidence, not a new trade rule."
        )
    elif overall_top_beats_bottom and len(top_beats_bottom_windows) >= 2:
        status = "observed_only_partial_rank_evidence_not_promotable"
        reason = (
            "Top score bucket beats bottom in enough places to keep observing, "
            "but strict monotonicity is not stable enough for promotion."
        )
    else:
        status = "observed_only_no_monotonic_rank_evidence"
        reason = (
            "The accepted candidate-pool score does not produce stable monotonic "
            "bucket evidence across the standard windows."
        )
    return {
        "passed_observed_only_validation": passed,
        "status": status,
        "reason": reason,
        "overall_strictly_monotonic": overall_strict,
        "overall_top_beats_bottom": overall_top_beats_bottom,
        "monotonic_windows": monotonic_windows,
        "top_beats_bottom_windows": top_beats_bottom_windows,
        "top_positive_windows": top_positive_windows,
        "window_count": len(WINDOWS),
    }


def _field_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    fields = [
        PRIMARY_SCORE_FIELD,
        "pnl",
        "paper_notional_usd",
        "entry_date",
        "exit_date",
        "ticker",
        "known_at",
    ]
    out: dict[str, Any] = OrderedDict()
    for field in fields:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        out[field] = {
            "present": present,
            "missing": total - present,
            "coverage_ratio": round(present / total, 6) if total else None,
        }
    return out


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {
            "passed": False,
            "path": _repo_rel(OPEN_POSITIONS_JSON),
            "reason": "missing_open_positions_json",
        }
    payload = _read_json(OPEN_POSITIONS_JSON)
    rows: list[dict[str, Any]] = []
    for key in ("positions", "observations"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    missing_entry = [
        str(row.get("ticker") or "<unknown>") for row in rows if not row.get("entry_date")
    ]
    missing_target = [
        str(row.get("ticker") or "<unknown>")
        for row in rows
        if row.get("target_price") in (None, "")
    ]
    return {
        "passed": not missing_entry and not missing_target,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_count": len(rows),
        "missing_entry_date_tickers": missing_entry,
        "missing_target_price_tickers": missing_target,
    }


def _unchanged_delta_metrics(source: dict[str, Any]) -> dict[str, Any]:
    before = source.get("after_metrics") or source.get("before_metrics") or {}
    by_window: dict[str, Any] = OrderedDict()
    for window in WINDOWS:
        if window not in before:
            continue
        by_window[window] = {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "sharpe_daily": 0.0,
            "strategy_total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0,
            "survival_rate": 0.0,
            "signals_generated": 0,
            "signals_survived": 0,
        }
    return {
        "aggregate": {
            "expected_value_score_delta_sum": 0.0,
            "total_pnl_delta_sum": 0.0,
            "trade_count_delta_sum": 0,
            "max_drawdown_delta_max": 0.0,
        },
        "by_window": by_window,
    }


def _build_report_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Fundamental Growth + RS Monotonic Rank Validation",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single variable: `fundamental_growth_rs_score_v1` tercile monotonicity "
        "on accepted exp-20260528-017 target trades. No production or backtest "
        "strategy behavior changed.",
        "",
        "## Overall Buckets",
        "",
        "| Bucket | Trades | Avg score | PnL | Avg PnL | Win rate | Max single positive share |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in BUCKET_ORDER:
        stats = payload["overall_score_bucket_summary"].get(bucket) or {}
        lines.append(
            "| {bucket} | {trades} | {score} | ${pnl:,.2f} | ${avg:,.2f} | {win} | {share} |".format(
                bucket=bucket,
                trades=stats.get("trade_count", 0),
                score=stats.get("avg_score"),
                pnl=float(stats.get("total_pnl") or 0.0),
                avg=float(stats.get("avg_pnl") or 0.0),
                win=stats.get("win_rate"),
                share=stats.get("max_single_positive_pnl_share"),
            )
        )
    lines.extend(
        [
            "",
            "## Window Evidence",
            "",
            "| Window | Top avg PnL | Middle avg PnL | Bottom avg PnL | Strict monotonic | Top > bottom |",
            "|---|---:|---:|---:|---|---|",
        ]
    )
    for window, summary in payload["window_score_bucket_summary"].items():
        lines.append(
            "| {window} | ${top:,.2f} | ${middle:,.2f} | ${bottom:,.2f} | {mono} | {tb} |".format(
                window=window,
                top=float((summary.get("top_tercile") or {}).get("avg_pnl") or 0.0),
                middle=float(
                    (summary.get("middle_tercile") or {}).get("avg_pnl") or 0.0
                ),
                bottom=float(
                    (summary.get("bottom_tercile") or {}).get("avg_pnl") or 0.0
                ),
                mono=_strictly_monotonic(summary),
                tb=_top_beats_bottom(summary),
            )
        )
    lines.extend(
        [
            "",
            "## Validation",
            "",
            "```json",
            json.dumps(payload["monotonicity"], indent=2, sort_keys=True),
            "```",
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "No JavaScript was used.",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_payload() -> dict[str, Any]:
    source = _load_source()
    rows = _flatten_target_trades(source)
    bucketed_rows = assign_score_terciles(rows)
    overall_summary = summarize_score_buckets(rows)
    window_summary = _window_summaries(rows)
    monotonicity = monotonicity_report(overall_summary, window_summary)
    field_coverage = _field_coverage(rows)
    timestamp = _now()

    before_after = source.get("after_metrics") or source.get("before_metrics") or {}
    target_trade_summary = source.get("target_trade_summary") or {}

    if monotonicity["passed_observed_only_validation"]:
        decision = "observed_only_monotonic_rank_evidence_needs_forward"
    elif monotonicity["overall_top_beats_bottom"]:
        decision = "observed_only_partial_rank_evidence_not_promotable"
    else:
        decision = "observed_only_no_monotonic_rank_evidence"

    interpretation = (
        f"{PRIMARY_SCORE_FIELD} validation status: {monotonicity['status']}. "
        f"{monotonicity['reason']} The accepted historical paper EV remains the "
        "reference evidence, but this run does not justify another scalar or live "
        "ranking change; forward replacement-value rows are still required."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "observed_only",
        "decision": decision,
        "hypothesis": (
            "If FUNDAMENTAL_GROWTH_RS_PAPER is a durable ranking alpha rather "
            "than only a candidate-pool/notional effect, higher "
            "fundamental_growth_rs_score_v1 terciles should outperform lower "
            "terciles monotonically across the three canonical windows."
        ),
        "change_summary": (
            "Read-only monotonic validation of the accepted Companyfacts "
            "operating-profit + RS paper candidate score; no strategy behavior changed."
        ),
        "change_type": "read_only_monotonic_rank_validation",
        "mechanism_family": "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260528-008",
            "exp-20260528-011",
            "exp-20260528-015",
            "exp-20260528-016",
            "exp-20260528-017",
            "exp-20260528-019",
            "exp-20260528-020",
            "exp-20260528-021",
            "exp-20260528-023",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "monotonic_validation_of_existing_production_visible_score",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "primary_score_field": PRIMARY_SCORE_FIELD,
            "bucket_method": "count_based_descending_terciles_within_overall_and_each_window",
            "locked_strategy_variables": [
                "candidate definition",
                "Companyfacts filed-date boundary",
                "operating-profit positive quality gate",
                "RS proxy leader definition",
                "top-1/day route",
                "10-trading-day hold",
                "low-volume support",
                "filing-recency support",
                "low-liability support",
                "closed-ledger governor",
                "core/live entries",
                "core/live ranking",
                "core/live sizing",
                "core/live exits",
            ],
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window protocol",
            "windows": WINDOWS,
            "source_experiment": "exp-20260528-017",
            "strategy_behavior_changed": False,
        },
        "date_range": {
            "label": "late_strong",
            **WINDOWS["late_strong"],
        },
        "secondary_windows": [
            {"label": label, **cfg}
            for label, cfg in WINDOWS.items()
            if label != "late_strong"
        ],
        "gate_questions": {
            "1_alpha_hypothesis": (
                "ranking / cross-sectional relative strength: the accepted "
                "Companyfacts+RS candidate score should show monotonic bucket "
                "outperformance if it is durable alpha."
            ),
            "1_playbook_alignment": (
                "Aligned with forward maturation and continuous ranking validation; "
                "it avoids another frozen-sample threshold/scalar retune."
            ),
            "2_history_check": (
                "The candidate-pool source and several support scalars were tested; "
                "recent adjacent support fields were rejected. No prior log was found "
                "for monotonic validation of the accepted score itself."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only validation passes only if overall terciles are "
                "strictly monotonic, at least two windows are strictly monotonic, "
                "and top tercile beats bottom tercile in all three windows. "
                "Any strategy change would still require a separate Gate 1-4 run."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260528_025_fundamental_growth_rs_monotonic_rank_validation.py"
            ),
        },
        "gate1": {
            "baseline_artifact": _repo_rel(SOURCE_ARTIFACT),
            "standard_windows": WINDOWS,
            "source_before_metrics": source.get("before_metrics"),
            "source_after_metrics": source.get("after_metrics"),
            "source_delta_metrics": source.get("delta_metrics"),
            "passed": True,
        },
        "gate2": {
            "runtime_fields": [
                PRIMARY_SCORE_FIELD,
                "pnl",
                "paper_notional_usd",
                "entry_date",
                "exit_date",
                "known_at",
            ],
            "field_coverage": field_coverage,
            "operator_open_positions_audit": _audit_open_positions(),
            "passed": all(
                row.get("coverage_ratio") == 1.0
                for row in field_coverage.values()
                if row
            ),
        },
        "gate3": {
            "new_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": min(
                _money(row.get("survival_rate"))
                for row in before_after.values()
                if isinstance(row, dict)
            ),
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "passed": True,
            "note": "No filter or selection rule changed; survival is inherited from the source accepted artifact.",
        },
        "gate4": {
            "strategy_change": False,
            "status": "not_applicable_observed_only",
            "monotonicity_validation": monotonicity,
            "passed": False,
            "reason": (
                "This experiment validates evidence density only. It does not "
                "retain or reject a strategy rule."
            ),
        },
        "before_metrics": before_after,
        "after_metrics": before_after,
        "delta_metrics": _unchanged_delta_metrics(source),
        "source_accepted_delta_metrics": source.get("delta_metrics"),
        "source_target_trade_summary": target_trade_summary,
        "target_trade_count": len(rows),
        "overall_score_bucket_summary": overall_summary,
        "window_score_bucket_summary": window_summary,
        "monotonicity": monotonicity,
        "field_coverage": field_coverage,
        "classified_trades": bucketed_rows,
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "interpretation": interpretation,
        "rejection_reason": (
            "Observed-only rank validation; no score weight, threshold, notional "
            "scalar, gate, paper adapter, or live rule is promoted."
        ),
        "next_retry_requires": [
            "closed forward replacement-value rows for FUNDAMENTAL_GROWTH_RS_PAPER",
            "cost-adjusted replacement value versus core/cash before activation",
            "separate Gate 1-4 strategy experiment before any rank or allocation change",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(SOURCE_ARTIFACT),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Fundamental Growth + RS monotonic rank validation",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    _write_text(ARTIFACT_MD, _build_report_markdown(payload))
    _append_jsonl_if_missing(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "target_trade_count": payload["target_trade_count"],
                    "overall_score_bucket_summary": payload[
                        "overall_score_bucket_summary"
                    ],
                    "monotonicity": payload["monotonicity"],
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
