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


EXP_ID = "exp-20260512-042"
RUN_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")
DATA_DIR = ROOT / "data"
OUT_DIR = DATA_DIR / "experiments" / EXP_ID
ARTIFACT = OUT_DIR / "form4_insider_overlay_refresh.json"
LOG_PATH = ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_PATH = ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
REPORT = ROOT / "docs" / "non_ohlcv_data_audit" / f"form4_insider_overlay_{EXP_ID}_20260512.md"
JSONL_PATH = ROOT / "docs" / "experiment_log.jsonl"

LATEST_TAG = "20260511"
LATEST_TX = DATA_DIR / "non_ohlcv" / f"form4_transactions_{LATEST_TAG}.jsonl"
LATEST_SUMMARY = DATA_DIR / "non_ohlcv" / f"form4_backfill_summary_{LATEST_TAG}.json"
QUANT_SIGNALS = DATA_DIR / f"quant_signals_{LATEST_TAG}.json"
UNIVERSE_STATE = DATA_DIR / f"universe_state_{LATEST_TAG}.json"
SEC_TICKERS = DATA_DIR / "sec_company_tickers.json"
PAPER_STATE = DATA_DIR / "form4_event_sleeve_paper_state.json"
PAPER_SNAPSHOTS = DATA_DIR / "form4_event_sleeve_paper_snapshots.jsonl"
BASELINE_ARTIFACT = DATA_DIR / "experiments" / "exp-20260510-015" / "trip_sector_taxonomy.json"
PRIOR_OVERLAY_LOG = ROOT / "docs" / "experiments" / "logs" / "exp-20260511-035.json"
PRIOR_CLUSTER_LOG = ROOT / "docs" / "experiments" / "logs" / "exp-20260512-017.json"
HISTORICAL_OUTCOMES = DATA_DIR / "non_ohlcv" / "form4_purchase_shadow_outcomes_20241002_20260421.json"

NON_COMPANY = {"SPY", "QQQ", "IWM", "GLD", "IAU", "SLV", "ARKX", "UFO"}
REQUIRED_FIELDS = [
    "ticker",
    "cik",
    "accession_number",
    "accepted_at",
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


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                row = json.loads(text)
                if isinstance(row, dict):
                    out.append(row)
    return out


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def repo_rel(path: Path | str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    try:
        return str(p.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def field_coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    total = len(rows)
    coverage: dict[str, dict[str, Any]] = {}
    for field in REQUIRED_FIELDS:
        count = sum(1 for row in rows if present(row.get(field)))
        coverage[field] = {
            "present_rows": count,
            "total_rows": total,
            "coverage": round(count / total, 6) if total else None,
        }
    coverage["filing_datetime"] = {
        "source_field": "accepted_at",
        "present_rows": coverage["accepted_at"]["present_rows"],
        "total_rows": total,
        "coverage": coverage["accepted_at"]["coverage"],
        "normalization_note": "accepted_at is the EDGAR acceptance timestamp used as filing_datetime.",
    }
    return coverage


def load_sec_map() -> dict[str, str]:
    payload = load_json(SEC_TICKERS, {}) or {}
    rows = payload.values() if isinstance(payload, dict) else payload
    mapping: dict[str, str] = {}
    for row in rows or []:
        if isinstance(row, dict) and row.get("ticker") and row.get("cik_str"):
            mapping[str(row["ticker"]).upper()] = str(row["cik_str"]).zfill(10)
    return mapping


def mapping_report(universe: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    mapping = load_sec_map()

    def segment(key: str) -> dict[str, Any]:
        tickers = [str(t).upper() for t in universe.get(key, [])]
        company = [ticker for ticker in tickers if ticker not in NON_COMPANY]
        return {
            "segment_key": key,
            "ticker_count": len(tickers),
            "company_ticker_count": len(company),
            "mapped_company_ticker_count": sum(1 for ticker in company if ticker in mapping),
            "missing_company_tickers": sorted(ticker for ticker in company if ticker not in mapping),
            "non_company_excluded": sorted(ticker for ticker in tickers if ticker in NON_COMPANY),
        }

    pilot_key = "pilot_trade_universe" if universe.get("pilot_trade_universe") else "governance_tradeable_universe"
    return {
        "mapping_source": repo_rel(SEC_TICKERS),
        "core_trade_universe": segment("core_trade_universe"),
        "pilot_universe": segment(pilot_key),
        "observation_universe": segment("observation_universe"),
        "latest_backfill_missing_cik_tickers": summary.get("missing_cik_tickers") or [],
    }


def accepted_baseline() -> tuple[dict[str, Any], dict[str, Any]]:
    fallback = {
        "late_strong": {
            "expected_value_score": 4.2340,
            "total_return_pct": 0.9409,
            "total_pnl": 94086.91,
            "sharpe_daily": 4.50,
            "max_drawdown_pct": 0.0548,
            "win_rate": 0.7895,
            "trade_count": 19,
            "signals_generated": 51,
            "signals_survived": 41,
            "survival_rate": 0.8039,
            "spy_buy_hold_return_pct": 0.0541,
            "qqq_buy_hold_return_pct": 0.0580,
        },
        "mid_weak": {
            "expected_value_score": 1.6689,
            "total_return_pct": 0.6181,
            "total_pnl": 61813.40,
            "sharpe_daily": 2.70,
            "max_drawdown_pct": 0.0941,
            "win_rate": 0.5238,
            "trade_count": 21,
            "signals_generated": 53,
            "signals_survived": 42,
            "survival_rate": 0.7925,
            "spy_buy_hold_return_pct": 0.2544,
            "qqq_buy_hold_return_pct": 0.3351,
        },
        "old_thin": {
            "expected_value_score": 0.3853,
            "total_return_pct": 0.2854,
            "total_pnl": 28544.11,
            "sharpe_daily": 1.35,
            "max_drawdown_pct": 0.0815,
            "win_rate": 0.4091,
            "trade_count": 22,
            "signals_generated": 60,
            "signals_survived": 55,
            "survival_rate": 0.9167,
            "spy_buy_hold_return_pct": -0.0672,
            "qqq_buy_hold_return_pct": -0.0749,
        },
    }
    payload = load_json(BASELINE_ARTIFACT, {}) or {}
    windows: dict[str, Any] = {}
    for label, default in fallback.items():
        metrics = dict(default)
        row = (payload.get("by_window") or {}).get(label, {})
        after = row.get("after_metrics") or {}
        for key in [
            "expected_value_score",
            "total_return_pct",
            "total_pnl",
            "sharpe_daily",
            "max_drawdown_pct",
            "win_rate",
            "trade_count",
            "signals_generated",
            "signals_survived",
            "survival_rate",
        ]:
            if key in after:
                metrics[key] = after[key]
        metrics["vs_spy_pct"] = round(metrics["total_return_pct"] - metrics["spy_buy_hold_return_pct"], 4)
        metrics["vs_qqq_pct"] = round(metrics["total_return_pct"] - metrics["qqq_buy_hold_return_pct"], 4)
        windows[label] = metrics
    aggregate = {
        "expected_value_score_sum": round(sum(row["expected_value_score"] for row in windows.values()), 6),
        "total_pnl_sum": round(sum(row["total_pnl"] for row in windows.values()), 2),
        "trade_count_sum": sum(int(row["trade_count"]) for row in windows.values()),
        "min_survival_rate": min(row["survival_rate"] for row in windows.values()),
        "max_drawdown_pct_max": max(row["max_drawdown_pct"] for row in windows.values()),
    }
    return windows, aggregate


def signal_rows(container: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = container.get(key)
    return rows if isinstance(rows, list) else []


def extract_candidate_surfaces(quant: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    state = quant.get("state_surface_queue") or {}
    return {
        "production_core_signals": signal_rows(quant, "signals"),
        "pilot_signals": signal_rows(quant, "pilot_signals"),
        "default_off_state_surface_scored_candidates": state.get("scored_candidates") or [],
        "default_off_state_surface_allowed_candidates": state.get("candidates") or [],
        "form4_event_queue_candidates": (quant.get("form4_event_queue") or {}).get("candidates") or [],
        "form4_event_sleeve_candidates": (quant.get("form4_event_sleeve") or {}).get("candidates") or [],
    }


def overlap(events: list[dict[str, Any]], quant: dict[str, Any]) -> dict[str, Any]:
    events_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        events_by_ticker[str(event.get("ticker") or "").upper()].append(event)

    out: dict[str, Any] = {}
    for surface, rows in extract_candidate_surfaces(quant).items():
        matches = []
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            if ticker not in events_by_ticker:
                continue
            matches.append({
                "ticker": ticker,
                "surface": surface,
                "signal_date": row.get("date") or row.get("created_asof") or row.get("usable_trade_date") or row.get("entry_date"),
                "strategy": row.get("strategy") or row.get("surface") or row.get("source"),
                "trade_enabled": bool(row.get("trade_enabled") or row.get("pilot_trade_enabled")),
                "matched_form4_events": events_by_ticker[ticker],
            })
        out[surface] = {
            "candidate_count": len(rows),
            "tagged_count": len(matches),
            "matches": matches,
        }
    return out


def add_fresh_event_context(events: list[dict[str, Any]], historical_events: list[dict[str, Any]]) -> None:
    by_ticker = defaultdict(list)
    for event in sorted(historical_events + events, key=lambda row: (row.get("usable_trade_date") or "", row.get("ticker") or "")):
        ticker = str(event.get("ticker") or "").upper()
        date = str(event.get("usable_trade_date") or "")[:10]
        if not ticker or not date:
            continue
        prior = [row for row in by_ticker[ticker] if row.get("usable_trade_date") < date]
        event["cluster_buying_30d_partial"] = sum(
            1 for row in prior
            if 0 <= days_between(str(row.get("usable_trade_date")), date) <= 30
        ) >= 1 or int(event.get("owner_count") or 0) >= 2
        event["first_purchase_1y_local_archive"] = not any(
            0 < days_between(str(row.get("usable_trade_date")), date) <= 366
            for row in prior
        )
        by_ticker[ticker].append(event)


def days_between(start: str, end: str) -> int:
    start_dt = datetime.strptime(start[:10], "%Y-%m-%d")
    end_dt = datetime.strptime(end[:10], "%Y-%m-%d")
    return (end_dt - start_dt).days


def historical_reference() -> dict[str, Any]:
    prior_overlay = load_json(PRIOR_OVERLAY_LOG, {}) or {}
    prior_cluster = load_json(PRIOR_CLUSTER_LOG, {}) or {}
    outcomes = load_json(HISTORICAL_OUTCOMES, {}) or {}
    prior_overlay_hist = (
        (prior_overlay.get("forward_return_of_tagged_candidates") or {})
        .get("historical_shadow_reference_not_new_evidence")
        or {}
    )
    outcomes_with_90d = (
        prior_overlay_hist.get("standalone_purchase_outcomes_with_90d_added")
        or {}
    )
    outcome_cohorts = outcomes_with_90d.get("cohorts") or outcomes.get("cohorts") or {}
    return {
        "prior_overlay_experiment": {
            "experiment_id": prior_overlay.get("experiment_id"),
            "decision": prior_overlay.get("decision"),
            "summary": prior_overlay.get("decision_rationale"),
            "fresh_forward_queue_candidates": (prior_overlay.get("fresh_form4_events") or {}).get("forward_queue_candidate_count_ge_500k"),
        },
        "prior_cluster_preentry_rs": {
            "experiment_id": prior_cluster.get("experiment_id"),
            "decision": prior_cluster.get("decision"),
            "aggregate_delta": prior_cluster.get("aggregate_delta"),
            "gate4": prior_cluster.get("gate4"),
        },
        "standalone_purchase_forward_outcomes": {
            "source": (
                outcomes_with_90d.get("source")
                or repo_rel(HISTORICAL_OUTCOMES)
            ),
            "cohorts": outcome_cohorts,
        },
    }


def snapshot_counts() -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for snap in read_jsonl(PAPER_SNAPSHOTS):
        day = snap.get("asof_date")
        if not day:
            continue
        row = counts.setdefault(day, {"snapshot_count": 0, "candidate_count_sum": 0, "filled_count_sum": 0, "closed_count_sum": 0})
        row["snapshot_count"] += 1
        row["candidate_count_sum"] += int(snap.get("candidate_count") or 0)
        row["filled_count_sum"] += int(snap.get("filled_count") or 0)
        row["closed_count_sum"] += int(snap.get("closed_count_today") or 0)
    return {day: counts[day] for day in sorted(counts)[-8:]}


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    existing = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(json.loads(line).get("experiment_id"))
            except Exception:
                pass
    if row["experiment_id"] in existing:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.4f}"


def build_report(record: dict[str, Any]) -> str:
    baseline = record["baseline_metrics"]
    hist = record["historical_experiment_check"]["historical_shadow_reference"]["standalone_purchase_forward_outcomes"]["cohorts"]
    meaningful = (hist.get("meaningful_purchase_v1") or {}).get("horizons") or {}
    lines = [
        "# Form 4 Insider Overlay Refresh",
        "",
        f"- experiment_id: `{EXP_ID}`",
        f"- generated_at: `{RUN_AT}`",
        "- mechanism_family: `insider_form4_open_market_purchase_confirmation_overlay`",
        "- run_mode: `data_audit_shadow_only`",
        "- production_impact: no production signal, ranking, sizing, order, run, or backtest path changed",
        "",
        "## Hypothesis",
        "",
        record["hypothesis"],
        "",
        "## Data Availability / PIT",
        "",
        f"- source: `{record['non_ohlcv_data_source']}`",
        f"- date_range: `{record['data_availability_pit_status']['date_range']['start']} -> {record['data_availability_pit_status']['date_range']['end']}`",
        f"- rows: `{record['data_availability_pit_status']['rows_written']}`",
        f"- PIT-safe rows: `{record['data_availability_pit_status']['pit_safe_count']}`",
        f"- CIK mapping gap: `{', '.join(record['data_availability_pit_status']['missing_cik_tickers']) or 'none'}`",
        f"- open-market purchase transactions: `{record['data_availability_pit_status']['open_market_purchase_transaction_count']}`",
        f"- meaningful >=$50k event-days: `{record['shadow_or_replay_metrics']['fresh']['meaningful_purchase_event_count_ge_50k']}`",
        f"- forward queue >=$500k candidates: `{record['shadow_or_replay_metrics']['fresh']['forward_queue_candidate_count_ge_500k']}`",
        "",
        "## Baseline Metrics",
        "",
        "| Window | EV | Return | PnL | Sharpe | Max DD | Win rate | Trades | Generated | Survived | Survival | vs SPY | vs QQQ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in ["late_strong", "mid_weak", "old_thin"]:
        m = baseline[label]
        lines.append(
            f"| {label} | {m['expected_value_score']:.4f} | {m['total_return_pct']:.4f} | "
            f"${m['total_pnl']:,.2f} | {m['sharpe_daily']:.2f} | {m['max_drawdown_pct']:.4f} | "
            f"{m['win_rate']:.4f} | {m['trade_count']} | {int(m['signals_generated'])} | "
            f"{int(m['signals_survived'])} | {m['survival_rate']:.4f} | {m['vs_spy_pct']:.4f} | "
            f"{m['vs_qqq_pct']:.4f} |"
        )
    lines.extend([
        "",
        "## Fresh Shadow Overlay",
        "",
        f"- production-core tagged candidates: `{record['candidate_overlap_and_slot_value']['fresh_production_core_overlap_count']}`",
        f"- pilot tagged candidates: `{record['candidate_overlap_and_slot_value']['fresh_pilot_overlap_count']}`",
        f"- default-off state-surface tagged candidates: `{record['candidate_overlap_and_slot_value']['fresh_state_surface_overlap_count']}`",
        f"- scarce-slot value: `{record['candidate_overlap_and_slot_value']['scarce_slot_opportunity_cost']['reason']}`",
        f"- forward returns: `{record['forward_return_of_tagged_candidates']['reason']}`",
        "",
        "## Historical Reference",
        "",
        "These rows are carried forward from prior artifacts; they are not new acceptance evidence.",
        "",
        "| Cohort | Horizon | Count | Avg return | Win rate | Avg excess vs SPY | Excess win rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for horizon in ["5", "10", "20", "60", "90"]:
        row = meaningful.get(horizon, {})
        lines.append(
            f"| meaningful_purchase_v1 | {horizon}d | {row.get('count', 0)} | "
            f"{_fmt_pct(row.get('avg_return_pct'))}% | {_fmt_pct(row.get('win_rate'))} | "
            f"{_fmt_pct(row.get('avg_excess_vs_spy_pct'))}% | {_fmt_pct(row.get('excess_win_rate'))} |"
        )
    lines.extend([
        "",
        "## Decision",
        "",
        "`shadow_only`. Data is present and PIT-dateable, but the latest snapshot has no production-core Form 4 overlay hit and no mature forward outcome. Keep collecting append-only paper evidence.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    rows = read_jsonl(LATEST_TX)
    summary = load_json(LATEST_SUMMARY, {}) or {}
    quant = load_json(QUANT_SIGNALS, {}) or {}
    universe = load_json(UNIVERSE_STATE, {}) or {}
    paper_state = load_json(PAPER_STATE, {}) or {}

    start = (summary.get("date_range") or {}).get("start")
    end = (summary.get("date_range") or {}).get("end")
    events = aggregate_purchase_events(rows, start=start, end=end)
    meaningful = [event for event in events if event.get("meaningful_purchase_v1")]
    forward_queue = [event for event in events if qualifies_forward_queue_event(event)]

    historical_payload = load_json(HISTORICAL_OUTCOMES, {}) or {}
    historical_events = [event for event in historical_payload.get("events") or [] if event.get("meaningful_purchase_v1")]
    add_fresh_event_context(meaningful, historical_events)

    overlaps = overlap(meaningful, quant)
    baseline, baseline_aggregate = accepted_baseline()
    historical = historical_reference()

    record: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": RUN_AT,
        "status": "observed_only",
        "lane": "alpha_discovery",
        "change_type": "data_audit_shadow_overlay",
        "component": "docs/experiments/logs, docs/non_ohlcv_data_audit, data/experiments artifact only",
        "hypothesis": "Public-market insider Form 4 buying, especially CEO/CFO large buys, clustered buys, first buys, and post-drawdown buys, may confirm existing trend_long/breakout_long candidates. This run refreshes local PIT-safe availability and existing-signal shadow overlap only.",
        "non_ohlcv_data_source": repo_rel(LATEST_TX),
        "mechanism_family": "insider_form4_open_market_purchase_confirmation_overlay",
        "historical_experiment_check": {
            "exact_or_near_prior_experiments": [
                "exp-20260503-017",
                "exp-20260503-048",
                "exp-20260503-052",
                "exp-20260503-053",
                "exp-20260504-001",
                "exp-20260504-034",
                "exp-20260505-010",
                "exp-20260508-028",
                "exp-20260510-016",
                "exp-20260511-035",
                "exp-20260512-017",
            ],
            "prior_result_summary": "Form 4 data is now available and PIT-dateable; historical meaningful purchases were positive as standalone shadow events, accepted-trade overlap was sparse, sale-pressure was rejected, raw cluster promotion was positive but under materiality, and pre-entry RS cluster replay was rejected for sample/materiality.",
            "new_evidence_this_run": "Latest local Form 4 transaction file is 2026-05-11 with 882 rows, 30 open-market purchase transactions, and 1 SNXX CIK mapping gap.",
            "anti_repeat_guardrail": "Do not retune Form 4 purchase-value thresholds, owner-role filters, cluster windows, or production promotion on this same sparse fresh sample.",
            "historical_shadow_reference": historical,
        },
        "single_causal_variable": "latest local Form 4 transaction availability and existing-signal overlay coverage as of 2026-05-11",
        "run_mode": "data_audit_shadow_only",
        "production_change_allowed": False,
        "date_range": {
            "late_strong": "2025-10-23 -> 2026-04-21",
            "mid_weak": "2025-04-23 -> 2025-10-22",
            "old_thin": "2024-10-02 -> 2025-04-22",
            "fresh_snapshot": f"{start} -> {end}",
        },
        "baseline_metrics": baseline,
        "baseline_aggregate": baseline_aggregate,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "expected_value_score_delta": {
            "aggregate": 0.0,
            "by_window": {label: 0.0 for label in baseline},
            "reason": "No strategy, replay, ranking, sizing, threshold, or production path changed.",
        },
        "data_availability_pit_status": {
            "latest_transactions_file": repo_rel(LATEST_TX),
            "latest_summary_file": repo_rel(LATEST_SUMMARY),
            "date_range": summary.get("date_range"),
            "rows_written": len(rows),
            "tickers_requested": summary.get("tickers_requested"),
            "tickers_mapped": summary.get("tickers_mapped"),
            "missing_cik_tickers": summary.get("missing_cik_tickers") or [],
            "pit_safe_count": sum(1 for row in rows if row.get("pit_safe_flag")),
            "pit_safe_fraction": round(sum(1 for row in rows if row.get("pit_safe_flag")) / len(rows), 6) if rows else None,
            "open_market_purchase_transaction_count": sum(1 for row in rows if row.get("open_market_purchase_flag")),
            "option_exercise_count": sum(1 for row in rows if row.get("option_exercise_flag")),
            "ten_b5_1_count": sum(1 for row in rows if row.get("10b5_1_flag")),
            "transaction_code_counts": summary.get("transaction_code_counts"),
            "field_coverage": field_coverage(rows),
            "cik_mapping_gap_report": mapping_report(universe, summary),
            "pit_status": "PIT-safe for filing-use date via accepted_at to conservative usable_trade_date; historical backfill remains a public-PIT proxy and forward append-only snapshots are stronger evidence.",
            "pit_risks": [
                "Backfilled rows were generated after the fact.",
                "10b5-1 detection is best-effort text parsing.",
                "insider_buy_value_to_market_cap is blocked because no PIT market-cap join exists.",
                "first_purchase_3y is not PIT-safe because the local Form 4 archive starts in 2024.",
            ],
        },
        "shadow_or_replay_metrics": {
            "fresh": {
                "open_market_event_count": len(events),
                "meaningful_purchase_event_count_ge_50k": len(meaningful),
                "forward_queue_candidate_count_ge_500k": len(forward_queue),
                "ceo_cfo_meaningful_event_count": sum(1 for event in meaningful if event.get("any_ceo_cfo_or_president")),
                "cluster_buying_30d_partial_event_count": sum(1 for event in meaningful if event.get("cluster_buying_30d_partial")),
                "first_purchase_1y_local_archive_count": sum(1 for event in meaningful if event.get("first_purchase_1y_local_archive")),
                "events": meaningful,
                "overlap_with_existing_signals": overlaps,
                "form4_event_queue_candidate_count": (quant.get("form4_event_queue") or {}).get("candidate_count"),
                "form4_event_sleeve_candidate_count": (quant.get("form4_event_sleeve") or {}).get("candidate_count"),
                "paper_state_open_positions": len(paper_state.get("open_positions") or []),
                "paper_state_closed_positions": len(paper_state.get("closed_positions") or []),
                "paper_snapshot_counts_recent": snapshot_counts(),
            },
            "historical_reference_not_new_evidence": historical,
        },
        "candidate_count": len(forward_queue),
        "overlap_with_existing_signals": overlaps,
        "candidate_overlap_and_slot_value": {
            "fresh_production_core_overlap_count": overlaps["production_core_signals"]["tagged_count"],
            "fresh_pilot_overlap_count": overlaps["pilot_signals"]["tagged_count"],
            "fresh_state_surface_overlap_count": overlaps["default_off_state_surface_scored_candidates"]["tagged_count"],
            "scarce_slot_opportunity_cost": {
                "measurable": False,
                "slot_conflict_value": None,
                "reason": "No fresh production-core Form 4 overlay hit and no trade-enabled Form 4 queue candidate; slot value is not measurable this run.",
            },
        },
        "forward_return_of_tagged_candidates": {
            "fresh_production_tagged_candidates": overlaps["production_core_signals"]["tagged_count"],
            "fresh_default_off_paper_tagged_candidates": overlaps["default_off_state_surface_scored_candidates"]["tagged_count"],
            "10d": None,
            "20d": None,
            "60d": None,
            "90d": None,
            "reason": "Fresh 2026-05-11 overlay candidates do not have mature 10/20/60/90d outcomes, and there is no production-core tagged signal.",
            "historical_reference_not_new_evidence": historical["standalone_purchase_forward_outcomes"],
        },
        "shadow_scoring_readiness": {
            "insider_buy_value_to_market_cap": "blocked_missing_pit_market_cap_join",
            "cluster_buying_30d": "partially computable locally; latest file only covers 2026-05-01 through 2026-05-11, historical cluster replay already rejected promotion",
            "CEO_CFO_buy_flag": "available via officer_title parsing",
            "first_purchase_1y": "computable against local archive; use only as shadow until PIT archive contract is explicit",
            "first_purchase_3y": "blocked_not_pit_safe_with_current_archive_window",
            "post_drawdown_purchase": "requires OHLCV context; no production-core tag this run",
            "exclude_option_exercise": "available",
            "exclude_tiny_purchase": "available through meaningful >=$50k and forward queue >=$500k thresholds",
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
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
        },
        "decision": "shadow_only",
        "decision_rationale": "Data is present and PIT-dateable, but the latest snapshot adds no production-core overlay hit, no mature tagged-candidate forward return, and no measurable scarce-slot value. Prior cluster/pre-entry RS evidence remains rejected for sample and materiality.",
        "next_minimum_action": "Keep accumulating append-only Form 4 paper snapshots; retry only after a new >=$500k CEO/CFO or cluster buy overlaps a production/pilot candidate with closed 10/20/60/90d outcomes, or after a PIT market-cap join enables buy-value-to-market-cap scoring.",
        "parameters": {
            "rule_family": "meaningful_purchase_v1 >= $50k for audit tags; forward queue >= $500k remains unchanged",
            "thresholds_changed": False,
            "owner_role_filters_changed": False,
            "locked_variables": [
                "entries",
                "exits",
                "ranking",
                "sizing",
                "portfolio_heat",
                "LLM_news",
                "production_orders",
                "Form4_thresholds",
            ],
        },
        "related_files": [
            repo_rel(TICKET_PATH),
            repo_rel(LOG_PATH),
            repo_rel(ARTIFACT),
            repo_rel(REPORT),
            repo_rel(LATEST_TX),
            repo_rel(LATEST_SUMMARY),
            repo_rel(Path(__file__)),
        ],
    }

    ticket = {
        "experiment_id": EXP_ID,
        "status": "completed",
        "lane": "alpha_discovery",
        "owner": "non_ohlcv_alpha_discovery",
        "hypothesis": record["hypothesis"],
        "change_type": record["change_type"],
        "single_causal_variable": record["single_causal_variable"],
        "baseline_result_file": repo_rel(BASELINE_ARTIFACT),
        "allowed_write_scope": [
            "docs/experiments/tickets",
            "docs/experiments/logs",
            "docs/non_ohlcv_data_audit",
            "data/experiments",
            "docs/experiment_log.jsonl",
        ],
        "must_not_touch": [
            "quant/signal_engine.py",
            "quant/risk_engine.py",
            "quant/portfolio_engine.py",
            "quant/run.py",
            "quant/backtester.py",
        ],
        "locked_variables": record["parameters"]["locked_variables"],
        "evaluation_windows": [
            {"start": "2025-10-23", "end": "2026-04-21"},
            {"start": "2025-04-23", "end": "2025-10-22"},
            {"start": "2024-10-02", "end": "2025-04-22"},
        ],
        "acceptance_rule": "data audit/shadow only: report coverage, PIT risk, CIK mapping gaps, existing-signal overlap, scarce-slot value, and forward return availability; no production change allowed",
        "created_at": RUN_AT,
        "completed_at": RUN_AT,
        "result": {
            "decision": record["decision"],
            "summary": record["decision_rationale"],
            "artifact": repo_rel(ARTIFACT),
            "log": repo_rel(LOG_PATH),
            "report": repo_rel(REPORT),
        },
        "notes": "scripts/create_experiment_ticket.py was invoked first, but the local registry reused occupied IDs; this collision-free ticket preserves the same requested scope.",
    }

    write_json(ARTIFACT, record)
    write_json(LOG_PATH, record)
    write_json(TICKET_PATH, ticket)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build_report(record), encoding="utf-8")
    append_jsonl_once(JSONL_PATH, record)

    print(json.dumps({
        "experiment_id": EXP_ID,
        "rows": len(rows),
        "pit_safe_fraction": record["data_availability_pit_status"]["pit_safe_fraction"],
        "meaningful_events": len(meaningful),
        "forward_queue_candidates": len(forward_queue),
        "production_core_tagged": overlaps["production_core_signals"]["tagged_count"],
        "pilot_tagged": overlaps["pilot_signals"]["tagged_count"],
        "state_surface_tagged": overlaps["default_off_state_surface_scored_candidates"]["tagged_count"],
        "decision": record["decision"],
        "artifact": repo_rel(ARTIFACT),
        "log": repo_rel(LOG_PATH),
        "report": repo_rel(REPORT),
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
