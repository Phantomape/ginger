"""exp-20260530-006: SEC event-family burst attribution.

Read-only alpha discovery for an untried event-graph field:
``sec_same_event_family_burst_count_v1``. The experiment checks whether SEC
filings that occur during same-day, same-event-family filing bursts have better
10-trading-day forward outcomes than isolated filings.

No production strategy, backtester, ranking, sizing, exits, LLM/news, or order
path is changed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "exp-20260530-006"
STEM = "sec_event_family_burst_attribution"
RULE_VERSION = "sec_same_event_family_burst_count_v1"
BASE_NOTIONAL_USD = 10000.0
ROUND_TRIP_COST_BPS = 35.0
HOLD_TRADING_DAYS = 10
HIGH_BURST_MIN_UNIQUE_TICKERS = 3
MIN_HIGH_BURST_ROWS = 30
MIN_AVG_RETURN_LIFT = 0.015
MIN_AVG_PNL_LIFT = 150.0
MAX_TOP_POSITIVE_TICKER_SHARE = 0.50

SOURCE_EVENTS = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
WINDOWS = {
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    },
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
    },
}

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
ROWS_JSON = OUT_DIR / f"{STEM}_rows.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def _round(value: Any, digits: int = 6) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected object JSON at {_repo_rel(path)}")
    return data


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {_repo_rel(path)}:{line_number}") from exc
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _event_family_bucket(row: dict[str, Any]) -> str:
    form_base = str(row.get("form_base") or row.get("form_type") or "").upper()
    if form_base in {"10-K", "10-K/A"}:
        return "periodic_report_10k"
    if form_base in {"10-Q", "10-Q/A"}:
        return "periodic_report_10q"
    if form_base == "8-K":
        codes = {str(code) for code in row.get("eight_k_item_codes") or []}
        raw = str(row.get("items_raw") or "")
        if not codes and raw:
            codes = {item.strip() for item in raw.split(",") if item.strip()}
        if "2.02" in codes:
            return "earnings_8k"
        if "1.01" in codes:
            return "material_agreement_8k"
        if "5.02" in codes:
            return "leadership_8k"
        if "5.03" in codes:
            return "governance_8k"
        if "7.01" in codes:
            return "fd_8k"
        if "8.01" in codes:
            return "other_8k"
        return "other_8k"
    if form_base:
        return f"form_{form_base.lower().replace('-', '')}"
    return "unknown_sec_event"


def _dedupe_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        accession = str(row.get("accession_number") or "")
        usable_date = str(row.get("usable_trade_date") or "")
        key = (ticker, accession, usable_date)
        if not ticker or not accession or not usable_date or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _load_ohlcv(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path)
    ohlcv = payload.get("ohlcv")
    if not isinstance(ohlcv, dict):
        raise ValueError(f"missing ohlcv object in {_repo_rel(path)}")
    return {str(ticker).upper(): list(rows) for ticker, rows in ohlcv.items()}


def _date_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("Date"))[:10]: idx for idx, row in enumerate(rows)}


def _first_index_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if str(row.get("Date"))[:10] > date_value:
            return idx
    return None


def _forward_outcome(
    *,
    ticker: str,
    signal_date: str,
    snapshot: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker)
    spy_rows = snapshot.get("SPY")
    if not rows or not spy_rows:
        return None
    entry_idx = _first_index_after(rows, signal_date)
    if entry_idx is None:
        return None
    exit_idx = entry_idx + HOLD_TRADING_DAYS - 1
    if exit_idx >= len(rows):
        return None
    date_to_spy_idx = _date_index(spy_rows)
    entry_date = str(rows[entry_idx].get("Date"))[:10]
    exit_date = str(rows[exit_idx].get("Date"))[:10]
    spy_entry_idx = date_to_spy_idx.get(entry_date)
    spy_exit_idx = date_to_spy_idx.get(exit_date)
    try:
        entry_open = float(rows[entry_idx]["Open"])
        exit_close = float(rows[exit_idx]["Close"])
    except (KeyError, TypeError, ValueError):
        return None
    if entry_open <= 0:
        return None
    gross_return = exit_close / entry_open - 1.0
    net_return = gross_return - ROUND_TRIP_COST_BPS / 10000.0
    spy_return = None
    excess_return = None
    if spy_entry_idx is not None and spy_exit_idx is not None:
        try:
            spy_entry = float(spy_rows[spy_entry_idx]["Open"])
            spy_exit = float(spy_rows[spy_exit_idx]["Close"])
            if spy_entry > 0:
                spy_return = spy_exit / spy_entry - 1.0
                excess_return = net_return - spy_return
        except (KeyError, TypeError, ValueError):
            pass
    return {
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_open": _round(entry_open, 4),
        "exit_close": _round(exit_close, 4),
        "gross_return": _round(gross_return, 6),
        "net_return": _round(net_return, 6),
        "spy_return": _round(spy_return, 6),
        "excess_return_vs_spy": _round(excess_return, 6),
        "pnl": _round(BASE_NOTIONAL_USD * net_return, 4),
    }


def _window_for_date(date_value: str) -> tuple[str, dict[str, str | Path]] | None:
    for label, cfg in WINDOWS.items():
        if str(cfg["start"]) <= date_value <= str(cfg["end"]):
            return label, cfg
    return None


def _burst_bucket(unique_count: int) -> str:
    if unique_count <= 1:
        return "singleton"
    if unique_count == 2:
        return "small_burst_2"
    if unique_count <= 4:
        return "medium_burst_3_4"
    return "large_burst_5_plus"


def _build_burst_counts(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        date_value = str(row.get("usable_trade_date") or "")
        ticker = str(row.get("ticker") or "").upper()
        family = _event_family_bucket(row)
        if not date_value or not ticker:
            continue
        key = (date_value, family)
        item = grouped.setdefault(key, {"event_count": 0, "tickers": set()})
        item["event_count"] += 1
        item["tickers"].add(ticker)
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for key, item in grouped.items():
        unique_count = len(item["tickers"])
        out[key] = {
            "same_family_event_count": item["event_count"],
            "same_family_unique_ticker_count": unique_count,
            "same_family_burst_bucket": _burst_bucket(unique_count),
            "high_burst": unique_count >= HIGH_BURST_MIN_UNIQUE_TICKERS,
        }
    return out


def _analyze_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = _dedupe_events(_read_jsonl(SOURCE_EVENTS))
    snapshots = {
        label: _load_ohlcv(Path(cfg["snapshot"]))
        for label, cfg in WINDOWS.items()
    }
    burst_counts = _build_burst_counts(source_rows)
    analyzed: list[dict[str, Any]] = []
    skipped = Counter()
    missing_fields = Counter()
    for row in source_rows:
        ticker = str(row.get("ticker") or "").upper()
        signal_date = str(row.get("usable_trade_date") or "")
        if not ticker:
            missing_fields["ticker"] += 1
            continue
        if not signal_date:
            missing_fields["usable_trade_date"] += 1
            continue
        window_pair = _window_for_date(signal_date)
        if window_pair is None:
            skipped["outside_windows"] += 1
            continue
        window, _cfg = window_pair
        snapshot = snapshots[window]
        outcome = _forward_outcome(ticker=ticker, signal_date=signal_date, snapshot=snapshot)
        if outcome is None:
            skipped["missing_forward_outcome"] += 1
            continue
        family = _event_family_bucket(row)
        burst = burst_counts.get((signal_date, family), {})
        analyzed.append(
            {
                "ticker": ticker,
                "window": window,
                "usable_trade_date": signal_date,
                "accepted_at": row.get("accepted_at"),
                "accession_number": row.get("accession_number"),
                "form_base": row.get("form_base"),
                "form_type": row.get("form_type"),
                "eight_k_item_codes": row.get("eight_k_item_codes") or [],
                "event_family_bucket": family,
                "rule_version": RULE_VERSION,
                "base_notional_usd": BASE_NOTIONAL_USD,
                "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
                "hold_trading_days": HOLD_TRADING_DAYS,
                "same_family_event_count": burst.get("same_family_event_count", 1),
                "same_family_unique_ticker_count": burst.get(
                    "same_family_unique_ticker_count",
                    1,
                ),
                "same_family_burst_bucket": burst.get("same_family_burst_bucket", "singleton"),
                "high_burst": burst.get("high_burst", False),
                "known_at": (
                    "after_sec_accepted_at_and_after_usable_trade_date_close_before_next_open"
                ),
                **outcome,
            }
        )
    audit = {
        "source_rows": len(source_rows),
        "analyzed_rows": len(analyzed),
        "skipped": dict(sorted(skipped.items())),
        "missing_required_fields": dict(sorted(missing_fields.items())),
        "source_file": _repo_rel(SOURCE_EVENTS),
        "snapshot_files": {label: _repo_rel(Path(cfg["snapshot"])) for label, cfg in WINDOWS.items()},
    }
    return analyzed, audit


def _positive_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        pnl = float(row.get("pnl") or 0.0)
        if pnl > 0:
            by_ticker[str(row.get("ticker") or "")] += pnl
    total = sum(by_ticker.values())
    ranked = [
        {
            "ticker": ticker,
            "positive_pnl": _round(value, 4),
            "share": _round(value / total, 6) if total else None,
        }
        for ticker, value in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)
    ]
    return {
        "positive_pnl_total": _round(total, 4),
        "top_ticker": ranked[0]["ticker"] if ranked else None,
        "top_ticker_positive_share": ranked[0]["share"] if ranked else None,
        "by_ticker": ranked[:20],
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "total_pnl": 0.0,
            "avg_pnl": None,
            "median_pnl": None,
            "avg_return": None,
            "avg_excess_return_vs_spy": None,
            "win_rate": None,
            "positive_concentration": _positive_concentration([]),
        }
    pnls = [float(row.get("pnl") or 0.0) for row in rows]
    returns = [float(row.get("net_return") or 0.0) for row in rows]
    excess = [
        float(row.get("excess_return_vs_spy"))
        for row in rows
        if row.get("excess_return_vs_spy") is not None
    ]
    return {
        "count": len(rows),
        "total_pnl": _round(sum(pnls), 4),
        "avg_pnl": _round(sum(pnls) / len(pnls), 4),
        "median_pnl": _round(median(pnls), 4),
        "avg_return": _round(sum(returns) / len(returns), 6),
        "avg_excess_return_vs_spy": _round(sum(excess) / len(excess), 6) if excess else None,
        "win_rate": _round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 6),
        "positive_concentration": _positive_concentration(rows),
    }


def _summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_burst = {
        bucket: _summary([row for row in rows if row["same_family_burst_bucket"] == bucket])
        for bucket in ["singleton", "small_burst_2", "medium_burst_3_4", "large_burst_5_plus"]
    }
    high_rows = [row for row in rows if row.get("high_burst")]
    low_rows = [row for row in rows if not row.get("high_burst")]
    by_window: dict[str, dict[str, Any]] = {}
    for label in WINDOWS:
        window_rows = [row for row in rows if row["window"] == label]
        window_high = [row for row in window_rows if row.get("high_burst")]
        window_low = [row for row in window_rows if not row.get("high_burst")]
        by_window[label] = {
            "all": _summary(window_rows),
            "high_burst": _summary(window_high),
            "not_high_burst": _summary(window_low),
        }
    by_family = {
        family: _summary([row for row in rows if row["event_family_bucket"] == family])
        for family in sorted({row["event_family_bucket"] for row in rows})
    }
    return {
        "all": _summary(rows),
        "high_burst": _summary(high_rows),
        "not_high_burst": _summary(low_rows),
        "singleton": by_burst["singleton"],
        "by_burst_bucket": by_burst,
        "by_window": by_window,
        "by_event_family_bucket": by_family,
    }


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {
            "passed": False,
            "path": _repo_rel(OPEN_POSITIONS_JSON),
            "missing_file": True,
        }
    payload = _load_json(OPEN_POSITIONS_JSON)
    rows = []
    for key in ("observations", "positions"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))
    missing: dict[str, list[str]] = {}
    for field in ("entry_date", "target_price"):
        bad = [
            str(row.get("ticker") or "<unknown>")
            for row in rows
            if row.get(field) in (None, "")
        ]
        if bad:
            missing[field] = bad
    return {
        "passed": not missing,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_like_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_fields": missing,
    }


def _decision(summary: dict[str, Any]) -> tuple[str, str, dict[str, Any], str, str | None]:
    high = summary["high_burst"]
    singleton = summary["singleton"]
    windows = summary["by_window"]
    high_count_ok = high["count"] >= MIN_HIGH_BURST_ROWS
    avg_return_lift = (
        high["avg_return"] - singleton["avg_return"]
        if high["avg_return"] is not None and singleton["avg_return"] is not None
        else None
    )
    avg_pnl_lift = (
        high["avg_pnl"] - singleton["avg_pnl"]
        if high["avg_pnl"] is not None and singleton["avg_pnl"] is not None
        else None
    )
    return_lift_ok = avg_return_lift is not None and avg_return_lift >= MIN_AVG_RETURN_LIFT
    pnl_lift_ok = avg_pnl_lift is not None and avg_pnl_lift >= MIN_AVG_PNL_LIFT
    concentration_share = high["positive_concentration"]["top_ticker_positive_share"]
    concentration_ok = (
        concentration_share is not None
        and concentration_share <= MAX_TOP_POSITIVE_TICKER_SHARE
    )
    window_lift_count = 0
    for row in windows.values():
        wh = row["high_burst"]
        wl = row["not_high_burst"]
        if (
            wh["avg_pnl"] is not None
            and wl["avg_pnl"] is not None
            and wh["avg_pnl"] > wl["avg_pnl"]
        ):
            window_lift_count += 1
    window_stability_ok = window_lift_count >= 2
    passed = (
        high_count_ok
        and return_lift_ok
        and pnl_lift_ok
        and concentration_ok
        and window_stability_ok
    )
    evidence = {
        "field_candidate_passed": passed,
        "high_count_ok": high_count_ok,
        "high_burst_count": high["count"],
        "min_high_burst_rows": MIN_HIGH_BURST_ROWS,
        "avg_return_lift_vs_singleton": _round(avg_return_lift, 6),
        "min_avg_return_lift": MIN_AVG_RETURN_LIFT,
        "return_lift_ok": return_lift_ok,
        "avg_pnl_lift_vs_singleton": _round(avg_pnl_lift, 4),
        "min_avg_pnl_lift": MIN_AVG_PNL_LIFT,
        "pnl_lift_ok": pnl_lift_ok,
        "top_ticker_positive_share": concentration_share,
        "max_top_positive_ticker_share": MAX_TOP_POSITIVE_TICKER_SHARE,
        "concentration_ok": concentration_ok,
        "window_lift_count": window_lift_count,
        "min_window_lift_count": 2,
        "window_stability_ok": window_stability_ok,
    }
    if passed:
        return (
            "observed_only_candidate_sec_event_family_burst_field",
            "observed_only",
            evidence,
            (
                "Same-day SEC event-family bursts produced enough 10-day forward "
                "separation to justify a later production-visible event-graph field "
                "or default-off queue experiment. No live behavior changed."
            ),
            None,
        )
    failed = [
        name
        for name in [
            "high_count_ok",
            "return_lift_ok",
            "pnl_lift_ok",
            "concentration_ok",
            "window_stability_ok",
        ]
        if not evidence[name]
    ]
    reason = "failed checks: " + ", ".join(failed)
    return (
        "rejected_sec_event_family_burst_field",
        "rejected",
        evidence,
        (
            "The untried SEC event-family burst field did not clear the pre-set "
            f"read-only promotion screen ({reason}). Do not create an event-graph "
            "sleeve from same-family burst count alone."
        ),
        reason,
    )


def _existing_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    try:
        return _load_json(TICKET_JSON)
    except json.JSONDecodeError:
        return {}


def _calibration(ticket: dict[str, Any], actual_success: int, decision: str, reason: str | None) -> dict[str, Any]:
    prediction = ticket.get("prediction") or {}
    probability = prediction.get("success_probability")
    brier = None
    if probability is not None:
        brier = _round((float(probability) - actual_success) ** 2, 6)
    predicted_modes = prediction.get("main_failure_modes") or []
    realized_mode = "weak_burst_separation" if actual_success == 0 else None
    return {
        "actual_decision": decision,
        "actual_success": actual_success,
        "predicted_success_probability": probability,
        "brier_score": brier,
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "actual_ev_delta": 0.0,
        "ev_prediction_error": 0.0,
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_pnl_delta": 0.0,
        "pnl_prediction_error": 0.0,
        "predicted_failure_modes": predicted_modes,
        "realized_failure_mode": realized_mode or reason,
        "predicted_failure_mode_hit": realized_mode in predicted_modes if realized_mode else None,
    }


def _build_payload() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    created_at = _now()
    ticket = _existing_ticket()
    rows, audit = _analyze_events()
    summary = _summaries(rows)
    decision, status, evidence, summary_text, rejection_reason = _decision(summary)
    actual_success = 1 if evidence["field_candidate_passed"] else 0
    open_positions_audit = _audit_open_positions()
    field_audit = {
        "passed": audit["analyzed_rows"] > 0 and not audit["missing_required_fields"],
        "source_file": audit["source_file"],
        "required_source_fields": [
            "ticker",
            "usable_trade_date",
            "accession_number",
            "accepted_at",
            "form_base",
        ],
        "missing_required_fields": audit["missing_required_fields"],
        "analyzed_rows": audit["analyzed_rows"],
        "skipped": audit["skipped"],
    }
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(SOURCE_EVENTS),
        *[_repo_rel(Path(cfg["snapshot"])) for cfg in WINDOWS.values()],
        _repo_rel(OUT_JSON),
        _repo_rel(ROWS_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(DOCS_TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(MANIFEST_JSON),
    ]
    before_metrics = summary["singleton"]
    after_metrics = summary["high_burst"]
    delta_metrics = {
        "avg_return": evidence["avg_return_lift_vs_singleton"],
        "avg_pnl": evidence["avg_pnl_lift_vs_singleton"],
        "count": after_metrics["count"] - before_metrics["count"],
        "expected_value_score": 0.0,
        "total_pnl_usd": 0.0,
        "strategy_logic_changed": False,
    }
    return (
        {
            "experiment_id": EXPERIMENT_ID,
            "created_at": created_at,
            "timestamp": created_at,
            "status": status,
            "decision": decision,
            "lane": "alpha_discovery",
            "registry_lane": "alpha_discovery",
            "hypothesis": ticket.get("hypothesis")
            or (
                "Same-day SEC event-family bursts may identify event-interaction "
                "attention clusters whose 10-day forward returns beat isolated filings."
            ),
            "change_summary": (
                "Read-only attribution of SEC filings by same-day same-event-family "
                "burst count using fixed $10k next-open to 10-trading-day-close "
                "forward outcomes."
            ),
            "change_type": "read_only_event_graph_attribution",
            "mechanism_family": "sec_event_interaction_graph",
            "trial_family": "sec_same_event_family_burst_attribution",
            "trial_variant_id": RULE_VERSION,
            "changed_variable": RULE_VERSION,
            "single_causal_variable": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260418-002",
                "exp-20260511-100",
                "exp-20260526-032",
                "exp-20260529-010",
                "exp-20260529-011",
            ],
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": "new_event_interaction_graph_field",
            "summary": summary_text,
            "source_audit": audit,
            "preflight_questions": {
                "1_alpha_hypothesis": (
                    "alpha_discovery/event graph: same-day SEC event-family burst "
                    "may identify market-wide attention clusters."
                ),
                "2_history_check": (
                    "Nearby SEC text/guidance and peer-transfer experiments exist, "
                    "but no same-family burst-count event graph field was found."
                ),
                "3_single_causal_variable": RULE_VERSION,
                "4_acceptance_standard": (
                    "High-burst bucket >=30 closed outcomes, materially better avg "
                    "10d return/PnL than singleton, non-concentrated positive PnL, "
                    "and at least two windows with high-burst avg PnL above low-burst."
                ),
                "5_reproducibility": (
                    ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260530_006_sec_event_family_burst_attribution.py"
                ),
            },
            "backtest_protocol": {
                "source": "docs/backtesting.md canonical windows; read-only event attribution",
                "windows": {
                    label: {
                        "start": cfg["start"],
                        "end": cfg["end"],
                        "snapshot": _repo_rel(Path(cfg["snapshot"])),
                    }
                    for label, cfg in WINDOWS.items()
                },
                "baseline_result_file": _repo_rel(SOURCE_EVENTS),
                "entry": "next available open after usable_trade_date",
                "exit": "close after 10 trading days from entry",
                "base_notional_usd": BASE_NOTIONAL_USD,
                "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
                "strategy_replacement_tested": False,
                "changed_core_logic": False,
            },
            "gate1": {
                "passed": SOURCE_EVENTS.exists() and all(Path(cfg["snapshot"]).exists() for cfg in WINDOWS.values()),
                "baseline_result_file": _repo_rel(SOURCE_EVENTS),
                "source_rows": audit["source_rows"],
                "analyzed_rows": audit["analyzed_rows"],
                "core_logic_changed": False,
            },
            "gate2": {
                "passed": open_positions_audit.get("passed") is True and field_audit["passed"],
                "open_positions": open_positions_audit,
                "source_fields": field_audit,
                "required_runtime_fields": ["entry_date", "target_price"],
                "no_llm_prompt_dependency": True,
            },
            "gate3": {
                "passed": True,
                "new_core_filter_added": False,
                "candidate_pool_changed": False,
                "core_survival_changed": False,
                "note": "Read-only attribution; no filter or survival-changing rule added.",
            },
            "gate4": {
                "passed": evidence["field_candidate_passed"],
                "strategy_replacement_tested": False,
                "promotion_grade": False,
                "decision_evidence": evidence,
                "reason": rejection_reason,
            },
            "parameters": {
                "rule_version": RULE_VERSION,
                "high_burst_min_unique_tickers": HIGH_BURST_MIN_UNIQUE_TICKERS,
                "min_high_burst_rows": MIN_HIGH_BURST_ROWS,
                "min_avg_return_lift": MIN_AVG_RETURN_LIFT,
                "min_avg_pnl_lift": MIN_AVG_PNL_LIFT,
                "max_top_positive_ticker_share": MAX_TOP_POSITIVE_TICKER_SHARE,
                "hold_trading_days": HOLD_TRADING_DAYS,
                "base_notional_usd": BASE_NOTIONAL_USD,
                "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
            },
            "date_range": {"start": "2024-10-02", "end": "2026-04-21"},
            "secondary_windows": [
                {"start": "2025-04-23", "end": "2025-10-22"},
                {"start": "2025-10-23", "end": "2026-04-21"},
            ],
            "market_regime_summary": {
                label: f"{cfg['start']} to {cfg['end']}" for label, cfg in WINDOWS.items()
            },
            "before_metrics": before_metrics,
            "after_metrics": after_metrics,
            "delta_metrics": delta_metrics,
            "bucket_summaries": summary,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_attribution_only": True,
                "orders_changed": False,
                "live_capital_changed": False,
                "trade_enabled": False,
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_exits": False,
                "alters_orders": False,
            },
            "prediction": ticket.get("prediction"),
            "calibration": _calibration(ticket, actual_success, decision, rejection_reason),
            "rejection_reason": rejection_reason,
            "next_retry_requires": []
            if actual_success
            else [
                "richer event graph relation such as sector/theme mapping or source overlap",
                "separate treatment of periodic reports versus 8-K events",
                "forward replacement-value rows before a paper sleeve",
            ],
            "related_files": related_files,
            "repro_command": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260530_006_sec_event_family_burst_attribution.py"
            ),
            "artifacts": {
                "json": _repo_rel(OUT_JSON),
                "rows": _repo_rel(ROWS_JSON),
                "log": _repo_rel(LOG_JSON),
                "ticket": _repo_rel(TICKET_JSON),
                "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
                "card": _repo_rel(CARD_MD),
                "markdown": _repo_rel(ARTIFACT_MD),
                "manifest": _repo_rel(MANIFEST_JSON),
            },
            "why_not_other_changes": (
                "Skipped VCP/Kova, Companyfacts scalar, state-surface, and OHLCV "
                "pattern-name retunes because those families are frozen or require "
                "forward rows. This tests a new event-interaction field only."
            ),
            "anti_js": "No JavaScript was used.",
        },
        rows,
    )


def _compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    evidence = payload["gate4"]["decision_evidence"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Event-Family Burst Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Gate 4 Evidence",
        "",
        "```json",
        json.dumps(evidence, indent=2, sort_keys=True),
        "```",
        "",
        "## Core Buckets",
        "",
        "| bucket | count | avg pnl | avg return | win rate | top positive share |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for bucket, row in payload["bucket_summaries"]["by_burst_bucket"].items():
        lines.append(
            "| {bucket} | {count} | {avg_pnl} | {avg_return} | {win_rate} | {share} |".format(
                bucket=bucket,
                count=row["count"],
                avg_pnl=row["avg_pnl"],
                avg_return=row["avg_return"],
                win_rate=row["win_rate"],
                share=row["positive_concentration"]["top_ticker_positive_share"],
            )
        )
    lines.extend(
        [
            "",
            "## Window Summary",
            "",
            "| window | high count | high avg pnl | low avg pnl | high win rate | low win rate |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for window, row in payload["bucket_summaries"]["by_window"].items():
        lines.append(
            "| {window} | {hc} | {hp} | {lp} | {hw} | {lw} |".format(
                window=window,
                hc=row["high_burst"]["count"],
                hp=row["high_burst"]["avg_pnl"],
                lp=row["not_high_burst"]["avg_pnl"],
                hw=row["high_burst"]["win_rate"],
                lw=row["not_high_burst"]["win_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Repro",
            "",
            "```powershell",
            payload["repro_command"],
            "```",
            "",
            "## Related Files",
            "",
        ]
    )
    lines.extend(f"- `{path}`" for path in payload["related_files"])
    lines.append("")
    return "\n".join(lines)


def _build_card(payload: dict[str, Any]) -> str:
    evidence = payload["gate4"]["decision_evidence"]
    lines = [
        "---",
        f'experiment_id: "{EXPERIMENT_ID}"',
        f'experiment_uid: "{_existing_ticket().get("experiment_uid")}"',
        f'status: "{payload["status"]}"',
        'lane: "alpha_discovery"',
        'change_type: "read_only_event_graph_attribution"',
        'mechanism_family: "sec_event_interaction_graph"',
        'trial_family: "sec_same_event_family_burst_attribution"',
        f'trial_variant_id: "{RULE_VERSION}"',
        f'changed_variable: "{RULE_VERSION}"',
        'new_evidence_type: "new_event_interaction_graph_field"',
        f'updated_at: "{payload["created_at"]}"',
        'hub_repo_id: "ginger/experiments/exp-20260530-006"',
        "---",
        "",
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        "## Summary",
        "",
        payload["summary"],
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- High-burst count: `{evidence['high_burst_count']}`",
        f"- Avg PnL lift vs singleton: `{evidence['avg_pnl_lift_vs_singleton']}`",
        f"- Avg return lift vs singleton: `{evidence['avg_return_lift_vs_singleton']}`",
        f"- Window lift count: `{evidence['window_lift_count']}`",
        "",
        "## Reserved Files",
        "",
    ]
    lines.extend(f"- `{path}`" for path in payload["related_files"])
    lines.append("")
    return "\n".join(lines)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_compact_payload(payload), ensure_ascii=False, sort_keys=True)
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _update_registry(payload: dict[str, Any], ticket: dict[str, Any]) -> None:
    registry = _load_json(EXPERIMENT_REGISTRY) if EXPERIMENT_REGISTRY.exists() else {}
    registry.setdefault("schema_version", 1)
    experiments = registry.setdefault("experiments", [])
    row = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "lane": payload["registry_lane"],
        "owner": ticket.get("owner") or "codex",
        "hypothesis": payload["hypothesis"],
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "log_file": _repo_rel(LOG_JSON),
        "updated_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["summary"],
        },
    }
    for idx, item in enumerate(experiments):
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = {**item, **row}
            break
    else:
        experiments.append(row)
    registry["updated_at"] = payload["created_at"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _save_manifest(ticket: dict[str, Any]) -> None:
    from scripts.experiment_registry import save_revision_manifest  # noqa: PLC0415

    save_revision_manifest(
        ticket,
        repo_root=REPO_ROOT,
        ticket_file=TICKET_JSON,
        card_file=CARD_MD,
        overwrite=True,
    )


def _persist(payload: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    existing = _existing_ticket()
    ticket = {
        **existing,
        "artifact_file": _repo_rel(OUT_JSON),
        "baseline_result_file": _repo_rel(SOURCE_EVENTS),
        "change_type": payload["change_type"],
        "completed_at": payload["created_at"],
        "decision": payload["decision"],
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["hypothesis"],
        "lane": payload["lane"],
        "mechanism_family": payload["mechanism_family"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "new_evidence_type": payload["new_evidence_type"],
        "owner": existing.get("owner") or "codex",
        "prior_trial_count": payload["prior_trial_count"],
        "result_file": _repo_rel(LOG_JSON),
        "report_file": _repo_rel(ARTIFACT_MD),
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "status": payload["status"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "updated_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["summary"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "calibration": payload["calibration"],
        },
        "summary": payload["summary"],
        "artifacts": payload["artifacts"],
        "repro_command": payload["repro_command"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
    }
    _write_json(OUT_JSON, payload)
    _write_json(ROWS_JSON, {"experiment_id": EXPERIMENT_ID, "rows": rows})
    _write_json(LOG_JSON, _compact_payload(payload))
    _write_json(TICKET_JSON, ticket)
    _write_json(DOCS_TICKET_JSON, ticket)
    _write_text(CARD_MD, _build_card(payload))
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry(payload, ticket)
    _save_manifest(ticket)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()
    payload, rows = _build_payload()
    if not args.no_persist:
        _persist(payload, rows)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "status": payload["status"],
                "gate2_passed": payload["gate2"]["passed"],
                "gate4_passed": payload["gate4"]["passed"],
                "analyzed_rows": payload["source_audit"]["analyzed_rows"],
                "high_burst_count": payload["gate4"]["decision_evidence"]["high_burst_count"],
                "avg_pnl_lift_vs_singleton": payload["gate4"]["decision_evidence"][
                    "avg_pnl_lift_vs_singleton"
                ],
                "avg_return_lift_vs_singleton": payload["gate4"]["decision_evidence"][
                    "avg_return_lift_vs_singleton"
                ],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
