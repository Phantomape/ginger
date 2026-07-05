"""exp-20260704-002: options earnings event-distance forward attribution.

Observed-only alpha search. This joins the refreshed exp-20260630-008
OnclickMedia options forward outcome ledger to daily earnings snapshots and
tests one fixed risk-allocation context: quality options rows entered within
0-30 calendar days of the next scheduled earnings date should show weaker
settled 10-day cash/SPY/QQQ replacement value than rows more than 60 days away.

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


EXPERIMENT_ID = "exp-20260704-002"
OWNER = "alpha-explore"
SLUG = "options_earnings_event_distance_forward_value"
RUNNER = f"quant/experiments/exp_20260704_002_{SLUG}.py"
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
OUT_JSON = DATA_DIR / f"exp_20260704_002_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "OnclickMedia options forward rows joined to daily earnings snapshots may "
    "show that near-earnings option demand carries weaker 10-day cash/SPY/QQQ "
    "replacement value than ordinary far-from-event quality options rows, "
    "making event distance a future risk-allocation context."
)
CHANGE_TYPE = "observed_only_forward_attribution"
MECHANISM_FAMILY = "production_visible_forward_options_attribution"
TRIAL_FAMILY = "onclickmedia_options_earnings_event_distance_forward_value"
TRIAL_VARIANT_ID = "fixed_quality_event_distance_0_30_31_60_gt60_v1"
CHANGED_VARIABLE = "onclickmedia_options_earnings_event_distance_forward_value_v1"
NEW_EVIDENCE_TYPE = "new_event_distance_field"
NEW_EVIDENCE_AXIS = (
    "Daily earnings snapshots add a fixed PIT event-distance field to the "
    "exp-20260630-008 closed options ledger. This is not a put/call, IV, open "
    "interest, moneyness, spread, liquidity, top-N, hold, cooldown, notional, "
    "or response-curve retry on the rejected options demand family."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260630-008",
    "exp-20260630-010",
    "exp-20260702-007",
]
CAUSAL_COMPONENTS = [
    "closed options outcome ledger",
    "daily earnings snapshot join",
    "event-distance buckets",
    "cash SPY QQQ replacement-value attribution",
    "no strategy behavior change",
]

PRIMARY_HORIZON = 10
COMPARATORS = ["cash", "spy", "qqq"]
REPLACEMENT_KEYS = {
    "cash": f"replacement_value_{PRIMARY_HORIZON}d_vs_cash_usd",
    "spy": f"replacement_value_{PRIMARY_HORIZON}d_vs_spy_usd",
    "qqq": f"replacement_value_{PRIMARY_HORIZON}d_vs_qqq_usd",
}
EVENT_BUCKETS = [
    {
        "name": "near_event_0_30",
        "min_days": 0,
        "max_days": 30,
        "description": "0 to 30 calendar days before next scheduled earnings",
    },
    {
        "name": "mid_event_31_60",
        "min_days": 31,
        "max_days": 60,
        "description": "31 to 60 calendar days before next scheduled earnings",
    },
    {
        "name": "far_event_gt60",
        "min_days": 61,
        "max_days": None,
        "description": "More than 60 calendar days before next scheduled earnings",
    },
]
NEAR_BUCKET = "near_event_0_30"
FAR_BUCKET = "far_event_gt60"

ACCEPTANCE_RULE = {
    "primary_horizon": PRIMARY_HORIZON,
    "event_buckets": EVENT_BUCKETS,
    "min_near_rows": 100,
    "min_far_rows": 100,
    "min_near_tickers": 20,
    "min_far_tickers": 20,
    "near_must_underperform_far_median_for": COMPARATORS,
    "near_must_underperform_far_mean_count_gte": 2,
    "max_single_negative_loss_share_guardrail": 0.50,
    "negative_loss_hhi_guardrail": 0.35,
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
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260704-002/",
    "experiments/cards/exp-20260704-002.md",
    "experiments/manifests/exp-20260704-002.json",
    "experiments/tickets/exp-20260704-002.json",
    "experiments/logs/exp-20260704-002.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
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
    except OSError:
        pass
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


def concentration(values: list[float]) -> dict[str, Any]:
    losses = [abs(value) for value in values if value < 0 and math.isfinite(value)]
    total_loss = sum(losses)
    if total_loss <= 0:
        return {
            "negative_count": 0,
            "negative_loss_sum_abs": 0.0,
            "max_single_negative_loss_share": 0.0,
            "negative_loss_hhi": 0.0,
            "passes_guardrail": True,
        }
    shares = [loss / total_loss for loss in losses]
    return {
        "negative_count": len(losses),
        "negative_loss_sum_abs": round(total_loss, 4),
        "max_single_negative_loss_share": round(max(shares), 6),
        "negative_loss_hhi": round(sum(share * share for share in shares), 6),
        "passes_guardrail": (
            max(shares) <= ACCEPTANCE_RULE["max_single_negative_loss_share_guardrail"]
            and sum(share * share for share in shares)
            <= ACCEPTANCE_RULE["negative_loss_hhi_guardrail"]
        ),
    }


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
            **concentration([]),
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
        **concentration(clean),
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


def days_to_next_earnings(snapshot_item: Mapping[str, Any], quote_date: date) -> int | None:
    next_date = parse_date(snapshot_item.get("next_earnings_date"))
    if next_date is not None:
        days = (next_date - quote_date).days
        return days if days >= 0 else None
    days = as_int(snapshot_item.get("days_to_earnings"))
    return days if days is not None and days >= 0 else None


def event_bucket(days_to_earnings: int | None) -> str | None:
    if days_to_earnings is None:
        return None
    for bucket in EVENT_BUCKETS:
        if days_to_earnings < bucket["min_days"]:
            continue
        max_days = bucket["max_days"]
        if max_days is None or days_to_earnings <= max_days:
            return str(bucket["name"])
    return None


def enrich_rows(rows: Iterable[Mapping[str, Any]], snapshot_index: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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

        days = days_to_next_earnings(snapshot_item, quote_date)
        bucket = event_bucket(days)
        if days is None or bucket is None:
            counters["quality_rows_without_days_to_earnings"] += 1
            continue

        counters["joined_rows"] += 1
        counters[f"bucket_{bucket}"] += 1
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
                "days_to_next_earnings": days,
                "event_bucket": bucket,
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
            "missing_join_examples": missing_examples,
        }
    )
    return enriched, coverage


def group_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_bucket: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_bucket[str(row["event_bucket"])].append(row)

    summary: dict[str, Any] = {}
    for bucket in [item["name"] for item in EVENT_BUCKETS]:
        bucket_rows = by_bucket.get(str(bucket), [])
        days = [as_float(row.get("days_to_next_earnings")) for row in bucket_rows]
        clean_days = [value for value in days if value is not None]
        entry_dates = {row.get("entry_date") for row in bucket_rows if row.get("entry_date")}
        quote_dates = {row.get("quote_date") for row in bucket_rows if row.get("quote_date")}
        tickers = {row.get("ticker") for row in bucket_rows if row.get("ticker")}
        summary[str(bucket)] = {
            "n": len(bucket_rows),
            "ticker_count": len(tickers),
            "entry_date_count": len(entry_dates),
            "quote_date_count": len(quote_dates),
            "days_to_next_earnings": {
                "min": round_or_none(min(clean_days) if clean_days else None),
                "max": round_or_none(max(clean_days) if clean_days else None),
                "mean": round_or_none(mean(clean_days) if clean_days else None),
                "median": round_or_none(median(clean_days) if clean_days else None),
            },
            "replacement_metrics": {
                comparator: metric_stats(
                    [
                        as_float(
                            row.get(
                                f"replacement_value_{PRIMARY_HORIZON}d_vs_{comparator}_usd"
                            )
                        )
                        for row in bucket_rows
                        if as_float(
                            row.get(
                                f"replacement_value_{PRIMARY_HORIZON}d_vs_{comparator}_usd"
                            )
                        )
                        is not None
                    ]
                )
                for comparator in COMPARATORS
            },
            "top_tickers": dict(Counter(row.get("ticker") for row in bucket_rows).most_common(8)),
            "sample_rows": [
                {
                    "ticker": row.get("ticker"),
                    "quote_date": row.get("quote_date"),
                    "entry_date": row.get("entry_date"),
                    "days_to_next_earnings": row.get("days_to_next_earnings"),
                    "event_bucket": row.get("event_bucket"),
                    "cash_10d": round_or_none(row.get("replacement_value_10d_vs_cash_usd"), 2),
                    "spy_10d": round_or_none(row.get("replacement_value_10d_vs_spy_usd"), 2),
                    "qqq_10d": round_or_none(row.get("replacement_value_10d_vs_qqq_usd"), 2),
                }
                for row in bucket_rows[:5]
            ],
        }
    return summary


def compare_near_far(summary: Mapping[str, Any]) -> dict[str, Any]:
    near = summary.get(NEAR_BUCKET, {})
    far = summary.get(FAR_BUCKET, {})
    support: dict[str, Any] = {}
    for comparator in COMPARATORS:
        near_metrics = (near.get("replacement_metrics") or {}).get(comparator, {})
        far_metrics = (far.get("replacement_metrics") or {}).get(comparator, {})
        near_mean = as_float(near_metrics.get("mean"))
        far_mean = as_float(far_metrics.get("mean"))
        near_median = as_float(near_metrics.get("median"))
        far_median = as_float(far_metrics.get("median"))
        support[comparator] = {
            "near_mean": round_or_none(near_mean),
            "far_mean": round_or_none(far_mean),
            "mean_delta_near_minus_far": (
                round(near_mean - far_mean, 4)
                if near_mean is not None and far_mean is not None
                else None
            ),
            "near_median": round_or_none(near_median),
            "far_median": round_or_none(far_median),
            "median_delta_near_minus_far": (
                round(near_median - far_median, 4)
                if near_median is not None and far_median is not None
                else None
            ),
            "near_underperforms_far_mean": (
                near_mean < far_mean if near_mean is not None and far_mean is not None else False
            ),
            "near_underperforms_far_median": (
                near_median < far_median
                if near_median is not None and far_median is not None
                else False
            ),
        }
    return support


def acceptance(summary: Mapping[str, Any], support: Mapping[str, Any]) -> dict[str, Any]:
    near = summary.get(NEAR_BUCKET, {})
    far = summary.get(FAR_BUCKET, {})
    near_metrics = near.get("replacement_metrics") or {}
    concentration_checks = {
        comparator: {
            "max_single_negative_loss_share": (
                near_metrics.get(comparator, {}).get("max_single_negative_loss_share")
            ),
            "negative_loss_hhi": near_metrics.get(comparator, {}).get("negative_loss_hhi"),
            "passes_guardrail": near_metrics.get(comparator, {}).get("passes_guardrail"),
        }
        for comparator in COMPARATORS
    }
    checks = {
        "near_rows_gte_min": (near.get("n") or 0) >= ACCEPTANCE_RULE["min_near_rows"],
        "far_rows_gte_min": (far.get("n") or 0) >= ACCEPTANCE_RULE["min_far_rows"],
        "near_tickers_gte_min": (
            near.get("ticker_count") or 0
        ) >= ACCEPTANCE_RULE["min_near_tickers"],
        "far_tickers_gte_min": (
            far.get("ticker_count") or 0
        ) >= ACCEPTANCE_RULE["min_far_tickers"],
        "near_underperforms_far_all_medians": all(
            bool(support[comparator]["near_underperforms_far_median"])
            for comparator in COMPARATORS
        ),
        "near_underperforms_far_at_least_2_means": sum(
            1
            for comparator in COMPARATORS
            if bool(support[comparator]["near_underperforms_far_mean"])
        )
        >= ACCEPTANCE_RULE["near_must_underperform_far_mean_count_gte"],
        "near_loss_concentration_guardrail": all(
            bool(concentration_checks[comparator]["passes_guardrail"])
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
    support = compare_near_far(groups)
    accepted = acceptance(groups, support)
    observed_only_lead = bool(accepted["accepted_observed_only_lead"])
    decision = (
        "observed_only_positive_options_earnings_event_distance_lead"
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
        "near_vs_far_support": support,
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
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": ticket.get(
            "prediction",
            {
                "success_probability": 0.28,
                "expected_ev_delta": None,
                "expected_pnl_delta": None,
                "main_failure_modes": [
                    "no_monotonic_event_distance_edge",
                    "event_proximity_sample_too_thin",
                    "earnings_snapshot_join_sparse",
                    "options_quality_noise_dominates",
                ],
                "confidence_reason": (
                    "The options demand edge failed on prior closed rows, but "
                    "daily earnings snapshots create a new event-distance axis."
                ),
            },
        ),
        "calibration": {
            "pre_run_success_probability": (
                ticket.get("prediction") or {}
            ).get("success_probability", 0.28),
            "post_run_success": observed_only_lead,
            "surprise_note": (
                "Event distance separated near and far quality options rows."
                if observed_only_lead
                else "Fixed event-distance buckets did not meet the predeclared lead bar."
            ),
        },
        "pre_run_questions": {
            "alpha_hypothesis": HYPOTHESIS,
            "category": "risk allocation / candidate-pool context",
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
            "comparators": COMPARATORS,
            "event_buckets": EVENT_BUCKETS,
            "require_outcome_status": "closed_10d_forward",
            "require_quality_pass": True,
            "snapshot_join": "latest earnings snapshot with snapshot_date <= quote_date",
            "days_to_earnings": "recomputed as next_earnings_date - quote_date when available",
            "no_options_demand_thresholds": True,
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
                "earnings.next_earnings_date",
                "earnings.days_to_earnings",
            ],
            "field_coverage": coverage,
            "target_price_note": (
                "target_price is not used or present for this fixed-horizon "
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
                else "Observed-only event-distance lead bar failed; no strategy change accepted."
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
                "Near-event quality options rows underperformed far-event rows "
                "on the predeclared support metrics with enough breadth."
                if observed_only_lead
                else "The event-distance join produced usable rows, but the "
                "fixed near-vs-far separation did not satisfy the predeclared "
                "sample, direction, and concentration checks."
            ),
            "decision_basis": decision,
            "forbidden_near_neighbor_retry": (
                "Do not retune the 0-30/31-60/>60 day buckets, quote-vs-entry "
                "date join, options demand thresholds, IV/OI/spread/liquidity "
                "cuts, top-N, hold days, notional, cooldown, or response curves "
                "on the same exp-20260630-008 options ledger."
            ),
            "new_evidence_required": (
                "Valid next evidence requires materially more closed options "
                "forward rows carrying the unchanged event-distance field, "
                "historical PIT options-chain coverage across canonical windows, "
                "borrow/loan cost context, or a genuinely different production "
                "event/cost field."
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
    support = primary["near_vs_far_support"]
    rows = [
        "| Bucket | Rows | Tickers | Dates | Mean cash | Mean SPY | Mean QQQ | Median cash |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in [item["name"] for item in EVENT_BUCKETS]:
        item = buckets[bucket]
        metrics = item["replacement_metrics"]
        rows.append(
            "| {bucket} | {n} | {tickers} | {dates} | {cash} | {spy} | {qqq} | {median} |".format(
                bucket=bucket,
                n=item["n"],
                tickers=item["ticker_count"],
                dates=item["entry_date_count"],
                cash=money(metrics["cash"]["mean"]),
                spy=money(metrics["spy"]["mean"]),
                qqq=money(metrics["qqq"]["mean"]),
                median=money(metrics["cash"]["median"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: options earnings event-distance forward value",
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
            "## Near Minus Far Deltas",
            "",
            f"- Cash mean: `{money(support['cash']['mean_delta_near_minus_far'])}`; "
            f"median: `{money(support['cash']['median_delta_near_minus_far'])}`",
            f"- SPY mean: `{money(support['spy']['mean_delta_near_minus_far'])}`; "
            f"median: `{money(support['spy']['median_delta_near_minus_far'])}`",
            f"- QQQ mean: `{money(support['qqq']['mean_delta_near_minus_far'])}`; "
            f"median: `{money(support['qqq']['median_delta_near_minus_far'])}`",
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
            "single_causal_variable": CHANGED_VARIABLE,
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
                "near_rows": buckets[NEAR_BUCKET]["n"],
                "far_rows": buckets[FAR_BUCKET]["n"],
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
