"""exp-20260528-007: true expectation ranking replacement attribution.

Observed-only alpha search. This compares the existing daily alpha_score rank
against alpha_score plus expectation/residual component score on the full
per-date ranking surface. It does not alter signal generation, ranking, sizing,
exits, LLM/news, paper sleeves, or orders.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260528-007"
STEM = "expectation_true_ranking_replacement_attribution"
MECHANISM_FAMILY = "expectation_residual_leadership"
TRIAL_FAMILY = "expectation_true_ranking_replacement_attribution"
CHANGED_VARIABLE = "old_alpha_score_plus_expectation_residual_component_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = Path(__file__).resolve().parent
QUANT_DIR = REPO_ROOT / "quant"
for path in (EXPERIMENTS_DIR, QUANT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from exp_20260525_017_expectation_residual_leadership_attribution import (  # noqa: E402
    FORWARD_HORIZONS,
    PAPER_NOTIONAL_USD,
    _coerce_date,
    _float,
    build_price_lookup,
    load_candidates,
)
from exp_20260525_031_revision_lead_window_attribution import (  # noqa: E402
    next_trading_date_on_or_after,
    trading_dates_from_ohlcv,
)
from exp_20260526_030_expectation_direction_untried_ideas_suite import (  # noqa: E402
    ANTI_JS,
    BASELINE,
    build_context,
    expectation_residual_component_score,
    field_coverage,
)
from exp_20260528_005_expectation_watchlist_old_alpha_score_join import (  # noqa: E402
    build_old_alpha_score_index,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

RANK_BUCKET_ORDER = [
    "top_decile",
    "top_quartile",
    "upper_mid",
    "lower_mid",
    "bottom_quartile",
    "missing_score",
]
REPLACEMENT_BUCKET_ORDER = [
    "retained_top_decile",
    "new_combined_top_decile",
    "old_top_decile_dropped",
    "neither_top_decile",
]
MIN_TOP_CLOSED_5D = 30
MIN_TOP_CLOSED_10D = 20
MIN_REPLACEMENT_CLOSED_5D = 10
MIN_REPLACEMENT_CLOSED_10D = 8
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50

NEARBY_PRIORS = [
    {
        "experiment_id": "exp-20260526-033",
        "finding": "Proxy ranking test was blocked by old_alpha_score_rows=0.",
    },
    {
        "experiment_id": "exp-20260528-005",
        "finding": "old_alpha_score was joined for 751/751 watchlist rows.",
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return _repo_rel(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(compact + "\n", encoding="utf-8")
        return

    found = False
    with path.open("r", encoding="utf-8", errors="replace") as src:
        for line in src:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                found = True
                break

    if not found:
        with path.open("a", encoding="utf-8", newline="\n") as dst:
            dst.write(compact + "\n")
        return

    tmp_path = path.with_name(f"{path.name}.{EXPERIMENT_ID}.tmp")
    replaced = False
    with path.open("r", encoding="utf-8", errors="replace") as src, tmp_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as dst:
        for line in src:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                dst.write(line if line.endswith("\n") else line + "\n")
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    dst.write(compact + "\n")
                    replaced = True
                continue
            dst.write(line if line.endswith("\n") else line + "\n")
    tmp_path.replace(path)


def rank_bucket(rank_pct: float | None) -> str:
    if rank_pct is None:
        return "missing_score"
    if rank_pct <= 0.10:
        return "top_decile"
    if rank_pct <= 0.25:
        return "top_quartile"
    if rank_pct <= 0.50:
        return "upper_mid"
    if rank_pct <= 0.75:
        return "lower_mid"
    return "bottom_quartile"


def build_watchlist_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        feature_date = row.get("feature_context_date")
        ticker = str(row.get("ticker") or "").upper()
        if feature_date and ticker:
            out[(str(feature_date), ticker)] = row
    return out


def missing_outcome(reason: str) -> dict[str, Any]:
    return {
        "closed": False,
        "return": None,
        "pnl_proxy": None,
        "future_date": None,
        "gap_reason": reason,
    }


def build_surface_rows(
    *,
    rank_index: dict[tuple[str, str], dict[str, Any]],
    watchlist_index: dict[tuple[str, str], dict[str, Any]],
    watchlist_dates: set[str],
    prices: Any,
    trading_dates: list[date],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (feature_date, ticker), old_rank in sorted(rank_index.items()):
        if feature_date not in watchlist_dates:
            continue
        watchlist_row = watchlist_index.get((feature_date, ticker))
        component_score = (
            expectation_residual_component_score(watchlist_row)
            if watchlist_row
            else 0.0
        )
        old_score = _float(old_rank.get("old_alpha_score"), None)
        effective_trade_date = next_trading_date_on_or_after(
            _coerce_date(feature_date),
            trading_dates,
        )
        if effective_trade_date is not None:
            forward_outcomes = {
                f"{horizon}d": prices.forward_return(
                    ticker,
                    effective_trade_date,
                    horizon,
                )
                for horizon in FORWARD_HORIZONS
            }
        else:
            forward_outcomes = {
                f"{horizon}d": missing_outcome("missing_effective_trade_date")
                for horizon in FORWARD_HORIZONS
            }
        row = {
            "feature_context_date": feature_date,
            "signal_effective_trade_date": effective_trade_date.isoformat()
            if effective_trade_date
            else None,
            "ticker": ticker,
            **old_rank,
            "expectation_watchlist_join_status": "joined"
            if watchlist_row
            else "missing_watchlist_row",
            "expectation_residual_component_score": component_score,
            "combined_alpha_score": round(old_score + component_score, 6)
            if old_score is not None
            else None,
            "forward_outcomes": forward_outcomes,
        }
        if watchlist_row:
            row.update(
                {
                    "primary_bucket": watchlist_row.get("primary_bucket"),
                    "wide_watchlist_bucket": watchlist_row.get("wide_watchlist_bucket"),
                    "primary_expectation_positive": watchlist_row.get(
                        "primary_expectation_positive"
                    ),
                    "wide_watchlist_positive": watchlist_row.get(
                        "wide_watchlist_positive"
                    ),
                    "watchlist_signal_basis": watchlist_row.get(
                        "watchlist_signal_basis"
                    ),
                    "support_30d_positive": watchlist_row.get("support_30d_positive"),
                    "scout_prev_positive": watchlist_row.get("scout_prev_positive"),
                    "residual_leader": watchlist_row.get("residual_leader"),
                    "residual_state": watchlist_row.get("residual_state"),
                    "residual_strength_score": watchlist_row.get(
                        "residual_strength_score"
                    ),
                    "eps_estimate_delta_7d": watchlist_row.get(
                        "eps_estimate_delta_7d"
                    ),
                    "eps_estimate_delta_30d": watchlist_row.get(
                        "eps_estimate_delta_30d"
                    ),
                    "eps_estimate_delta_prev": watchlist_row.get(
                        "eps_estimate_delta_prev"
                    ),
                }
            )
        else:
            row.update(
                {
                    "primary_bucket": "missing_watchlist_row",
                    "wide_watchlist_bucket": "missing_watchlist_row",
                    "primary_expectation_positive": False,
                    "wide_watchlist_positive": False,
                    "watchlist_signal_basis": ["none"],
                    "support_30d_positive": False,
                    "scout_prev_positive": False,
                    "residual_leader": False,
                    "residual_state": "missing_watchlist_row",
                    "residual_strength_score": None,
                    "eps_estimate_delta_7d": None,
                    "eps_estimate_delta_30d": None,
                    "eps_estimate_delta_prev": None,
                }
            )
        rows.append(row)
    return rows


def assign_daily_ranks(rows: list[dict[str, Any]], score_key: str, prefix: str) -> None:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[str(row.get("feature_context_date"))].append(row)

    for feature_date, date_rows in by_date.items():
        scored = [
            row
            for row in date_rows
            if _float(row.get(score_key), None) is not None
        ]
        scored.sort(
            key=lambda row: (
                -(_float(row.get(score_key), -999.0) or -999.0),
                str(row.get("ticker") or ""),
            )
        )
        total = len(scored)
        for idx, row in enumerate(scored):
            rank_pct = (idx + 1) / total if total else None
            row[f"{prefix}_rank"] = idx + 1
            row[f"{prefix}_rank_pct"] = round(rank_pct, 6) if rank_pct is not None else None
            row[f"{prefix}_rank_bucket"] = rank_bucket(rank_pct)
            row[f"{prefix}_rank_scope"] = "daily_full_ranking_surface"
            row[f"{prefix}_rank_date"] = feature_date
        for row in date_rows:
            if _float(row.get(score_key), None) is None:
                row[f"{prefix}_rank"] = None
                row[f"{prefix}_rank_pct"] = None
                row[f"{prefix}_rank_bucket"] = "missing_score"
                row[f"{prefix}_rank_scope"] = "daily_full_ranking_surface"
                row[f"{prefix}_rank_date"] = feature_date


def classify_replacement_bucket(row: dict[str, Any]) -> str:
    old_top = row.get("old_daily_alpha_score_rank_bucket") == "top_decile"
    combined_top = row.get("combined_daily_alpha_score_rank_bucket") == "top_decile"
    if old_top and combined_top:
        return "retained_top_decile"
    if combined_top:
        return "new_combined_top_decile"
    if old_top:
        return "old_top_decile_dropped"
    return "neither_top_decile"


def add_replacement_fields(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        old_rank = row.get("old_daily_alpha_score_rank")
        combined_rank = row.get("combined_daily_alpha_score_rank")
        if old_rank is not None and combined_rank is not None:
            row["daily_rank_improvement"] = old_rank - combined_rank
        else:
            row["daily_rank_improvement"] = None
        row["replacement_bucket"] = classify_replacement_bucket(row)


def compact_row(row: dict[str, Any] | None, horizon_key: str | None = None) -> dict[str, Any] | None:
    if not row:
        return None
    out = {
        "feature_context_date": row.get("feature_context_date"),
        "signal_effective_trade_date": row.get("signal_effective_trade_date"),
        "ticker": row.get("ticker"),
        "replacement_bucket": row.get("replacement_bucket"),
        "old_alpha_score": row.get("old_alpha_score"),
        "old_daily_alpha_score_rank": row.get("old_daily_alpha_score_rank"),
        "old_daily_alpha_score_rank_bucket": row.get(
            "old_daily_alpha_score_rank_bucket"
        ),
        "expectation_residual_component_score": row.get(
            "expectation_residual_component_score"
        ),
        "combined_alpha_score": row.get("combined_alpha_score"),
        "combined_daily_alpha_score_rank": row.get(
            "combined_daily_alpha_score_rank"
        ),
        "combined_daily_alpha_score_rank_bucket": row.get(
            "combined_daily_alpha_score_rank_bucket"
        ),
        "daily_rank_improvement": row.get("daily_rank_improvement"),
        "expectation_watchlist_join_status": row.get(
            "expectation_watchlist_join_status"
        ),
        "primary_bucket": row.get("primary_bucket"),
        "watchlist_signal_basis": row.get("watchlist_signal_basis"),
        "residual_state": row.get("residual_state"),
    }
    if horizon_key:
        outcome = (row.get("forward_outcomes") or {}).get(horizon_key) or {}
        out.update(
            {
                "forward_return": outcome.get("return"),
                "pnl_proxy": outcome.get("pnl_proxy"),
                "future_date": outcome.get("future_date"),
                "gap_reason": outcome.get("gap_reason"),
            }
        )
    return out


def summarize_rows(rows: list[dict[str, Any]], horizon_key: str) -> dict[str, Any]:
    closed = [
        row
        for row in rows
        if ((row.get("forward_outcomes") or {}).get(horizon_key) or {}).get("closed")
    ]
    returns = [
        _float(((row.get("forward_outcomes") or {}).get(horizon_key) or {}).get("return"), None)
        for row in closed
    ]
    returns = [value for value in returns if value is not None]
    pnl_rows = [
        (
            row,
            _float(((row.get("forward_outcomes") or {}).get(horizon_key) or {}).get("pnl_proxy"), 0.0)
            or 0.0,
        )
        for row in closed
    ]
    positive = [(row, pnl) for row, pnl in pnl_rows if pnl > 0]
    positive_total = sum(pnl for _row, pnl in positive)
    top5_positive = sum(
        pnl for _row, pnl in sorted(positive, key=lambda item: item[1], reverse=True)[:5]
    )
    by_ticker_positive: Counter[str] = Counter()
    for row, pnl in positive:
        by_ticker_positive[str(row.get("ticker"))] += pnl
    worst = min(
        closed,
        key=lambda row: _float(
            ((row.get("forward_outcomes") or {}).get(horizon_key) or {}).get("return"),
            0.0,
        )
        or 0.0,
        default=None,
    )
    total_pnl = sum(pnl for _row, pnl in pnl_rows)
    return {
        "closed_outcomes": len(closed),
        "avg_return": round(sum(returns) / len(returns), 6) if returns else None,
        "total_pnl_proxy": round(total_pnl, 2) if pnl_rows else None,
        "avg_pnl_proxy": round(total_pnl / len(pnl_rows), 2) if pnl_rows else None,
        "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 6)
        if returns
        else None,
        "tail_loss": round(min(returns), 6) if returns else None,
        "worst_row": compact_row(worst, horizon_key) if worst else None,
        "top5_positive_contribution_share": (
            round(top5_positive / positive_total, 6) if positive_total > 0 else None
        ),
        "max_single_ticker_positive_share": (
            round(max(by_ticker_positive.values()) / positive_total, 6)
            if positive_total > 0 and by_ticker_positive
            else None
        ),
        "positive_pnl_by_ticker": {
            ticker: round(value, 2)
            for ticker, value in sorted(by_ticker_positive.items())
        },
    }


def horizon_summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {f"{horizon}d": summarize_rows(rows, f"{horizon}d") for horizon in FORWARD_HORIZONS}


def summarize_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "ticker_count": len({row.get("ticker") for row in rows}),
        "tickers": sorted({str(row.get("ticker")) for row in rows}),
        "date_count": len({row.get("feature_context_date") for row in rows}),
        "join_status_counts": dict(
            Counter(str(row.get("expectation_watchlist_join_status")) for row in rows)
        ),
        "primary_bucket_counts": dict(
            Counter(str(row.get("primary_bucket")) for row in rows)
        ),
        "replacement_bucket_counts": dict(
            Counter(str(row.get("replacement_bucket")) for row in rows)
        ),
        "horizons": horizon_summaries(rows),
    }


def bucket_summary(rows: list[dict[str, Any]], bucket_key: str, order: list[str]) -> dict[str, Any]:
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_bucket[str(row.get(bucket_key) or "missing")].append(row)
    ordered = list(order)
    for bucket in sorted(by_bucket):
        if bucket not in ordered:
            ordered.append(bucket)
    return {bucket: summarize_bucket(by_bucket.get(bucket, [])) for bucket in ordered}


def selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    old_top = [
        row for row in rows if row.get("old_daily_alpha_score_rank_bucket") == "top_decile"
    ]
    combined_top = [
        row
        for row in rows
        if row.get("combined_daily_alpha_score_rank_bucket") == "top_decile"
    ]
    new_combined = [
        row for row in rows if row.get("replacement_bucket") == "new_combined_top_decile"
    ]
    dropped = [
        row for row in rows if row.get("replacement_bucket") == "old_top_decile_dropped"
    ]
    retained = [
        row for row in rows if row.get("replacement_bucket") == "retained_top_decile"
    ]
    return {
        "old_top_decile": summarize_bucket(old_top),
        "combined_top_decile": summarize_bucket(combined_top),
        "new_combined_top_decile": summarize_bucket(new_combined),
        "old_top_decile_dropped": summarize_bucket(dropped),
        "retained_top_decile": summarize_bucket(retained),
    }


def closed_count(summary: dict[str, Any], selection: str, horizon: str) -> int:
    return (
        ((summary.get(selection) or {}).get("horizons") or {}).get(horizon) or {}
    ).get("closed_outcomes") or 0


def avg_return(summary: dict[str, Any], selection: str, horizon: str) -> float | None:
    return (
        ((summary.get(selection) or {}).get("horizons") or {}).get(horizon) or {}
    ).get("avg_return")


def total_pnl(summary: dict[str, Any], selection: str, horizon: str) -> float | None:
    return (
        ((summary.get(selection) or {}).get("horizons") or {}).get(horizon) or {}
    ).get("total_pnl_proxy")


def concentration_passed(top_summary: dict[str, Any]) -> bool:
    for horizon in ("5d", "10d"):
        row = (top_summary.get("horizons") or {}).get(horizon) or {}
        top5 = row.get("top5_positive_contribution_share")
        single = row.get("max_single_ticker_positive_share")
        if top5 is None or single is None:
            return False
        if top5 > MAX_TOP5_POSITIVE_SHARE or single > MAX_SINGLE_TICKER_POSITIVE_SHARE:
            return False
    return True


def evaluate_gate(summary: dict[str, Any]) -> dict[str, Any]:
    data_gap_reasons = []
    for selection in ("old_top_decile", "combined_top_decile"):
        if closed_count(summary, selection, "5d") < MIN_TOP_CLOSED_5D:
            data_gap_reasons.append(f"{selection}_5d_closed_below_minimum")
        if closed_count(summary, selection, "10d") < MIN_TOP_CLOSED_10D:
            data_gap_reasons.append(f"{selection}_10d_closed_below_minimum")
    for selection in ("new_combined_top_decile", "old_top_decile_dropped"):
        if closed_count(summary, selection, "5d") < MIN_REPLACEMENT_CLOSED_5D:
            data_gap_reasons.append(f"{selection}_5d_closed_below_minimum")
        if closed_count(summary, selection, "10d") < MIN_REPLACEMENT_CLOSED_10D:
            data_gap_reasons.append(f"{selection}_10d_closed_below_minimum")
    if data_gap_reasons:
        return {
            "promotion_gate_passed": False,
            "ranking_replacement_attribution_passed": False,
            "decision": "observed_only_data_gap",
            "reason": "insufficient_closed_forward_outcomes",
            "data_gap_reasons": data_gap_reasons,
            "thresholds": gate_thresholds(),
        }

    comparisons = []
    directional_passed = True
    for horizon in ("5d", "10d"):
        old_avg = avg_return(summary, "old_top_decile", horizon)
        combined_avg = avg_return(summary, "combined_top_decile", horizon)
        old_pnl = total_pnl(summary, "old_top_decile", horizon)
        combined_pnl = total_pnl(summary, "combined_top_decile", horizon)
        new_avg = avg_return(summary, "new_combined_top_decile", horizon)
        dropped_avg = avg_return(summary, "old_top_decile_dropped", horizon)
        new_pnl = total_pnl(summary, "new_combined_top_decile", horizon)
        dropped_pnl = total_pnl(summary, "old_top_decile_dropped", horizon)
        top_passed = (
            old_avg is not None
            and combined_avg is not None
            and combined_avg > old_avg
            and old_pnl is not None
            and combined_pnl is not None
            and combined_pnl > old_pnl
        )
        replacement_passed = (
            new_avg is not None
            and dropped_avg is not None
            and new_avg > dropped_avg
            and new_pnl is not None
            and dropped_pnl is not None
            and new_pnl > dropped_pnl
        )
        directional_passed = directional_passed and top_passed and replacement_passed
        comparisons.append(
            {
                "horizon": horizon,
                "old_top_avg_return": old_avg,
                "combined_top_avg_return": combined_avg,
                "old_top_total_pnl_proxy": old_pnl,
                "combined_top_total_pnl_proxy": combined_pnl,
                "new_combined_avg_return": new_avg,
                "dropped_old_avg_return": dropped_avg,
                "new_combined_total_pnl_proxy": new_pnl,
                "dropped_old_total_pnl_proxy": dropped_pnl,
                "top_decile_passed": top_passed,
                "replacement_passed": replacement_passed,
            }
        )
    concentration = {
        "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "combined_top_decile": {
            "5d": (summary["combined_top_decile"]["horizons"] or {}).get("5d"),
            "10d": (summary["combined_top_decile"]["horizons"] or {}).get("10d"),
        },
    }
    concentration["passed"] = concentration_passed(summary["combined_top_decile"])
    passed = directional_passed and concentration["passed"]
    return {
        "promotion_gate_passed": False,
        "ranking_replacement_attribution_passed": passed,
        "decision": (
            "observed_only_promising_requires_gate4"
            if passed
            else "observed_only_no_promotable_edge"
        ),
        "reason": (
            "combined_score_beats_old_score_and_replacement_rows"
            if passed
            else "combined_score_failed_directional_or_concentration_gate"
        ),
        "data_gap_reasons": [],
        "thresholds": gate_thresholds(),
        "comparisons": comparisons,
        "concentration": concentration,
    }


def gate_thresholds() -> dict[str, Any]:
    return {
        "min_top_closed_5d": MIN_TOP_CLOSED_5D,
        "min_top_closed_10d": MIN_TOP_CLOSED_10D,
        "min_replacement_closed_5d": MIN_REPLACEMENT_CLOSED_5D,
        "min_replacement_closed_10d": MIN_REPLACEMENT_CLOSED_10D,
        "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    keep_keys = (
        "experiment_id",
        "timestamp",
        "status",
        "hypothesis",
        "change_summary",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "component",
        "parameters",
        "date_range",
        "gate_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "coverage",
        "selection_summary",
        "bucket_summary",
        "gate",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "expected_value_score_delta",
        "llm_metrics",
        "production_impact",
        "decision",
        "rejection_reason",
        "next_evidence_needed",
        "related_files",
        "anti_js",
    )
    return {key: payload[key] for key in keep_keys if key in payload}


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Expectation True Ranking Replacement Attribution",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']}`",
        f"- changed_variable: `{payload['changed_variable']}`",
        f"- gate_reason: `{payload['gate']['reason']}`",
        "",
        "## Summary",
        "",
        payload["change_summary"],
        "",
        "## Gate",
        "",
        "```json",
        json.dumps(_safe(payload["gate"]), indent=2, sort_keys=True),
        "```",
        "",
        "## Coverage",
        "",
        "```json",
        json.dumps(_safe(payload["coverage"]), indent=2, sort_keys=True),
        "```",
        "",
        "## Selection Summary",
        "",
        "```json",
        json.dumps(_safe(payload["selection_summary"]), indent=2, sort_keys=True),
        "```",
        "",
        "## Next Evidence Needed",
        "",
        payload["next_evidence_needed"],
        "",
        ANTI_JS,
        "",
    ]
    return "\n".join(lines)


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not EXPERIMENT_REGISTRY.exists():
        return
    registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8"))
    entry = {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "lane": "alpha_discovery",
        "owner": "codex-expectation-ranking-replacement",
        "hypothesis": payload["hypothesis"],
        "ticket_file": _repo_rel(DOC_TICKET),
        "log_file": _repo_rel(DOC_LOG),
        "updated_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "artifact": _repo_rel(DOC_ARTIFACT),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["gate"].get("reason"),
        },
    }
    experiments = registry.setdefault("experiments", [])
    for idx, row in enumerate(experiments):
        if row.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = {**row, **entry}
            break
    else:
        experiments.append(entry)
    registry["updated_at"] = payload["timestamp"]
    EXPERIMENT_REGISTRY.write_text(
        json.dumps(_safe(registry), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def persist_payload(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "owner": "codex-expectation-ranking-replacement",
        "status": payload["status"],
        "decision": payload["decision"],
        "single_causal_variable": payload["single_causal_variable"],
        "artifact_file": _repo_rel(OUT_JSON),
        "result_file": _repo_rel(DOC_LOG),
        "updated_at": payload["timestamp"],
    }
    _write_json(DOC_TICKET, ticket)
    _write_json(DOCS_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))
    _upsert_registry(payload)


def build_payload(data_dir: Path | None = None) -> dict[str, Any]:
    data_dir = data_dir or (REPO_ROOT / "data")
    timestamp = _utc_now()
    context = build_context(data_dir)
    watchlist_rows = context["rows"]
    watchlist_index = build_watchlist_index(watchlist_rows)
    watchlist_dates = {
        str(row.get("feature_context_date"))
        for row in watchlist_rows
        if row.get("feature_context_date")
    }
    _, features_by_date = load_candidates(data_dir)
    rank_index, date_summaries, failures = build_old_alpha_score_index(features_by_date)
    prices = build_price_lookup(data_dir)
    trading_dates = trading_dates_from_ohlcv(data_dir, prices)
    rows = build_surface_rows(
        rank_index=rank_index,
        watchlist_index=watchlist_index,
        watchlist_dates=watchlist_dates,
        prices=prices,
        trading_dates=trading_dates,
    )
    assign_daily_ranks(rows, "old_alpha_score", "old_daily_alpha_score")
    assign_daily_ranks(rows, "combined_alpha_score", "combined_daily_alpha_score")
    add_replacement_fields(rows)

    summary = selection_summary(rows)
    replacement_summary = bucket_summary(
        rows,
        "replacement_bucket",
        REPLACEMENT_BUCKET_ORDER,
    )
    old_rank_summary = bucket_summary(
        rows,
        "old_daily_alpha_score_rank_bucket",
        RANK_BUCKET_ORDER,
    )
    combined_rank_summary = bucket_summary(
        rows,
        "combined_daily_alpha_score_rank_bucket",
        RANK_BUCKET_ORDER,
    )
    gate = evaluate_gate(summary)
    status = "observed_only_data_gap" if gate["decision"] == "observed_only_data_gap" else "observed_only"
    decision = gate["decision"]
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(DOC_LOG),
        _repo_rel(DOC_TICKET),
        _repo_rel(DOCS_TICKET),
        _repo_rel(DOC_ARTIFACT),
        _repo_rel(EXPERIMENT_LOG_JSONL),
        _repo_rel(EXPERIMENT_REGISTRY),
    ]
    coverage = {
        "surface_rows_total": len(rows),
        "watchlist_rows_total": len(watchlist_rows),
        "watchlist_date_count": len(watchlist_dates),
        "ranking_surface_feature_date_count": len(date_summaries),
        "evaluated_feature_dates": sorted(watchlist_dates),
        "join_status_counts": dict(
            Counter(str(row.get("expectation_watchlist_join_status")) for row in rows)
        ),
        "replacement_bucket_counts": dict(
            Counter(str(row.get("replacement_bucket")) for row in rows)
        ),
        "old_rank_bucket_counts": dict(
            Counter(str(row.get("old_daily_alpha_score_rank_bucket")) for row in rows)
        ),
        "combined_rank_bucket_counts": dict(
            Counter(
                str(row.get("combined_daily_alpha_score_rank_bucket")) for row in rows
            )
        ),
        "field_coverage": field_coverage(
            rows,
            [
                "feature_context_date",
                "signal_effective_trade_date",
                "old_alpha_score",
                "old_daily_alpha_score_rank",
                "combined_alpha_score",
                "combined_daily_alpha_score_rank",
                "expectation_residual_component_score",
                "replacement_bucket",
                "forward_outcomes",
            ],
        ),
        "closed_forward_outcomes": {
            f"{horizon}d": sum(
                1
                for row in rows
                if ((row.get("forward_outcomes") or {}).get(f"{horizon}d") or {}).get(
                    "closed"
                )
            )
            for horizon in FORWARD_HORIZONS
        },
        "surface_rebuild_failures": failures,
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Adding expectation/residual evidence to the existing alpha_score "
            "will improve the full daily cross-sectional top-decile ranking "
            "and replacement rows versus the old alpha_score alone."
        ),
        "change_summary": (
            "Observed-only true ranking replacement attribution. For each "
            "feature_context_date with expectation watchlist coverage, the "
            "script ranks the full daily surface by old_alpha_score and by "
            "old_alpha_score + expectation_residual_component_score, then "
            "compares top-decile and new-vs-dropped replacement buckets."
        ),
        "change_type": "observed_only_ranking_replacement_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 2,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "true_full_surface_ranking_replacement_attribution",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "old_score_source": "quant/cross_sectional_ranking_surface.py",
            "expectation_component_source": "exp-20260525-034 watchlist rows",
            "combined_score_formula": "old_alpha_score + expectation_residual_component_score",
            "component_score_formula": "1.0*primary_7d_positive + 0.35*prev_delta_positive + 0.25*30d_positive + 0.5*residual_leader",
            "ranking_scope": "per feature_context_date full ranking surface",
            "replacement_bucket": "new combined top decile versus old top decile dropped",
            "forward_horizons": list(FORWARD_HORIZONS),
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "anti_js": ANTI_JS,
        },
        "date_range": context["watchlist_payload"].get("date_range"),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Combined old_alpha_score plus expectation/residual component "
                "improves daily full-surface top-decile selection."
            ),
            "2_history_check": (
                "exp-20260526-033 was only a proxy because old_alpha_score was "
                "missing. exp-20260528-005 repaired the join with 100% coverage."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only pass requires combined top decile and new "
                "combined rows to beat old top decile / dropped old rows on "
                "both 5d and 10d avg return and total PnL, with sufficient "
                "closed outcomes and concentration below guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260528_007_expectation_true_ranking_replacement_attribution.py"
            ),
        },
        "gate1": {
            "passed": True,
            **BASELINE,
            "note": "Observed-only attribution; no before/after core strategy metrics change.",
        },
        "gate2": {
            "passed": True,
            "rule_dependencies": [
                "feature_context_date",
                "ticker",
                "daily quant feature snapshots",
                "old_alpha_score",
                "expectation/residual watchlist rows",
                "local OHLCV forward prices",
            ],
            "source_gate2": context["watchlist_payload"].get("gate2"),
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "passed": True,
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "passed": False,
            "note": "A promising attribution result can only unlock a later strategy Gate 1-4 experiment.",
        },
        "coverage": coverage,
        "selection_summary": summary,
        "bucket_summary": {
            "replacement_bucket": replacement_summary,
            "old_daily_alpha_score_rank_bucket": old_rank_summary,
            "combined_daily_alpha_score_rank_bucket": combined_rank_summary,
        },
        "sample_rows": {
            "new_combined_top_decile": [
                compact_row(row)
                for row in sorted(
                    [
                        item
                        for item in rows
                        if item.get("replacement_bucket") == "new_combined_top_decile"
                    ],
                    key=lambda item: item.get("combined_daily_alpha_score_rank") or 999999,
                )[:80]
            ],
            "old_top_decile_dropped": [
                compact_row(row)
                for row in sorted(
                    [
                        item
                        for item in rows
                        if item.get("replacement_bucket") == "old_top_decile_dropped"
                    ],
                    key=lambda item: item.get("old_daily_alpha_score_rank") or 999999,
                )[:80]
            ],
        },
        "gate": gate,
        "before_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE[
                "accepted_core_expected_value_score_sum"
            ],
            "accepted_core_total_pnl_sum": BASELINE["accepted_core_total_pnl_sum"],
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE[
                "accepted_core_expected_value_score_sum"
            ],
            "accepted_core_total_pnl_sum": BASELINE["accepted_core_total_pnl_sum"],
            "strategy_behavior_changed": False,
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": 0.0,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "observed_only_attribution": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "rejection_reason": None
        if gate["ranking_replacement_attribution_passed"]
        else gate["reason"],
        "next_evidence_needed": (
            "If promising, create a separate default-off or strategy Gate 1-4 "
            "experiment with shared production-visible ranking logic. If not "
            "promising, do not promote this simple additive expectation/residual "
            "component; pivot to PEAD eligibility or richer expectation fields."
        ),
        "related_files": related_files,
        "anti_js": ANTI_JS,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(REPO_ROOT / "data"))
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    payload = build_payload(Path(args.data_dir))
    if not args.no_persist:
        persist_payload(payload)

    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "gate": payload["gate"],
                "coverage": {
                    "surface_rows_total": payload["coverage"]["surface_rows_total"],
                    "watchlist_date_count": payload["coverage"]["watchlist_date_count"],
                    "replacement_bucket_counts": payload["coverage"][
                        "replacement_bucket_counts"
                    ],
                    "closed_forward_outcomes": payload["coverage"][
                        "closed_forward_outcomes"
                    ],
                },
                "output": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
