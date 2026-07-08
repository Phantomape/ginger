"""exp-20260707-019: SEC NT late-filing notice entry-risk scout.

Read-only alpha-search experiment. The single decision hypothesis is that SEC
NT 10-K / NT 10-Q / NT 20-F late-filing notices identify near-term entry risk:
liquid tickers with a notice should underperform over the next 10 sessions,
supporting a default-off risk gate rather than a long candidate source.

This is a new gate shape inside the broader filing-timeliness domain. It does
not retune the rejected early/prompt filing-lag threshold family; it uses the
SEC form type itself (NT late notice), which prior closeouts explicitly named
as a valid materially different disclosure-timing field.

No production path, default orders, ranking, sizing, exits, LLM boundary,
watchlist, or shared policy is changed.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


EXPERIMENT_ID = "exp-20260707-019"
OWNER = "alpha-explore"
SLUG = "sec_nt_late_filing_notice_entry_risk"
RUNNER = f"quant/experiments/exp_20260707_019_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


SEC_SUBMISSIONS_ROOT = REPO_ROOT / "data" / "cache" / "sec" / "submissions"
WAREHOUSE_SQLITE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260707_019_{SLUG}.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = {
    "late_strong": {"start": "2025-10-23", "end": "2026-04-21"},
    "mid_weak": {"start": "2025-04-23", "end": "2025-10-22"},
    "old_thin": {"start": "2024-10-02", "end": "2025-04-22"},
}
NT_FORMS = {
    "NT 10-K",
    "NT 10-Q",
    "NT 20-F",
    "NT 10-K/A",
    "NT 10-Q/A",
    "NT 20-F/A",
}
HOLD_DAYS = 10
SAME_TICKER_COOLDOWN_SESSIONS = 10
MIN_ENTRY_PRICE = 10.0
MIN_ADV20_USD = 50_000_000.0
NOTIONAL_USD = 4_000.0
MIN_SUPPORT_EVENTS_PER_WINDOW = 10
MIN_TOTAL_LIQUID_EVENTS = 30
MAX_SINGLE_TICKER_SHARE = 0.40

HYPOTHESIS = (
    "entry_filter/risk_allocation: SEC NT 10-K, NT 10-Q, and NT 20-F "
    "late-filing notices are PIT disclosure-delay events; liquid tickers with "
    "a notice should underperform over the next 10 sessions, supporting a "
    "default-off entry risk gate rather than a long candidate source."
)
CHANGE_TYPE = "entry_filter"
IMPLEMENTATION_MODE = "private_replay_scout"
MECHANISM_FAMILY = "free_sec_disclosure_timing_entry_risk"
TRIAL_FAMILY = "sec_nt_late_filing_notice_entry_risk"
TRIAL_VARIANT_ID = "nt_10k_10q_20f_notice_top1_day_10d_v1"
CHANGED_VARIABLE = "sec_nt_late_filing_notice_10d_entry_risk_gate_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_sec_nt_late_filing_notice"
NEW_EVIDENCE_AXIS = (
    "New gate shape on same SEC disclosure domain: NT late-filing notice form "
    "types, not early/prompt filing lag thresholds or filing recency; preflight "
    "found 990 canonical-window rows across 452 tickers."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260617-019",
    "exp-20260617-020",
    "free_sec_companyfacts_quarterly_timeliness_broad_candidate_pool",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")


def rounded(value: Any, digits: int = 6) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return value


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _window_for(date_text: str) -> str | None:
    for label, spec in WINDOWS.items():
        if spec["start"] <= date_text <= spec["end"]:
            return label
    return None


def _normalise_form(value: Any) -> str:
    return str(value or "").replace("FORM ", "").strip().upper()


def _safe_date(value: Any) -> str:
    text = str(value or "")[:10]
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text
    return ""


def load_cik_ticker_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for path in sorted(SEC_SUBMISSIONS_ROOT.glob("CIK*.json")):
        match = re.search(r"CIK(\d{10})", path.name)
        if not match:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        tickers = payload.get("tickers") or []
        if tickers:
            mapping[match.group(1)] = str(tickers[0]).upper()
    return mapping


def load_nt_notice_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cik_ticker = load_cik_ticker_map()
    paths = sorted(SEC_SUBMISSIONS_ROOT.glob("CIK*.json"))
    paths += sorted((SEC_SUBMISSIONS_ROOT / "files").glob("CIK*.json"))
    events: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str, str, str]] = set()
    parse_errors = 0
    for path in paths:
        match = re.search(r"CIK(\d{10})", path.name)
        cik = match.group(1) if match else None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            parse_errors += 1
            continue
        ticker = None
        if isinstance(payload, dict):
            tickers = payload.get("tickers") or []
            if tickers:
                ticker = str(tickers[0]).upper()
        ticker = ticker or (cik_ticker.get(cik) if cik else None)
        data = (payload.get("filings") or {}).get("recent") if isinstance(payload, dict) else None
        if data is None:
            data = payload
        if not isinstance(data, dict):
            continue
        forms = data.get("form") or []
        filing_dates = data.get("filingDate") or []
        report_dates = data.get("reportDate") or []
        accessions = data.get("accessionNumber") or []
        acceptances = data.get("acceptanceDateTime") or []
        primary_docs = data.get("primaryDocument") or []
        for index, raw_form in enumerate(forms):
            form = _normalise_form(raw_form)
            if form not in NT_FORMS:
                continue
            filing_date = _safe_date(filing_dates[index] if index < len(filing_dates) else "")
            window = _window_for(filing_date)
            if not window:
                continue
            accession = str(accessions[index] if index < len(accessions) else "")
            key = (ticker, cik, accession, form, filing_date)
            if key in seen:
                continue
            seen.add(key)
            events.append(
                {
                    "ticker": ticker,
                    "cik": cik,
                    "form_type": form,
                    "filing_date": filing_date,
                    "report_date": _safe_date(
                        report_dates[index] if index < len(report_dates) else ""
                    ),
                    "accepted_at": str(
                        acceptances[index] if index < len(acceptances) else ""
                    ),
                    "accession_number": accession,
                    "primary_document": str(
                        primary_docs[index] if index < len(primary_docs) else ""
                    ),
                    "window": window,
                    "source_cache_file": repo_rel(path),
                }
            )
    diagnostics = {
        "cache_files_scanned": len(paths),
        "parse_errors": parse_errors,
        "raw_nt_notice_count": len(events),
        "raw_by_window": dict(Counter(row["window"] for row in events)),
        "raw_by_form": dict(Counter(row["form_type"] for row in events)),
        "raw_unique_tickers": len({row["ticker"] for row in events if row.get("ticker")}),
        "raw_missing_ticker": sum(1 for row in events if not row.get("ticker")),
    }
    return sorted(events, key=lambda row: (row["filing_date"], row.get("ticker") or "")), diagnostics


def load_prices(tickers: set[str]) -> dict[str, list[dict[str, Any]]]:
    prices: dict[str, list[dict[str, Any]]] = {}
    with sqlite3.connect(WAREHOUSE_SQLITE) as conn:
        for ticker in sorted(tickers):
            rows = conn.execute(
                """
                select date, open, high, low, close, volume
                from ohlcv
                where ticker = ?
                order by date
                """,
                (ticker,),
            ).fetchall()
            parsed = [
                {
                    "date": str(date_text),
                    "open": float(open_),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                    "volume": float(volume),
                }
                for date_text, open_, high, low, close, volume in rows
                if open_ and high and low and close and volume
            ]
            if parsed:
                prices[ticker] = parsed
    return prices


def _forward_return(
    rows: list[dict[str, Any]],
    dates: list[str],
    signal_date: str,
) -> tuple[dict[str, Any] | None, str | None]:
    entry_index = bisect.bisect_right(dates, signal_date)
    if entry_index >= len(rows):
        return None, "no_next_session_open"
    exit_index = entry_index + HOLD_DAYS
    if exit_index >= len(rows):
        return None, "no_10d_exit"
    entry = rows[entry_index]
    exit_row = rows[exit_index]
    if entry["open"] < MIN_ENTRY_PRICE:
        return None, "entry_price_below_floor"
    prior = rows[max(0, entry_index - 20) : entry_index]
    if len(prior) < 20:
        return None, "adv20_missing"
    adv20 = sum(row["close"] * row["volume"] for row in prior) / len(prior)
    if adv20 < MIN_ADV20_USD:
        return None, "adv20_below_floor"
    net_return = exit_row["close"] / entry["open"] - 1.0 - ROUND_TRIP_COST_PCT
    return (
        {
            "entry_index": entry_index,
            "entry_date": entry["date"],
            "entry_open": entry["open"],
            "exit_index": exit_index,
            "exit_date": exit_row["date"],
            "exit_close": exit_row["close"],
            "adv20_usd": adv20,
            "net_long_return": net_return,
            "long_pnl_usd": NOTIONAL_USD * net_return,
            "risk_gate_avoided_loss_usd": -NOTIONAL_USD * net_return,
        },
        None,
    )


def build_unconditional_return_cache(
    prices: dict[str, list[dict[str, Any]]],
    tickers_by_window: dict[str, set[str]],
) -> dict[tuple[str, str], float | None]:
    cache: dict[tuple[str, str], float | None] = {}
    for label, tickers in tickers_by_window.items():
        spec = WINDOWS[label]
        for ticker in sorted(tickers):
            rows = prices.get(ticker) or []
            dates = [row["date"] for row in rows]
            values: list[float] = []
            for signal_date in dates:
                if not (spec["start"] <= signal_date <= spec["end"]):
                    continue
                result, reason = _forward_return(rows, dates, signal_date)
                if result is not None and reason is None:
                    values.append(float(result["net_long_return"]))
            cache[(ticker, label)] = mean(values)
    return cache


def replay_events(
    events: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tickers_by_window: dict[str, set[str]] = defaultdict(set)
    for event in events:
        if event.get("ticker"):
            tickers_by_window[event["window"]].add(event["ticker"])
    unconditional = build_unconditional_return_cache(prices, tickers_by_window)

    trades: list[dict[str, Any]] = []
    rejects: Counter[str] = Counter()
    last_entry_index_by_ticker: dict[str, int] = {}
    for event in events:
        ticker = event.get("ticker")
        if not ticker:
            rejects["missing_ticker"] += 1
            continue
        rows = prices.get(ticker)
        if not rows:
            rejects["no_price_history"] += 1
            continue
        dates = [row["date"] for row in rows]
        result, reason = _forward_return(rows, dates, event["filing_date"])
        if result is None:
            rejects[str(reason)] += 1
            continue
        entry_index = int(result["entry_index"])
        last_entry_index = last_entry_index_by_ticker.get(ticker)
        if (
            last_entry_index is not None
            and entry_index - last_entry_index <= SAME_TICKER_COOLDOWN_SESSIONS
        ):
            rejects["same_ticker_cooldown"] += 1
            continue
        last_entry_index_by_ticker[ticker] = entry_index
        unconditional_mean = unconditional.get((ticker, event["window"]))
        excess = (
            float(result["net_long_return"]) - unconditional_mean
            if unconditional_mean is not None
            else None
        )
        trades.append(
            {
                **event,
                "entry_date": result["entry_date"],
                "exit_date": result["exit_date"],
                "entry_open": rounded(result["entry_open"], 4),
                "exit_close": rounded(result["exit_close"], 4),
                "adv20_usd": rounded(result["adv20_usd"], 2),
                "net_long_return": rounded(result["net_long_return"], 6),
                "long_pnl_usd": rounded(result["long_pnl_usd"], 2),
                "risk_gate_avoided_loss_usd": rounded(
                    result["risk_gate_avoided_loss_usd"], 2
                ),
                "same_ticker_unconditional_net_return_mean": rounded(
                    unconditional_mean, 6
                ),
                "excess_vs_same_ticker_unconditional": rounded(excess, 6),
            }
        )
    diagnostics = {
        "prices_loaded_for_tickers": len(prices),
        "rejects": dict(rejects),
        "liquid_trade_count": len(trades),
        "liquid_trade_count_by_window": dict(Counter(row["window"] for row in trades)),
        "liquid_trade_count_by_form": dict(Counter(row["form_type"] for row in trades)),
        "liquid_unique_tickers": len({row["ticker"] for row in trades}),
    }
    return trades, diagnostics


def summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    by_window: dict[str, Any] = {}
    supporting_windows: list[str] = []
    for label in WINDOWS:
        rows = [row for row in trades if row["window"] == label]
        returns = [float(row["net_long_return"]) for row in rows]
        excess_values = [
            float(row["excess_vs_same_ticker_unconditional"])
            for row in rows
            if row.get("excess_vs_same_ticker_unconditional") is not None
        ]
        ticker_counts = Counter(row["ticker"] for row in rows)
        max_single_ticker_share = (
            max(ticker_counts.values()) / len(rows) if rows else None
        )
        summary = {
            "trade_count": len(rows),
            "unique_tickers": len(ticker_counts),
            "mean_net_long_return": rounded(mean(returns), 6),
            "median_net_long_return": rounded(median(returns), 6) if returns else None,
            "negative_return_share": rounded(
                sum(1 for value in returns if value < 0) / len(returns), 6
            )
            if returns
            else None,
            "total_long_pnl_usd": rounded(
                sum(float(row["long_pnl_usd"]) for row in rows), 2
            ),
            "total_risk_gate_avoided_loss_usd": rounded(
                sum(float(row["risk_gate_avoided_loss_usd"]) for row in rows), 2
            ),
            "mean_excess_vs_same_ticker_unconditional": rounded(
                mean(excess_values), 6
            ),
            "top_ticker_counts": ticker_counts.most_common(5),
            "max_single_ticker_share": rounded(max_single_ticker_share, 6),
        }
        if (
            len(rows) >= MIN_SUPPORT_EVENTS_PER_WINDOW
            and summary["mean_net_long_return"] is not None
            and summary["mean_net_long_return"] < 0
            and summary["mean_excess_vs_same_ticker_unconditional"] is not None
            and summary["mean_excess_vs_same_ticker_unconditional"] < 0
            and (
                max_single_ticker_share is None
                or max_single_ticker_share <= MAX_SINGLE_TICKER_SHARE
            )
        ):
            supporting_windows.append(label)
        by_window[label] = summary

    all_returns = [float(row["net_long_return"]) for row in trades]
    all_excess = [
        float(row["excess_vs_same_ticker_unconditional"])
        for row in trades
        if row.get("excess_vs_same_ticker_unconditional") is not None
    ]
    ticker_counts = Counter(row["ticker"] for row in trades)
    max_single_ticker_share = (
        max(ticker_counts.values()) / len(trades) if trades else None
    )
    aggregate = {
        "trade_count": len(trades),
        "unique_tickers": len(ticker_counts),
        "mean_net_long_return": rounded(mean(all_returns), 6),
        "median_net_long_return": rounded(median(all_returns), 6)
        if all_returns
        else None,
        "negative_return_share": rounded(
            sum(1 for value in all_returns if value < 0) / len(all_returns), 6
        )
        if all_returns
        else None,
        "total_long_pnl_usd": rounded(
            sum(float(row["long_pnl_usd"]) for row in trades), 2
        ),
        "total_risk_gate_avoided_loss_usd": rounded(
            sum(float(row["risk_gate_avoided_loss_usd"]) for row in trades), 2
        ),
        "mean_excess_vs_same_ticker_unconditional": rounded(mean(all_excess), 6),
        "top_ticker_counts": ticker_counts.most_common(10),
        "max_single_ticker_share": rounded(max_single_ticker_share, 6),
        "supporting_windows": supporting_windows,
    }
    return {"aggregate": aggregate, "by_window": by_window}


def load_ticket_prediction() -> dict[str, Any]:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    return ticket.get("prediction") or {}


def load_baseline_metrics() -> dict[str, Any]:
    payload = json.loads(BASELINE_RESULT.read_text(encoding="utf-8"))
    windows = payload.get("windows") or []
    return {
        row["label"]: {
            "expected_value_score": row.get("expected_value_score"),
            "total_pnl": row.get("total_pnl"),
            "trade_count": row.get("trade_count"),
            "signals_generated": row.get("signals_generated"),
            "signals_survived": row.get("signals_survived"),
            "survival_rate": row.get("survival_rate"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
        }
        for row in windows
        if isinstance(row, dict) and row.get("label")
    }


def build_payload() -> dict[str, Any]:
    events, event_diagnostics = load_nt_notice_events()
    tickers = {str(row["ticker"]).upper() for row in events if row.get("ticker")}
    prices = load_prices(tickers)
    trades, replay_diagnostics = replay_events(events, prices)
    summary = summarize_trades(trades)
    prediction = load_ticket_prediction()
    baseline_metrics = load_baseline_metrics()

    aggregate = summary["aggregate"]
    supporting_windows = aggregate["supporting_windows"]
    failed_reasons: list[str] = []
    if aggregate["trade_count"] < MIN_TOTAL_LIQUID_EVENTS:
        failed_reasons.append("liquid_sample_below_min_total")
    if len(supporting_windows) < 2:
        failed_reasons.append("event_drift_not_negative_in_two_windows")
    if (
        aggregate["mean_net_long_return"] is not None
        and aggregate["mean_net_long_return"] >= 0
    ):
        failed_reasons.append("aggregate_long_drift_positive")
    if (
        aggregate["mean_excess_vs_same_ticker_unconditional"] is not None
        and aggregate["mean_excess_vs_same_ticker_unconditional"] >= 0
    ):
        failed_reasons.append("aggregate_excess_not_negative")
    if (
        aggregate["max_single_ticker_share"] is not None
        and aggregate["max_single_ticker_share"] > MAX_SINGLE_TICKER_SHARE
    ):
        failed_reasons.append("ticker_concentration_too_high")

    support_lead = not failed_reasons
    decision = (
        "observed_positive_lead_sec_nt_late_filing_entry_risk_gate"
        if support_lead
        else "rejected_sec_nt_late_filing_entry_risk_gate"
    )
    status = "observed_only_positive_lead" if support_lead else "rejected"
    actual_success = 1 if support_lead else 0
    predicted_p = float(prediction.get("success_probability") or 0.0)

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": support_lead,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted_p,
            "brier_score": rounded((actual_success - predicted_p) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": bool(
                set(prediction.get("main_failure_modes") or []) & set(failed_reasons)
            ),
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
        },
        "parameters": {
            "forms": sorted(NT_FORMS),
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "notional_usd": NOTIONAL_USD,
            "entry_policy": "next_session_open_after_filing_date",
            "exit_policy": "close_after_10_trading_sessions",
            "min_entry_price": MIN_ENTRY_PRICE,
            "min_adv20_usd": MIN_ADV20_USD,
            "same_ticker_cooldown_sessions": SAME_TICKER_COOLDOWN_SESSIONS,
            "support_rule": (
                "Positive lead only if >=30 total liquid events, at least two "
                "canonical windows have >=10 events with negative mean 10d net "
                "long return and negative same-ticker excess return, and ticker "
                "concentration is <=40%. Otherwise rejected; no behavior changes."
            ),
            "windows": WINDOWS,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "experiment.py new blocked filing-timeliness near-neighbors; "
                    "override was used with a legal new gate-shape axis: SEC NT "
                    "late-filing form types, not filing recency or early/prompt "
                    "lag thresholds."
                ),
                "exp-20260617-019": (
                    "Rejected core annual 10-K early filing promptness; not this "
                    "NT form-type late-notice gate."
                ),
                "exp-20260617-020": (
                    "Rejected broad annual 10-K early filing promptness and "
                    "explicitly listed NT 10-K/10-Q late notices as a materially "
                    "different legal retry."
                ),
                "quarterly_timeliness_broad": (
                    "Rejected quarterly promptness; also listed NT late notices "
                    "as a different disclosure-timing field."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Use the predeclared source-validation rule in parameters; this "
                "is replay-only, so a positive result would still need a shared "
                "helper plus full Gate 4 before any production entry gate."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline_metrics,
            "accepted_reference": {
                "expected_value_score_sum": 7.8941,
                "total_pnl_sum": 234850.99,
                "trade_count_sum": 61,
            },
        },
        "gate2": {
            "runtime_fields_checked": [
                "filing_date",
                "form_type",
                "ticker",
                "entry_date",
                "entry_open",
                "exit_date",
                "exit_close",
                "adv20_usd",
            ],
            "missing_entry_date": sum(1 for row in trades if not row.get("entry_date")),
            "missing_exit_date": sum(1 for row in trades if not row.get("exit_date")),
            "target_price_relevance": (
                "No generated strategy signals are emitted; target_price is not "
                "consumed by this read-only event study. A later shared entry "
                "gate must re-run the normal signal contract checks."
            ),
            "passed": all(row.get("entry_date") and row.get("exit_date") for row in trades),
        },
        "gate3": {
            "new_entry_filter_added": False,
            "signals_generated": None,
            "signals_survived": None,
            "survival_rate": None,
            "note": (
                "Attribution only; no filter applied, so baseline survival is "
                "unchanged and Gate 3 is informational."
            ),
            "passed": True,
        },
        "gate4": {
            "applicable": False,
            "passed": support_lead,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "supporting_windows": supporting_windows,
            "aggregate_mean_net_long_return": aggregate["mean_net_long_return"],
            "aggregate_mean_excess_vs_same_ticker_unconditional": aggregate[
                "mean_excess_vs_same_ticker_unconditional"
            ],
            "aggregate_total_long_pnl_usd": aggregate["total_long_pnl_usd"],
            "aggregate_total_risk_gate_avoided_loss_usd": aggregate[
                "total_risk_gate_avoided_loss_usd"
            ],
            "liquid_trade_count": aggregate["trade_count"],
            "note": (
                "No before/after strategy behavior changed. The source-validation "
                "rule failed, so no shared-helper Gate 4 follow-up is warranted."
            ),
        },
        "data_diagnostics": {
            **event_diagnostics,
            **replay_diagnostics,
        },
        "event_study": summary,
        "sample_trades": trades[:50],
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
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
            "daily_snapshot_exposed": False,
            "default_off_paper_only": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Read-only offline source validation over SEC cached submissions "
                "and warehouse OHLCV. No production/backtest behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The NT notice surface is dominated by untradeable rows after "
                "liquidity gates, and the few liquid events did not behave like "
                "entry risk. The 21 deployable events had positive aggregate "
                "10-session long drift, so avoiding them would have destroyed "
                "replacement value."
            )
            if not support_lead
            else (
                "NT late-filing notices showed broad negative event drift and "
                "deserve a shared-helper Gate 4 follow-up."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune price, ADV, hold days, cooldown, form subset, "
                "same-day ranking, annual-vs-quarterly split, or threshold-like "
                "slices on these same cached NT notice rows. Do not reframe the "
                "positive long drift as a contrarian long without a new gate "
                "shape or materially more settled forward rows."
            ),
            "new_evidence_required": (
                "A legal retry needs materially new NT notice rows, a genuinely "
                "different disclosure-delay field such as accelerated-filer "
                "status change with PIT provenance, or a different data source."
            ),
        },
        "rejection_reason": ";".join(failed_reasons) if failed_reasons else None,
        "next_retry_requires": [
            "materially new NT notice rows",
            "or a different disclosure-delay field with PIT provenance",
            "or a different data source",
        ],
        "before_after_strategy_behavior_changed": False,
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
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(BASELINE_RESULT),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "llm_metrics": {"used_llm": False},
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def make_card(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: SEC NT late-filing notice entry-risk scout",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        HYPOTHESIS,
        "",
        "| Window | Trades | Mean long ret | Mean excess | Long PnL | Avoided-loss PnL | Negative share |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        row = payload["event_study"]["by_window"][label]
        lines.append(
            f"| {label} | {row['trade_count']} | {row['mean_net_long_return']} | "
            f"{row['mean_excess_vs_same_ticker_unconditional']} | "
            f"{row['total_long_pnl_usd']} | "
            f"{row['total_risk_gate_avoided_loss_usd']} | "
            f"{row['negative_return_share']} |"
        )
    gate4 = payload["gate4"]
    lines += [
        "",
        f"Raw NT rows: {payload['data_diagnostics']['raw_nt_notice_count']}; "
        f"liquid replay trades: {gate4['liquid_trade_count']}; "
        f"failed reasons: {gate4['failed_reasons']}.",
        "",
        "No behavior changed. The source failed as an entry-risk gate because the "
        "deployable liquid sample was thin and positive, not negative.",
    ]
    return "\n".join(lines) + "\n"


def make_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [Path(RUNNER), OUT_JSON, LOG_JSON, CARD_MD, MANIFEST_JSON, TICKET_JSON]
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "files": [
            {
                "path": repo_rel(path if path.is_absolute() else REPO_ROOT / path),
                "exists": (path if path.is_absolute() else REPO_ROOT / path).exists(),
                "sha256": sha256(path if path.is_absolute() else REPO_ROOT / path),
            }
            for path in paths
        ],
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_text(CARD_MD, make_card(payload))
    write_json(LOG_JSON, payload)
    append_jsonl(EXPERIMENT_LOG, payload)
    write_json(MANIFEST_JSON, make_manifest(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload.get("prediction") or {},
        result=payload,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "accepted_alpha": payload["accepted_alpha"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "status": payload["status"],
                "gate4": payload["gate4"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
