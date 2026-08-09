"""exp-20260713-008: ClinicalTrials.gov Phase 3 first-results full stack.

The candidate source is fixed before replay: twelve exact lead-sponsor names,
the first ACTUAL results-posted Record History version, issuer green and ahead
of SPY on the first eligible session, top one per day by excess return, a
ten-session same-ticker cooldown, next-open entry, tenth-session close, $4k,
and 35 bps round-trip costs.  Historical source payloads are frozen verbatim in
canonical JSON bytes and hashed.  The target sleeve is daily marked to market
against the active July-12 post-MTM Gate-1 baseline.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from clinicaltrials_phase3_results_paper_sleeve import (  # noqa: E402
    BASE_NOTIONAL_USD,
    ROUND_TRIP_COST_PCT,
    RULE_VERSION,
    SPONSOR_TO_TICKER,
    build_clinicaltrials_phase3_results_candidates,
    fetch_clinicaltrials_phase3_result_events,
    load_clinicaltrials_phase3_results_archive,
    replay_clinicaltrials_phase3_results_paper_trades,
    save_clinicaltrials_phase3_results_archive,
)
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


EXPERIMENT_ID = "exp-20260713-008"
OWNER = "alpha-explore"
BASELINE_SUMMARY = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
SOURCE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "clinicaltrials_phase3_results"
HISTORY_DIR = SOURCE_DIR / "history"
ARCHIVE_PATH = SOURCE_DIR / "events.json"
INDEX_PATH = SOURCE_DIR / "current_query_index.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
AUX_OHLCV_PATH = OUT_DIR / "auxiliary_ohlcv.json"
RESULT_PATH = OUT_DIR / "clinicaltrials_phase3_results_replay.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
ARTIFACT_PATH = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_clinicaltrials_phase3_results.md"

MIN_TARGET_TRADES = 20
MIN_TARGET_TICKERS = 3
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
}

WINDOWS = OrderedDict(
    (
        ("late_strong", ("2025-10-23", "2026-04-21")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("old_thin", ("2024-10-02", "2025-04-22")),
    )
)

PREDICTION = {
    "success_probability": 0.30,
    "expected_ev_delta": 0.30,
    "expected_pnl_delta": 5000.0,
    "main_failure_modes": [
        "stale_results_disclosure",
        "pharma_ticker_concentration",
        "accepted_comparator_not_beaten",
        "current_record_revision_leakage",
    ],
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _sha_rows(rows: Any) -> str:
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _archive_is_complete(events: list[dict[str, Any]]) -> bool:
    if not events:
        return False
    for row in events:
        path = HISTORY_DIR / f"{row['nct_id']}_v{row['history_version']}.json"
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != row.get("raw_sha256"):
            return False
    return True


def materialize_source(
    start: str,
    end: str,
    *,
    ohlcv_by_window: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    if INDEX_PATH.exists():
        index_events = (_read_json(INDEX_PATH).get("events") or [])
    else:
        index_events = fetch_clinicaltrials_phase3_result_events(
            start,
            end,
            resolve_history=False,
            timeout=30.0,
        )
        _write_json(
            INDEX_PATH,
            {
                "schema": "clinicaltrials_phase3_current_query_retrieval_index_v1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "survivorship_caveat": "Current exact-sponsor retrieval index only; exact first-post history version is the eligibility authority.",
                "events": index_events,
            },
        )

    # Price confirmation/top1/cooldown use only date/sponsor identity and
    # historical OHLCV. Resolve exact version payloads only for this non-inert
    # preflight set; exact records are then replayed from scratch and can fail
    # closed if sponsor/phase/date changed.
    preflight = [{**row, "history_version": "preflight_current_index"} for row in index_events]
    candidate_ncts: set[str] = set()
    for label, (window_start, window_end) in WINDOWS.items():
        candidates, _ = build_clinicaltrials_phase3_results_candidates(
            events=preflight,
            ohlcv_by_ticker=ohlcv_by_window[label],
            start=window_start,
            end=window_end,
        )
        candidate_ncts.update(str(row["nct_id"]) for row in candidates)

    events = load_clinicaltrials_phase3_results_archive(ARCHIVE_PATH)
    refreshed = False
    if not _archive_is_complete(events) or len(events) < len(candidate_ncts):
        events = fetch_clinicaltrials_phase3_result_events(
            start,
            end,
            resolve_history=True,
            timeout=30.0,
            archive_payload_dir=HISTORY_DIR,
        )
        save_clinicaltrials_phase3_results_archive(ARCHIVE_PATH, events)
        refreshed = True
    if not _archive_is_complete(events):
        raise RuntimeError("ClinicalTrials exact-history archive failed hash verification")
    return events, {
        "path": str(ARCHIVE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "history_dir": str(HISTORY_DIR.relative_to(REPO_ROOT)).replace("\\", "/"),
        "event_count": len(events),
        "retrieval_index_event_count": len(index_events),
        "preflight_non_inert_nct_count": len(candidate_ncts),
        "ticker_count": len({row["ticker"] for row in events}),
        "tickers": sorted({row["ticker"] for row in events}),
        "payload_hashes_verified": True,
        "refreshed": refreshed,
        "retrieval_prefilter": "current exact sponsor names; exact first-post history version is final eligibility authority",
        "known_survivorship_caveat": "A study whose lead sponsor changed away from a preregistered name before the current query can be missed by the retrieval prefilter.",
    }, index_events


def load_ohlcv(
    start: str,
    end: str,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Load the frozen auxiliary rowset, creating it once from the warehouse."""
    if AUX_OHLCV_PATH.exists():
        payload = _read_json(AUX_OHLCV_PATH)
        output = payload.get("ohlcv") or {}
        expected_hash = payload.get("rowset_sha256")
        actual_hash = _sha_rows(output)
        if payload.get("start") != start or payload.get("end") != end:
            raise RuntimeError("frozen auxiliary OHLCV range does not match the replay contract")
        if not expected_hash or expected_hash != actual_hash:
            raise RuntimeError("frozen auxiliary OHLCV rowset failed hash verification")
        return output, {
            "path": str(AUX_OHLCV_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "rowset_sha256": actual_hash,
            "source_at_freeze": payload.get("source_at_freeze"),
        }

    tickers = sorted(set(SPONSOR_TO_TICKER.values()) | {"SPY"})
    placeholders = ",".join("?" for _ in tickers)
    query = f"""
        SELECT ticker, date, open, high, low, close
        FROM ohlcv
        WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?
        ORDER BY ticker, date
    """
    output: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    with sqlite3.connect(str(WAREHOUSE)) as connection:
        for ticker, day, open_, high, low, close in connection.execute(
            query, [*tickers, start, end]
        ):
            output[str(ticker)].append(
                {
                    "date": str(day),
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                }
            )
    rowset_hash = _sha_rows(output)
    _write_json(
        AUX_OHLCV_PATH,
        {
            "schema": "clinicaltrials_phase3_auxiliary_ohlcv_v1",
            "source_at_freeze": str(WAREHOUSE.relative_to(REPO_ROOT)).replace("\\", "/"),
            "start": start,
            "end": end,
            "rowset_sha256": rowset_hash,
            "ohlcv": output,
        },
    )
    return output, {
        "path": str(AUX_OHLCV_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "rowset_sha256": rowset_hash,
        "source_at_freeze": str(WAREHOUSE.relative_to(REPO_ROOT)).replace("\\", "/"),
    }


def _window_ohlcv(
    broad_rows: dict[str, list[dict[str, Any]]],
    baseline_window: dict[str, Any],
    auxiliary_source: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Use exact Gate-1 snapshot bars where available, broad rows otherwise."""
    snapshot_path = REPO_ROOT / baseline_window["source"]
    payload = _read_json(snapshot_path)
    snapshot = payload.get("ohlcv") or {}
    output = {ticker: list(rows) for ticker, rows in broad_rows.items()}
    exact_tickers: list[str] = []
    for ticker in sorted(set(SPONSOR_TO_TICKER.values()) | {"SPY"}):
        if snapshot.get(ticker):
            output[ticker] = list(snapshot[ticker])
            exact_tickers.append(ticker)
    missing = [ticker for ticker, rows in output.items() if not rows]
    if missing:
        raise RuntimeError(f"required OHLCV coverage missing: {missing}")
    return output, {
        "gate1_snapshot": str(snapshot_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "exact_snapshot_tickers": exact_tickers,
        "frozen_auxiliary_fill_tickers": sorted(set(output) - set(exact_tickers)),
        "frozen_auxiliary_source": auxiliary_source,
    }


def _baseline_window_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["label"]: row for row in summary["windows"]}


def _baseline_curve(window: dict[str, Any]) -> list[tuple[str, float]]:
    artifact = _read_json(REPO_ROOT / window["path"])
    series = artifact["sharpe_inference"]["return_series"]
    equity = 100_000.0
    curve: list[tuple[str, float]] = []
    for row in series:
        equity *= 1.0 + float(row["return"])
        curve.append((str(row["date"]), equity))
    expected = 100_000.0 + float(window["total_pnl"])
    if not curve or abs(curve[-1][1] - expected) > 0.02:
        raise RuntimeError(f"baseline return-series reconstruction drift for {window['label']}")
    return curve


def _bar_index(ohlcv: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {
        ticker: {
            str(row.get("date") or row.get("Date")): float(row.get("close") if "close" in row else row.get("Close"))
            for row in rows
            if (row.get("close") if "close" in row else row.get("Close")) not in (None, 0)
        }
        for ticker, rows in ohlcv.items()
    }


def _target_mark_on_date(
    trades: list[dict[str, Any]],
    close_by_ticker: dict[str, dict[str, float]],
    day: str,
) -> float:
    mark = 0.0
    for trade in trades:
        if day < trade["entry_date"]:
            continue
        if day >= trade["exit_date"]:
            mark += float(trade["pnl"])
            continue
        close = close_by_ticker.get(trade["ticker"], {}).get(day)
        if close is None:
            # All names use the SPY calendar. Missing exact session data is a
            # measurement failure rather than an implicit stale-price fill.
            raise RuntimeError(f"missing MTM close for {trade['ticker']} on {day}")
        gross = close / float(trade["entry_price"]) - 1.0
        mark += float(trade["paper_notional_usd"]) * (gross - ROUND_TRIP_COST_PCT / 2.0)
    return mark


def _curve_metrics(curve: list[tuple[str, float]], *, trade_count: int) -> dict[str, Any]:
    previous = 100_000.0
    returns: list[dict[str, Any]] = []
    for day, equity in curve:
        value = equity / previous - 1.0 if previous else 0.0
        returns.append({"date": day, "return": value})
        previous = equity
    values = [equity for _, equity in curve]
    samples = [row["return"] for row in returns]
    sharpe_full = None
    if len(samples) >= 2:
        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / (len(samples) - 1)
        if variance > 0:
            sharpe_full = mean / math.sqrt(variance) * math.sqrt(252)
    peak = 100_000.0
    drawdown = 0.0
    for equity in values:
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak)
    total_pnl = values[-1] - 100_000.0
    total_return_public = round(total_pnl / 100_000.0, 4)
    sharpe_public = round(sharpe_full, 2) if sharpe_full is not None else None
    return {
        "total_pnl": round(total_pnl, 2),
        "benchmarks": {"strategy_total_return_pct": total_return_public},
        "sharpe_daily": sharpe_public,
        "sharpe_daily_full_precision": sharpe_full,
        "expected_value_score": (
            round(total_return_public * sharpe_public, 4)
            if sharpe_public is not None
            else None
        ),
        "max_drawdown_pct": round(drawdown, 4),
        "total_trades": trade_count,
        "return_series": returns,
        "return_series_sha256": _sha_rows(returns),
    }


def combine_window(
    baseline: dict[str, Any],
    trades: list[dict[str, Any]],
    ohlcv: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, float]]]:
    base_curve = _baseline_curve(baseline)
    close_index = _bar_index(ohlcv)
    combined = [
        (day, equity + _target_mark_on_date(trades, close_index, day))
        for day, equity in base_curve
    ]
    before = {
        "total_pnl": baseline["total_pnl"],
        "benchmarks": {"strategy_total_return_pct": round(float(baseline["total_pnl"]) / 100_000.0, 4)},
        "sharpe_daily": baseline["sharpe_daily"],
        "sharpe_daily_full_precision": baseline["sharpe_daily_full_precision"],
        "expected_value_score": baseline["expected_value_score"],
        "max_drawdown_pct": baseline["max_drawdown_pct"],
        "total_trades": baseline["trade_count"],
        "signals_generated": baseline["signals_generated"],
        "signals_survived": baseline["signals_survived"],
        "survival_rate": baseline["survival_rate"],
    }
    after = _curve_metrics(combined, trade_count=int(baseline["trade_count"]) + len(trades))
    return before, after, combined


def _target_summary(by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_ticker: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    for trades in by_window.values():
        for trade in trades:
            by_ticker[trade["ticker"]] += float(trade["pnl"])
            counts[trade["ticker"]] += 1
    positive = {ticker: pnl for ticker, pnl in by_ticker.items() if pnl > 0}
    positive_total = sum(positive.values())
    shares = sorted((pnl / positive_total for pnl in positive.values()), reverse=True) if positive_total else []
    return {
        "total_trade_count": sum(counts.values()),
        "ticker_count": len(counts),
        "tickers": sorted(counts),
        "window_count": sum(bool(rows) for rows in by_window.values()),
        "by_window_count": {label: len(rows) for label, rows in by_window.items()},
        "by_ticker_count": dict(sorted(counts.items())),
        "by_ticker_pnl": {ticker: round(pnl, 2) for ticker, pnl in sorted(by_ticker.items())},
        "total_pnl": round(sum(by_ticker.values()), 2),
        "single_ticker_positive_share": round(shares[0], 6) if shares else None,
        "hhi_concentration": round(sum(share * share for share in shares), 6) if shares else None,
        "top_5_contribution_pct": round(sum(shares[:5]), 6) if shares else None,
    }


def build_payload() -> dict[str, Any]:
    baseline_summary = _read_json(BASELINE_SUMMARY)
    baseline_windows = _baseline_window_map(baseline_summary)
    combined_start = min(start for start, _ in WINDOWS.values())
    combined_end = max(end for _, end in WINDOWS.values())
    broad_ohlcv, auxiliary_source = load_ohlcv("2024-09-01", "2026-05-15")
    ohlcv_by_window: dict[str, dict[str, Any]] = {}
    auxiliary_bar_identity: dict[str, Any] = {}
    for label in WINDOWS:
        ohlcv_by_window[label], auxiliary_bar_identity[label] = _window_ohlcv(
            broad_ohlcv, baseline_windows[label], auxiliary_source
        )
    events, source, index_events = materialize_source(
        combined_start,
        combined_end,
        ohlcv_by_window=ohlcv_by_window,
    )

    rows: dict[str, Any] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    generated_total = 0
    survived_total = 0
    for label, (start, end) in WINDOWS.items():
        ohlcv = ohlcv_by_window[label]
        replay = replay_clinicaltrials_phase3_results_paper_trades(
            events=events,
            ohlcv_by_ticker=ohlcv,
            start=start,
            end=end,
        )
        trades = replay["trades"]
        before, after, combined_curve = combine_window(baseline_windows[label], trades, ohlcv)
        generated = sum(start <= row["results_first_post_date"] <= end for row in index_events)
        survived = len(replay["selected_candidates"])
        generated_total += generated
        survived_total += survived
        trades_by_window[label] = trades
        rows[label] = {
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "delta": {
                "expected_value_score": round(after["expected_value_score"] - before["expected_value_score"], 4),
                "total_pnl": round(after["total_pnl"] - before["total_pnl"], 2),
                "max_drawdown_pct": round(after["max_drawdown_pct"] - before["max_drawdown_pct"], 4),
            },
            "signals_generated": generated,
            "signals_survived": survived,
            "survival_rate": round(survived / generated, 6) if generated else 0.0,
            "target_trades": trades,
            "unsettled": replay["unsettled"],
            "reject_totals": replay["reject_totals"],
            "combined_curve_sha256": _sha_rows(combined_curve),
        }

    target = _target_summary(trades_by_window)
    aggregate = {
        "before_expected_value_score_sum": round(sum(row["before"]["expected_value_score"] for row in rows.values()), 4),
        "after_expected_value_score_sum": round(sum(row["after"]["expected_value_score"] for row in rows.values()), 4),
        "expected_value_score_delta_sum": round(sum(row["delta"]["expected_value_score"] for row in rows.values()), 4),
        "before_total_pnl_sum": round(sum(row["before"]["total_pnl"] for row in rows.values()), 2),
        "after_total_pnl_sum": round(sum(row["after"]["total_pnl"] for row in rows.values()), 2),
        "total_pnl_delta_sum": round(sum(row["delta"]["total_pnl"] for row in rows.values()), 2),
        "windows_ev_improved": sum(row["delta"]["expected_value_score"] > 0 for row in rows.values()),
        "windows_ev_regressed": sum(row["delta"]["expected_value_score"] < 0 for row in rows.values()),
        "windows_pnl_improved": sum(row["delta"]["total_pnl"] > 0 for row in rows.values()),
        "windows_pnl_regressed": sum(row["delta"]["total_pnl"] < 0 for row in rows.values()),
        "max_drawdown_worse_max": max(row["delta"]["max_drawdown_pct"] for row in rows.values()),
    }
    gate_metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "adjusted_trade_count": target["total_trade_count"],
        "adjusted_windows": [label for label, trades in trades_by_window.items() if trades],
        "adjusted_window_count": target["window_count"],
        "max_drawdown_worse_max": aggregate["max_drawdown_worse_max"],
        "single_ticker_positive_share": target["single_ticker_positive_share"],
        "hhi_concentration": target["hhi_concentration"],
        "top_5_contribution_pct": target["top_5_contribution_pct"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / target["total_trade_count"]
            if target["total_trade_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(require_tail_concentration_not_worse=False)
    strict = evaluate_gate4(gate_metrics, thresholds=thresholds, check_materiality=True)
    canonical = evaluate_gate4(gate_metrics, thresholds=thresholds, check_materiality=False)
    failures = list(canonical["hard_failures"])
    if target["total_trade_count"] < MIN_TARGET_TRADES:
        failures.append("ticket_target_trade_count_below_20")
    if target["ticker_count"] < MIN_TARGET_TICKERS:
        failures.append("ticket_target_ticker_count_below_3")
    if target["window_count"] < MIN_TARGET_WINDOWS:
        failures.append("ticket_target_window_coverage_below_3")
    if aggregate["windows_pnl_regressed"] > 0:
        failures.append("window_pnl_regression")
    if aggregate["total_pnl_delta_sum"] <= COMPARATOR["total_pnl_delta_sum"]:
        failures.append("accepted_distribution_pnl_comparator_not_beaten")
    # The daily materializer currently emits exact-version source observations
    # pending price confirmation, but has not yet persisted the same candidate
    # and 10-day lifecycle. If the historical alpha wins, this blocker must be
    # removed inside this same experiment before paper acceptance.
    daily_candidate_parity_complete = False
    if not daily_candidate_parity_complete:
        failures.append("daily_candidate_lifecycle_parity_incomplete")
    gate4 = {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": list(dict.fromkeys(failures)),
        "canonical": canonical,
        "strict_materiality": strict,
        "metrics": gate_metrics,
    }
    envelope = ExecutionEnvelope(
        base_notional=BASE_NOTIONAL_USD,
        max_capital_pct=0.44,
        min_dollar_volume=None,
        slippage_bps=17.5,
        max_displacement=0,
        max_concurrent=11,
        order_semantics="next_open_then_10_session_horizon_close",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.05,
        notes="Default-off top1/day; 35bps all-in round trip; no core displacement.",
    )
    live = evaluate_live_readiness(
        envelope=envelope,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
        dsr_report=None,
    )
    verdict = full_stack_verdict(gate4=gate4, live_readiness=live, envelope=envelope)
    target_return_panel = {
        label: row["after"]["return_series"] for label, row in rows.items()
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "status": "accepted_paper_pending_forward" if gate4["passed"] else "rejected",
        "decision": (
            "accepted_paper_pending_forward_clinicaltrials_phase3_results"
            if gate4["passed"]
            else "rejected_clinicaltrials_phase3_results_candidate_pool"
        ),
        "accepted_alpha": gate4["passed"],
        "hypothesis": "A mapped public drug sponsor's first Phase 3 results posting, price-confirmed green and ahead of SPY, continues from next open through the tenth close.",
        "rule_version": RULE_VERSION,
        "source": source,
        "windows": rows,
        "gate1": {
            "passed": True,
            "baseline": str(BASELINE_SUMMARY.relative_to(REPO_ROOT)).replace("\\", "/"),
            "auxiliary_bar_identity": auxiliary_bar_identity,
            "comparator_note": "The archived comparator EV is pre-MTM and not binding across the July-12 schema migration; its PnL floor remains comparable and binding.",
        },
        "gate2": {
            "passed": bool(target["total_trade_count"]) and all(trade.get("entry_date") and trade.get("target_price") for trades in trades_by_window.values() for trade in trades),
            "sentinel_fields": ["entry_date", "target_price"],
            "exact_history_fields": ["history_version", "source_url", "raw_sha256", "results_first_post_date"],
        },
        "gate3": {
            "passed": generated_total > 0 and survived_total / generated_total >= 0.05,
            "signals_generated": generated_total,
            "signals_survived": survived_total,
            "survival_rate": round(survived_total / generated_total, 6) if generated_total else 0.0,
        },
        "aggregate": aggregate,
        "target_summary": target,
        "accepted_comparator": COMPARATOR,
        "gate4": gate4,
        "full_stack": {
            "verdict": verdict,
            "daily_candidate_parity_complete": daily_candidate_parity_complete,
            "execution_envelope": envelope.to_dict(),
            "live_readiness": live,
        },
        "target_return_panel_sha256": _sha_rows(target_return_panel),
        "target_return_panel": target_return_panel,
        "prediction": PREDICTION,
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "core_ranking_changed": False,
            "core_sizing_changed": False,
            "core_exits_changed": False,
            "daily_wiring_retained": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "shared_helper": "quant/clinicaltrials_phase3_results_paper_sleeve.py",
        },
        "post_run_reflection": {
            "why_result_happened": "; ".join(gate4["hard_failures"]) if failures else "The fixed source cleared every preregistered historical and full-stack gate.",
            "forbidden_near_neighbor_retry": "Do not retune sponsor aliases, green/SPY thresholds, rank, cooldown, hold, notional, cost, or window slices on this frozen source.",
            "new_evidence_required": "A genuinely new clinical-results direction classifier/source or at least 30 closed forward replacement-value trades; threshold and sponsor-map sweeps are not new evidence.",
        },
        "reproduction_command": f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name}",
    }


def _write_close_artifacts(payload: dict[str, Any]) -> None:
    rows = payload["windows"]
    before = {
        "schema": "clinicaltrials_gate4_aggregate_before_v1",
        "expected_value_score": payload["aggregate"]["before_expected_value_score_sum"],
        "total_pnl": payload["aggregate"]["before_total_pnl_sum"],
        "max_drawdown_pct": max(row["before"]["max_drawdown_pct"] for row in rows.values()),
        "total_trades": sum(row["before"]["total_trades"] for row in rows.values()),
        "survival_rate": min(row["before"]["survival_rate"] for row in rows.values()),
        "benchmarks": {"strategy_total_return_pct": round(payload["aggregate"]["before_total_pnl_sum"] / 100_000.0, 4)},
    }
    after = {
        "schema": "clinicaltrials_gate4_aggregate_after_v1",
        "expected_value_score": payload["aggregate"]["after_expected_value_score_sum"],
        "total_pnl": payload["aggregate"]["after_total_pnl_sum"],
        "max_drawdown_pct": max(row["after"]["max_drawdown_pct"] for row in rows.values()),
        "total_trades": sum(row["after"]["total_trades"] for row in rows.values()),
        "survival_rate": payload["gate3"]["survival_rate"],
        "benchmarks": {"strategy_total_return_pct": round(payload["aggregate"]["after_total_pnl_sum"] / 100_000.0, 4)},
    }
    _write_json(BEFORE_PATH, before)
    _write_json(AFTER_PATH, after)


def _write_artifact(payload: dict[str, Any]) -> None:
    lines = [
        f"# {EXPERIMENT_ID} ClinicalTrials.gov Phase 3 results",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Full-stack verdict: `{payload['full_stack']['verdict']['verdict']}`",
        f"- Source events / tickers: `{payload['source']['event_count']}` / `{payload['source']['ticker_count']}`",
        f"- Target trades / tickers / windows: `{payload['target_summary']['total_trade_count']}` / `{payload['target_summary']['ticker_count']}` / `{payload['target_summary']['window_count']}`",
        f"- Aggregate EV delta: `{payload['aggregate']['expected_value_score_delta_sum']}`",
        f"- Aggregate PnL delta: `${payload['aggregate']['total_pnl_delta_sum']:,.2f}`",
        f"- Gate 3 survival: `{payload['gate3']['survival_rate']:.2%}`",
        f"- Gate 4 failures: `{', '.join(payload['gate4']['hard_failures']) or 'none'}`",
        "",
        "Historical replay uses only exact ACTUAL first-post Record History versions. No daily production wiring was retained after the Gate 4 rejection.",
    ]
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    payload = build_payload()
    _write_json(RESULT_PATH, payload)
    _write_close_artifacts(payload)
    _write_artifact(payload)
    print(json.dumps({
        "decision": payload["decision"],
        "source": payload["source"],
        "target_summary": payload["target_summary"],
        "aggregate": payload["aggregate"],
        "gate4_failures": payload["gate4"]["hard_failures"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
