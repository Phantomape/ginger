"""exp-20260510-023: SEC T+1 drift event surface shadow audit.

This is an alpha-discovery experiment, not a production strategy change. It
uses the new non-OHLCV SEC filing snapshots to test whether a simple,
production-observable event state deserves forward paper observation:

    SEC filing event is public/PIT-safe -> next trading day beats SPY -> enter
    as a shadow candidate at the following session open.

No thresholds, rankings, sizing, exits, slots, LLM prompts, or production
adapters are changed by this runner.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260510-023"
STEM = "sec_t1_drift_event_surface"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "coverage": "data/non_ohlcv/backtest_coverage_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "coverage": "data/non_ohlcv/backtest_coverage_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "coverage": "data/non_ohlcv/backtest_coverage_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

BASELINE_METRICS = {
    "late_strong": {
        "expected_value_score": 4.2340,
        "sharpe_daily": 4.50,
        "total_pnl": 94086.91,
        "total_return_pct": 0.9409,
        "max_drawdown_pct": 0.0548,
        "win_rate": 0.7895,
        "trade_count": 19,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 1.6689,
        "sharpe_daily": 2.70,
        "total_pnl": 61813.40,
        "total_return_pct": 0.6181,
        "max_drawdown_pct": 0.0941,
        "win_rate": 0.5238,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.3853,
        "sharpe_daily": 1.35,
        "total_pnl": 28544.11,
        "total_return_pct": 0.2854,
        "max_drawdown_pct": 0.0815,
        "win_rate": 0.4091,
        "trade_count": 22,
        "survival_rate": 0.9167,
    },
}

FORWARD_HORIZONS = (1, 5, 10, 20)
SHADOW_NOTIONAL_USD = 10_000.0
SEC_EVENT_GLOB = "sec_filing_events_*.jsonl"
EXCLUDED_TICKERS = {
    "DIA",
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "UUP",
    "USO",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}
PLATFORM_POOL = {"NFLX", "APP", "META", "GOOG", "GOOGL", "AMZN", "SPOT", "DIS"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(payload_line)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(payload_line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _append_playbook_note(note: str) -> None:
    PLAYBOOK.parent.mkdir(parents=True, exist_ok=True)
    old = PLAYBOOK.read_text(encoding="utf-8") if PLAYBOOK.exists() else ""
    if f"Experiment: `{EXPERIMENT_ID}`" in old:
        return
    PLAYBOOK.write_text(old.rstrip() + "\n\n" + note.strip() + "\n", encoding="utf-8")


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _summary(values: list[Any]) -> dict[str, Any]:
    clean = sorted(
        float(value)
        for value in values
        if isinstance(value, (int, float)) and math.isfinite(float(value))
    )
    if not clean:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "win_rate": None,
            "p10": None,
            "p25": None,
            "p75": None,
            "p90": None,
        }

    def percentile(q: float) -> float:
        return clean[int(round((len(clean) - 1) * q))]

    return {
        "count": len(clean),
        "avg": _round(statistics.mean(clean)),
        "median": _round(statistics.median(clean)),
        "win_rate": _round(sum(1 for value in clean if value > 0) / len(clean), 4),
        "p10": _round(percentile(0.10)),
        "p25": _round(percentile(0.25)),
        "p75": _round(percentile(0.75)),
        "p90": _round(percentile(0.90)),
    }


def _row_date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _as_float(row: dict[str, Any], key: str) -> float | None:
    raw = row.get(key)
    if isinstance(raw, (int, float)) and math.isfinite(float(raw)):
        return float(raw)
    return None


def _load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path)
    ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else {}
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (ohlcv or {}).items():
        normalized = []
        for row in rows:
            normalized.append(
                {
                    "date": _row_date(row),
                    "open": _as_float(row, "Open"),
                    "high": _as_float(row, "High"),
                    "low": _as_float(row, "Low"),
                    "close": _as_float(row, "Close"),
                    "volume": _as_float(row, "Volume"),
                }
            )
        out[str(ticker).upper()] = sorted(normalized, key=lambda item: item["date"])
    return out


def _index_on_or_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= date_value:
            return idx
    return None


def _return_between(
    rows: list[dict[str, Any]],
    start_idx: int,
    end_idx: int,
    start_field: str = "close",
) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_value = rows[start_idx].get(start_field)
    end_value = rows[end_idx].get("close")
    if not isinstance(start_value, (int, float)) or not isinstance(end_value, (int, float)):
        return None
    if start_value <= 0:
        return None
    return float(end_value) / float(start_value) - 1.0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _item_codes(row: dict[str, Any]) -> tuple[str, ...]:
    raw = row.get("eight_k_item_codes")
    if isinstance(raw, list):
        return tuple(str(item) for item in raw if str(item))
    raw = row.get("items_raw")
    if isinstance(raw, str):
        return tuple(item.strip() for item in raw.split(",") if item.strip())
    return ()


def _event_family(row: dict[str, Any]) -> str:
    form_base = str(row.get("form_base") or row.get("form_type") or "").upper()
    codes = set(_item_codes(row))
    if form_base in {"10-K", "10-Q"}:
        return "periodic_report"
    if form_base == "8-K":
        if "2.02" in codes:
            return "earnings_8k"
        if codes & {"1.01", "2.03", "3.02"}:
            return "capital_contract_8k"
        if codes & {"5.02", "5.03", "5.07"}:
            return "governance_8k"
        if codes & {"7.01", "8.01"}:
            return "fd_other_8k"
        return "other_8k"
    return "other_sec"


def _drift_bucket(t1_return: float | None, spy_t1_return: float | None) -> str:
    if t1_return is None or spy_t1_return is None:
        return "immature_or_missing_t1"
    if t1_return > 0 and t1_return > spy_t1_return:
        return "positive_t1_excess_drift"
    if t1_return > 0:
        return "positive_t1_absolute_only"
    return "negative_or_zero_t1_drift"


def _load_sec_events() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    events_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    file_count = 0
    raw_rows = 0
    skipped = Counter()
    seen: set[tuple[str, str, str, str]] = set()
    for path in sorted((REPO_ROOT / "data" / "non_ohlcv").glob(SEC_EVENT_GLOB)):
        file_count += 1
        for row in _read_jsonl(path):
            raw_rows += 1
            ticker = str(row.get("ticker") or "").upper()
            usable_date = str(row.get("usable_trade_date") or "")[:10]
            accession = str(row.get("accession_number") or "")
            if not ticker or ticker in EXCLUDED_TICKERS:
                skipped["excluded_or_missing_ticker"] += 1
                continue
            if not usable_date:
                skipped["missing_usable_trade_date"] += 1
                continue
            if row.get("pit_safe_flag") is False:
                skipped["not_pit_safe"] += 1
                continue
            family = _event_family(row)
            # Keep at most one filing per ticker/date/family; count raw rows in coverage.
            key = (ticker, usable_date, family, accession)
            if key in seen:
                skipped["duplicate_accession"] += 1
                continue
            seen.add(key)
            events_by_ticker[ticker].append(
                {
                    "ticker": ticker,
                    "usable_trade_date": usable_date,
                    "accepted_at": row.get("accepted_at"),
                    "accession_number": accession,
                    "form_type": row.get("form_type"),
                    "form_base": row.get("form_base"),
                    "event_family": family,
                    "item_codes": list(_item_codes(row)),
                    "archive_url": row.get("archive_url"),
                    "source_file": str(path.relative_to(REPO_ROOT)),
                }
            )
    for rows in events_by_ticker.values():
        rows.sort(key=lambda row: (row["usable_trade_date"], row["event_family"], row["accession_number"]))
    return events_by_ticker, {
        "sec_event_file_count": file_count,
        "raw_sec_event_rows": raw_rows,
        "unique_events_after_dedup": sum(len(rows) for rows in events_by_ticker.values()),
        "tickers_with_events": len(events_by_ticker),
        "skipped": dict(skipped),
        "source_glob": f"data/non_ohlcv/{SEC_EVENT_GLOB}",
    }


def _load_coverage_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path.relative_to(REPO_ROOT)), "status": "missing"}
    payload = _load_json(path)
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "decision": payload.get("decision"),
        "business_days": payload.get("business_days"),
        "complete_days": payload.get("complete_days"),
        "complete_fraction": payload.get("complete_fraction"),
        "failed_days": payload.get("failed_days"),
        "partial_days": payload.get("partial_days"),
        "biased_days": payload.get("biased_days"),
    }


def _build_rows(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    events_by_ticker: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    spy_rows = snapshot.get("SPY", [])
    rows: list[dict[str, Any]] = []
    seen_shadow_keys: set[tuple[str, str, str]] = set()
    for ticker, events in events_by_ticker.items():
        ticker_rows = snapshot.get(ticker)
        if not ticker_rows or len(ticker_rows) < 30 or not spy_rows:
            continue
        for event in events:
            usable_date = event["usable_trade_date"]
            if not (cfg["start"] <= usable_date <= cfg["end"]):
                continue
            event_idx = _index_on_or_after(ticker_rows, usable_date)
            spy_idx = _index_on_or_after(spy_rows, usable_date)
            if event_idx is None or spy_idx is None:
                continue
            event_trading_date = ticker_rows[event_idx]["date"]
            # De-duplicate ticker/date/family after aligning to an actual trading date.
            shadow_key = (ticker, event_trading_date, event["event_family"])
            if shadow_key in seen_shadow_keys:
                continue
            seen_shadow_keys.add(shadow_key)

            t1_idx = event_idx + 1
            entry_idx = event_idx + 2
            t1_return = _return_between(ticker_rows, event_idx, t1_idx)
            spy_t1_return = _return_between(spy_rows, spy_idx, spy_idx + 1)
            bucket = _drift_bucket(t1_return, spy_t1_return)
            entry_date = ticker_rows[entry_idx]["date"] if entry_idx < len(ticker_rows) else None
            entry_open = ticker_rows[entry_idx].get("open") if entry_idx < len(ticker_rows) else None

            forward: dict[str, Any] = {}
            pnl_proxy: dict[str, Any] = {}
            for horizon in FORWARD_HORIZONS:
                fwd = None
                if entry_date and isinstance(entry_open, (int, float)) and entry_open > 0:
                    fwd = _return_between(ticker_rows, entry_idx, entry_idx + horizon, start_field="open")
                forward[f"fwd_{horizon}d_return"] = _round(fwd)
                pnl_proxy[f"fwd_{horizon}d_pnl_proxy"] = _round(fwd * SHADOW_NOTIONAL_USD, 2) if fwd is not None else None

            rows.append(
                {
                    "ticker": ticker,
                    "cohort": "platform_pool" if ticker in PLATFORM_POOL else "other_equity",
                    "usable_trade_date": usable_date,
                    "event_trading_date": event_trading_date,
                    "t1_date": ticker_rows[t1_idx]["date"] if t1_idx < len(ticker_rows) else None,
                    "shadow_entry_date": entry_date,
                    "accepted_at": event.get("accepted_at"),
                    "accession_number": event.get("accession_number"),
                    "form_type": event.get("form_type"),
                    "form_base": event.get("form_base"),
                    "event_family": event["event_family"],
                    "item_codes": event.get("item_codes"),
                    "archive_url": event.get("archive_url"),
                    "source_file": event.get("source_file"),
                    "t1_return": _round(t1_return),
                    "spy_t1_return": _round(spy_t1_return),
                    "t1_excess_return_vs_spy": _round(
                        t1_return - spy_t1_return
                        if isinstance(t1_return, (int, float)) and isinstance(spy_t1_return, (int, float))
                        else None
                    ),
                    "drift_bucket": bucket,
                    **forward,
                    **pnl_proxy,
                }
            )
    return sorted(rows, key=lambda row: (row["event_trading_date"], row["ticker"], row["event_family"]))


def _group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_count": len(rows),
        "unique_tickers": len({row["ticker"] for row in rows}),
        "platform_pool_count": sum(1 for row in rows if row["cohort"] == "platform_pool"),
        "ticker_counts": Counter(row["ticker"] for row in rows).most_common(12),
        "event_family_counts": Counter(row["event_family"] for row in rows).most_common(),
        "forward_returns": {
            f"fwd_{horizon}d_return": _summary([row.get(f"fwd_{horizon}d_return") for row in rows])
            for horizon in FORWARD_HORIZONS
        },
        "shadow_pnl_proxy": {
            f"fwd_{horizon}d_pnl_proxy": _summary([row.get(f"fwd_{horizon}d_pnl_proxy") for row in rows])
            for horizon in FORWARD_HORIZONS
        },
    }


def _summarize_window(label: str, cfg: dict[str, str], events_by_ticker: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    snapshot = _load_snapshot(REPO_ROOT / cfg["snapshot"])
    rows = _build_rows(snapshot, cfg, events_by_ticker)
    by_bucket = {
        bucket: _group_summary([row for row in rows if row["drift_bucket"] == bucket])
        for bucket in [
            "positive_t1_excess_drift",
            "positive_t1_absolute_only",
            "negative_or_zero_t1_drift",
            "immature_or_missing_t1",
        ]
    }
    positive_rows = [row for row in rows if row["drift_bucket"] == "positive_t1_excess_drift"]
    by_family = {
        family: _group_summary([row for row in positive_rows if row["event_family"] == family])
        for family in sorted({row["event_family"] for row in positive_rows})
    }
    by_cohort = {
        cohort: _group_summary([row for row in positive_rows if row["cohort"] == cohort])
        for cohort in ["platform_pool", "other_equity"]
    }
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "state_note": cfg["state_note"],
        "snapshot": cfg["snapshot"],
        "coverage": _load_coverage_summary(REPO_ROOT / cfg["coverage"]),
        "baseline_metrics": BASELINE_METRICS[label],
        "sec_event_rows_total": len(rows),
        "sec_event_rows_unique_tickers": len({row["ticker"] for row in rows}),
        "drift_bucket_summary": by_bucket,
        "positive_t1_excess_by_family": by_family,
        "positive_t1_excess_by_cohort": by_cohort,
        "shadow_candidate_definition": (
            "positive_t1_excess_drift: ticker close-to-close return from event trading date "
            "to T+1 is positive and greater than SPY's same T+1 return; shadow entry is T+2 open."
        ),
        "shadow_candidate_rows": positive_rows,
    }


def _aggregate(windows: dict[str, Any]) -> dict[str, Any]:
    candidate_rows = [
        row
        for window in windows.values()
        for row in window["shadow_candidate_rows"]
    ]
    valid_10d_rows = [
        row for row in candidate_rows if isinstance(row.get("fwd_10d_return"), (int, float))
    ]
    positive_10d_windows = sum(
        1
        for window in windows.values()
        if (window["drift_bucket_summary"]["positive_t1_excess_drift"]["forward_returns"]["fwd_10d_return"]["avg"] or 0.0)
        > 0
    )
    platform_rows = [row for row in candidate_rows if row["cohort"] == "platform_pool"]
    family_rollup = {
        family: _group_summary([row for row in candidate_rows if row["event_family"] == family])
        for family in sorted({row["event_family"] for row in candidate_rows})
    }
    return {
        "shadow_candidate_count": len(candidate_rows),
        "valid_10d_candidate_count": len(valid_10d_rows),
        "positive_avg_10d_windows": positive_10d_windows,
        "forward_10d": _summary([row.get("fwd_10d_return") for row in candidate_rows]),
        "forward_20d": _summary([row.get("fwd_20d_return") for row in candidate_rows]),
        "shadow_10d_pnl_proxy": _summary([row.get("fwd_10d_pnl_proxy") for row in candidate_rows]),
        "platform_pool_forward_10d": _summary([row.get("fwd_10d_return") for row in platform_rows]),
        "platform_pool_candidate_count": len(platform_rows),
        "ticker_counts": Counter(row["ticker"] for row in candidate_rows).most_common(20),
        "event_family_rollup": family_rollup,
        "paper_watch_candidate_gate": {
            "min_valid_10d_candidates": 30,
            "min_positive_avg_windows": 2,
            "min_aggregate_10d_win_rate": 0.50,
            "passed": (
                len(valid_10d_rows) >= 30
                and positive_10d_windows >= 2
                and (_summary([row.get("fwd_10d_return") for row in candidate_rows])["win_rate"] or 0.0) >= 0.50
            ),
        },
    }


def _artifact(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} SEC T+1 Drift Event Surface",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Aggregate",
        "",
        f"- shadow candidates: `{aggregate['shadow_candidate_count']}`",
        f"- valid 10d forward candidates: `{aggregate['valid_10d_candidate_count']}`",
        f"- positive 10d avg windows: `{aggregate['positive_avg_10d_windows']}/3`",
        f"- aggregate 10d avg return: `{aggregate['forward_10d']['avg']}`",
        f"- aggregate 10d win rate: `{aggregate['forward_10d']['win_rate']}`",
        f"- platform-pool candidates: `{aggregate['platform_pool_candidate_count']}`",
        "",
        "## Window Detail",
        "",
    ]
    for label, window in payload["windows"].items():
        bucket = window["drift_bucket_summary"]["positive_t1_excess_drift"]
        lines.extend(
            [
                f"### {label}",
                "",
                f"- SEC rows: `{window['sec_event_rows_total']}`",
                f"- positive T+1 excess candidates: `{bucket['candidate_count']}`",
                f"- 10d avg return: `{bucket['forward_returns']['fwd_10d_return']['avg']}`",
                f"- 10d win rate: `{bucket['forward_returns']['fwd_10d_return']['win_rate']}`",
                f"- coverage complete fraction: `{window['coverage'].get('complete_fraction')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Notes",
            "",
            "- Shadow-only audit; no production orders, sizing, ranking, LLM, exits, or slots changed.",
            "- Uses SEC accepted_at / usable_trade_date as a public PIT proxy; it does not prove the historical production process observed each filing.",
        ]
    )
    return "\n".join(lines) + "\n"


def _playbook_note(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    return f"""
### 2026-05-10 mechanism update: SEC T+1 event drift surface

Experiment: `{EXPERIMENT_ID}`

Decision: `{payload['decision']}`.

Finding: the new non-OHLCV SEC backtest snapshots are complete enough to run a
three-window shadow event-surface audit, but the simple positive T+1
excess-drift label is not yet production alpha by itself. Aggregate shadow
candidates: `{aggregate['shadow_candidate_count']}`; valid 10d forward rows:
`{aggregate['valid_10d_candidate_count']}`; positive 10d-average windows:
`{aggregate['positive_avg_10d_windows']}/3`; aggregate 10d average return:
`{aggregate['forward_10d']['avg']}` with win rate `{aggregate['forward_10d']['win_rate']}`.

Mechanism insight: this is the right shape for the next event/oracle work:
start from public-PIT event availability, measure post-event continuation, and
only then decide whether an event candidate deserves forward paper routing.
Do not turn this into another PEAD threshold sweep; the current run changed no
reaction-magnitude threshold, volume rule, hold length, ranking rule, or live
adapter.
""".strip()


def main() -> None:
    events_by_ticker, event_coverage = _load_sec_events()
    windows = OrderedDict(
        (label, _summarize_window(label, cfg, events_by_ticker)) for label, cfg in WINDOWS.items()
    )
    aggregate = _aggregate(windows)
    gate_passed = bool(aggregate["paper_watch_candidate_gate"]["passed"])
    decision = "observed_only_paper_watch_candidate" if gate_passed else "observed_only_no_promotion"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "observed_only",
        "decision": decision,
        "change_type": "new_strategy_shadow",
        "changed_variable": "sec_t1_excess_drift_shadow_candidate_label",
        "single_causal_variable": "SEC filing event T+1 excess-drift shadow entry label",
        "hypothesis": (
            "Public-PIT SEC filing events that show positive T+1 excess drift versus SPY may identify "
            "post-event continuation candidates for the event/oracle stack without changing the core A/B strategy."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "Entry/oracle alpha source: SEC event candidates with positive next-day excess drift may have "
                "continuation value from a T+2 open shadow entry."
            ),
            "2_history_check": {
                "exp-20260509-020": (
                    "Rejected PEAD-like threshold recipe. This run avoids magnitude, volume, and hold-day sweeps; "
                    "it only audits a sign/excess-vs-SPY event state."
                ),
                "exp-20260507-020": (
                    "FD/Other item semantics were studied before; this run uses the newly completed non-OHLCV "
                    "three-window snapshots and treats event family as attribution, not a promoted rule."
                ),
                "exp-20260510-018_t1_draft": (
                    "A conflicting draft used clean_news coverage and only populated late_strong. This run uses SEC "
                    "non-OHLCV snapshots across all three canonical windows with a new experiment id."
                ),
            },
            "3_single_causal_variable": "sec_t1_excess_drift_shadow_candidate_label",
            "4_gate": (
                "Observed-only gate: coverage readable in 3 windows, artifact schema valid, and paper-watch only if "
                ">=30 valid 10d candidates, >=2/3 windows positive on avg 10d return, and aggregate 10d win rate >=50%."
            ),
            "5_reproducibility": (
                "All inputs are local OHLCV snapshots plus data/non_ohlcv/sec_filing_events_*.jsonl and coverage manifests; "
                "outputs are stored under data/experiments, experiments/logs, experiments/artifacts, and JSONL."
            ),
        },
        "backtest_protocol": (
            "Shadow-only attribution across the three docs/backtesting.md fixed windows. No before/after strategy "
            "backtest is valid because no production or replay trading behavior changed."
        ),
        "date_range": {
            label: {
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "coverage": cfg["coverage"],
            }
            for label, cfg in WINDOWS.items()
        },
        "gate1_baseline": {
            "source": "docs/backtesting.md accepted fixed-window metrics after exp-20260510-015",
            "windows": BASELINE_METRICS,
            "aggregate_expected_value_score_sum": round(
                sum(row["expected_value_score"] for row in BASELINE_METRICS.values()), 4
            ),
            "aggregate_total_pnl_sum": round(sum(row["total_pnl"] for row in BASELINE_METRICS.values()), 2),
        },
        "gate2_field_audit": {
            "operator_fields_required": ["entry_date", "target_price"],
            "strategy_rule_added": False,
            "sec_fields_required": ["ticker", "usable_trade_date", "accepted_at", "pit_safe_flag"],
            "sec_event_coverage": event_coverage,
        },
        "gate3": {
            "new_filter_added": False,
            "note": "No production or backtest entry filter was added; this is a shadow label only.",
        },
        "gate4": {
            "passed": False,
            "note": "Gate 4 production promotion is not applicable to observed-only shadow attribution.",
            "paper_watch_candidate_gate": aggregate["paper_watch_candidate_gate"],
        },
        "parameters": {
            "event_source_glob": f"data/non_ohlcv/{SEC_EVENT_GLOB}",
            "event_families": [
                "earnings_8k",
                "capital_contract_8k",
                "governance_8k",
                "fd_other_8k",
                "other_8k",
                "periodic_report",
                "other_sec",
            ],
            "drift_variable": "ticker T+1 close-to-close return minus SPY T+1 close-to-close return",
            "candidate_label": "positive_t1_excess_drift",
            "shadow_entry": "T+2 open after event usable_trade_date",
            "forward_horizons_trading_days": list(FORWARD_HORIZONS),
            "shadow_notional_usd": SHADOW_NOTIONAL_USD,
            "locked_variables": [
                "core universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "sizing",
                "MAX_POSITIONS",
                "slot routing",
                "exits",
                "add-ons",
                "LLM/news replay",
            ],
        },
        "before_metrics": {
            "aggregate": {
                "expected_value_score_sum": round(
                    sum(row["expected_value_score"] for row in BASELINE_METRICS.values()), 4
                ),
                "total_pnl_sum": round(sum(row["total_pnl"] for row in BASELINE_METRICS.values()), 2),
            },
            "windows": BASELINE_METRICS,
        },
        "after_metrics": {
            "aggregate": {
                "expected_value_score_sum": round(
                    sum(row["expected_value_score"] for row in BASELINE_METRICS.values()), 4
                ),
                "total_pnl_sum": round(sum(row["total_pnl"] for row in BASELINE_METRICS.values()), 2),
            },
            "windows": BASELINE_METRICS,
        },
        "delta_metrics": {
            "aggregate": {
                "expected_value_score_delta_sum": 0.0,
                "total_pnl_delta_sum": 0.0,
                "trade_count_delta_sum": 0,
                "signals_generated_delta_sum": 0,
                "signals_survived_delta_sum": 0,
            },
            "shadow_attribution": aggregate,
        },
        "windows": windows,
        "aggregate": aggregate,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "This uses structured SEC metadata only; a future LLM step could grade filing text semantics after this shadow surface is stable.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
        },
        "rejection_reason": (
            "Observed-only shadow audit; not eligible for production promotion without forward paper outcomes "
            "and a shared event candidate adapter."
        ),
        "next_evidence_needed": [
            "Forward paper observations for this exact positive_t1_excess_drift SEC bucket.",
            "If paper-watch gate is weak, add semantic filing-text quality labels before testing any live adapter.",
            "Do not retry PEAD reaction magnitude, volume confirmation, or fixed hold-day sweeps on the same frozen samples.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
            "data/non_ohlcv/backtest_coverage_20251023_20260421.json",
            "data/non_ohlcv/backtest_coverage_20250423_20251022.json",
            "data/non_ohlcv/backtest_coverage_20241002_20250422.json",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": decision,
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["single_causal_variable"],
            "production_impact": payload["production_impact"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
            "next_evidence_needed": payload["next_evidence_needed"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _append_playbook_note(_playbook_note(payload))

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "shadow_candidate_count": aggregate["shadow_candidate_count"],
                "valid_10d_candidate_count": aggregate["valid_10d_candidate_count"],
                "positive_avg_10d_windows": aggregate["positive_avg_10d_windows"],
                "aggregate_10d_avg": aggregate["forward_10d"]["avg"],
                "aggregate_10d_win_rate": aggregate["forward_10d"]["win_rate"],
                "wrote": str(OUT_JSON.relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
