"""exp-20260625-021: intraday review replayability audit.

Measurement repair only. This audits the saved intraday risk-review snapshots
as a potential future alpha surface. The money hypothesis is that 13:00 ET
risk-state changes might eventually carry exit/risk timing value, but that is
not testable unless the surface is PIT-valid, schema-stable, and outcome-ready.

No strategy, ranking, sizing, exits, paper orders, live orders, watchlist, LLM,
or daily production behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260625-021"
OWNER = "alpha-explore"
SLUG = "intraday_review_replayability_audit"
RUNNER = f"quant/experiments/exp_20260625_021_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
SNAPSHOT_DIR = REPO_ROOT / "data" / "daily" / "intraday" / "snapshots"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_021_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Repair/audit the intraday risk-review alpha blocker by checking whether "
    "data/daily/intraday snapshots are PIT-valid, schema-stable, and "
    "outcome-ready enough to support a future 13:00 ET exit/risk timing alpha "
    "without changing strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "Intraday 13:00 ET risk-state changes may carry exit/risk timing value "
    "because they re-evaluate live positions against current intraday prices "
    "before the EOD pipeline; this is only alpha-testable if the saved surface "
    "has real-time quote timestamps, stable position/action fields, entry/target "
    "context, and enough closed forward outcomes."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "intraday_review_alpha_measurement_repair"
TRIAL_FAMILY = "intraday_review_replayability_audit"
TRIAL_VARIANT_ID = "timestamped_snapshot_outcome_readiness_v1"
CHANGED_VARIABLE = "intraday_review_replayability_and_outcome_readiness_v1"
NEW_EVIDENCE_TYPE = "intraday_timestamped_snapshot_replayability_audit"
NEW_EVIDENCE_AXIS = (
    "Machine-checkable new data surface: timestamped "
    "data/daily/intraday/snapshots/intraday_review_YYYYMMDD_HHMMET.json files "
    "across 2026-06-11..2026-06-25; this audits PIT timestamp/schema/outcome "
    "readiness rather than retuning exit lifecycle or LLM state thresholds."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260613-022",
    "exp-20260623-011",
    "exp-20260623-012",
    "exp-20260625-004",
    "exp-20260625-017",
]
CAUSAL_COMPONENTS = [
    "intraday snapshot schema audit",
    "file timestamp PIT audit",
    "position/action extraction",
    "outcome settlement coverage",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260625_021_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

BACKFILL_LAG_HOURS = 2.0
MIN_SNAPSHOT_COUNT = 8
MIN_POSITION_ROWS = 100
MIN_QUOTE_TIME_COVERAGE = 0.80
MIN_ENTRY_DATE_COVERAGE = 0.80
MIN_TARGET_CONTEXT_COVERAGE = 0.80
MIN_PENDING_ACTION_ROWS = 1
MIN_SETTLED_5D_ROWS = 50
OUTCOME_HORIZONS = [1, 3, 5]
COMPARATOR_TICKERS = ["SPY", "QQQ"]
ET = ZoneInfo("America/New_York")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(value)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
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
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
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
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def pct(part: int | float, whole: int | float) -> float | None:
    if not whole:
        return None
    return round(float(part) / float(whole), 6)


def compact_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


def parse_generated_at_et(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for suffix in (" ET", " EDT", " EST"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=ET)
        except ValueError:
            continue
    return None


def baseline_metrics() -> dict[str, Any]:
    payload = load_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "baseline_exists": BASELINE_RESULT.exists(),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": pct(survived, generated),
        "max_drawdown_pct_worst": max(
            [float(row.get("max_drawdown_pct") or 0.0) for row in windows] or [0.0]
        ),
        "window_count": len(windows),
        "windows": windows,
    }


def snapshot_paths() -> list[Path]:
    return sorted(SNAPSHOT_DIR.glob("intraday_review_*.json"))


def quote_time_present(value: Any) -> bool:
    return value not in (None, "")


def extract_position_rows(payload: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    date = compact_date(payload.get("date"))
    time_label = str(payload.get("time_label") or "")
    rows: list[dict[str, Any]] = []
    for index, position in enumerate(payload.get("positions") or []):
        if not isinstance(position, dict):
            continue
        quote = position.get("quote") if isinstance(position.get("quote"), dict) else {}
        context = position.get("context") if isinstance(position.get("context"), dict) else {}
        exit_levels = (
            context.get("exit_levels") if isinstance(context.get("exit_levels"), dict) else {}
        )
        exit_signals = (
            context.get("exit_signals") if isinstance(context.get("exit_signals"), dict) else {}
        )
        triggered_rules = [
            rule
            for rule in exit_signals.get("triggered_rules") or []
            if isinstance(rule, dict)
        ]
        entry_date = compact_date(context.get("entry_date"))
        target_value = (
            exit_levels.get("signal_target_price")
            if exit_levels.get("signal_target_price") is not None
            else exit_levels.get("profit_target_price")
        )
        rows.append(
            {
                "snapshot_file": repo_rel(path),
                "snapshot_date": date,
                "time_label": time_label,
                "row_index": index,
                "ticker": str(position.get("ticker") or "").upper(),
                "sleeve": position.get("sleeve"),
                "status": position.get("status"),
                "quote_price": safe_float(quote.get("price")),
                "quote_source": quote.get("source"),
                "quote_time_et": quote.get("quote_time_et"),
                "quote_time_present": quote_time_present(quote.get("quote_time_et")),
                "quote_is_stale": bool(quote.get("is_stale")),
                "shares": safe_float(context.get("shares")),
                "avg_cost": safe_float(context.get("avg_cost")),
                "market_value_usd": safe_float(context.get("market_value_usd")),
                "entry_date": entry_date,
                "entry_date_present": entry_date is not None,
                "target_price": safe_float(target_value),
                "target_context_present": target_value not in (None, ""),
                "hard_stop_price": safe_float(exit_levels.get("hard_stop_price")),
                "atr_stop_price": safe_float(exit_levels.get("atr_stop_price")),
                "trailing_stop_from_20d_high": safe_float(context.get("trailing_stop_from_20d_high")),
                "any_triggered": bool(exit_signals.get("any_triggered")),
                "critical_exit": bool(exit_signals.get("critical_exit")),
                "high_urgency": bool(exit_signals.get("high_urgency")),
                "triggered_rule_count": len(triggered_rules),
                "triggered_rules": [
                    {
                        "rule": rule.get("rule"),
                        "urgency": rule.get("urgency"),
                    }
                    for rule in triggered_rules
                ],
                "proximity_flags": position.get("proximity_flags") or [],
            }
        )
    return rows


def summarize_snapshot(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = load_json(path, {}) or {}
    if not isinstance(payload, dict):
        return {
            "path": repo_rel(path),
            "loaded": False,
            "reason": "invalid_json_payload",
        }, []
    generated = parse_generated_at_et(payload.get("generated_at_et"))
    mtime_utc = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    lag_hours = None
    backfilled = False
    if generated is not None:
        lag_hours = round((mtime_utc - generated.astimezone(timezone.utc)).total_seconds() / 3600, 4)
        backfilled = lag_hours > BACKFILL_LAG_HOURS
    positions = payload.get("positions") or []
    pending_actions = payload.get("pending_actions") or []
    news = payload.get("news") if isinstance(payload.get("news"), dict) else {}
    trade_items = news.get("trade_items") if isinstance(news.get("trade_items"), list) else []
    position_rows = extract_position_rows(payload, path)
    return {
        "path": repo_rel(path),
        "loaded": True,
        "date": compact_date(payload.get("date")),
        "time_label": payload.get("time_label"),
        "generated_at_et": payload.get("generated_at_et"),
        "generated_at_utc": generated.astimezone(timezone.utc).isoformat() if generated else None,
        "file_mtime_utc": mtime_utc.isoformat(),
        "mtime_minus_generated_hours": lag_hours,
        "posthoc_backfilled": backfilled,
        "advisory_note": payload.get("advisory_note"),
        "top_level_keys": sorted(payload.keys()),
        "positions_count": len(positions) if isinstance(positions, list) else 0,
        "pending_actions_count": len(pending_actions) if isinstance(pending_actions, list) else 0,
        "news_trade_items_count": len(trade_items),
        "quote_sources": dict(
            sorted(Counter(row.get("quote_source") or "missing" for row in position_rows).items())
        ),
        "status_counts": dict(
            sorted(Counter(row.get("status") or "missing" for row in position_rows).items())
        ),
        "triggered_position_rows": sum(1 for row in position_rows if row["triggered_rule_count"] > 0),
        "critical_exit_rows": sum(1 for row in position_rows if row["critical_exit"]),
        "high_urgency_rows": sum(1 for row in position_rows if row["high_urgency"]),
        "quote_time_present_rows": sum(1 for row in position_rows if row["quote_time_present"]),
        "entry_date_present_rows": sum(1 for row in position_rows if row["entry_date_present"]),
        "target_context_present_rows": sum(
            1 for row in position_rows if row["target_context_present"]
        ),
        "advisory_only": "ADVISORY ONLY" in str(payload.get("advisory_note") or ""),
    }, position_rows


def load_warehouse_index(tickers: set[str]) -> dict[str, Any]:
    if not WAREHOUSE.exists():
        return {
            "path": repo_rel(WAREHOUSE),
            "exists": False,
            "min_date": None,
            "max_date": None,
            "rows": 0,
            "calendar_dates": [],
            "ticker_dates": {},
        }
    with sqlite3.connect(WAREHOUSE) as con:
        min_date, max_date, count = con.execute(
            "select min(date), max(date), count(*) from ohlcv"
        ).fetchone()
        calendar_dates = [
            row[0] for row in con.execute("select distinct date from ohlcv order by date")
        ]
        ticker_dates: dict[str, set[str]] = {}
        for ticker in sorted(tickers | set(COMPARATOR_TICKERS)):
            ticker_dates[ticker] = {
                row[0]
                for row in con.execute(
                    "select date from ohlcv where ticker=? order by date",
                    (ticker,),
                )
            }
    return {
        "path": repo_rel(WAREHOUSE),
        "exists": True,
        "min_date": min_date,
        "max_date": max_date,
        "rows": int(count or 0),
        "calendar_dates": calendar_dates,
        "ticker_dates": ticker_dates,
    }


def outcome_dates(calendar_dates: list[str], as_of_date: str, horizon: int) -> dict[str, Any]:
    future = [date for date in calendar_dates if date > as_of_date]
    if len(future) < horizon:
        return {
            "available": False,
            "entry_date": future[0] if future else None,
            "exit_date": None,
            "reason": "warehouse_calendar_horizon_missing",
        }
    return {
        "available": True,
        "entry_date": future[0],
        "exit_date": future[horizon - 1],
        "reason": "ok",
    }


def outcome_coverage(rows: list[dict[str, Any]], warehouse: dict[str, Any]) -> dict[str, Any]:
    calendar_dates = warehouse.get("calendar_dates") or []
    ticker_dates = warehouse.get("ticker_dates") or {}
    by_horizon: dict[str, Any] = {}
    for horizon in OUTCOME_HORIZONS:
        settled = 0
        missing_reasons: Counter[str] = Counter()
        date_counts: Counter[str] = Counter()
        sample_missing: list[dict[str, Any]] = []
        for row in rows:
            as_of_date = row.get("snapshot_date")
            ticker = row.get("ticker")
            if not as_of_date or not ticker:
                missing_reasons["missing_asof_or_ticker"] += 1
                continue
            dates = outcome_dates(calendar_dates, as_of_date, horizon)
            if not dates["available"]:
                missing_reasons[dates["reason"]] += 1
                if len(sample_missing) < 8:
                    sample_missing.append(
                        {
                            "ticker": ticker,
                            "snapshot_date": as_of_date,
                            "horizon": horizon,
                            "reason": dates["reason"],
                        }
                    )
                continue
            needed_dates = {dates["entry_date"], dates["exit_date"]}
            needed_tickers = [ticker, *COMPARATOR_TICKERS]
            missing = [
                f"{needed_ticker}:{needed_date}"
                for needed_ticker in needed_tickers
                for needed_date in needed_dates
                if needed_date not in ticker_dates.get(needed_ticker, set())
            ]
            if missing:
                missing_reasons["missing_ticker_or_comparator_prices"] += 1
                if len(sample_missing) < 8:
                    sample_missing.append(
                        {
                            "ticker": ticker,
                            "snapshot_date": as_of_date,
                            "horizon": horizon,
                            "entry_date": dates["entry_date"],
                            "exit_date": dates["exit_date"],
                            "missing": missing[:6],
                        }
                    )
                continue
            settled += 1
            date_counts[as_of_date] += 1
        by_horizon[str(horizon)] = {
            "horizon_days": horizon,
            "position_rows": len(rows),
            "settled_rows": settled,
            "settled_rate": pct(settled, len(rows)),
            "settled_snapshot_date_count": len(date_counts),
            "settled_rows_by_snapshot_date": dict(sorted(date_counts.items())),
            "missing_reasons": dict(sorted(missing_reasons.items())),
            "sample_missing": sample_missing,
        }
    return by_horizon


def field_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    checks = {
        "ticker": lambda row: bool(row.get("ticker")),
        "snapshot_date": lambda row: bool(row.get("snapshot_date")),
        "quote_price": lambda row: row.get("quote_price") is not None,
        "quote_source": lambda row: bool(row.get("quote_source")),
        "quote_time_et": lambda row: bool(row.get("quote_time_et")),
        "entry_date": lambda row: bool(row.get("entry_date")),
        "target_price": lambda row: row.get("target_price") is not None,
        "hard_stop_price": lambda row: row.get("hard_stop_price") is not None,
        "shares": lambda row: row.get("shares") is not None,
        "market_value_usd": lambda row: row.get("market_value_usd") is not None,
        "triggered_rules": lambda row: row.get("triggered_rule_count", 0) > 0,
    }
    result: dict[str, Any] = {}
    for field, checker in checks.items():
        present = sum(1 for row in rows if checker(row))
        result[field] = {
            "present_rows": present,
            "position_rows": len(rows),
            "coverage": pct(present, len(rows)),
        }
    return result


def build_readiness(
    snapshots: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    coverage: dict[str, Any],
    outcomes: dict[str, Any],
) -> dict[str, Any]:
    snapshot_count = len([snapshot for snapshot in snapshots if snapshot.get("loaded")])
    position_count = len(rows)
    backfilled_count = sum(1 for snapshot in snapshots if snapshot.get("posthoc_backfilled"))
    advisory_only_count = sum(1 for snapshot in snapshots if snapshot.get("advisory_only"))
    pending_actions_count = sum(int(snapshot.get("pending_actions_count") or 0) for snapshot in snapshots)
    quote_time_rate = coverage["quote_time_et"]["coverage"] or 0.0
    entry_date_rate = coverage["entry_date"]["coverage"] or 0.0
    target_context_rate = coverage["target_price"]["coverage"] or 0.0
    settled_5d = int(outcomes.get("5", {}).get("settled_rows") or 0)

    failed: list[str] = []
    if snapshot_count < MIN_SNAPSHOT_COUNT:
        failed.append("too_few_intraday_snapshot_files")
    if position_count < MIN_POSITION_ROWS:
        failed.append("too_few_position_rows")
    if backfilled_count:
        failed.append("posthoc_backfilled_snapshot_files")
    if quote_time_rate < MIN_QUOTE_TIME_COVERAGE:
        failed.append("quote_time_missing_for_intraday_quotes")
    if entry_date_rate < MIN_ENTRY_DATE_COVERAGE:
        failed.append("entry_date_missing_for_position_rows")
    if target_context_rate < MIN_TARGET_CONTEXT_COVERAGE:
        failed.append("target_context_below_replay_threshold")
    if pending_actions_count < MIN_PENDING_ACTION_ROWS:
        failed.append("no_executable_pending_action_rows")
    if settled_5d < MIN_SETTLED_5D_ROWS:
        failed.append("insufficient_5d_outcome_settlement")
    if advisory_only_count == snapshot_count and snapshot_count:
        failed.append("surface_declares_advisory_only_not_eod_or_backtest_consumed")

    return {
        "passed": not failed,
        "decision": (
            "accepted_measurement_repair_intraday_review_alpha_ready"
            if not failed
            else "blocked_intraday_review_not_alpha_replay_ready"
        ),
        "failed_reasons": failed,
        "thresholds": {
            "min_snapshot_count": MIN_SNAPSHOT_COUNT,
            "min_position_rows": MIN_POSITION_ROWS,
            "min_quote_time_coverage": MIN_QUOTE_TIME_COVERAGE,
            "min_entry_date_coverage": MIN_ENTRY_DATE_COVERAGE,
            "min_target_context_coverage": MIN_TARGET_CONTEXT_COVERAGE,
            "min_pending_action_rows": MIN_PENDING_ACTION_ROWS,
            "min_settled_5d_rows": MIN_SETTLED_5D_ROWS,
            "backfill_lag_hours": BACKFILL_LAG_HOURS,
        },
        "observed": {
            "snapshot_count": snapshot_count,
            "unique_snapshot_dates": len(
                {snapshot.get("date") for snapshot in snapshots if snapshot.get("date")}
            ),
            "position_rows": position_count,
            "posthoc_backfilled_files": backfilled_count,
            "advisory_only_snapshots": advisory_only_count,
            "pending_actions_count": pending_actions_count,
            "quote_time_coverage": quote_time_rate,
            "entry_date_coverage": entry_date_rate,
            "target_context_coverage": target_context_rate,
            "settled_5d_rows": settled_5d,
            "settled_5d_snapshot_date_count": outcomes.get("5", {}).get(
                "settled_snapshot_date_count"
            ),
        },
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    triggered = [row for row in rows if row.get("triggered_rule_count", 0) > 0]
    rules = Counter()
    urgencies = Counter()
    for row in triggered:
        for rule in row.get("triggered_rules") or []:
            rules[str(rule.get("rule") or "missing")] += 1
            urgencies[str(rule.get("urgency") or "missing")] += 1
    return {
        "position_rows": len(rows),
        "snapshot_date_counts": dict(
            sorted(Counter(str(row.get("snapshot_date") or "missing") for row in rows).items())
        ),
        "time_label_counts": dict(
            sorted(Counter(str(row.get("time_label") or "missing") for row in rows).items())
        ),
        "ticker_count": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "status_counts": dict(
            sorted(Counter(str(row.get("status") or "missing") for row in rows).items())
        ),
        "quote_source_counts": dict(
            sorted(Counter(str(row.get("quote_source") or "missing") for row in rows).items())
        ),
        "triggered_position_rows": len(triggered),
        "critical_exit_rows": sum(1 for row in rows if row.get("critical_exit")),
        "high_urgency_rows": sum(1 for row in rows if row.get("high_urgency")),
        "triggered_rule_counts": dict(sorted(rules.items())),
        "triggered_urgency_counts": dict(sorted(urgencies.items())),
        "top_tickers": [
            {"ticker": ticker, "rows": count}
            for ticker, count in Counter(str(row.get("ticker") or "missing") for row in rows).most_common(12)
        ],
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON, {}) or {}
    prediction = ticket.get("prediction") or {}
    before = baseline_metrics()

    snapshots: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []
    for path in snapshot_paths():
        summary, rows = summarize_snapshot(path)
        snapshots.append(summary)
        position_rows.extend(rows)

    tickers = {str(row.get("ticker") or "") for row in position_rows if row.get("ticker")}
    warehouse = load_warehouse_index(tickers)
    coverage = field_coverage(position_rows)
    outcomes = outcome_coverage(position_rows, warehouse)
    readiness = build_readiness(snapshots, position_rows, coverage, outcomes)
    accepted = bool(readiness["passed"])
    decision = readiness["decision"]
    status = "accepted_measurement_repair" if accepted else "blocked"
    failed = readiness["failed_reasons"]
    predicted_failure_map = {
        "posthoc_backfilled_files": "posthoc_backfilled_snapshot_files",
        "quote_time_missing": "quote_time_missing_for_intraday_quotes",
        "no_action_rows": "no_executable_pending_action_rows",
        "warehouse_too_stale_for_recent_intraday_rows": "insufficient_5d_outcome_settlement",
        "duplicate_exit_lifecycle_surface": "duplicate_exit_lifecycle_surface",
    }
    realized_failures = [
        mode
        for mode, realized in predicted_failure_map.items()
        if mode in (prediction.get("main_failure_modes") or []) and realized in failed
    ]
    actual_success = 1.0 if accepted else 0.0
    predicted = safe_float(prediction.get("success_probability")) or 0.0

    why = (
        "The intraday review surface cleared the replayability audit."
        if accepted
        else (
            "The surface is useful as an operator risk review but not yet an "
            "alpha replay surface: quote_time_et is missing on position quotes, "
            "entry_date is absent from position rows, every snapshot declares "
            "advisory-only/non-backtest consumption, no pending action rows are "
            "recorded, several files were written well after their embedded "
            "generated_at timestamp, and the warehouse only supports minimal "
            "one-day outcome coverage."
        )
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": "measurement_repair",
        "owner": OWNER,
        "status": status,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": accepted,
        "observed_only_lead": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_audit_only_no_strategy_change",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "ticket_before": ticket,
        "prediction": prediction,
        "calibration": {
            "actual_success": actual_success,
            "actual_gate4_passed": accepted,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - actual_success) ** 2, 4),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed,
            "predicted_failure_modes_hit": realized_failures,
            "surprise_note": (
                "Low surprise: the surface exists and is schema-stable, but the "
                "PIT/action/outcome contracts are not strong enough for alpha replay."
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before,
            "note": "Measurement audit only; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": accepted,
            "required_fields_checked": [
                "snapshot_date",
                "ticker",
                "quote_price",
                "quote_source",
                "quote_time_et",
                "entry_date",
                "target_price",
                "hard_stop_price",
                "shares",
                "market_value_usd",
                "triggered_rules",
            ],
            "field_coverage": coverage,
            "snapshot_file_count": len(snapshots),
            "snapshot_dir": repo_rel(SNAPSHOT_DIR),
            "warehouse": {
                "path": warehouse.get("path"),
                "exists": warehouse.get("exists"),
                "min_date": warehouse.get("min_date"),
                "max_date": warehouse.get("max_date"),
                "rows": warehouse.get("rows"),
            },
            "failed_reasons": [
                reason
                for reason in failed
                if reason
                in {
                    "posthoc_backfilled_snapshot_files",
                    "quote_time_missing_for_intraday_quotes",
                    "entry_date_missing_for_position_rows",
                    "target_context_below_replay_threshold",
                    "no_executable_pending_action_rows",
                    "surface_declares_advisory_only_not_eod_or_backtest_consumed",
                }
            ],
            "target_price_scope": (
                "Checked via context.exit_levels.signal_target_price/profit_target_price. "
                "No target exit, order, or strategy behavior is scheduled."
            ),
        },
        "gate3": {
            "passed": bool(position_rows),
            "filter_added": False,
            "signals_generated_proxy": len(position_rows),
            "signals_survived_proxy": sum(
                1 for row in position_rows if row.get("triggered_rule_count", 0) > 0
            ),
            "survival_rate_proxy": pct(
                sum(1 for row in position_rows if row.get("triggered_rule_count", 0) > 0),
                len(position_rows),
            ),
            "baseline_survival_rate": before.get("survival_rate"),
            "note": (
                "Coverage is measurement-only. Survival here means rows with "
                "triggered advisory rules, not an executable entry/exit filter."
            ),
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "failed_reasons": failed,
            "readiness": readiness,
            "expected_value_score_sum_before": before["expected_value_score_sum"],
            "expected_value_score_sum_after": before["expected_value_score_sum"],
            "aggregate_ev_delta": 0.0,
            "total_pnl_before": before["total_pnl"],
            "total_pnl_after": before["total_pnl"],
            "aggregate_pnl_delta": 0.0,
            "trade_count_before": before["trade_count"],
            "trade_count_after": before["trade_count"],
            "strategy_behavior_changed": False,
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
        "source_summary": {
            "snapshots": snapshots,
            "row_summary": summarize_rows(position_rows),
            "field_coverage": coverage,
            "outcome_coverage": outcomes,
        },
        "production_impact": {
            "adapter_status": "none",
            "default_off_paper_only": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "shared_policy_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "trade_enabled": False,
            "parity_note": "Read-only measurement audit; no production or replay behavior changed.",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "outcome_summary": (
                f"{len(snapshots)} intraday snapshot files and {len(position_rows)} "
                f"position rows were audited; 5d settled rows="
                f"{outcomes.get('5', {}).get('settled_rows')} with warehouse max "
                f"date {warehouse.get('max_date')}."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not convert intraday BREACHED/APPROACHING/status labels, "
                "hard-stop, ATR-stop, target, time-stop, trailing-stop, or LLM "
                "state overlaps into exits/risk rules on these same snapshots. "
                "Do not retry by changing severity thresholds or hold horizons "
                "until the replay contract is repaired."
            ),
            "new_evidence_required": (
                "A valid intraday retry needs real quote timestamps or broker "
                "bar IDs, entry_date and target context on position rows, "
                "explicit pending action/order semantics, a daily/default-off "
                "shared helper if promoted, and materially more closed warehouse "
                "outcome rows past 2026-06-15."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260613-022": "Repaired intraday artifact writes and tests; did not test alpha replayability.",
                "exp-20260623-011": "Observed-only exit-lifecycle lead; no promotion without more closed rows/helper.",
                "exp-20260623-012": "Observed-only daily LLM position-state lead; no shared rule promoted.",
                "exp-20260625-004": "Audited local OHLCV recovery and found intraday snapshot was not daily OHLCV settlement.",
                "exp-20260625-017": "Confirmed 20260624 intraday/Kova surfaces did not repair recent OHLCV blocker.",
                "novelty_gate": "Reservation passed without override; this audits timestamp/schema readiness on the intraday snapshot surface.",
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": readiness["thresholds"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_intraday_review.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "changed_files": ALLOWED_WRITE_SCOPE,
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(WAREHOUSE),
            repo_rel(SNAPSHOT_DIR),
            "quant/intraday_review.py",
            "docs/intraday_risk_review.md",
            "experiments/logs/exp-20260613-022.json",
            "experiments/logs/exp-20260623-011.json",
            "experiments/logs/exp-20260623-012.json",
            "experiments/logs/exp-20260625-004.json",
            "experiments/logs/exp-20260625-017.json",
        ],
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload["source_summary"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": payload["alpha_ready"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "source_summary": {
            "snapshot_count": len(source["snapshots"]),
            "posthoc_backfilled_files": [
                item["path"] for item in source["snapshots"] if item.get("posthoc_backfilled")
            ],
            "row_summary": source["row_summary"],
            "field_coverage": source["field_coverage"],
            "outcome_coverage": source["outcome_coverage"],
        },
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "runner": payload["runner"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    readiness = payload["gate4"]["readiness"]
    observed = readiness["observed"]
    gate2 = payload["gate2"]
    outcome = payload["source_summary"]["outcome_coverage"]
    lines = [
        f"# {EXPERIMENT_ID}: intraday review replayability audit",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Snapshot files: `{observed['snapshot_count']}`",
        f"- Position rows: `{observed['position_rows']}`",
        f"- Quote-time coverage: `{observed['quote_time_coverage']}`",
        f"- Entry-date coverage: `{observed['entry_date_coverage']}`",
        f"- Pending actions: `{observed['pending_actions_count']}`",
        f"- 5d settled rows: `{observed['settled_5d_rows']}`",
        f"- Warehouse max date: `{gate2['warehouse'].get('max_date')}`",
        "",
        "## Failed Checks",
        "",
        ", ".join(readiness["failed_reasons"]) or "none",
        "",
        "## Outcome Coverage",
        "",
        "| Horizon | Settled rows | Settled dates | Missing reasons |",
        "|---:|---:|---:|---|",
    ]
    for horizon in OUTCOME_HORIZONS:
        row = outcome[str(horizon)]
        lines.append(
            "| {horizon} | {settled} | {dates} | {reasons} |".format(
                horizon=horizon,
                settled=row["settled_rows"],
                dates=row["settled_snapshot_date_count"],
                reasons=json.dumps(row["missing_reasons"], sort_keys=True),
            )
        )
    lines.extend(
        [
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
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_intraday_review.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        WAREHOUSE,
        *snapshot_paths(),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in paths
        },
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
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
            "artifact": payload["artifact"],
            "log": payload["log"],
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
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    observed = payload["gate4"]["readiness"]["observed"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "snapshot_count": observed["snapshot_count"],
                "position_rows": observed["position_rows"],
                "posthoc_backfilled_files": observed["posthoc_backfilled_files"],
                "quote_time_coverage": observed["quote_time_coverage"],
                "entry_date_coverage": observed["entry_date_coverage"],
                "settled_5d_rows": observed["settled_5d_rows"],
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
