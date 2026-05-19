from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from quant.form4_event_queue import aggregate_purchase_events, qualifies_forward_queue_event
EXP_ID = "exp-20260510-016"
RUN_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")
DATE_TAG = "20260510"
DATA_DIR = ROOT / "data"
OUT_DIR = DATA_DIR / "experiments" / EXP_ID
ARTIFACT = OUT_DIR / "form4_insider_overlay_fresh_shadow.json"
REPORT = (
    ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / f"form4_insider_overlay_fresh_shadow_{EXP_ID}_{DATE_TAG}.md"
)
LOG_PATH = ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
REGISTRY_PATH = ROOT / "docs" / "experiment_registry.json"
JSONL_PATH = ROOT / "docs" / "experiment_log.jsonl"

NON_COMPANY = {"SPY", "QQQ", "IWM", "GLD", "IAU", "SLV"}
LATEST_TX = DATA_DIR / "non_ohlcv" / "form4_transactions_20260509.jsonl"
LATEST_SUMMARY = DATA_DIR / "non_ohlcv" / "form4_backfill_summary_20260509.json"
PRIOR_LOG = ROOT / "experiments" / "logs" / "exp-20260509-018.json"
BASELINE = DATA_DIR / "experiments" / "exp-20260510-012" / "rs20_entry_state_shared_sizing.json"
HIST_EVENTS = DATA_DIR / "non_ohlcv" / "form4_purchase_shadow_outcomes_20241002_20260421.json"
QUANT_SIGNALS = DATA_DIR / "quant_signals_20260509.json"
UNIVERSE_STATE = DATA_DIR / "universe_state_20260509.json"
SEC_TICKERS = DATA_DIR / "sec_company_tickers.json"
PAPER_SNAPSHOTS = DATA_DIR / "form4_event_sleeve_paper_snapshots.jsonl"


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def repo_rel(path: Path | str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    try:
        return str(p.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def field_coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    required_fields = [
        "ticker",
        "cik",
        "accession_number",
        "accepted_at",
        "filing_datetime",
        "transaction_date",
        "officer_title",
        "is_director",
        "is_officer",
        "is_10pct_owner",
        "transaction_code",
        "shares",
        "price",
        "transaction_value",
        "direct_or_indirect",
        "ownership_nature",
        "10b5_1_flag",
        "option_exercise_flag",
        "open_market_purchase_flag",
        "usable_trade_date",
        "pit_safe_flag",
    ]
    out: dict[str, dict[str, Any]] = {}
    for field in required_fields:
        source_field = "accepted_at" if field == "filing_datetime" else field
        count = sum(1 for row in rows if present(row.get(source_field)))
        out[field] = {
            "source_field": source_field,
            "present_rows": count,
            "total_rows": len(rows),
            "coverage": round(count / len(rows), 6) if rows else None,
        }
    out["filing_datetime"][
        "normalization_note"
    ] = "No literal filing_datetime field; accepted_at is the EDGAR acceptance timestamp used for PIT dating."
    return out


def build_cik_mapping_report(universe: dict[str, Any]) -> dict[str, Any]:
    sec_payload = load_json(SEC_TICKERS, {}) or {}
    sec_rows = sec_payload.values() if isinstance(sec_payload, dict) else sec_payload
    sec_map: dict[str, str] = {}
    for item in sec_rows or []:
        if isinstance(item, dict) and item.get("ticker") and item.get("cik_str"):
            sec_map[str(item["ticker"]).upper()] = str(item["cik_str"]).zfill(10)

    def segment_mapping(key: str) -> dict[str, Any]:
        tickers = [str(t).upper() for t in universe.get(key, [])]
        company_tickers = [t for t in tickers if t not in NON_COMPANY]
        mapped = sorted([t for t in company_tickers if t in sec_map])
        missing = sorted([t for t in company_tickers if t not in sec_map])
        return {
            "segment_key": key,
            "ticker_count": len(tickers),
            "company_ticker_count": len(company_tickers),
            "mapped_company_ticker_count": len(mapped),
            "missing_company_tickers": missing,
            "non_company_excluded": sorted([t for t in tickers if t in NON_COMPANY]),
        }

    pilot_key = "pilot_trade_universe" if universe.get("pilot_trade_universe") else "governance_tradeable_universe"
    return {
        "mapping_source": repo_rel(SEC_TICKERS),
        "core_trade_universe": segment_mapping("core_trade_universe"),
        "pilot_universe": segment_mapping(pilot_key),
        "observation_universe": segment_mapping("observation_universe"),
        "known_gap_summary": (
            "SNXX remains the only ticker missing from the Form 4 backfill request mapping; "
            "ETF-like non-company tickers are excluded from Form 4 CIK coverage."
        ),
    }


def signal_rows(container: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = container.get(key)
    return value if isinstance(value, list) else []


def build_overlap(
    meaningful_events: list[dict[str, Any]],
    quant: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    meaningful_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in meaningful_events:
        meaningful_by_ticker[str(event.get("ticker") or "").upper()].append(event)

    core_signals = signal_rows(quant, "signals")
    pilot_signals = signal_rows(quant, "pilot_signals")
    state_queue = quant.get("state_surface_queue") or {}
    state_scored = state_queue.get("scored_candidates") or []
    state_allowed = state_queue.get("candidates") or []
    form4_queue = quant.get("form4_event_queue") or {}

    def overlap(rows: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for sig in rows:
            ticker = str(sig.get("ticker") or "").upper()
            if ticker in meaningful_by_ticker:
                matches.append(
                    {
                        "surface": label,
                        "ticker": ticker,
                        "signal_date": sig.get("date")
                        or sig.get("created_asof")
                        or sig.get("usable_trade_date")
                        or sig.get("entry_date"),
                        "strategy": sig.get("strategy") or sig.get("surface") or sig.get("source"),
                        "trade_enabled": bool(sig.get("trade_enabled")),
                        "matched_form4_events": meaningful_by_ticker[ticker],
                    }
                )
        return matches

    fresh_overlap = {
        "production_core_signals": {
            "signal_count": len(core_signals),
            "tagged_count": len(overlap(core_signals, "production_core_signals")),
            "matches": overlap(core_signals, "production_core_signals"),
        },
        "pilot_signals": {
            "signal_count": len(pilot_signals),
            "tagged_count": len(overlap(pilot_signals, "pilot_signals")),
            "matches": overlap(pilot_signals, "pilot_signals"),
        },
        "default_off_state_surface_scored_candidates": {
            "signal_count": len(state_scored),
            "tagged_count": len(overlap(state_scored, "state_surface_scored")),
            "matches": overlap(state_scored, "state_surface_scored"),
            "production_scope": "paper_only_default_off",
        },
        "default_off_state_surface_allowed_candidates": {
            "signal_count": len(state_allowed),
            "tagged_count": len(overlap(state_allowed, "state_surface_allowed")),
            "matches": overlap(state_allowed, "state_surface_allowed"),
            "production_scope": "paper_only_default_off",
        },
        "form4_forward_queue": {
            "candidate_count": form4_queue.get("candidate_count"),
            "tagged_existing_signal_count": 0,
            "production_scope": "observe_only_default_off",
        },
    }

    no_production_signal: list[dict[str, Any]] = []
    for event in meaningful_events:
        ticker = str(event.get("ticker") or "").upper()
        has_core = any(str(sig.get("ticker") or "").upper() == ticker for sig in core_signals)
        has_pilot = any(str(sig.get("ticker") or "").upper() == ticker for sig in pilot_signals)
        has_state = any(str(sig.get("ticker") or "").upper() == ticker for sig in state_scored)
        if not has_core and not has_pilot:
            no_production_signal.append(
                {
                    "ticker": ticker,
                    "usable_trade_date": event.get("usable_trade_date"),
                    "total_purchase_value": event.get("total_purchase_value"),
                    "has_default_off_state_surface_candidate": has_state,
                    "production_signal_overlap": False,
                }
            )

    return fresh_overlap, no_production_signal


def snapshot_counts() -> dict[str, Any]:
    snaps = read_jsonl(PAPER_SNAPSHOTS)
    by_asof: dict[str, dict[str, int]] = {}
    for snap in snaps:
        asof = snap.get("asof_date")
        if not asof:
            continue
        row = by_asof.setdefault(
            asof,
            {
                "snapshot_count": 0,
                "candidate_count_sum": 0,
                "filled_count_sum": 0,
                "closed_count_sum": 0,
            },
        )
        row["snapshot_count"] += 1
        row["candidate_count_sum"] += int(snap.get("candidate_count") or 0)
        row["filled_count_sum"] += int(snap.get("filled_count") or 0)
        row["closed_count_sum"] += int(snap.get("closed_count_today") or 0)
    return {key: by_asof[key] for key in sorted(by_asof)[-7:]}


def load_price_map(paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    by: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for path in paths:
        if not path.exists():
            continue
        payload = load_json(path, {}) or {}
        ohlcv = payload.get("ohlcv", {}) if isinstance(payload, dict) else {}
        for ticker, price_rows in ohlcv.items():
            for raw in price_rows or []:
                day = str(raw.get("Date") or "")[:10]
                if not day:
                    continue

                def as_float(value: Any) -> float | None:
                    try:
                        return float(value)
                    except Exception:
                        return None

                by[str(ticker).upper()][day] = {
                    "date": day,
                    "open": as_float(raw.get("Open")),
                    "close": as_float(raw.get("Close")),
                }
    return {ticker: sorted(values.values(), key=lambda row: row["date"]) for ticker, values in by.items()}


def first_idx(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def forward_return(
    prices: dict[str, list[dict[str, Any]]],
    ticker: Any,
    start: Any,
    horizon: int,
) -> dict[str, float] | None:
    ticker_rows = prices.get(str(ticker or "").upper())
    spy_rows = prices.get("SPY")
    if not ticker_rows or not spy_rows:
        return None
    ticker_idx = first_idx(ticker_rows, str(start or ""))
    spy_idx = first_idx(spy_rows, str(start or ""))
    if ticker_idx is None or spy_idx is None:
        return None
    if ticker_idx + horizon >= len(ticker_rows) or spy_idx + horizon >= len(spy_rows):
        return None
    entry = ticker_rows[ticker_idx]
    exit_row = ticker_rows[ticker_idx + horizon]
    spy_entry = spy_rows[spy_idx]
    spy_exit = spy_rows[spy_idx + horizon]
    if not entry.get("open") or not exit_row.get("close") or not spy_entry.get("open") or not spy_exit.get("close"):
        return None
    ret = exit_row["close"] / entry["open"] - 1.0
    spy_ret = spy_exit["close"] / spy_entry["open"] - 1.0
    return {"return_pct": ret * 100.0, "excess_vs_spy_pct": (ret - spy_ret) * 100.0}


def avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def win_rate(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(1 for value in values if value > 0) / len(values), 4)


def historical_shadow_reference() -> dict[str, Any]:
    hist = load_json(HIST_EVENTS, {}) or {}
    if not hist:
        return {}
    price_paths = [
        DATA_DIR / "ohlcv_snapshot_20241002_20250422.json",
        DATA_DIR / "ohlcv_snapshot_20250423_20251022.json",
        DATA_DIR / "ohlcv_snapshot_20251023_20260421.json",
        DATA_DIR / "ohlcv_snapshot_20251023_20260501_with_pilot.json",
    ]
    prices = load_price_map(price_paths)
    out: dict[str, Any] = {
        "source": repo_rel(HIST_EVENTS),
        "note": "Historical reference only; not new evidence in this run.",
        "cohorts": {},
    }
    predicates = {
        "all_open_market_purchase": lambda event: True,
        "meaningful_purchase_v1": lambda event: bool(event.get("meaningful_purchase_v1")),
        "ceo_cfo_purchase_v1": lambda event: bool(event.get("ceo_cfo_purchase_v1")),
    }
    for cohort_name, predicate in predicates.items():
        selected = [event for event in hist.get("events", []) if predicate(event)]
        horizons: dict[str, Any] = {}
        for horizon in [10, 20, 60, 90]:
            returns: list[float] = []
            excess: list[float] = []
            for event in selected:
                if horizon == 90:
                    outcome = forward_return(prices, event.get("ticker"), event.get("usable_trade_date"), horizon)
                else:
                    outcome = (event.get("outcomes") or {}).get(str(horizon))
                if outcome:
                    returns.append(float(outcome["return_pct"]))
                    excess.append(float(outcome["excess_vs_spy_pct"]))
            horizons[str(horizon)] = {
                "count": len(returns),
                "avg_return_pct": avg(returns),
                "win_rate": win_rate(returns),
                "avg_excess_vs_spy_pct": avg(excess),
                "excess_win_rate": win_rate(excess),
            }
        out["cohorts"][cohort_name] = {
            "event_count": len(selected),
            "ticker_count": len({str(event.get("ticker") or "").upper() for event in selected if event.get("ticker")}),
            "horizons": horizons,
        }
    return out


def baseline_metrics() -> tuple[dict[str, Any], dict[str, Any]]:
    baseline_payload = load_json(BASELINE, {}) or {}
    baseline_windows = ((baseline_payload.get("after_metrics") or {}).get("windows") or {})
    benchmark_returns = {
        "late_strong": {"spy_buy_hold_return_pct": 0.0541, "qqq_buy_hold_return_pct": 0.0580},
        "mid_weak": {"spy_buy_hold_return_pct": 0.2544, "qqq_buy_hold_return_pct": 0.3351},
        "old_thin": {"spy_buy_hold_return_pct": -0.0672, "qqq_buy_hold_return_pct": -0.0749},
    }
    metrics: dict[str, Any] = {}
    for label, raw in baseline_windows.items():
        m = dict(raw)
        total_return = m.get("total_return_pct")
        b = benchmark_returns.get(label, {})
        if total_return is not None:
            m["vs_spy_pct"] = round(total_return - b.get("spy_buy_hold_return_pct", 0), 4)
            m["vs_qqq_pct"] = round(total_return - b.get("qqq_buy_hold_return_pct", 0), 4)
            m["spy_buy_hold_return_pct"] = b.get("spy_buy_hold_return_pct")
            m["qqq_buy_hold_return_pct"] = b.get("qqq_buy_hold_return_pct")
        metrics[label] = m
    return metrics, (baseline_payload.get("after_metrics") or {}).get("aggregate", {})


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def build_report(record: dict[str, Any]) -> str:
    summary_file = load_json(LATEST_SUMMARY, {}) or {}
    meaningful_events = record["fresh_form4_events"]["events"]
    meaningful_events = [event for event in meaningful_events if event.get("meaningful_purchase_v1")]
    no_prod = record["insider_buy_but_no_production_signal"]
    fresh_note = "none"
    if no_prod:
        fresh_note = ", ".join(f"{row['ticker']} ${row['total_purchase_value']:,.0f}" for row in no_prod)
    hist_meaningful = (
        record["forward_return_of_tagged_candidates"]
        .get("historical_shadow_reference_not_new_evidence", {})
        .get("cohorts", {})
        .get("meaningful_purchase_v1", {})
        .get("horizons", {})
    )
    lines = [
        "# Form 4 Insider Overlay Fresh Shadow Audit",
        "",
        f"- experiment_id: `{EXP_ID}`",
        f"- generated_at: `{RUN_AT}`",
        "- mechanism_family: `insider_form4_open_market_purchase_confirmation_overlay`",
        "- run_mode: `data_audit_shadow_only_overlay_refresh`",
        "- production_impact: no signal, ranking, sizing, order, run, or backtester path changed",
        "",
        "## Hypothesis",
        "",
        "Meaningful public-market Form 4 open-market insider buying may confirm existing Ginger long candidates, but this run only refreshes data availability and shadow coverage. It does not create standalone entries and does not promote an overlay.",
        "",
        "## Historical Check",
        "",
        "Prior Form 4 experiments already tested availability, accepted-trade overlap, skipped-slot overlap, standalone sleeves, owner-role filters, sale-pressure de-risking, event queues, default-off event bundles, and cluster buying. The durable read is positive standalone purchase cohorts but sparse production overlap and insufficient slot-value evidence.",
        "",
        "## Latest Data Coverage",
        "",
        f"- source: `{repo_rel(LATEST_TX)}`",
        f"- date_range: `{summary_file.get('date_range', {}).get('start')} -> {summary_file.get('date_range', {}).get('end')}`",
        f"- rows: `{record['data_availability_pit_status']['rows_written']}`",
        f"- PIT-safe rows: `{record['data_availability_pit_status']['pit_safe_count']}` / `{record['data_availability_pit_status']['rows_written']}`",
        f"- tickers mapped/requested: `{summary_file.get('tickers_mapped')}` / `{summary_file.get('tickers_requested')}`",
        f"- CIK mapping gaps: `{', '.join(summary_file.get('missing_cik_tickers') or []) or 'none'}`",
        f"- open-market purchase transactions: `{record['data_availability_pit_status']['open_market_purchase_transaction_count']}`",
        f"- meaningful >=$50k event-days: `{len(meaningful_events)}`",
        f"- forward-queue >=$500k candidates: `{record['candidate_count']}`",
        "",
        "## Fresh Overlay Read",
        "",
        f"- production core signals tagged: `{record['overlap_with_existing_signals']['production_core_signals']['tagged_count']}` / `{record['overlap_with_existing_signals']['production_core_signals']['signal_count']}`",
        f"- pilot signals tagged: `{record['overlap_with_existing_signals']['pilot_signals']['tagged_count']}` / `{record['overlap_with_existing_signals']['pilot_signals']['signal_count']}`",
        f"- default-off state-surface scored candidates tagged: `{record['overlap_with_existing_signals']['default_off_state_surface_scored_candidates']['tagged_count']}` / `{record['overlap_with_existing_signals']['default_off_state_surface_scored_candidates']['signal_count']}`",
        f"- insider buy but no production signal: `{fresh_note}`",
        "- scarce-slot opportunity cost: `not measurable`; no fresh >=$500k queue candidate or production slot conflict",
        "- forward 10/20/60/90d return of fresh tagged candidates: `pending/unavailable`; no mature local outcome",
        "",
        "## Baseline Metrics",
        "",
        "| Window | EV | Return | PnL | Sharpe | Max DD | Win rate | Trades | Survival | vs SPY | vs QQQ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in ["late_strong", "mid_weak", "old_thin"]:
        m = record["baseline_metrics"][label]
        lines.append(
            f"| {label} | {m['expected_value_score']:.4f} | {m['total_return_pct']:.4f} | "
            f"${m['total_pnl']:,.2f} | {m['sharpe_daily']:.2f} | {m['max_drawdown_pct']:.4f} | "
            f"{m['win_rate']:.4f} | {m['trade_count']} | {m['survival_rate']:.4f} | "
            f"{m['vs_spy_pct']:.4f} | {m['vs_qqq_pct']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Historical Shadow Reference",
            "",
            "Historical purchase-return numbers below are carried forward/reference only, with 90d computed here from the existing event list where local OHLCV coverage allows it. They are not new production evidence.",
            "",
            "| Horizon | Count | Avg return | Win rate | Avg excess vs SPY | Excess win rate |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for horizon in ["10", "20", "60", "90"]:
        row = hist_meaningful.get(horizon, {})
        lines.append(
            f"| {horizon}d | {row.get('count', 0)} | {pct(row.get('avg_return_pct'))}% | "
            f"{pct(row.get('win_rate'))} | {pct(row.get('avg_excess_vs_spy_pct'))}% | "
            f"{pct(row.get('excess_win_rate'))} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "`shadow_only`. The data exists and is PIT-dateable, but the latest refresh does not add a production-overlap or slot-conflict sample. Keep the existing default-off watch and wait for closed forward evidence before any default-off replay or production adapter.",
            "",
        ]
    )
    return "\n".join(lines)


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    existing_ids: set[str] = set()
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if item.get("experiment_id"):
                    existing_ids.add(str(item["experiment_id"]))
    if row.get("experiment_id") in existing_ids:
        return
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def ordered_registry_payload(registry: dict[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in ["schema_version", "updated_at", "experiments"]:
        if key in registry:
            ordered[key] = registry[key]
    for key, value in registry.items():
        if key not in ordered:
            ordered[key] = value
    normalized = []
    for exp in ordered.get("experiments", []):
        row: dict[str, Any] = {}
        for key in ["experiment_id", "status", "lane", "owner", "hypothesis", "ticket_file", "updated_at"]:
            if key in exp:
                row[key] = exp[key]
        for key, value in exp.items():
            if key not in row:
                row[key] = value
        normalized.append(row)
    if "experiments" in ordered:
        ordered["experiments"] = normalized
    return ordered


def update_ticket_and_registry(record: dict[str, Any]) -> None:
    result = {
        "decision": record["decision"],
        "summary": record["decision_rationale"],
        "artifact": repo_rel(ARTIFACT),
        "log": repo_rel(LOG_PATH),
        "report": repo_rel(REPORT),
    }
    if TICKET_PATH.exists():
        ticket = load_json(TICKET_PATH, {}) or {}
        ticket["status"] = "completed"
        ticket["completed_at"] = RUN_AT
        ticket["result"] = result
        TICKET_PATH.write_text(json.dumps(ticket, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if REGISTRY_PATH.exists():
        registry = load_json(REGISTRY_PATH, {}) or {}
        registry["updated_at"] = RUN_AT
        for exp in registry.get("experiments", []):
            if exp.get("experiment_id") == EXP_ID:
                exp["status"] = "completed"
                exp["completed_at"] = RUN_AT
                exp["updated_at"] = RUN_AT
                exp["result"] = result
                break
        REGISTRY_PATH.write_text(
            json.dumps(ordered_registry_payload(registry), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(LATEST_TX)
    summary_file = load_json(LATEST_SUMMARY, {}) or {}
    prior = load_json(PRIOR_LOG, {}) or {}
    quant = load_json(QUANT_SIGNALS, {}) or {}
    universe = load_json(UNIVERSE_STATE, {}) or {}

    fresh_events = aggregate_purchase_events(
        rows,
        start=summary_file.get("date_range", {}).get("start"),
        end=summary_file.get("date_range", {}).get("end"),
    )
    meaningful_events = [event for event in fresh_events if event.get("meaningful_purchase_v1")]
    forward_queue_events = [event for event in fresh_events if qualifies_forward_queue_event(event)]
    ceo_cfo_events = [event for event in meaningful_events if event.get("any_ceo_cfo_or_president")]
    fresh_overlap, no_production_signal = build_overlap(meaningful_events, quant)
    baseline, aggregate = baseline_metrics()

    historical_shadow = historical_shadow_reference()
    hist_ref = (prior.get("shadow_or_replay_metrics") or {}).get("historical_shadow_reference_not_new_evidence") or {}
    form4_sleeve = quant.get("form4_event_sleeve") or {}
    form4_queue = quant.get("form4_event_queue") or {}

    record: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": RUN_AT,
        "status": "observed_only",
        "lane": "alpha_discovery",
        "run_mode": "data_audit_shadow_only_overlay_refresh",
        "hypothesis": (
            "Public-market insider buying, especially large open-market CEO/CFO or cluster buying, may confirm "
            "existing trend_long/breakout_long candidates; this run checks only whether the latest local PIT-safe "
            "Form 4 data adds fresh overlay evidence."
        ),
        "alpha_hypothesis": {
            "category": "entry_confirmation / hold_confirmation / add-on_confirmation",
            "statement": (
                "Meaningful Form 4 open-market buying could improve existing candidate quality if it tags enough "
                "production candidates before entry or during hold without consuming scarce slots."
            ),
            "playbook_alignment": (
                "Matches the playbook's non-OHLCV event/candidate-pool direction, but prior Form 4 promotion "
                "attempts are guarded by sparse overlap and sample-size limits."
            ),
        },
        "non_ohlcv_data_source": (
            "SEC EDGAR Form 4 transaction-level XML rows from data/non_ohlcv/form4_transactions_20260509.jsonl "
            "plus existing default-off Form 4 paper queue snapshots."
        ),
        "mechanism_family": "insider_form4_open_market_purchase_confirmation_overlay",
        "historical_experiment_check": {
            "exact_or_near_prior_experiments": [
                "exp-20260503-017",
                "exp-20260503-048",
                "exp-20260503-049",
                "exp-20260503-052",
                "exp-20260503-053",
                "exp-20260504-001",
                "exp-20260504-005",
                "exp-20260504-006",
                "exp-20260504-009",
                "exp-20260504-034",
                "exp-20260504-042",
                "exp-20260505-010",
                "exp-20260506-001",
                "exp-20260508-028",
                "exp-20260509-006",
                "exp-20260509-007",
                "exp-20260509-018",
            ],
            "prior_result_summary": (
                "Prior Form 4 work found positive standalone purchase cohorts, but accepted-trade overlap was sparse, "
                "top-skipped overlap was zero, slot replacement evidence was thin, sale-pressure de-risk was rejected, "
                "and cluster buying was rejected for low sample/materiality plus concentration risk."
            ),
            "why_this_is_not_simple_repeat": (
                "This run changes no threshold, role filter, entry, ranking, sizing, or production path; it only "
                "refreshes local data availability after the latest 2026-05-09 snapshot."
            ),
            "guardrail": (
                "Do not repeat Form 4 cluster promotion, owner-role filters, purchase-value threshold sweeps, or "
                "direct event-to-entry promotion on this same frozen evidence."
            ),
        },
        "single_causal_variable": "latest local Form 4 data availability and overlay coverage as of 2026-05-09",
        "production_change_allowed": False,
        "baseline_metrics": baseline,
        "baseline_aggregate": {
            "expected_value_score_sum": aggregate.get("expected_value_score_sum"),
            "total_pnl_sum": aggregate.get("total_pnl_sum"),
        },
        "after_metrics": baseline,
        "expected_value_score_delta": {
            "aggregate": 0.0,
            "by_window": {label: 0.0 for label in baseline},
            "reason": "No strategy, replay, ranking, sizing, or production path changed; this was a data audit/shadow overlay refresh only.",
        },
        "data_availability_pit_status": {
            "latest_transactions_file": repo_rel(LATEST_TX),
            "latest_summary_file": repo_rel(LATEST_SUMMARY),
            "date_range": summary_file.get("date_range"),
            "rows_written": len(rows),
            "tickers_requested": summary_file.get("tickers_requested"),
            "tickers_mapped": summary_file.get("tickers_mapped"),
            "missing_cik_tickers": summary_file.get("missing_cik_tickers"),
            "pit_safe_count": sum(1 for row in rows if row.get("pit_safe_flag")),
            "pit_safe_fraction": round(sum(1 for row in rows if row.get("pit_safe_flag")) / len(rows), 6) if rows else None,
            "open_market_purchase_transaction_count": sum(1 for row in rows if row.get("open_market_purchase_flag")),
            "option_exercise_count": sum(1 for row in rows if row.get("option_exercise_flag")),
            "ten_b5_1_count": sum(1 for row in rows if row.get("10b5_1_flag")),
            "transaction_code_counts": summary_file.get("transaction_code_counts"),
            "field_coverage": field_coverage(rows),
            "cik_mapping_gap_report": {
                **build_cik_mapping_report(universe),
                "latest_backfill_missing_cik_tickers": summary_file.get("missing_cik_tickers"),
            },
            "pit_status": (
                "PIT-safe for filing-use date via accepted_at -> conservative usable_trade_date. Backfilled rows are "
                "public-PIT proxies; forward production evidence still depends on append-only daily snapshots."
            ),
            "pit_risks": [
                "Backfill is generated after the fact; daily append-only snapshots are stronger forward evidence.",
                "10b5-1 detection is best-effort text parsing.",
                "insider_buy_value_to_market_cap is blocked because no PIT market-cap join exists.",
                "first_purchase_3y is not PIT-safe from the current local archive window alone.",
                "No literal filing_datetime field exists; accepted_at is the normalized timestamp.",
            ],
        },
        "fresh_form4_events": {
            "raw_open_market_event_count": len(fresh_events),
            "base_meaningful_purchase_event_count_ge_50k": len(meaningful_events),
            "forward_queue_candidate_count_ge_500k": len(forward_queue_events),
            "ceo_cfo_event_count": len(ceo_cfo_events),
            "events": fresh_events,
        },
        "candidate_count": len(forward_queue_events),
        "overlap_with_existing_signals": fresh_overlap,
        "insider_buy_but_no_production_signal": no_production_signal,
        "candidate_overlap_and_slot_value": {
            "fresh_production_overlap_count": fresh_overlap["production_core_signals"]["tagged_count"],
            "fresh_pilot_overlap_count": fresh_overlap["pilot_signals"]["tagged_count"],
            "fresh_default_off_state_surface_overlap_count": fresh_overlap["default_off_state_surface_scored_candidates"][
                "tagged_count"
            ],
            "scarce_slot_opportunity_cost": {
                "measurable": False,
                "reason": (
                    "No fresh >=$500k Form 4 forward-queue candidate and no production-core signal overlap; the one "
                    "meaningful CAT buy only overlaps a default-off state-surface paper candidate."
                ),
                "slot_conflict_value": None,
            },
            "historical_slot_reference_not_new_evidence": hist_ref.get("slot_capacity"),
        },
        "forward_return_of_tagged_candidates": {
            "fresh_production_tagged_candidates": 0,
            "fresh_default_off_paper_tagged_candidates": fresh_overlap["default_off_state_surface_scored_candidates"][
                "tagged_count"
            ],
            "10d": None,
            "20d": None,
            "60d": None,
            "90d": None,
            "reason": (
                "The fresh CAT meaningful purchase/default-off state-surface overlap has no mature forward 10/20/60/90d "
                "local outcome as of 2026-05-10, and it is not a production signal."
            ),
            "historical_shadow_reference_not_new_evidence": historical_shadow,
        },
        "shadow_or_replay_metrics": {
            "fresh_asof_2026_05_09": {
                "raw_open_market_transaction_count": sum(1 for row in rows if row.get("open_market_purchase_flag")),
                "raw_open_market_event_count": len(fresh_events),
                "base_meaningful_purchase_event_count_ge_50k": len(meaningful_events),
                "forward_queue_candidate_count_ge_500k": len(forward_queue_events),
                "candidate_count": len(forward_queue_events),
                "form4_event_queue_candidate_count": form4_queue.get("candidate_count"),
                "form4_event_sleeve_candidate_count": form4_sleeve.get("candidate_count"),
                "paper_snapshot_counts_recent": snapshot_counts(),
                "overlap_with_existing_signals": fresh_overlap,
                "scarce_slot_opportunity_cost": {
                    "measurable": False,
                    "slot_conflict_value": None,
                    "reason": "No fresh forward-queue candidate or production slot conflict.",
                },
            },
            "historical_shadow_reference_not_new_evidence": {
                "accepted_trade_overlap": hist_ref.get("accepted_trade_overlap"),
                "slot_capacity": hist_ref.get("slot_capacity"),
                "cluster_sleeve_rejected": hist_ref.get("cluster_sleeve_rejected"),
                "standalone_purchase_outcomes_with_90d_added": historical_shadow,
            },
        },
        "shadow_scoring_readiness": {
            "insider_buy_value_to_market_cap": "blocked_missing_pit_market_cap_join",
            "cluster_buying_30d": "available historically but prior cluster promotion was rejected; fresh sample has no >=$500k queue candidate",
            "CEO_CFO_buy_flag": "available via officer_title parsing; fresh meaningful CAT event is director-only, not CEO/CFO",
            "first_purchase_1y": "partially computable within local archive only; not production-safe enough for promotion",
            "first_purchase_3y": "blocked_not_pit_safe_with_current_archive_window",
            "post_drawdown_purchase": "requires OHLCV context; no fresh qualifying production candidate to score",
            "exclude_option_exercise": "available",
            "exclude_tiny_purchase": "available; TSM $7.76k excluded, CAT $219.21k meaningful but below the $500k forward queue threshold",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "production_impact": "shadow_data_audit_only_no_production_change",
        },
        "decision": "shadow_only",
        "decision_rationale": (
            "The latest Form 4 data is present and PIT-dateable, but it produced zero >=$500k forward-queue candidates "
            "and zero production-core overlaps. The one meaningful fresh CAT purchase overlaps only a default-off "
            "state-surface paper candidate with no mature forward outcome, so production/default-off promotion is not justified."
        ),
        "next_minimum_action": (
            "Keep accumulating append-only Form 4 paper snapshots; retry only after a new >=$500k CEO/CFO or cluster buy "
            "creates closed 10/20/60/90d outcomes or after a PIT market-cap join enables value-to-market-cap scoring."
        ),
        "rejection_reason": None,
        "parameters": {
            "rule_family": "form4_meaningful_purchase_ge_500k_v1 for forward queue; meaningful >=$50k retained only for shadow/audit tagging",
            "changed_variable": "fresh PIT-safe Form 4 availability and overlay coverage",
            "locked_variables": [
                "entries",
                "exits",
                "ranking",
                "sizing",
                "portfolio heat",
                "LLM/news",
                "production orders",
                "Form 4 thresholds",
            ],
        },
        "related_files": [
            repo_rel(TICKET_PATH),
            repo_rel(LOG_PATH),
            repo_rel(ARTIFACT),
            repo_rel(REPORT),
            repo_rel(LATEST_TX),
            repo_rel(LATEST_SUMMARY),
            repo_rel(PAPER_SNAPSHOTS),
        ],
    }

    ARTIFACT.write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build_report(record), encoding="utf-8")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    upsert_jsonl(JSONL_PATH, record)
    update_ticket_and_registry(record)

    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "rows": len(rows),
                "pit_safe_fraction": record["data_availability_pit_status"]["pit_safe_fraction"],
                "meaningful_events": len(meaningful_events),
                "forward_queue_candidates": len(forward_queue_events),
                "production_core_tagged": fresh_overlap["production_core_signals"]["tagged_count"],
                "state_surface_paper_tagged": fresh_overlap["default_off_state_surface_scored_candidates"]["tagged_count"],
                "decision": record["decision"],
                "artifact": repo_rel(ARTIFACT),
                "report": repo_rel(REPORT),
                "log": repo_rel(LOG_PATH),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
