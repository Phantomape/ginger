"""exp-20260704-014: options earnings surprise-history forward attribution.

Observed-only alpha search. This joins the refreshed exp-20260630-008
OnclickMedia options forward outcome ledger to daily earnings snapshots and
tests one fixed attribution shape: tickers with consistently positive
historical EPS surprise history should show better 10-day cash/SPY/QQQ
replacement value than weak or missing surprise-history names.

No strategy behavior, shared helper, daily snapshot, paper order, live order,
ranking, sizing, exit, watchlist, or LLM behavior changes.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260704-014"
OWNER = "alpha-explore"
SLUG = "options_earnings_surprise_history_forward_value"
RUNNER = f"quant/experiments/exp_20260704_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUTCOME_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260630-008"
    / "options_forward_outcome_refresh_all_current_sources.jsonl"
)
EARNINGS_SNAPSHOT_DIR = REPO_ROOT / "data" / "daily" / "snapshots" / "earnings"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260704_014_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: OnclickMedia closed options forward rows joined to "
    "daily earnings snapshots may show that tickers with consistently positive "
    "historical EPS surprise history have better 10-day cash SPY QQQ replacement "
    "value than weak or missing surprise-history names, without changing options "
    "demand thresholds or trading behavior."
)
CHANGE_TYPE = "observed_only_forward_attribution"
MECHANISM_FAMILY = "production_visible_options_earnings_surprise_forward_attribution"
TRIAL_FAMILY = "onclickmedia_options_earnings_surprise_history_forward_attribution"
TRIAL_VARIANT_ID = "fixed_surprise_history_positive_vs_weak_missing_forward10_v1"
CHANGED_VARIABLE = "onclickmedia_options_earnings_surprise_history_forward_value_v1"
SINGLE_CAUSAL_VARIABLE = CHANGED_VARIABLE
NEW_EVIDENCE_TYPE = "closed_options_forward_rows_plus_daily_earnings_surprise_history_join"
NEW_EVIDENCE_AXIS = (
    "Closed OnclickMedia 10-day options replacement rows are joined to the "
    "daily earnings snapshot surprise-history field. This is a fixed "
    "cross-surface attribution and not an options threshold, event-distance, "
    "hold-period, notional, IV/OI/spread/liquidity, or response-curve retune."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260704-002",
    "exp-20260531-001",
    "exp-20260421-008",
]
CAUSAL_COMPONENTS = [
    "closed options outcome ledger",
    "daily earnings snapshot surprise-history join",
    "cash SPY QQQ replacement attribution",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260704-014/exp_20260704_014_options_earnings_surprise_history_forward_value.json",
    "experiments/cards/exp-20260704-014.md",
    "experiments/manifests/exp-20260704-014.json",
    "experiments/tickets/exp-20260704-014.json",
    "experiments/logs/exp-20260704-014.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

PRIMARY_HORIZON = 10
COMPARATORS = ("cash", "spy", "qqq")
REPLACEMENT_KEYS = {
    "cash": f"replacement_value_{PRIMARY_HORIZON}d_vs_cash_usd",
    "spy": f"replacement_value_{PRIMARY_HORIZON}d_vs_spy_usd",
    "qqq": f"replacement_value_{PRIMARY_HORIZON}d_vs_qqq_usd",
}
POSITIVE_BUCKET = "consistent_positive_surprise"
WEAK_BUCKET = "weak_or_negative_surprise"
MISSING_BUCKET = "missing_or_insufficient_surprise"
MIXED_BUCKET = "mixed_surprise_history"
CONTROL_GROUP = "weak_or_missing_surprise_control"
BUCKETS = (POSITIVE_BUCKET, WEAK_BUCKET, MISSING_BUCKET, MIXED_BUCKET)
ACCEPTANCE_RULE = {
    "primary_horizon": PRIMARY_HORIZON,
    "snapshot_join": "latest earnings snapshot with snapshot_date <= quote_date",
    "positive_bucket": (
        "historical_surprise_count >= 4, positive_surprise_count >= 3, "
        "avg_historical_surprise_pct >= 5.0"
    ),
    "weak_bucket": (
        "historical_surprise_count >= 4 and "
        "(positive_surprise_count <= 2 or avg_historical_surprise_pct <= 0)"
    ),
    "missing_bucket": "avg_historical_surprise_pct missing or history_count < 4",
    "control_group": "weak_or_negative_surprise + missing_or_insufficient_surprise",
    "min_history_count": 4,
    "min_positive_bucket_rows": 100,
    "min_control_rows": 100,
    "min_positive_bucket_tickers": 20,
    "min_control_tickers": 20,
    "positive_cash_mean_must_be_gt_zero": True,
    "positive_must_beat_control_mean_for": list(COMPARATORS),
    "positive_must_beat_control_median_for": list(COMPARATORS),
    "max_positive_bucket_single_positive_pnl_share": 0.35,
    "max_positive_bucket_positive_pnl_hhi": 0.20,
}
DEFAULT_PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "surprise_history_overlaps_pead",
        "options_demand_noise_dominates",
        "sample_concentration",
        "no_incremental_replacement_value",
    ],
    "confidence_reason": (
        "Options event-distance alone failed, and earnings surprise history has "
        "prior PEAD failures, but this is a new fixed cross-surface attribution "
        "using closed OnclickMedia 10d replacement rows plus daily earnings "
        "snapshot surprise history rather than an options threshold or "
        "pre-earnings candidate-pool retune."
    ),
}
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "daily_snapshot_exposed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "watchlist_changed": False,
    "llm_decision_boundary_changed": False,
    "live_ready": False,
    "live_realism_evaluated": False,
    "uses_options_forward_outcome_ledger": True,
    "uses_daily_earnings_snapshots": True,
    "forward_only_not_fixed_window_pit_coverage": True,
    "parity_note": (
        "Observed-only attribution on experiment-owned forward outcome rows. "
        "No shared policy/helper or production adapter behavior changed."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                item = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL") from exc
            if isinstance(item, dict):
                rows.append(item)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def as_int(value: Any) -> int | None:
    number = as_float(value)
    return None if number is None else int(number)


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text[:8], fmt).date()
        except ValueError:
            continue
    return None


def round_or_none(value: Any, digits: int = 4) -> float | None:
    number = as_float(value)
    return None if number is None else round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def percentile(values: list[float], ratio: float) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    position = (len(clean) - 1) * ratio
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return clean[lower]
    return clean[lower] + (clean[upper] - clean[lower]) * (position - lower)


def metric_stats(values: list[float]) -> dict[str, Any]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return {
            "n": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "p25": None,
            "p75": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(clean),
        "sum": round(sum(clean), 4),
        "mean": round(mean(clean), 4),
        "median": round(median(clean), 4),
        "p25": round(percentile(clean, 0.25), 4),
        "p75": round(percentile(clean, 0.75), 4),
        "min": round(min(clean), 4),
        "max": round(max(clean), 4),
        "positive_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def positive_concentration(
    rows: Iterable[Mapping[str, Any]], replacement_key: str
) -> dict[str, Any]:
    pnl_by_ticker: Counter[str] = Counter()
    for row in rows:
        value = as_float(row.get(replacement_key))
        ticker = str(row.get("ticker") or "").upper()
        if value is not None and value > 0 and ticker:
            pnl_by_ticker[ticker] += value
    total = sum(pnl_by_ticker.values())
    if total <= 0:
        return {
            "positive_pnl": 0.0,
            "positive_ticker_count": 0,
            "max_single_positive_pnl_share": None,
            "positive_pnl_hhi": None,
            "top_positive_tickers": [],
            "passes_guardrail": False,
        }
    shares = [value / total for value in pnl_by_ticker.values()]
    max_share = max(shares)
    hhi = sum(share * share for share in shares)
    return {
        "positive_pnl": round(total, 4),
        "positive_ticker_count": len(pnl_by_ticker),
        "max_single_positive_pnl_share": round(max_share, 6),
        "positive_pnl_hhi": round(hhi, 6),
        "top_positive_tickers": [
            {"ticker": ticker, "positive_pnl": round(value, 2), "share": round(value / total, 4)}
            for ticker, value in pnl_by_ticker.most_common(8)
        ],
        "passes_guardrail": (
            max_share <= ACCEPTANCE_RULE["max_positive_bucket_single_positive_pnl_share"]
            and hhi <= ACCEPTANCE_RULE["max_positive_bucket_positive_pnl_hhi"]
        ),
    }


def baseline_summary(path: Path) -> dict[str, Any]:
    data = read_json(path, {})
    windows = data.get("windows") if isinstance(data, dict) else []
    if not isinstance(windows, list):
        windows = []
    signals_generated = sum(as_int(item.get("signals_generated")) or 0 for item in windows)
    signals_survived = sum(as_int(item.get("signals_survived")) or 0 for item in windows)
    return {
        "source": repo_rel(path),
        "exists": path.exists(),
        "window_count": len(windows),
        "windows": [
            {
                "label": item.get("label"),
                "start": item.get("start"),
                "end": item.get("end"),
                "expected_value_score": round_or_none(item.get("expected_value_score")),
                "total_pnl": round_or_none(item.get("total_pnl"), 2),
                "trade_count": as_int(item.get("trade_count")),
                "signals_generated": as_int(item.get("signals_generated")),
                "signals_survived": as_int(item.get("signals_survived")),
                "survival_rate": round_or_none(item.get("survival_rate"), 6),
            }
            for item in windows
        ],
        "aggregate_expected_value_score": round(
            sum(as_float(item.get("expected_value_score")) or 0.0 for item in windows), 4
        ),
        "aggregate_total_pnl": round(
            sum(as_float(item.get("total_pnl")) or 0.0 for item in windows), 2
        ),
        "aggregate_trade_count": sum(as_int(item.get("trade_count")) or 0 for item in windows),
        "aggregate_signals_generated": signals_generated,
        "aggregate_signals_survived": signals_survived,
        "aggregate_survival_rate": (
            round(signals_survived / signals_generated, 6) if signals_generated else None
        ),
    }


def load_earnings_snapshots() -> dict[str, Any]:
    snapshots: dict[date, dict[str, Any]] = {}
    for path in sorted(EARNINGS_SNAPSHOT_DIR.glob("earnings_snapshot_*.json")):
        payload = read_json(path, {})
        snapshot_date = parse_date(payload.get("date") or path.stem.rsplit("_", 1)[-1])
        if snapshot_date is None:
            continue
        earnings = payload.get("earnings")
        if not isinstance(earnings, dict):
            continue
        snapshots[snapshot_date] = {
            "path": path,
            "date": snapshot_date,
            "coverage": payload.get("coverage") if isinstance(payload, dict) else {},
            "earnings": {
                str(ticker).upper(): value
                for ticker, value in earnings.items()
                if isinstance(value, dict)
            },
        }
    dates = sorted(snapshots)
    return {"dates": dates, "snapshots": snapshots}


def snapshot_for_quote(
    snapshot_index: Mapping[str, Any], quote_date: date
) -> dict[str, Any] | None:
    dates: list[date] = snapshot_index["dates"]
    index = bisect.bisect_right(dates, quote_date) - 1
    if index < 0:
        return None
    return snapshot_index["snapshots"][dates[index]]


def surprise_history(snapshot_item: Mapping[str, Any]) -> dict[str, Any]:
    raw_values = snapshot_item.get("historical_surprise_pct")
    values: list[float] = []
    if isinstance(raw_values, list):
        for item in raw_values:
            value = as_float(item)
            if value is not None:
                values.append(value)
    avg = as_float(snapshot_item.get("avg_historical_surprise_pct"))
    if avg is None and values:
        avg = mean(values)
    positive_count = sum(1 for value in values if value > 0)
    nonpositive_count = sum(1 for value in values if value <= 0)
    return {
        "historical_surprise_count": len(values),
        "positive_surprise_count": positive_count,
        "nonpositive_surprise_count": nonpositive_count,
        "avg_historical_surprise_pct": round_or_none(avg),
        "historical_surprise_pct": [round(value, 4) for value in values],
    }


def surprise_bucket(history: Mapping[str, Any]) -> str:
    count = as_int(history.get("historical_surprise_count")) or 0
    positive_count = as_int(history.get("positive_surprise_count")) or 0
    avg = as_float(history.get("avg_historical_surprise_pct"))
    if count < ACCEPTANCE_RULE["min_history_count"] or avg is None:
        return MISSING_BUCKET
    if positive_count >= 3 and avg >= 5.0:
        return POSITIVE_BUCKET
    if positive_count <= 2 or avg <= 0.0:
        return WEAK_BUCKET
    return MIXED_BUCKET


def enrich_rows(
    rows: Iterable[Mapping[str, Any]], snapshot_index: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    missing_examples: list[dict[str, Any]] = []

    for row in rows:
        counters["total_rows"] += 1
        if row.get("outcome_status") == "closed_10d_forward":
            counters["closed_10d_rows"] += 1
        else:
            continue
        if row.get("quality_pass") is True:
            counters["quality_closed_10d_rows"] += 1
        else:
            continue

        ticker = str(row.get("ticker") or "").upper().strip()
        quote_date = parse_date(row.get("quote_date"))
        entry_date = parse_date(row.get("entry_date"))
        if ticker:
            counters["quality_rows_with_ticker"] += 1
        if entry_date is not None:
            counters["quality_rows_with_entry_date"] += 1
        if row.get("target_price") is not None:
            counters["quality_rows_with_target_price"] += 1
        if row.get("entry_price") is not None:
            counters["quality_rows_with_entry_price"] += 1
        if quote_date is None:
            counters["quality_rows_missing_quote_date"] += 1
            continue

        replacement_values = {
            comparator: as_float(row.get(key))
            for comparator, key in REPLACEMENT_KEYS.items()
        }
        if all(value is not None for value in replacement_values.values()):
            counters["quality_rows_with_all_10d_replacements"] += 1
        else:
            counters["quality_rows_missing_replacements"] += 1
            continue

        snapshot = snapshot_for_quote(snapshot_index, quote_date)
        if snapshot is None:
            counters["quality_rows_without_snapshot"] += 1
            if len(missing_examples) < 5:
                missing_examples.append({"ticker": ticker, "quote_date": quote_date.isoformat()})
            continue
        snapshot_item = snapshot["earnings"].get(ticker)
        if not snapshot_item:
            counters["quality_rows_without_ticker_earnings"] += 1
            if len(missing_examples) < 5:
                missing_examples.append(
                    {
                        "ticker": ticker,
                        "quote_date": quote_date.isoformat(),
                        "snapshot_date": snapshot["date"].isoformat(),
                    }
                )
            continue

        history = surprise_history(snapshot_item)
        bucket = surprise_bucket(history)
        counters["joined_rows"] += 1
        counters[f"bucket_{bucket}"] += 1
        if history["historical_surprise_count"] >= ACCEPTANCE_RULE["min_history_count"]:
            counters["joined_rows_with_sufficient_history"] += 1
        else:
            counters["joined_rows_with_insufficient_history"] += 1

        enriched.append(
            {
                "ticker": ticker,
                "quote_date": quote_date.isoformat(),
                "entry_date": entry_date.isoformat() if entry_date else None,
                "observation_id": row.get("observation_id"),
                "source_experiment_id": row.get("source_experiment_id"),
                "snapshot_date": snapshot["date"].isoformat(),
                "snapshot_file": repo_rel(snapshot["path"]),
                "next_earnings_date": snapshot_item.get("next_earnings_date"),
                "eps_actual_last": round_or_none(snapshot_item.get("eps_actual_last")),
                "eps_estimate": round_or_none(snapshot_item.get("eps_estimate")),
                **history,
                "surprise_bucket": bucket,
                "replacement_value_10d_vs_cash_usd": replacement_values["cash"],
                "replacement_value_10d_vs_spy_usd": replacement_values["spy"],
                "replacement_value_10d_vs_qqq_usd": replacement_values["qqq"],
            }
        )

    coverage = dict(counters)
    quality_rows = counters["quality_closed_10d_rows"]
    coverage.update(
        {
            "earnings_snapshot_file_count": len(snapshot_index["dates"]),
            "first_snapshot_date": (
                snapshot_index["dates"][0].isoformat() if snapshot_index["dates"] else None
            ),
            "last_snapshot_date": (
                snapshot_index["dates"][-1].isoformat() if snapshot_index["dates"] else None
            ),
            "join_rate_on_quality_rows": (
                round(counters["joined_rows"] / quality_rows, 6) if quality_rows else None
            ),
            "sufficient_history_rate_on_joined_rows": (
                round(counters["joined_rows_with_sufficient_history"] / counters["joined_rows"], 6)
                if counters["joined_rows"]
                else None
            ),
            "missing_join_examples": missing_examples,
        }
    )
    return enriched, coverage


def summarize_group(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    tickers = {row.get("ticker") for row in rows if row.get("ticker")}
    entry_dates = {row.get("entry_date") for row in rows if row.get("entry_date")}
    quote_dates = {row.get("quote_date") for row in rows if row.get("quote_date")}
    avg_surprises = [
        value
        for value in (as_float(row.get("avg_historical_surprise_pct")) for row in rows)
        if value is not None
    ]
    history_counts = [
        value
        for value in (as_float(row.get("historical_surprise_count")) for row in rows)
        if value is not None
    ]
    return {
        "n": len(rows),
        "ticker_count": len(tickers),
        "entry_date_count": len(entry_dates),
        "quote_date_count": len(quote_dates),
        "avg_historical_surprise_pct": {
            "mean": round_or_none(mean(avg_surprises) if avg_surprises else None),
            "median": round_or_none(median(avg_surprises) if avg_surprises else None),
            "min": round_or_none(min(avg_surprises) if avg_surprises else None),
            "max": round_or_none(max(avg_surprises) if avg_surprises else None),
        },
        "historical_surprise_count": {
            "mean": round_or_none(mean(history_counts) if history_counts else None),
            "median": round_or_none(median(history_counts) if history_counts else None),
        },
        "replacement_metrics": {
            comparator: metric_stats(
                [
                    as_float(row.get(f"replacement_value_{PRIMARY_HORIZON}d_vs_{comparator}_usd"))
                    for row in rows
                    if as_float(
                        row.get(f"replacement_value_{PRIMARY_HORIZON}d_vs_{comparator}_usd")
                    )
                    is not None
                ]
            )
            for comparator in COMPARATORS
        },
        "positive_concentration": {
            comparator: positive_concentration(
                rows, f"replacement_value_{PRIMARY_HORIZON}d_vs_{comparator}_usd"
            )
            for comparator in COMPARATORS
        },
        "top_tickers": dict(Counter(row.get("ticker") for row in rows).most_common(8)),
        "sample_rows": [
            {
                "ticker": row.get("ticker"),
                "quote_date": row.get("quote_date"),
                "entry_date": row.get("entry_date"),
                "avg_historical_surprise_pct": row.get("avg_historical_surprise_pct"),
                "historical_surprise_count": row.get("historical_surprise_count"),
                "positive_surprise_count": row.get("positive_surprise_count"),
                "surprise_bucket": row.get("surprise_bucket"),
                "cash_10d": round_or_none(row.get("replacement_value_10d_vs_cash_usd"), 2),
                "spy_10d": round_or_none(row.get("replacement_value_10d_vs_spy_usd"), 2),
                "qqq_10d": round_or_none(row.get("replacement_value_10d_vs_qqq_usd"), 2),
            }
            for row in rows[:5]
        ],
    }


def group_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_bucket: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_bucket[str(row["surprise_bucket"])].append(row)

    summary = {bucket: summarize_group(by_bucket.get(bucket, [])) for bucket in BUCKETS}
    control_rows = by_bucket.get(WEAK_BUCKET, []) + by_bucket.get(MISSING_BUCKET, [])
    summary[CONTROL_GROUP] = summarize_group(control_rows)
    summary["all_joined"] = summarize_group(rows)
    return summary


def compare_positive_control(summary: Mapping[str, Any]) -> dict[str, Any]:
    positive = summary.get(POSITIVE_BUCKET, {})
    control = summary.get(CONTROL_GROUP, {})
    support: dict[str, Any] = {}
    for comparator in COMPARATORS:
        positive_metrics = (positive.get("replacement_metrics") or {}).get(comparator, {})
        control_metrics = (control.get("replacement_metrics") or {}).get(comparator, {})
        positive_mean = as_float(positive_metrics.get("mean"))
        control_mean = as_float(control_metrics.get("mean"))
        positive_median = as_float(positive_metrics.get("median"))
        control_median = as_float(control_metrics.get("median"))
        support[comparator] = {
            "positive_mean": round_or_none(positive_mean),
            "control_mean": round_or_none(control_mean),
            "mean_delta_positive_minus_control": (
                round(positive_mean - control_mean, 4)
                if positive_mean is not None and control_mean is not None
                else None
            ),
            "positive_median": round_or_none(positive_median),
            "control_median": round_or_none(control_median),
            "median_delta_positive_minus_control": (
                round(positive_median - control_median, 4)
                if positive_median is not None and control_median is not None
                else None
            ),
            "positive_beats_control_mean": (
                positive_mean > control_mean
                if positive_mean is not None and control_mean is not None
                else False
            ),
            "positive_beats_control_median": (
                positive_median > control_median
                if positive_median is not None and control_median is not None
                else False
            ),
        }
    return support


def acceptance(summary: Mapping[str, Any], support: Mapping[str, Any]) -> dict[str, Any]:
    positive = summary.get(POSITIVE_BUCKET, {})
    control = summary.get(CONTROL_GROUP, {})
    positive_metrics = positive.get("replacement_metrics") or {}
    positive_cash_mean = as_float((positive_metrics.get("cash") or {}).get("mean"))
    concentration_checks = {
        comparator: (positive.get("positive_concentration") or {}).get(comparator, {})
        for comparator in COMPARATORS
    }
    checks = {
        "positive_rows_gte_min": (
            positive.get("n") or 0
        ) >= ACCEPTANCE_RULE["min_positive_bucket_rows"],
        "control_rows_gte_min": (control.get("n") or 0) >= ACCEPTANCE_RULE["min_control_rows"],
        "positive_tickers_gte_min": (
            positive.get("ticker_count") or 0
        ) >= ACCEPTANCE_RULE["min_positive_bucket_tickers"],
        "control_tickers_gte_min": (
            control.get("ticker_count") or 0
        ) >= ACCEPTANCE_RULE["min_control_tickers"],
        "positive_cash_mean_gt_zero": (
            positive_cash_mean > 0.0 if positive_cash_mean is not None else False
        ),
        "positive_beats_control_all_means": all(
            bool(support[comparator]["positive_beats_control_mean"])
            for comparator in COMPARATORS
        ),
        "positive_beats_control_all_medians": all(
            bool(support[comparator]["positive_beats_control_median"])
            for comparator in COMPARATORS
        ),
        "positive_concentration_guardrail": all(
            bool(concentration_checks[comparator].get("passes_guardrail"))
            for comparator in COMPARATORS
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "accepted_observed_only_lead": not failed,
        "checks": checks,
        "failed_reasons": failed,
        "concentration_checks": concentration_checks,
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_summary(BASELINE_RESULT)
    outcome_rows = read_jsonl(OUTCOME_LEDGER)
    snapshot_index = load_earnings_snapshots()
    enriched, coverage = enrich_rows(outcome_rows, snapshot_index)
    groups = group_summary(enriched)
    support = compare_positive_control(groups)
    accepted = acceptance(groups, support)
    observed_only_lead = bool(accepted["accepted_observed_only_lead"])
    decision = (
        "observed_only_positive_options_earnings_surprise_history_lead"
        if observed_only_lead
        else "observed_only_rejected"
    )

    before_metrics = baseline
    after_metrics = {**baseline, "strategy_identity_unchanged": True}
    delta_metrics = {
        "aggregate_expected_value_score_delta": 0.0,
        "aggregate_total_pnl_delta": 0.0,
        "aggregate_trade_count_delta": 0,
        "strategy_behavior_changed": False,
    }
    primary_summary = {
        "settled_quality_rows": coverage.get("quality_closed_10d_rows", 0),
        "joined_rows": coverage.get("joined_rows", 0),
        "join_rate_on_quality_rows": coverage.get("join_rate_on_quality_rows"),
        "buckets": groups,
        "positive_vs_control_support": support,
        "acceptance": accepted,
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only",
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_forward_attribution_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": ticket.get("prediction") or DEFAULT_PREDICTION,
        "calibration": {
            "pre_run_success_probability": (
                ticket.get("prediction") or DEFAULT_PREDICTION
            ).get("success_probability"),
            "post_run_success": observed_only_lead,
            "surprise_note": (
                "Positive surprise-history options rows beat weak/missing controls."
                if observed_only_lead
                else "Fixed surprise-history buckets did not meet the predeclared lead bar."
            ),
        },
        "pre_run_questions": {
            "alpha_hypothesis": HYPOTHESIS,
            "category": "candidate pool / risk allocation context",
            "similar_prior": {
                "experiments": NEARBY_PRIOR_EXPERIMENTS,
                "novelty_result": (ticket.get("novelty") or {}).get("nearest"),
                "reason_not_repeat": NEW_EVIDENCE_AXIS,
            },
            "single_policy_bundle": CAUSAL_COMPONENTS,
            "success_criteria": ACCEPTANCE_RULE,
            "reproducibility": [
                RUNNER_COMMAND,
                ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            ],
        },
        "parameters": {
            "primary_horizon": PRIMARY_HORIZON,
            "comparators": list(COMPARATORS),
            "buckets": list(BUCKETS),
            "control_group": CONTROL_GROUP,
            "require_outcome_status": "closed_10d_forward",
            "require_quality_pass": True,
            "snapshot_join": ACCEPTANCE_RULE["snapshot_join"],
            "no_options_demand_thresholds": True,
            "no_event_distance_thresholds": True,
            "no_strategy_behavior_change": True,
        },
        "source_summary": {
            "outcome_ledger": repo_rel(OUTCOME_LEDGER),
            "baseline_result": repo_rel(BASELINE_RESULT),
            "earnings_snapshot_dir": repo_rel(EARNINGS_SNAPSHOT_DIR),
            "coverage": coverage,
        },
        "primary_summary": primary_summary,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "gate1": {
            "passed": baseline["exists"] and baseline["window_count"] == 3,
            "baseline_result": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": coverage.get("quality_rows_with_entry_date", 0) > 0
            and coverage.get("quality_rows_with_all_10d_replacements", 0) > 0
            and coverage.get("joined_rows", 0) > 0,
            "dependency_fields": [
                "ticker",
                "quote_date",
                "entry_date",
                "entry_price",
                "quality_pass",
                "outcome_status",
                "replacement_value_10d_vs_cash_usd",
                "replacement_value_10d_vs_spy_usd",
                "replacement_value_10d_vs_qqq_usd",
                "earnings.historical_surprise_pct",
                "earnings.avg_historical_surprise_pct",
            ],
            "field_coverage": coverage,
            "target_price_note": (
                "target_price is not used for this fixed-horizon "
                "replacement-value ledger; entry_price and replacement-value "
                "fields are present instead."
            ),
        },
        "gate3": {
            "passed": coverage.get("quality_closed_10d_rows", 0)
            >= math.ceil(max(coverage.get("closed_10d_rows", 0), 1) * 0.05),
            "signals_generated": coverage.get("closed_10d_rows", 0),
            "signals_survived": coverage.get("quality_closed_10d_rows", 0),
            "survival_rate": (
                round(
                    coverage.get("quality_closed_10d_rows", 0)
                    / coverage.get("closed_10d_rows", 1),
                    6,
                )
                if coverage.get("closed_10d_rows", 0)
                else None
            ),
            "joined_attribution_rows": coverage.get("joined_rows", 0),
            "join_rate_on_quality_rows": coverage.get("join_rate_on_quality_rows"),
            "note": (
                "This is an observed-only attribution, not an executable "
                "survival-filter change."
            ),
        },
        "gate4": {
            "passed": observed_only_lead,
            "strategy_gate4_not_applicable": True,
            "reason": (
                "Observed-only lead bar passed; no strategy change accepted."
                if observed_only_lead
                else "Observed-only surprise-history lead bar failed; no strategy change accepted."
            ),
            "acceptance_rule": ACCEPTANCE_RULE,
            "acceptance": accepted,
            "failed_reasons": accepted["failed_reasons"],
            "before_after_delta": delta_metrics,
            "no_strategy_behavior_change": True,
        },
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "The consistently positive surprise-history bucket beat the "
                "weak/missing control on the predeclared support metrics with "
                "enough breadth."
                if observed_only_lead
                else "The fixed surprise-history join produced usable rows, "
                "but the positive bucket did not satisfy all sample, breadth, "
                "outperformance, and concentration checks versus the weak/"
                "missing control."
            ),
            "decision_basis": decision,
            "forbidden_near_neighbor_retry": (
                "Do not retune avg_historical_surprise_pct, positive-count, "
                "history-count, missing-history, options demand, event-distance, "
                "IV/OI/spread/liquidity, top-N, hold days, notional, cooldown, "
                "or response-curve thresholds on the same exp-20260630-008 "
                "options ledger."
            ),
            "new_evidence_required": (
                "Valid next evidence requires materially more closed options "
                "forward rows under the unchanged surprise-history contract, "
                "historical PIT options-chain coverage across canonical windows, "
                "borrow/loan cost context, or richer earnings-event fields such "
                "as guidance direction, same-event revenue/EPS mix, revisions, "
                "or call tone."
            ),
        },
        "related_files": [
            repo_rel(OUTCOME_LEDGER),
            repo_rel(EARNINGS_SNAPSHOT_DIR),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }
    return payload


def compact_log(payload: Mapping[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "pre_run_questions",
        "parameters",
        "source_summary",
        "primary_summary",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: Mapping[str, Any]) -> str:
    primary = payload["primary_summary"]
    buckets = primary["buckets"]
    support = primary["positive_vs_control_support"]
    rows = [
        "| Bucket | Rows | Tickers | Dates | Avg surprise | Mean cash | Mean SPY | Mean QQQ | Median cash |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in [*BUCKETS, CONTROL_GROUP]:
        item = buckets[bucket]
        metrics = item["replacement_metrics"]
        rows.append(
            "| {bucket} | {n} | {tickers} | {dates} | {avg} | {cash} | {spy} | {qqq} | {median} |".format(
                bucket=bucket,
                n=item["n"],
                tickers=item["ticker_count"],
                dates=item["entry_date_count"],
                avg=item["avg_historical_surprise_pct"]["mean"],
                cash=money(metrics["cash"]["mean"]),
                spy=money(metrics["spy"]["mean"]),
                qqq=money(metrics["qqq"]["mean"]),
                median=money(metrics["cash"]["median"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: options earnings surprise-history forward value",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            "- Accepted alpha: `false`",
            f"- Observed-only lead: `{str(payload['observed_only_lead']).lower()}`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Primary 10d Buckets",
            "",
            *rows,
            "",
            "## Positive Minus Weak/Missing Control",
            "",
            f"- Cash mean: `{money(support['cash']['mean_delta_positive_minus_control'])}`; "
            f"median: `{money(support['cash']['median_delta_positive_minus_control'])}`",
            f"- SPY mean: `{money(support['spy']['mean_delta_positive_minus_control'])}`; "
            f"median: `{money(support['spy']['median_delta_positive_minus_control'])}`",
            f"- QQQ mean: `{money(support['qqq']['mean_delta_positive_minus_control'])}`; "
            f"median: `{money(support['qqq']['median_delta_positive_minus_control'])}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
        OUTCOME_LEDGER,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "earnings_snapshot_dir": {
            "path": repo_rel(EARNINGS_SNAPSHOT_DIR),
            "file_count": payload["source_summary"]["coverage"].get(
                "earnings_snapshot_file_count"
            ),
            "first_snapshot_date": payload["source_summary"]["coverage"].get(
                "first_snapshot_date"
            ),
            "last_snapshot_date": payload["source_summary"]["coverage"].get(
                "last_snapshot_date"
            ),
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log(payload)
    save_experiment_log_entry(log_record, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
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
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    ticket_before = payload.get("ticket_before") or {}
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
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "hub_identity": ticket_before.get("hub_identity"),
            "novelty": ticket_before.get("novelty"),
            "claimed_at": ticket_before.get("claimed_at"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    buckets = payload["primary_summary"]["buckets"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "quality_10d_rows": payload["primary_summary"]["settled_quality_rows"],
                "joined_rows": payload["primary_summary"]["joined_rows"],
                "positive_rows": buckets[POSITIVE_BUCKET]["n"],
                "control_rows": buckets[CONTROL_GROUP]["n"],
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
