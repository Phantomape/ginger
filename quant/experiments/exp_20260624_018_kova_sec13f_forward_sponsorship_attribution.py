"""exp-20260624-018: Kova SEC13F forward sponsorship attribution.

Observed-only alpha attribution. This reads the exp-20260624-017 Kova SEC13F
forward outcome ledger and tests whether stronger PIT institutional sponsorship
separates settled 1d/3d/5d cash, SPY, and QQQ replacement value.

No strategy, helper, ranking, sizing, exit, order, watchlist, LLM, paper sleeve,
or production daily behavior changes in this experiment.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260624-018"
OWNER = "alpha-explore"
SLUG = "kova_sec13f_forward_sponsorship_attribution"
RUNNER = f"quant/experiments/exp_20260624_018_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_018_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SOURCE_OUTCOME_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260624-017"
    / "kova_sec13f_forward_outcome_settlement_ledger.jsonl"
)

HYPOTHESIS = (
    "Observed-only attribution: Kova forward rows with stronger PIT SEC13F "
    "institutional sponsorship should show better settled 1d/3d/5d cash/SPY/QQQ "
    "replacement value than weak or missing sponsorship rows, creating a future "
    "shared default-off Kova evidence lead without changing strategy behavior."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "kova_multisource_forward_attribution"
TRIAL_FAMILY = "kova_sec13f_forward_sponsorship_attribution"
TRIAL_VARIANT_ID = "post_exp017_partial_forward_1d3d5_v1"
CHANGED_VARIABLE = "kova_sec13f_forward_sponsorship_monotonicity_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-014",
    "exp-20260624-016",
    "exp-20260624-017",
]
NEW_EVIDENCE_AXIS = (
    "New exp-20260624-017 Kova SEC13F outcome ledger rows with settled 1d/3d/5d "
    "cash/SPY/QQQ replacement values for 2026-06-13+ observations; not a "
    "frozen-window 13F holder-count/value, RS, Companyfacts, top-N, hold, "
    "cooldown, notional, or allocator threshold retry."
)
CAUSAL_COMPONENTS = [
    "exp017 settled forward outcome ledger",
    "SEC13F holder/value buckets",
    "cash SPY QQQ replacement-value attribution",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260624-018/exp_20260624_018_kova_sec13f_forward_sponsorship_attribution.json",
    "experiments/cards/exp-20260624-018.md",
    "experiments/manifests/exp-20260624-018.json",
    "experiments/tickets/exp-20260624-018.json",
    "experiments/logs/exp-20260624-018.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HORIZONS = (1, 3, 5)
PRIMARY_HORIZON = 5
BUCKETS = ["low_sponsorship", "mid_sponsorship", "high_sponsorship"]
REPLACEMENT_SUFFIXES = ("cash", "spy", "qqq")
CONFIG = {
    "primary_horizon": PRIMARY_HORIZON,
    "min_primary_sponsorship_rows": 500,
    "min_primary_missing_rows": 100,
    "min_primary_asof_dates": 3,
    "min_supporting_horizons_high_beats_low": 2,
    "max_single_positive_pnl_share": 0.50,
    "positive_pnl_hhi_guardrail": 0.35,
}
DEFAULT_PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no_monotonic_sponsorship_separation",
        "qqq_only_short_horizon_beta",
        "mega_cap_concentration",
        "too_few_5d_quality_rows",
        "forward_window_too_short",
    ],
    "confidence_reason": (
        "exp-20260624-016/017 finally provide PIT SEC13F holder/value fields plus "
        "partial settled forward replacement values, which is the required new "
        "evidence. Confidence stays low because prior Kova RS/growth monotonicity "
        "failed, 10d rows are not closed, and SEC13F is delayed ownership context "
        "that can easily proxy mega-cap beta rather than alpha."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict):
        return prediction
    return dict(DEFAULT_PREDICTION)


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    drawdowns = [
        float(window.get("max_drawdown_pct"))
        for window in windows
        if window.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "windows": windows,
    }


def percentile_rank(value: float, sorted_values: list[float]) -> float | None:
    if not sorted_values:
        return None
    left = bisect.bisect_left(sorted_values, value)
    right = bisect.bisect_right(sorted_values, value)
    # Average rank for ties, normalized to [0, 1].
    avg_zero_based_rank = (left + right - 1) / 2.0
    if len(sorted_values) == 1:
        return 1.0
    return avg_zero_based_rank / (len(sorted_values) - 1)


def log_feature(row: dict[str, Any], key: str) -> float | None:
    value = safe_float(row.get(key))
    if value is None or value <= 0:
        return None
    return math.log1p(value)


def source_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [str(row.get("observation_id") or "") for row in rows if row.get("observation_id")]
    asof_dates = sorted({str(row.get("asof_date") or "")[:10] for row in rows if row.get("asof_date")})
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    return {
        "source_outcome_ledger": repo_rel(SOURCE_OUTCOME_LEDGER),
        "source_exists": SOURCE_OUTCOME_LEDGER.exists(),
        "source_rows": len(rows),
        "duplicate_observation_ids": len(ids) - len(set(ids)),
        "ticker_count": len(tickers),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "asof_date_count": len(asof_dates),
        "sec13f_status_counts": dict(
            sorted(Counter(str(row.get("sec13f_status") or "missing") for row in rows).items())
        ),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in rows).items())
        ),
    }


def add_sponsorship_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    holder_values = []
    total_values = []
    position_values = []
    for row in rows:
        if row.get("sec13f_status") != "ok":
            continue
        holder = log_feature(row, "sec13f_holder_count")
        total = log_feature(row, "sec13f_total_value_usd")
        position = log_feature(row, "sec13f_position_row_count")
        if holder is not None:
            holder_values.append(holder)
        if total is not None:
            total_values.append(total)
        if position is not None:
            position_values.append(position)
    holder_values.sort()
    total_values.sort()
    position_values.sort()

    scored: list[dict[str, Any]] = []
    for row in rows:
        out = dict(row)
        score_parts = []
        holder = log_feature(row, "sec13f_holder_count")
        total = log_feature(row, "sec13f_total_value_usd")
        position = log_feature(row, "sec13f_position_row_count")
        for value, population in (
            (holder, holder_values),
            (total, total_values),
            (position, position_values),
        ):
            if value is None:
                continue
            ranked = percentile_rank(value, population)
            if ranked is not None:
                score_parts.append(ranked)
        score = mean(score_parts)
        out["sec13f_sponsorship_score"] = round_or_none(score, 8)
        out["sec13f_sponsorship_component_count"] = len(score_parts)
        scored.append(out)
    return scored


def status_field(horizon: int) -> str:
    return f"forward_{horizon}d_status"


def metric_field(horizon: int, suffix: str) -> str:
    return f"replacement_value_{horizon}d_vs_{suffix}_usd"


def settled_for_horizon(rows: list[dict[str, Any]], horizon: int) -> list[dict[str, Any]]:
    return [row for row in rows if row.get(status_field(horizon)) == "settled"]


def sponsorship_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("sec13f_status") == "ok"
        and safe_float(row.get("sec13f_sponsorship_score")) is not None
    ]


def assign_buckets(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            safe_float(row.get("sec13f_sponsorship_score")) or -1.0,
            str(row.get("ticker") or ""),
            str(row.get("asof_date") or ""),
        ),
    )
    buckets = {key: [] for key in BUCKETS}
    total = len(ordered)
    if not total:
        return buckets
    for index, row in enumerate(ordered):
        bucket_index = min(2, int(index * 3 / total))
        buckets[BUCKETS[bucket_index]].append(row)
    return buckets


def numeric_values(rows: list[dict[str, Any]], field: str) -> list[float]:
    values = []
    for row in rows:
        value = safe_float(row.get(field))
        if value is not None:
            values.append(value)
    return values


def concentration(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    by_ticker: Counter[str] = Counter()
    for row in rows:
        value = safe_float(row.get(field))
        if value is None or value <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker] += value
    positive_total = sum(by_ticker.values())
    top = [
        {"ticker": ticker, "pnl": round(value, 2), "share": round(value / positive_total, 6)}
        for ticker, value in by_ticker.most_common(8)
    ] if positive_total > 0 else []
    hhi = sum((value / positive_total) ** 2 for value in by_ticker.values()) if positive_total > 0 else None
    max_share = top[0]["share"] if top else None
    return {
        "positive_pnl": round(positive_total, 2),
        "positive_ticker_count": len(by_ticker),
        "max_single_positive_pnl_share": max_share,
        "positive_pnl_hhi": round_or_none(hhi, 6),
        "top_positive_tickers": top,
    }


def summarize_metric(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "mean": round_or_none(mean(values), 4),
        "median": round_or_none(median(values), 4) if values else None,
        "sum": round(sum(values), 2) if values else 0.0,
        "min": round(min(values), 2) if values else None,
        "max": round(max(values), 2) if values else None,
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 4)
        if values
        else None,
    }


def summarize_group(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    score_values = numeric_values(rows, "sec13f_sponsorship_score")
    asof_dates = sorted({str(row.get("asof_date") or "")[:10] for row in rows if row.get("asof_date")})
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    metrics = {}
    for suffix in REPLACEMENT_SUFFIXES:
        field = metric_field(horizon, suffix)
        metrics[f"replacement_value_vs_{suffix}_usd"] = summarize_metric(numeric_values(rows, field))
    return {
        "n": len(rows),
        "ticker_count": len(tickers),
        "asof_date_count": len(asof_dates),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "score_mean": round_or_none(mean(score_values), 6),
        "score_median": round_or_none(median(score_values), 6) if score_values else None,
        "sec13f_status_counts": dict(
            sorted(Counter(str(row.get("sec13f_status") or "missing") for row in rows).items())
        ),
        "replacement_metrics": metrics,
        "cash_positive_concentration": concentration(rows, metric_field(horizon, "cash")),
    }


def _rankdata(values: list[float]) -> list[float]:
    ordered = sorted((value, index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][0] == ordered[cursor][0]:
            end += 1
        avg_rank = (cursor + end - 1) / 2.0
        for _, index in ordered[cursor:end]:
            ranks[index] = avg_rank
        cursor = end
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    x_mean = mean(xs)
    y_mean = mean(ys)
    if x_mean is None or y_mean is None:
        return None
    xdiff = [value - x_mean for value in xs]
    ydiff = [value - y_mean for value in ys]
    denom_x = math.sqrt(sum(value * value for value in xdiff))
    denom_y = math.sqrt(sum(value * value for value in ydiff))
    if denom_x <= 0 or denom_y <= 0:
        return None
    return sum(x * y for x, y in zip(xdiff, ydiff)) / (denom_x * denom_y)


def spearman(rows: list[dict[str, Any]], horizon: int, suffix: str) -> float | None:
    xs = []
    ys = []
    field = metric_field(horizon, suffix)
    for row in rows:
        score = safe_float(row.get("sec13f_sponsorship_score"))
        value = safe_float(row.get(field))
        if score is None or value is None:
            continue
        xs.append(score)
        ys.append(value)
    if len(xs) < 3:
        return None
    return round_or_none(pearson(_rankdata(xs), _rankdata(ys)), 6)


def compare_mean(summary: dict[str, Any], bucket_a: str, bucket_b: str, suffix: str) -> bool:
    a = summary["bucket_summary"][bucket_a]["replacement_metrics"][f"replacement_value_vs_{suffix}_usd"]["mean"]
    b = summary["bucket_summary"][bucket_b]["replacement_metrics"][f"replacement_value_vs_{suffix}_usd"]["mean"]
    return a is not None and b is not None and a > b


def compare_median(summary: dict[str, Any], bucket_a: str, bucket_b: str, suffix: str) -> bool:
    a = summary["bucket_summary"][bucket_a]["replacement_metrics"][f"replacement_value_vs_{suffix}_usd"]["median"]
    b = summary["bucket_summary"][bucket_b]["replacement_metrics"][f"replacement_value_vs_{suffix}_usd"]["median"]
    return a is not None and b is not None and a > b


def horizon_analysis(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    settled_rows = settled_for_horizon(rows, horizon)
    ok_rows = sponsorship_rows(settled_rows)
    missing_rows = [
        row for row in settled_rows if row.get("sec13f_status") != "ok"
    ]
    buckets = assign_buckets(ok_rows)
    bucket_summary = {name: summarize_group(bucket_rows, horizon) for name, bucket_rows in buckets.items()}
    missing_summary = summarize_group(missing_rows, horizon)
    spearman_by_metric = {
        suffix: spearman(ok_rows, horizon, suffix) for suffix in REPLACEMENT_SUFFIXES
    }
    return {
        "horizon": horizon,
        "settled_rows": len(settled_rows),
        "sponsorship_rows": len(ok_rows),
        "missing_or_skipped_sponsorship_rows": len(missing_rows),
        "all_settled_summary": summarize_group(settled_rows, horizon),
        "missing_or_skipped_sponsorship_summary": missing_summary,
        "bucket_summary": bucket_summary,
        "spearman_score_to_replacement": spearman_by_metric,
        "high_beats_low_mean": {
            suffix: compare_mean(
                {"bucket_summary": bucket_summary},
                "high_sponsorship",
                "low_sponsorship",
                suffix,
            )
            for suffix in REPLACEMENT_SUFFIXES
        },
        "high_beats_low_median": {
            suffix: compare_median(
                {"bucket_summary": bucket_summary},
                "high_sponsorship",
                "low_sponsorship",
                suffix,
            )
            for suffix in REPLACEMENT_SUFFIXES
        },
    }


def build_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored_rows = add_sponsorship_scores(rows)
    horizons = {str(horizon): horizon_analysis(scored_rows, horizon) for horizon in HORIZONS}
    return {
        "source_summary": source_summary(rows),
        "score_definition": (
            "sec13f_sponsorship_score = average percentile rank of log1p(holder_count), "
            "log1p(total_value_usd), and log1p(position_row_count) among SEC13F-ok "
            "rows. Missing/skipped SEC13F rows are measured separately and not ranked."
        ),
        "horizons": horizons,
        "sample_scored_rows": [
            {
                "ticker": row.get("ticker"),
                "asof_date": row.get("asof_date"),
                "sec13f_status": row.get("sec13f_status"),
                "sec13f_holder_count": row.get("sec13f_holder_count"),
                "sec13f_total_value_usd": row.get("sec13f_total_value_usd"),
                "sec13f_position_row_count": row.get("sec13f_position_row_count"),
                "sec13f_sponsorship_score": row.get("sec13f_sponsorship_score"),
                "replacement_value_5d_vs_cash_usd": row.get("replacement_value_5d_vs_cash_usd"),
                "replacement_value_5d_vs_spy_usd": row.get("replacement_value_5d_vs_spy_usd"),
                "replacement_value_5d_vs_qqq_usd": row.get("replacement_value_5d_vs_qqq_usd"),
            }
            for row in scored_rows[:5]
        ],
    }


def evaluate_gate4(analysis: dict[str, Any]) -> dict[str, Any]:
    primary = analysis["horizons"][str(PRIMARY_HORIZON)]
    high = primary["bucket_summary"]["high_sponsorship"]
    low = primary["bucket_summary"]["low_sponsorship"]
    missing = primary["missing_or_skipped_sponsorship_summary"]
    concentration = high["cash_positive_concentration"]
    support_counts = {}
    for suffix in REPLACEMENT_SUFFIXES:
        support_counts[f"mean_{suffix}_high_beats_low_horizon_count"] = sum(
            1
            for horizon in HORIZONS
            if analysis["horizons"][str(horizon)]["high_beats_low_mean"][suffix]
        )
    checks = {
        "primary_sponsorship_sample_min_passed": (
            primary["sponsorship_rows"] >= CONFIG["min_primary_sponsorship_rows"]
        ),
        "primary_missing_sample_min_passed": (
            primary["missing_or_skipped_sponsorship_rows"] >= CONFIG["min_primary_missing_rows"]
        ),
        "primary_asof_dates_min_passed": (
            primary["all_settled_summary"]["asof_date_count"] >= CONFIG["min_primary_asof_dates"]
        ),
        "high_mean_cash_beats_low": primary["high_beats_low_mean"]["cash"],
        "high_median_cash_beats_low": primary["high_beats_low_median"]["cash"],
        "high_mean_spy_beats_low": primary["high_beats_low_mean"]["spy"],
        "high_median_spy_beats_low": primary["high_beats_low_median"]["spy"],
        "high_mean_qqq_beats_low": primary["high_beats_low_mean"]["qqq"],
        "high_median_qqq_beats_low": primary["high_beats_low_median"]["qqq"],
        "spearman_cash_positive": (
            (primary["spearman_score_to_replacement"]["cash"] or 0.0) > 0.0
        ),
        "spearman_spy_positive": (
            (primary["spearman_score_to_replacement"]["spy"] or 0.0) > 0.0
        ),
        "spearman_qqq_positive": (
            (primary["spearman_score_to_replacement"]["qqq"] or 0.0) > 0.0
        ),
        "high_mean_cash_beats_missing": (
            high["replacement_metrics"]["replacement_value_vs_cash_usd"]["mean"] is not None
            and missing["replacement_metrics"]["replacement_value_vs_cash_usd"]["mean"] is not None
            and high["replacement_metrics"]["replacement_value_vs_cash_usd"]["mean"]
            > missing["replacement_metrics"]["replacement_value_vs_cash_usd"]["mean"]
        ),
        "high_mean_spy_beats_missing": (
            high["replacement_metrics"]["replacement_value_vs_spy_usd"]["mean"] is not None
            and missing["replacement_metrics"]["replacement_value_vs_spy_usd"]["mean"] is not None
            and high["replacement_metrics"]["replacement_value_vs_spy_usd"]["mean"]
            > missing["replacement_metrics"]["replacement_value_vs_spy_usd"]["mean"]
        ),
        "high_mean_qqq_beats_missing": (
            high["replacement_metrics"]["replacement_value_vs_qqq_usd"]["mean"] is not None
            and missing["replacement_metrics"]["replacement_value_vs_qqq_usd"]["mean"] is not None
            and high["replacement_metrics"]["replacement_value_vs_qqq_usd"]["mean"]
            > missing["replacement_metrics"]["replacement_value_vs_qqq_usd"]["mean"]
        ),
        "multi_horizon_mean_cash_support": (
            support_counts["mean_cash_high_beats_low_horizon_count"]
            >= CONFIG["min_supporting_horizons_high_beats_low"]
        ),
        "multi_horizon_mean_spy_support": (
            support_counts["mean_spy_high_beats_low_horizon_count"]
            >= CONFIG["min_supporting_horizons_high_beats_low"]
        ),
        "multi_horizon_mean_qqq_support": (
            support_counts["mean_qqq_high_beats_low_horizon_count"]
            >= CONFIG["min_supporting_horizons_high_beats_low"]
        ),
        "concentration_max_share_passed": (
            concentration["max_single_positive_pnl_share"] is not None
            and concentration["max_single_positive_pnl_share"]
            <= CONFIG["max_single_positive_pnl_share"]
        ),
        "concentration_hhi_passed": (
            concentration["positive_pnl_hhi"] is not None
            and concentration["positive_pnl_hhi"] <= CONFIG["positive_pnl_hhi_guardrail"]
        ),
    }
    failed = [key for key, passed in checks.items() if not passed]
    observed_lead = not failed
    decision = (
        "observed_only_positive_kova_sec13f_sponsorship_lead_not_promoted"
        if observed_lead
        else "rejected_no_monotonic_kova_sec13f_sponsorship_edge"
    )
    return {
        "observed_only_lead": observed_lead,
        "decision": decision,
        "failed_reasons": failed,
        "acceptance_checks": checks,
        "support_counts": support_counts,
        "strategy_rerun_required": False,
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "max_drawdown_pct": 0.0,
        },
        "lead_limitations": [
            "Forward-only post-2026-06-13 observations, not canonical fixed-window PIT coverage.",
            "10d outcomes remain pending and are excluded from the decision.",
            "No shared helper or daily adapter was promoted.",
        ],
    }


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = safe_float(prediction.get("success_probability")) or 0.0
    actual = 1 if success else 0
    return {
        "actual_success": actual,
        "predicted_success_probability": probability,
        "brier_score": round((probability - actual) ** 2, 4),
        "predicted_failure_modes": list(prediction.get("main_failure_modes") or []),
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": bool(
            set(prediction.get("main_failure_modes") or []) & set(failed)
        ),
        "surprise_note": (
            "The SEC13F sponsorship score separated partial forward rows strongly "
            "enough for an observed-only lead, but it remains forward-only and not "
            "promoted."
            if success
            else "The sponsorship score did not clear the preregistered monotonic, "
            "benchmark, or concentration checks; this matches the low-confidence "
            "prior that delayed 13F context may mostly proxy broad ownership beta."
        ),
    }


def build_payload() -> dict[str, Any]:
    rows = read_jsonl(SOURCE_OUTCOME_LEDGER)
    baseline = load_baseline_metrics()
    prediction = load_ticket_prediction()
    analysis = build_analysis(rows)
    gate4 = evaluate_gate4(analysis)
    observed_lead = bool(gate4["observed_only_lead"])
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    now = utc_now()
    why = (
        "The fixed PIT SEC13F holder/value sponsorship score separated settled "
        "Kova forward replacement rows across cash, SPY, and QQQ, but the result "
        "is still forward-only attribution and did not promote a helper or change "
        "strategy behavior."
        if observed_lead
        else "The fixed PIT SEC13F holder/value sponsorship score did not show "
        "robust monotonic replacement-value separation across the settled 1d/3d/5d "
        "Kova rows. Delayed 13F sponsorship is useful context here, but not a "
        "standalone Kova ranking or candidate-pool edge on this forward sample."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_lead,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "partial_closed_forward_replacement_value_rows",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260623-014": (
                    "Rejected Kova RS/growth alignment monotonicity on earlier "
                    "closed forward rows. This run tests the newly repaired SEC13F "
                    "sponsorship field on exp017 post-2026-06-13 rows."
                ),
                "exp-20260624-016": (
                    "Accepted measurement repair creating PIT-valid SEC13F "
                    "holder/value fields for Kova forward observations."
                ),
                "exp-20260624-017": (
                    "Accepted measurement repair settling 1d/3d/5d cash/SPY/QQQ "
                    "replacement values for those rows; 10d remains pending."
                ),
                "novelty_gate": (
                    "Reservation passed without override. The new evidence axis is "
                    "partial closed forward replacement rows, not a frozen-window "
                    "13F or Kova threshold retry."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: compute a fixed SEC13F "
                "sponsorship score from holder_count, total_value_usd, and "
                "position_row_count, bucket settled rows into tertiles, and test "
                "cash/SPY/QQQ replacement-value monotonicity. No trading policy "
                "changes."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if 5d sponsorship sample and missing sample "
                "floors pass, high sponsorship beats low on mean/median cash/SPY/QQQ, "
                "high beats missing on mean cash/SPY/QQQ, Spearman correlations are "
                "positive, at least two horizons support high>low by mean, and "
                "high-bucket positive PnL concentration passes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_outcome_ledger": repo_rel(SOURCE_OUTCOME_LEDGER),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "horizons": list(HORIZONS),
            "primary_horizon": PRIMARY_HORIZON,
            "bucket_method": "tertiles on sec13f_sponsorship_score within settled SEC13F-ok rows",
            "config": CONFIG,
            "score_definition": analysis["score_definition"],
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(rows) and analysis["source_summary"]["duplicate_observation_ids"] == 0,
            "fields_checked": [
                "observation_id",
                "asof_date",
                "ticker",
                "sec13f_status",
                "sec13f_holder_count",
                "sec13f_total_value_usd",
                "sec13f_position_row_count",
                "forward_1d_status",
                "forward_3d_status",
                "forward_5d_status",
                "replacement_value_1d_vs_cash_usd",
                "replacement_value_3d_vs_spy_usd",
                "replacement_value_5d_vs_qqq_usd",
                "entry_date",
                "target_price",
            ],
            "source_summary": analysis["source_summary"],
            "target_price_relevance": (
                "Not applicable: this is observed-only fixed-horizon outcome "
                "attribution and does not schedule target exits or orders."
            ),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": analysis["source_summary"]["source_rows"],
            "signals_survived": analysis["horizons"][str(PRIMARY_HORIZON)]["settled_rows"],
            "survival_rate": round(
                analysis["horizons"][str(PRIMARY_HORIZON)]["settled_rows"]
                / analysis["source_summary"]["source_rows"],
                4,
            )
            if analysis["source_summary"]["source_rows"]
            else None,
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
            "strategy_behavior_changed": False,
        },
        "attribution": analysis,
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "shared_helper_promoted": False,
            "uses_kova_forward_snapshots": True,
            "uses_sec13f_forward_context": True,
            "forward_only_not_fixed_window_pit_coverage": True,
            "live_ready": False,
            "live_realistic_execution_envelope": (
                "Not evaluated for live use; this is observed-only attribution "
                "and cannot become live-ready."
            ),
        },
        "calibration": calibration(prediction, observed_lead, gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry Kova SEC13F holder_count, total_value_usd, "
                "position_row_count, sponsorship score, RS, Companyfacts, top-N, "
                "hold, cooldown, notional, or allocator thresholds on the same "
                "exp017 partial forward rows. This fixed sponsorship attribution "
                "is the result for that surface."
            ),
            "new_evidence_required": (
                "A valid retry needs enough closed 10d replacement-value rows, "
                "materially richer PIT manager/flow provenance, borrow/options "
                "cross-evidence, or a shared default-off helper with canonical "
                "fixed-window PIT coverage."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(SOURCE_OUTCOME_LEDGER),
            repo_rel(OUT_JSON),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260623-014.json",
            "experiments/logs/exp-20260624-016.json",
            "experiments/logs/exp-20260624-017.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    attribution = payload["attribution"]
    primary = attribution["horizons"][str(PRIMARY_HORIZON)]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "source_summary": attribution["source_summary"],
            "score_definition": attribution["score_definition"],
            "primary_horizon": PRIMARY_HORIZON,
            "primary_horizon_summary": {
                "settled_rows": primary["settled_rows"],
                "sponsorship_rows": primary["sponsorship_rows"],
                "missing_or_skipped_sponsorship_rows": primary[
                    "missing_or_skipped_sponsorship_rows"
                ],
                "bucket_summary": primary["bucket_summary"],
                "missing_or_skipped_sponsorship_summary": primary[
                    "missing_or_skipped_sponsorship_summary"
                ],
                "spearman_score_to_replacement": primary[
                    "spearman_score_to_replacement"
                ],
                "high_beats_low_mean": primary["high_beats_low_mean"],
                "high_beats_low_median": primary["high_beats_low_median"],
            },
            "horizon_support": {
                horizon: {
                    "settled_rows": attribution["horizons"][horizon]["settled_rows"],
                    "sponsorship_rows": attribution["horizons"][horizon]["sponsorship_rows"],
                    "high_beats_low_mean": attribution["horizons"][horizon][
                        "high_beats_low_mean"
                    ],
                    "spearman_score_to_replacement": attribution["horizons"][horizon][
                        "spearman_score_to_replacement"
                    ],
                }
                for horizon in sorted(attribution["horizons"])
            },
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
        "artifact": payload["artifact"],
        "log": payload["log"],
    }


def money(value: Any) -> str:
    number = safe_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def card_bucket_row(name: str, summary: dict[str, Any]) -> str:
    metrics = summary["replacement_metrics"]
    return "| {name} | {n} | {score} | {cash} | {spy} | {qqq} | {median_cash} |".format(
        name=name,
        n=summary["n"],
        score=summary["score_median"],
        cash=money(metrics["replacement_value_vs_cash_usd"]["mean"]),
        spy=money(metrics["replacement_value_vs_spy_usd"]["mean"]),
        qqq=money(metrics["replacement_value_vs_qqq_usd"]["mean"]),
        median_cash=money(metrics["replacement_value_vs_cash_usd"]["median"]),
    )


def build_card(payload: dict[str, Any]) -> str:
    primary = payload["attribution"]["horizons"][str(PRIMARY_HORIZON)]
    rows = [
        "| Bucket | Rows | Median Score | Mean Cash | Mean SPY | Mean QQQ | Median Cash |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in BUCKETS:
        rows.append(card_bucket_row(bucket, primary["bucket_summary"][bucket]))
    rows.append(
        card_bucket_row(
            "missing_or_skipped",
            primary["missing_or_skipped_sponsorship_summary"],
        )
    )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova SEC13F forward sponsorship attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Primary 5d Buckets",
            "",
            *rows,
            "",
            f"- 5d sponsorship rows: `{primary['sponsorship_rows']}`",
            f"- 5d missing/skipped rows: `{primary['missing_or_skipped_sponsorship_rows']}`",
            f"- Spearman score to cash/SPY/QQQ: `{primary['spearman_score_to_replacement']['cash']}` / `{primary['spearman_score_to_replacement']['spy']}` / `{primary['spearman_score_to_replacement']['qqq']}`",
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        SOURCE_OUTCOME_LEDGER,
        BASELINE_RESULT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "attribution": log_record["attribution"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    primary = payload["attribution"]["horizons"][str(PRIMARY_HORIZON)]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "primary_horizon": PRIMARY_HORIZON,
                "primary_sponsorship_rows": primary["sponsorship_rows"],
                "primary_missing_or_skipped_rows": primary[
                    "missing_or_skipped_sponsorship_rows"
                ],
                "spearman": primary["spearman_score_to_replacement"],
                "high_beats_low_mean": primary["high_beats_low_mean"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
