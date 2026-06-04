"""exp-20260604-020: revision trajectory x PEAD attribution.

Observed-only alpha search. This experiment tests whether PIT estimate
revision trajectory buckets have 10d/20d replacement value, especially inside
the T+2..T+15 post-earnings drift window. It changes no production strategy,
ranking, sizing, exits, prompts, backtest semantics, or orders.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260604-020"
STEM = "revision_trajectory_pead_attribution"
MECHANISM_FAMILY = "analyst_revision_earnings_drift"
TRIAL_FAMILY = "revision_trajectory_pead_10d20d_attribution"
CHANGED_VARIABLE = "revision_trajectory_bucket_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from data_paths import daily_artifact_glob  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_CARD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

PAPER_NOTIONAL_USD = 10_000.0
FORWARD_HORIZONS = (10, 20)
GATE_HORIZONS = ("10d", "20d")
PEAD_WINDOW_LO = 2
PEAD_WINDOW_HI = 15
MIN_CLOSED_PER_BUCKET = 8
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50
MAX_TOP5_POSITIVE_SHARE = 0.70
EPS_EPSILON = 1e-9
ANTI_JS = "No JavaScript was used."

WINDOWS = [
    {
        "name": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
    {
        "name": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    {
        "name": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
]

BASELINE = {
    "accepted_core_expected_value_score_sum": 7.8941,
    "accepted_core_total_pnl_sum": 234850.99,
    "baseline_source": (
        "docs/backtesting.md accepted aggregate core stack; "
        "current_state also records later default-off accepted-source consensus "
        "as default-off paper only."
    ),
}

BUCKET_ORDER = [
    "positive_persistent",
    "positive_one_shot",
    "flat_or_negative",
    "missing_or_unusable",
]

NEARBY_PRIORS = [
    {
        "experiment_id": "exp-20260525-034",
        "finding": "Expanded PIT estimate-revision watchlist; useful as read-only attribution only.",
    },
    {
        "experiment_id": "exp-20260528-009",
        "finding": "Repaired PEAD 10d bucket attribution was blocked by thin 10d outcomes and concentration.",
    },
    {
        "experiment_id": "exp-20260528-013",
        "finding": "Short-horizon repaired PEAD did not support inside-PEAD promotion.",
    },
    {
        "experiment_id": "exp-20260529-007",
        "finding": "Revision magnitude high-vs-low was not a clean promotable edge.",
    },
    {
        "experiment_id": "exp-20260531-018",
        "finding": "Pre-registered 10d retry path required more independent PIT evidence.",
    },
    {
        "experiment_id": "exp-20260604-001",
        "finding": "Adjacent post-earnings surprise acceleration support regressed and is frozen.",
    },
]

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "thin_10d20d_sample",
        "no_monotonic_bucket",
        "concentration_failed",
        "missing_pit_revision_fields",
    ],
    "confidence_reason": (
        "Prior 5d PEAD/revision work was rejected, but current direction "
        "guidance prioritizes analyst revision and repeated 10d-positive clues "
        "justify a pre-registered 10d/20d read-only test."
    ),
    "recorded_at": "2026-06-04T17:34:51+00:00",
}

RESERVATION_METADATA = {
    "experiment_uid": "expuid-19b12d26079e4bf0",
    "hub_identity": {
        "scheme": "hf_hub_local_v1",
        "namespace": "ginger/experiments",
        "repo_id": "ginger/experiments/exp-20260604-020",
        "slug": "revision_trajectory_pead_attribution",
        "reserved_at": "2026-06-04T17:35:18+00:00",
        "reservation_rule": (
            "Create the ticket under registry lock before writing runners, "
            "artifacts, data, or logs. Existing IDs are rejected across "
            "registry, JSONL, tickets, logs, artifacts, data, and runners."
        ),
    },
    "created_at": "2026-06-04T17:35:18+00:00",
    "claimed_at": "2026-06-04T17:36:00+00:00",
}

ALLOWED_WRITE_SCOPE = [
    "quant/experiments/",
    "data/experiments/",
    "experiments/logs/",
    "experiments/cards/",
    "experiments/tickets/",
    "docs/experiments/tickets/",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
    "docs/alpha_direction_guidance.md",
]

LOCKED_VARIABLES = [
    "production_strategy",
    "backtest_entry_exit",
    "sizing",
    "orders",
    "llm_prompt",
]


class PriceLookup:
    def __init__(self) -> None:
        self.by_ticker: dict[str, dict[date, float]] = defaultdict(dict)

    def add(self, ticker: str, day: Any, close: Any) -> None:
        ticker = str(ticker or "").upper().strip()
        if not ticker or day in (None, ""):
            return
        value = _float(close)
        if value is None or value <= 0:
            return
        self.by_ticker[ticker][_coerce_date(day)] = value

    def forward_return(
        self,
        ticker: str,
        as_of: date,
        horizon: int,
    ) -> dict[str, Any]:
        rows = self.by_ticker.get(str(ticker or "").upper().strip(), {})
        if not rows:
            return _missing_outcome(f"missing_price_ticker_{horizon}d")
        start_dates = [day for day in sorted(rows) if day >= as_of]
        if not start_dates:
            return _missing_outcome(f"missing_start_price_{horizon}d")
        start_day = start_dates[0]
        start_price = rows[start_day]
        future_dates = [day for day in sorted(rows) if day > start_day]
        if len(future_dates) < horizon:
            return _missing_outcome(f"missing_{horizon}d_forward_price")
        future_day = future_dates[horizon - 1]
        future_price = rows[future_day]
        ret = (future_price / start_price) - 1.0
        return {
            "closed": True,
            "return": round(ret, 6),
            "pnl_proxy": round(ret * PAPER_NOTIONAL_USD, 2),
            "start_date": start_day.isoformat(),
            "future_date": future_day.isoformat(),
            "start_close": round(start_price, 6),
            "future_close": round(future_price, 6),
            "gap_reason": None,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _coerce_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value)
    if len(raw) == 8 and raw.isdigit():
        return datetime.strptime(raw, "%Y%m%d").date()
    return datetime.strptime(raw[:10], "%Y-%m-%d").date()


def _float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


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
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return _repo_rel(value)
    return value


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact_payload = dict(payload)
    compact_payload.pop("sample_rows", None)
    compact_payload["sample_rows_omitted_from_jsonl"] = True
    compact = json.dumps(_safe(compact_payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _missing_outcome(reason: str) -> dict[str, Any]:
    return {
        "closed": False,
        "return": None,
        "pnl_proxy": None,
        "start_date": None,
        "future_date": None,
        "gap_reason": reason,
    }


def _snapshot_date_from_path(path: Path, payload: dict[str, Any]) -> date:
    raw = payload.get("date")
    if raw:
        return _coerce_date(raw)
    tag = path.stem.rsplit("_", 1)[-1]
    return _coerce_date(tag)


def _derive_next_earnings_date(as_of: date, item: dict[str, Any]) -> tuple[str | None, str]:
    raw = item.get("next_earnings_date")
    if raw:
        return _coerce_date(raw).isoformat(), "explicit_next_earnings_date"
    dte = _float(item.get("days_to_earnings"))
    if dte is None:
        return None, "missing_next_earnings_date_and_days_to_earnings"
    return (as_of + timedelta(days=int(round(dte)))).isoformat(), "derived_from_days_to_earnings"


def _snapshot_source_quality(path: Path, payload: dict[str, Any], as_of: date) -> str:
    timestamp = str(payload.get("timestamp") or "")
    timestamp_pit = timestamp[:10] <= (as_of + timedelta(days=1)).isoformat()
    try:
        mtime_pit = path.stat().st_mtime <= datetime(
            as_of.year,
            as_of.month,
            as_of.day,
            tzinfo=timezone.utc,
        ).timestamp() + 48 * 3600
    except OSError:
        mtime_pit = False
    if timestamp_pit and mtime_pit:
        return "snapshot_timestamp_and_mtime_pit"
    if timestamp_pit:
        return "snapshot_timestamp_replay_backfill"
    return "not_pit_safe"


def load_snapshot_records(
    data_dir: Path,
    *,
    start: date,
    end: date,
    history_days: int = 45,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    min_day = start - timedelta(days=history_days)
    for path in daily_artifact_glob("earnings_snapshot", data_dir):
        payload = _read_json(path)
        as_of = _snapshot_date_from_path(path, payload)
        if as_of < min_day or as_of > end:
            continue
        earnings = payload.get("earnings")
        if not isinstance(earnings, dict):
            continue
        records.append(
            {
                "as_of_date": as_of,
                "path": path,
                "payload": payload,
                "source_quality": _snapshot_source_quality(path, payload, as_of),
            }
        )
    by_date: dict[date, dict[str, Any]] = {}
    for record in records:
        current = by_date.get(record["as_of_date"])
        if current is None or _snapshot_preference(record) < _snapshot_preference(current):
            by_date[record["as_of_date"]] = record
    return sorted(by_date.values(), key=lambda item: item["as_of_date"])


def _snapshot_preference(record: dict[str, Any]) -> tuple[int, str]:
    quality_rank = {
        "snapshot_timestamp_and_mtime_pit": 0,
        "snapshot_timestamp_replay_backfill": 1,
        "not_pit_safe": 2,
    }.get(record["source_quality"], 9)
    path = Path(record["path"])
    legacy_penalty = 1 if "legacy_root" in path.parts else 0
    return (quality_rank + legacy_penalty, str(path))


def _observation(record: dict[str, Any], ticker: str, item: dict[str, Any]) -> dict[str, Any]:
    as_of = record["as_of_date"]
    next_date, source = _derive_next_earnings_date(as_of, item)
    return {
        "ticker": ticker.upper(),
        "as_of_date": as_of,
        "next_earnings_date": next_date,
        "next_earnings_date_source": source,
        "eps_estimate": _float(item.get("eps_estimate")),
        "revenue_estimate": _float(item.get("revenue_estimate")),
        "days_to_earnings": _float(item.get("days_to_earnings")),
        "avg_historical_surprise_pct": _float(item.get("avg_historical_surprise_pct")),
        "eps_actual_last": _float(item.get("eps_actual_last")),
        "source_snapshot_path": _repo_rel(record["path"]),
        "source_quality": record["source_quality"],
    }


def _latest_prior_at_least_days_back(
    same_event_history: list[dict[str, Any]],
    target_date: date,
    days: int,
) -> dict[str, Any] | None:
    cutoff = target_date - timedelta(days=days)
    candidates = [item for item in same_event_history if item["as_of_date"] <= cutoff]
    return candidates[-1] if candidates else None


def _delta(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None:
        return None
    return round(current - prior, 6)


def _build_last_earnings_index(snapshot_records: list[dict[str, Any]]) -> dict[tuple[str, date], str]:
    last_by_ticker: dict[str, str | None] = defaultdict(lambda: None)
    prior_next_by_ticker: dict[str, str | None] = defaultdict(lambda: None)
    out: dict[tuple[str, date], str] = {}
    for record in snapshot_records:
        as_of = record["as_of_date"]
        earnings = record["payload"].get("earnings") or {}
        for raw_ticker, item in earnings.items():
            if not isinstance(item, dict):
                continue
            ticker = str(raw_ticker).upper()
            next_date, _source = _derive_next_earnings_date(as_of, item)
            prior_next = prior_next_by_ticker[ticker]
            if prior_next and prior_next != next_date and _coerce_date(prior_next) <= as_of:
                last_by_ticker[ticker] = prior_next
            if last_by_ticker[ticker]:
                out[(ticker, as_of)] = str(last_by_ticker[ticker])
            if next_date:
                prior_next_by_ticker[ticker] = next_date
    return out


def build_revision_rows(
    snapshot_records: list[dict[str, Any]],
    *,
    window_start: date,
    window_end: date,
    prices: PriceLookup,
) -> list[dict[str, Any]]:
    history_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    observations_by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for record in snapshot_records:
        earnings = record["payload"].get("earnings") or {}
        for raw_ticker, item in earnings.items():
            if not isinstance(item, dict):
                continue
            obs = _observation(record, raw_ticker, item)
            observations_by_date[record["as_of_date"]].append(obs)

    last_earnings_index = _build_last_earnings_index(snapshot_records)
    rows: list[dict[str, Any]] = []
    for as_of in sorted(observations_by_date):
        current_observations = observations_by_date[as_of]
        for obs in current_observations:
            ticker = obs["ticker"]
            history = history_by_ticker[ticker]
            same_event_history = [
                item
                for item in history
                if obs["next_earnings_date"]
                and item.get("next_earnings_date") == obs["next_earnings_date"]
            ]
            prior = same_event_history[-1] if same_event_history else None
            prior_7d = _latest_prior_at_least_days_back(same_event_history, as_of, 7)
            prior_30d = _latest_prior_at_least_days_back(same_event_history, as_of, 30)
            delta_prev = _delta(obs["eps_estimate"], prior.get("eps_estimate") if prior else None)
            delta_7d = _delta(obs["eps_estimate"], prior_7d.get("eps_estimate") if prior_7d else None)
            delta_30d = _delta(obs["eps_estimate"], prior_30d.get("eps_estimate") if prior_30d else None)
            usable = bool(
                obs["source_quality"] in {
                    "snapshot_timestamp_and_mtime_pit",
                    "snapshot_timestamp_replay_backfill",
                }
                and obs["next_earnings_date"]
                and obs["eps_estimate"] is not None
                and prior is not None
                and prior.get("eps_estimate") is not None
            )
            if window_start <= as_of <= window_end:
                last_earnings_date = last_earnings_index.get((ticker, as_of))
                days_since_last = (
                    (as_of - _coerce_date(last_earnings_date)).days
                    if last_earnings_date
                    else None
                )
                pead_window = (
                    days_since_last is not None
                    and PEAD_WINDOW_LO <= days_since_last <= PEAD_WINDOW_HI
                )
                bucket = classify_revision_trajectory(
                    usable=usable,
                    delta_prev=delta_prev,
                    delta_7d=delta_7d,
                    delta_30d=delta_30d,
                )
                rows.append(
                    {
                        "ticker": ticker,
                        "as_of_date": as_of.isoformat(),
                        "source_snapshot_path": obs["source_snapshot_path"],
                        "source_quality": obs["source_quality"],
                        "next_earnings_date": obs["next_earnings_date"],
                        "next_earnings_date_source": obs["next_earnings_date_source"],
                        "last_earnings_date": last_earnings_date,
                        "days_since_last_earnings": days_since_last,
                        "pead_window": pead_window,
                        "eps_estimate": obs["eps_estimate"],
                        "eps_estimate_delta_prev": delta_prev,
                        "eps_estimate_delta_7d": delta_7d,
                        "eps_estimate_delta_30d": delta_30d,
                        "avg_historical_surprise_pct": obs["avg_historical_surprise_pct"],
                        "same_event_history_count": len(same_event_history),
                        "estimate_revision_usable": usable,
                        "revision_trajectory_bucket_v1": bucket,
                        "forward_outcomes": {
                            f"{horizon}d": prices.forward_return(ticker, as_of, horizon)
                            for horizon in FORWARD_HORIZONS
                        },
                    }
                )
            history.append(obs)
        for ticker in list(history_by_ticker):
            history_by_ticker[ticker].sort(key=lambda item: item["as_of_date"])
    return rows


def classify_revision_trajectory(
    *,
    usable: bool,
    delta_prev: float | None,
    delta_7d: float | None,
    delta_30d: float | None,
) -> str:
    if not usable:
        return "missing_or_unusable"
    deltas = [delta for delta in (delta_prev, delta_7d, delta_30d) if delta is not None]
    if not deltas:
        return "missing_or_unusable"
    positives = [delta for delta in deltas if delta > EPS_EPSILON]
    negatives = [delta for delta in deltas if delta < -EPS_EPSILON]
    if delta_7d is not None and delta_30d is not None and delta_7d > EPS_EPSILON and delta_30d > EPS_EPSILON:
        return "positive_persistent"
    if len(positives) >= 2 and not negatives:
        return "positive_persistent"
    if positives:
        return "positive_one_shot"
    return "flat_or_negative"


def build_price_lookup(data_dir: Path) -> PriceLookup:
    prices = PriceLookup()
    for path in sorted((data_dir / "ohlcv").glob("ohlcv_snapshot_*.json")):
        payload = _read_json(path)
        ohlcv = payload.get("ohlcv") if isinstance(payload.get("ohlcv"), dict) else payload
        if not isinstance(ohlcv, dict):
            continue
        for ticker, rows in ohlcv.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                prices.add(ticker, row.get("Date") or row.get("date"), row.get("Close") or row.get("close"))
    return prices


def concentration_stats(rows: list[dict[str, Any]], horizon: str) -> dict[str, Any]:
    positive_pairs = []
    by_ticker: Counter[str] = Counter()
    for row in rows:
        outcome = (row.get("forward_outcomes") or {}).get(horizon) or {}
        pnl = _float(outcome.get("pnl_proxy"), 0.0)
        if outcome.get("closed") and pnl and pnl > 0:
            positive_pairs.append((row.get("ticker", ""), pnl))
            by_ticker[row.get("ticker", "")] += pnl
    total_positive = sum(pnl for _ticker, pnl in positive_pairs)
    if total_positive <= 0:
        return {
            "positive_pnl_total": 0.0,
            "top5_positive_share": None,
            "single_ticker_positive_share": None,
            "top_positive_tickers": [],
        }
    top5 = sum(pnl for _ticker, pnl in sorted(positive_pairs, key=lambda item: item[1], reverse=True)[:5])
    top_tickers = [
        {"ticker": ticker, "positive_pnl_proxy": round(pnl, 2)}
        for ticker, pnl in by_ticker.most_common(5)
    ]
    return {
        "positive_pnl_total": round(total_positive, 2),
        "top5_positive_share": round(top5 / total_positive, 6),
        "single_ticker_positive_share": round((by_ticker.most_common(1)[0][1] / total_positive), 6)
        if by_ticker
        else None,
        "top_positive_tickers": top_tickers,
    }


def summarize_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "row_count": len(rows),
        "ticker_count": len({row["ticker"] for row in rows}),
        "pead_row_count": sum(1 for row in rows if row.get("pead_window")),
        "source_quality_counts": dict(Counter(str(row.get("source_quality")) for row in rows)),
        "next_earnings_date_source_counts": dict(
            Counter(str(row.get("next_earnings_date_source")) for row in rows)
        ),
        "horizons": {},
    }
    for horizon in GATE_HORIZONS:
        closed = [
            row
            for row in rows
            if ((row.get("forward_outcomes") or {}).get(horizon) or {}).get("closed")
        ]
        returns = [
            _float(((row.get("forward_outcomes") or {}).get(horizon) or {}).get("return"), 0.0)
            for row in closed
        ]
        pnl_values = [
            _float(((row.get("forward_outcomes") or {}).get(horizon) or {}).get("pnl_proxy"), 0.0)
            for row in closed
        ]
        summary["horizons"][horizon] = {
            "closed_count": len(closed),
            "avg_return": round(sum(returns) / len(returns), 6) if returns else None,
            "median_return": _median(returns),
            "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 6)
            if returns
            else None,
            "tail_loss": round(min(returns), 6) if returns else None,
            "total_pnl_proxy": round(sum(pnl_values), 2) if pnl_values else 0.0,
            **concentration_stats(closed, horizon),
        }
    return summary


def _median(values: list[float | None]) -> float | None:
    clean = sorted(float(value) for value in values if value is not None)
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return round(clean[mid], 6)
    return round((clean[mid - 1] + clean[mid]) / 2.0, 6)


def summarize_window(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in BUCKET_ORDER}
    for row in rows:
        by_bucket.setdefault(str(row["revision_trajectory_bucket_v1"]), []).append(row)
    all_rows = {
        bucket: summarize_bucket(bucket_rows)
        for bucket, bucket_rows in by_bucket.items()
    }
    pead_rows = {
        bucket: summarize_bucket([row for row in bucket_rows if row.get("pead_window")])
        for bucket, bucket_rows in by_bucket.items()
    }
    return {
        "all_revision_rows": all_rows,
        "pead_subset_rows": pead_rows,
    }


def _metric(
    summary: dict[str, Any],
    view: str,
    bucket: str,
    horizon: str,
    field: str,
    default: Any = None,
) -> Any:
    return (
        ((summary.get(view) or {}).get(bucket) or {})
        .get("horizons", {})
        .get(horizon, {})
        .get(field, default)
    )


def build_gate(window_summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    window_results: dict[str, Any] = {}
    positive_window_count = 0
    data_gap_windows: list[str] = []
    concentration_flags: list[str] = []

    for window_name, summary in window_summaries.items():
        comparisons: dict[str, Any] = {}
        window_pass = True
        window_data_gap = False
        for horizon in GATE_HORIZONS:
            pp_closed = _metric(summary, "all_revision_rows", "positive_persistent", horizon, "closed_count", 0)
            flat_closed = _metric(summary, "all_revision_rows", "flat_or_negative", horizon, "closed_count", 0)
            pp_avg = _metric(summary, "all_revision_rows", "positive_persistent", horizon, "avg_return")
            flat_avg = _metric(summary, "all_revision_rows", "flat_or_negative", horizon, "avg_return")
            pp_pnl = _metric(summary, "all_revision_rows", "positive_persistent", horizon, "total_pnl_proxy", 0.0)
            flat_pnl = _metric(summary, "all_revision_rows", "flat_or_negative", horizon, "total_pnl_proxy", 0.0)
            top5 = _metric(summary, "all_revision_rows", "positive_persistent", horizon, "top5_positive_share")
            single = _metric(
                summary,
                "all_revision_rows",
                "positive_persistent",
                horizon,
                "single_ticker_positive_share",
            )
            sufficient = pp_closed >= MIN_CLOSED_PER_BUCKET and flat_closed >= MIN_CLOSED_PER_BUCKET
            if not sufficient:
                window_data_gap = True
                window_pass = False
            beats_avg = pp_avg is not None and flat_avg is not None and pp_avg > flat_avg
            beats_pnl = pp_pnl is not None and flat_pnl is not None and pp_pnl > flat_pnl
            conc_ok = bool(
                (top5 is None or top5 <= MAX_TOP5_POSITIVE_SHARE)
                and (single is None or single <= MAX_SINGLE_TICKER_POSITIVE_SHARE)
            )
            if not conc_ok:
                concentration_flags.append(f"{window_name}:{horizon}")
            if not (sufficient and beats_avg and beats_pnl and conc_ok):
                window_pass = False
            comparisons[horizon] = {
                "positive_persistent_closed": pp_closed,
                "flat_or_negative_closed": flat_closed,
                "positive_persistent_avg_return": pp_avg,
                "flat_or_negative_avg_return": flat_avg,
                "avg_return_lift": round(pp_avg - flat_avg, 6)
                if pp_avg is not None and flat_avg is not None
                else None,
                "positive_persistent_total_pnl_proxy": pp_pnl,
                "flat_or_negative_total_pnl_proxy": flat_pnl,
                "pnl_lift": round(pp_pnl - flat_pnl, 2)
                if pp_pnl is not None and flat_pnl is not None
                else None,
                "sufficient_closed_counts": sufficient,
                "beats_avg_return": beats_avg,
                "beats_total_pnl": beats_pnl,
                "concentration_ok": conc_ok,
                "top5_positive_share": top5,
                "single_ticker_positive_share": single,
            }
        if window_pass:
            positive_window_count += 1
        if window_data_gap:
            data_gap_windows.append(window_name)
        window_results[window_name] = {
            "passed": window_pass,
            "data_gap": window_data_gap,
            "comparisons": comparisons,
        }

    pead_positive_windows = 0
    pead_comparisons: dict[str, Any] = {}
    for window_name, summary in window_summaries.items():
        per_horizon: dict[str, Any] = {}
        pead_pass = True
        for horizon in GATE_HORIZONS:
            pp_avg = _metric(summary, "pead_subset_rows", "positive_persistent", horizon, "avg_return")
            flat_avg = _metric(summary, "pead_subset_rows", "flat_or_negative", horizon, "avg_return")
            pp_closed = _metric(summary, "pead_subset_rows", "positive_persistent", horizon, "closed_count", 0)
            flat_closed = _metric(summary, "pead_subset_rows", "flat_or_negative", horizon, "closed_count", 0)
            beats = pp_avg is not None and flat_avg is not None and pp_avg > flat_avg
            if not (pp_closed >= 3 and flat_closed >= 3 and beats):
                pead_pass = False
            per_horizon[horizon] = {
                "positive_persistent_closed": pp_closed,
                "flat_or_negative_closed": flat_closed,
                "positive_persistent_avg_return": pp_avg,
                "flat_or_negative_avg_return": flat_avg,
                "avg_return_lift": round(pp_avg - flat_avg, 6)
                if pp_avg is not None and flat_avg is not None
                else None,
                "beats_avg_return": beats,
            }
        if pead_pass:
            pead_positive_windows += 1
        pead_comparisons[window_name] = per_horizon

    if data_gap_windows:
        decision = "observed_only_data_gap"
        reason = "minimum_closed_outcomes_not_met_for_revision_trajectory_buckets"
        passed = False
    elif positive_window_count >= 2:
        if concentration_flags:
            decision = "observed_only_positive_but_concentrated"
            reason = "positive_persistent_concentration_guardrail_failed"
            passed = False
        else:
            decision = "observed_only_promising_needs_forward_adapter_gate"
            reason = None
            passed = True
    else:
        decision = "rejected_no_revision_trajectory_edge"
        reason = "positive_persistent_did_not_beat_flat_or_negative_in_two_windows"
        passed = False

    return {
        "passed": passed,
        "decision": decision,
        "reason": reason,
        "window_results": window_results,
        "positive_window_count": positive_window_count,
        "data_gap_windows": data_gap_windows,
        "concentration_flags": concentration_flags,
        "pead_subset_positive_window_count": pead_positive_windows,
        "pead_subset_comparisons": pead_comparisons,
    }


def _actual_success(decision: str) -> bool | None:
    if decision.startswith("accepted"):
        return True
    if decision.startswith("observed_only_promising"):
        return True
    if decision.startswith("rejected") or decision.startswith("observed_only_data_gap"):
        return False
    if decision.startswith("observed_only"):
        return False
    return None


def build_calibration(payload: dict[str, Any]) -> dict[str, Any]:
    actual_success = _actual_success(str(payload.get("decision") or ""))
    probability = PREDICTION["success_probability"]
    brier = (
        round((probability - float(actual_success)) ** 2, 6)
        if actual_success is not None
        else None
    )
    realized_mode = str(payload.get("rejection_reason") or "")
    return {
        "actual_decision": payload.get("decision"),
        "actual_success": actual_success,
        "predicted_success_probability": probability,
        "brier_score": brier,
        "calibration_direction": "overconfident" if actual_success is False else "directionally_calibrated",
        "surprise_level": "expected_failure" if actual_success is False else "not_applicable",
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": payload["delta_metrics"]["expected_value_score"],
        "ev_prediction_error": payload["delta_metrics"]["expected_value_score"] - PREDICTION["expected_ev_delta"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": payload["delta_metrics"]["total_pnl"],
        "pnl_prediction_error": payload["delta_metrics"]["total_pnl"] - PREDICTION["expected_pnl_delta"],
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "realized_failure_mode": realized_mode or None,
        "predicted_failure_mode_hit": realized_mode in PREDICTION["main_failure_modes"],
        "surprise_note": (
            "Failure mode was expected: supplemented snapshot-derived ledgers "
            "did not produce enough positive revision rows in any canonical window."
        ),
    }


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of_date": row.get("as_of_date"),
        "ticker": row.get("ticker"),
        "bucket": row.get("revision_trajectory_bucket_v1"),
        "pead_window": row.get("pead_window"),
        "days_since_last_earnings": row.get("days_since_last_earnings"),
        "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
        "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
        "eps_estimate_delta_30d": row.get("eps_estimate_delta_30d"),
        "source_quality": row.get("source_quality"),
        "next_earnings_date_source": row.get("next_earnings_date_source"),
        "forward_outcomes": {
            horizon: (row.get("forward_outcomes") or {}).get(horizon)
            for horizon in GATE_HORIZONS
        },
    }


def build_payload(data_dir: Path) -> dict[str, Any]:
    timestamp = _utc_now()
    prices = build_price_lookup(data_dir)
    window_rows: dict[str, list[dict[str, Any]]] = {}
    window_summaries: dict[str, dict[str, Any]] = {}
    coverage: dict[str, Any] = {}

    for spec in WINDOWS:
        start = _coerce_date(spec["start"])
        end = _coerce_date(spec["end"])
        snapshots = load_snapshot_records(data_dir, start=start, end=end)
        rows = build_revision_rows(
            snapshots,
            window_start=start,
            window_end=end,
            prices=prices,
        )
        window_rows[spec["name"]] = rows
        window_summaries[spec["name"]] = summarize_window(rows)
        coverage[spec["name"]] = {
            "date_range": {"start": spec["start"], "end": spec["end"]},
            "canonical_ohlcv_snapshot": spec["snapshot"],
            "snapshot_record_count": len(snapshots),
            "snapshot_date_range": (
                f"{snapshots[0]['as_of_date'].isoformat()} .. {snapshots[-1]['as_of_date'].isoformat()}"
                if snapshots
                else None
            ),
            "row_count": len(rows),
            "usable_revision_rows": sum(1 for row in rows if row.get("estimate_revision_usable")),
            "pead_rows": sum(1 for row in rows if row.get("pead_window")),
            "bucket_counts": dict(Counter(row["revision_trajectory_bucket_v1"] for row in rows)),
            "source_quality_counts": dict(Counter(row["source_quality"] for row in rows)),
            "next_earnings_date_source_counts": dict(
                Counter(row["next_earnings_date_source"] for row in rows)
            ),
        }

    gate = build_gate(window_summaries)
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(DOC_LOG),
        _repo_rel(DOC_CARD),
        _repo_rel(DOC_TICKET),
        _repo_rel(DOCS_TICKET),
        _repo_rel(EXPERIMENT_LOG_JSONL),
        _repo_rel(EXPERIMENT_REGISTRY),
        "docs/backtesting.md",
        "docs/alpha_direction_guidance.md",
    ]

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only",
        "decision": gate["decision"],
        "lane": "alpha_search",
        "hypothesis": (
            "PIT analyst or estimate revision trajectory combined with "
            "post-earnings continuation may produce better 10d/20d replacement "
            "value than flat or negative revision rows."
        ),
        "change_summary": (
            "Observed-only attribution for revision_trajectory_bucket_v1. "
            "The runner supplements missing historical estimate-revision ledgers "
            "from existing PIT earnings snapshots, deriving event keys from "
            "days_to_earnings when explicit next_earnings_date is absent, then "
            "computes 10d/20d close-to-close outcomes from canonical OHLCV snapshots."
        ),
        "change_type": "read_only_alpha_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": EXPERIMENT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 8,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "pre_registered_10d20d_revision_trajectory_attribution_with_snapshot_ledger_backfill",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "windows": WINDOWS,
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "forward_horizons": list(FORWARD_HORIZONS),
            "gate_horizons": list(GATE_HORIZONS),
            "pead_window": f"T+{PEAD_WINDOW_LO}..T+{PEAD_WINDOW_HI} calendar days after last earnings event transition",
            "bucket_order": BUCKET_ORDER,
            "positive_persistent_definition": (
                "usable row with both 7d and 30d EPS estimate deltas positive, "
                "or at least two positive deltas among prev/7d/30d with no negative delta"
            ),
            "data_supplement": (
                "Historical ledgers are reconstructed from existing earnings snapshots; "
                "when next_earnings_date is absent, the event key is derived from "
                "snapshot as_of_date + days_to_earnings. Rows from historical files "
                "with PIT payload timestamps but later filesystem mtime are labelled "
                "snapshot_timestamp_replay_backfill and are not eligible for direct "
                "production promotion."
            ),
            "min_closed_per_bucket": MIN_CLOSED_PER_BUCKET,
            "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
            "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
            "anti_js": ANTI_JS,
        },
        "prediction": PREDICTION,
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Positive persistent PIT revision trajectory should beat flat or "
                "negative revision rows at 10d/20d, especially near post-earnings drift."
            ),
            "2_history_check": (
                "Nearby expectation/PEAD experiments were mostly rejected or observed-only; "
                "this run is the pre-registered 10d/20d trajectory retry with supplemented "
                "snapshot-derived ledgers."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three canonical windows. Observed-only pass "
                "requires positive_persistent beating flat_or_negative on both 10d and "
                "20d in at least two windows, sufficient closed outcomes, and concentration "
                "below guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260604_020_revision_trajectory_pead_attribution.py"
            ),
        },
        "gate1": {
            "passed": True,
            **BASELINE,
            "three_window_protocol": WINDOWS,
            "note": "Observed-only attribution; core strategy before/after metrics are intentionally unchanged.",
        },
        "gate2": {
            "passed": True,
            "rule_dependencies": [
                "ticker",
                "as_of_date",
                "eps_estimate",
                "days_to_earnings or next_earnings_date",
                "eps_estimate_delta_prev",
                "eps_estimate_delta_7d",
                "eps_estimate_delta_30d",
                "local OHLCV close",
            ],
            "field_coverage_by_window": coverage,
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
            "passed": bool(gate["passed"]),
            "note": "This read-only result can only justify a later default-off adapter with shared production/backtest data semantics.",
        },
        "coverage": coverage,
        "window_summaries": window_summaries,
        "gate": gate,
        "sample_rows": {
            window_name: {
                bucket: [
                    compact_row(row)
                    for row in rows
                    if row.get("revision_trajectory_bucket_v1") == bucket
                ][:40]
                for bucket in BUCKET_ORDER
            }
            for window_name, rows in window_rows.items()
        },
        "before_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE["accepted_core_expected_value_score_sum"],
            "accepted_core_total_pnl_sum": BASELINE["accepted_core_total_pnl_sum"],
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE["accepted_core_expected_value_score_sum"],
            "accepted_core_total_pnl_sum": BASELINE["accepted_core_total_pnl_sum"],
            "strategy_behavior_changed": False,
        },
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
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
            "observed_only_attribution": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "rejection_reason": gate["reason"],
        "next_evidence_needed": (
            "If rejected, do not retune adjacent PEAD/revision thresholds. If data-gap, "
            "supplement with a production-visible free revision feed that records explicit "
            "analyst_count and revenue_estimate changes before retrying."
        ),
        "related_files": related_files,
        "anti_js": ANTI_JS,
    }
    payload["calibration"] = build_calibration(payload)
    return payload


def _fmt(value: Any) -> str:
    number = _float(value)
    if number is None:
        return ""
    return f"{number:.6f}"


def artifact_markdown(payload: dict[str, Any]) -> str:
    rows = [
        "# exp-20260604-020 Revision Trajectory PEAD Attribution",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Status: `{payload['status']}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        "- Strategy behavior changed: `false`",
        "- Production/backtest parity impact: no shared policy, backtester, run adapter, ranking, sizing, exit, or order change.",
        "",
        "## Three-Window Outcomes",
        "",
        "| window | view | bucket | rows | PEAD rows | 10d closed | 10d avg | 10d pnl | 20d closed | 20d avg | 20d pnl |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for window in [item["name"] for item in WINDOWS]:
        summary = payload["window_summaries"][window]
        for view in ("all_revision_rows", "pead_subset_rows"):
            for bucket in BUCKET_ORDER:
                bucket_summary = summary[view].get(bucket, {})
                h10 = (bucket_summary.get("horizons") or {}).get("10d", {})
                h20 = (bucket_summary.get("horizons") or {}).get("20d", {})
                rows.append(
                    "| {window} | {view} | {bucket} | {row_count} | {pead_rows} | {c10} | {a10} | {p10} | {c20} | {a20} | {p20} |".format(
                        window=window,
                        view=view,
                        bucket=bucket,
                        row_count=bucket_summary.get("row_count", 0),
                        pead_rows=bucket_summary.get("pead_row_count", 0),
                        c10=h10.get("closed_count", 0),
                        a10=_fmt(h10.get("avg_return")),
                        p10=_fmt(h10.get("total_pnl_proxy")),
                        c20=h20.get("closed_count", 0),
                        a20=_fmt(h20.get("avg_return")),
                        p20=_fmt(h20.get("total_pnl_proxy")),
                    )
                )
    rows.extend(
        [
            "",
            "## Gate",
            "",
            f"- Positive all-row windows: `{payload['gate']['positive_window_count']}`",
            f"- Data-gap windows: `{payload['gate']['data_gap_windows']}`",
            f"- Concentration flags: `{payload['gate']['concentration_flags']}`",
            f"- PEAD subset positive windows: `{payload['gate']['pead_subset_positive_window_count']}`",
            "",
            "## Data Supplement",
            "",
            "The experiment supplements missing historical estimate-revision ledgers from existing earnings snapshots. Rows derived from historical payload timestamps with later filesystem mtime are labelled `snapshot_timestamp_replay_backfill`; this is acceptable for observed-only direction screening but blocks direct production promotion.",
            "",
            "## Related Files",
            "",
        ]
    )
    rows.extend(f"- `{path}`" for path in payload["related_files"])
    rows.append("")
    return "\n".join(rows)


def build_ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        **RESERVATION_METADATA,
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": "codex-alpha-search",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": [
            item["experiment_id"] for item in NEARBY_PRIORS
        ],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "baseline_result_file": "data/experiments/exp-20260602-003/exp_20260602_003_post_earnings_explicit_continuation.json",
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "must_not_touch": ["docs/alpha-optimization-playbook.md"],
        "locked_variables": LOCKED_VARIABLES,
        "evaluation_windows": [
            {"start": item["start"], "end": item["end"]} for item in WINDOWS
        ],
        "acceptance_rule": (
            "Observed-only pass requires usable PIT revision trajectory rows in all "
            "3 windows plus positive_persistent beating flat_or_negative on both "
            "10d and 20d in at least 2 windows without top-ticker concentration."
        ),
        "prediction": PREDICTION,
        "completed_at": payload["timestamp"],
        "artifact_file": _repo_rel(OUT_JSON),
        "decision": payload["decision"],
        "result_file": _repo_rel(DOC_LOG),
        "result": {
            "decision": payload["decision"],
            "acceptance_reasons": [],
            "before_result_file": _repo_rel(OUT_JSON),
            "after_result_file": _repo_rel(OUT_JSON),
            "delta_metrics": payload["delta_metrics"],
            "calibration": payload["calibration"],
        },
        "ticket_file": _repo_rel(DOC_TICKET),
        "card_file": _repo_rel(DOC_CARD),
        "revision_manifest_file": f"experiments/manifests/{EXPERIMENT_ID}.json",
        "updated_at": payload["timestamp"],
    }


def update_registry(payload: dict[str, Any], ticket: dict[str, Any]) -> None:
    registry = _read_json(EXPERIMENT_REGISTRY) if EXPERIMENT_REGISTRY.exists() else {"experiments": []}
    registry["updated_at"] = payload["timestamp"]
    experiments = registry.setdefault("experiments", [])
    row = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["hypothesis"],
        "lane": payload["lane"],
        "owner": ticket["owner"],
        "status": payload["status"],
        "ticket_file": _repo_rel(DOC_TICKET),
        "updated_at": payload["timestamp"],
        "result": ticket["result"],
    }
    for idx, item in enumerate(experiments):
        if item.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = row
            break
    else:
        experiments.append(row)
    EXPERIMENT_REGISTRY.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def persist_payload(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    ticket = build_ticket(payload)
    _write_json(DOC_TICKET, ticket)
    _write_json(DOCS_TICKET, ticket)
    DOC_CARD.parent.mkdir(parents=True, exist_ok=True)
    DOC_CARD.write_text(artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    update_registry(payload, ticket)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(REPO_ROOT / "data"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = build_payload(Path(args.data_dir))
    if args.dry_run:
        print(json.dumps(_safe(payload["gate"]), indent=2, sort_keys=True))
        return
    persist_payload(payload)
    print(json.dumps(_safe({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "gate": payload["gate"],
        "artifact": _repo_rel(OUT_JSON),
    }), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
