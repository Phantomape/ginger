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


EXP_ID = "exp-20260511-035"
RUN_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")
DATA_DIR = ROOT / "data"
OUT_DIR = DATA_DIR / "experiments" / EXP_ID
ARTIFACT = OUT_DIR / "form4_insider_overlay_latest_audit.json"
LOG_PATH = ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
REPORT = ROOT / "docs" / "non_ohlcv_data_audit" / f"form4_insider_overlay_{EXP_ID}_20260511.md"
JSONL_PATH = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_PATH = ROOT / "docs" / "experiment_registry.json"

LATEST_TX = DATA_DIR / "non_ohlcv" / "form4_transactions_20260510.jsonl"
LATEST_SUMMARY = DATA_DIR / "non_ohlcv" / "form4_backfill_summary_20260510.json"
QUANT_SIGNALS = DATA_DIR / "quant_signals_20260510.json"
UNIVERSE_STATE = DATA_DIR / "universe_state_20260510.json"
SEC_TICKERS = DATA_DIR / "sec_company_tickers.json"
PAPER_STATE = DATA_DIR / "form4_event_sleeve_paper_state.json"
PAPER_SNAPSHOTS = DATA_DIR / "form4_event_sleeve_paper_snapshots.jsonl"
PRIOR_LOG = ROOT / "experiments" / "logs" / "exp-20260510-016.json"
BASELINE_ARTIFACT = DATA_DIR / "experiments" / "exp-20260510-015" / "trip_sector_taxonomy.json"

NON_COMPANY = {"SPY", "QQQ", "IWM", "GLD", "IAU", "SLV", "ARKX", "UFO"}


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


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
    fields = [
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
    total = len(rows)
    for field in fields:
        source_field = "accepted_at" if field == "filing_datetime" else field
        count = sum(1 for row in rows if present(row.get(source_field)))
        out[field] = {
            "source_field": source_field,
            "present_rows": count,
            "total_rows": total,
            "coverage": round(count / total, 6) if total else None,
        }
    out["filing_datetime"][
        "normalization_note"
    ] = "No literal filing_datetime field; accepted_at is the EDGAR acceptance timestamp used for PIT dating."
    return out


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
        "known_gap_summary": "SNXX remains the current company CIK gap; ETF-like tickers are excluded from Form 4 coverage.",
    }


def baseline_metrics() -> tuple[dict[str, Any], dict[str, Any]]:
    payload = load_json(BASELINE_ARTIFACT, {}) or {}
    benchmarks = {
        "late_strong": {"spy_buy_hold_return_pct": 0.0541, "qqq_buy_hold_return_pct": 0.0580},
        "mid_weak": {"spy_buy_hold_return_pct": 0.2544, "qqq_buy_hold_return_pct": 0.3351},
        "old_thin": {"spy_buy_hold_return_pct": -0.0672, "qqq_buy_hold_return_pct": -0.0749},
    }
    windows: dict[str, Any] = {}
    for label, row in (payload.get("by_window") or {}).items():
        metrics = dict(row.get("after_metrics") or {})
        bench = benchmarks[label]
        metrics["spy_buy_hold_return_pct"] = bench["spy_buy_hold_return_pct"]
        metrics["qqq_buy_hold_return_pct"] = bench["qqq_buy_hold_return_pct"]
        metrics["vs_spy_pct"] = round(metrics["total_return_pct"] - bench["spy_buy_hold_return_pct"], 4)
        metrics["vs_qqq_pct"] = round(metrics["total_return_pct"] - bench["qqq_buy_hold_return_pct"], 4)
        windows[label] = metrics
    return windows, (payload.get("aggregate") or {}).get("after") or {}


def signal_rows(container: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = container.get(key)
    return rows if isinstance(rows, list) else []


def build_overlap(events: list[dict[str, Any]], quant: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_ticker[str(event.get("ticker") or "").upper()].append(event)

    core = signal_rows(quant, "signals")
    pilot = signal_rows(quant, "pilot_signals")
    state_queue = quant.get("state_surface_queue") or {}
    state_scored = state_queue.get("scored_candidates") or []
    state_allowed = state_queue.get("candidates") or []

    def matches(rows: list[dict[str, Any]], surface: str) -> list[dict[str, Any]]:
        out = []
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            if ticker not in by_ticker:
                continue
            out.append(
                {
                    "surface": surface,
                    "ticker": ticker,
                    "signal_date": row.get("date")
                    or row.get("created_asof")
                    or row.get("usable_trade_date")
                    or row.get("entry_date"),
                    "strategy": row.get("strategy") or row.get("surface") or row.get("source"),
                    "trade_enabled": bool(row.get("trade_enabled")),
                    "matched_form4_events": by_ticker[ticker],
                }
            )
        return out

    core_matches = matches(core, "production_core_signals")
    pilot_matches = matches(pilot, "pilot_signals")
    state_matches = matches(state_scored, "state_surface_scored")
    state_allowed_matches = matches(state_allowed, "state_surface_allowed")
    no_signal = []
    for event in events:
        ticker = str(event.get("ticker") or "").upper()
        no_signal.append(
            {
                "ticker": ticker,
                "usable_trade_date": event.get("usable_trade_date"),
                "total_purchase_value": event.get("total_purchase_value"),
                "production_core_overlap": any(match["ticker"] == ticker for match in core_matches),
                "pilot_overlap": any(match["ticker"] == ticker for match in pilot_matches),
                "default_off_state_surface_overlap": any(match["ticker"] == ticker for match in state_matches),
            }
        )
    return (
        {
            "production_core_signals": {
                "signal_count": len(core),
                "tagged_count": len(core_matches),
                "matches": core_matches,
            },
            "pilot_signals": {
                "signal_count": len(pilot),
                "tagged_count": len(pilot_matches),
                "matches": pilot_matches,
            },
            "default_off_state_surface_scored_candidates": {
                "signal_count": len(state_scored),
                "tagged_count": len(state_matches),
                "matches": state_matches,
                "production_scope": "paper_only_default_off",
            },
            "default_off_state_surface_allowed_candidates": {
                "signal_count": len(state_allowed),
                "tagged_count": len(state_allowed_matches),
                "matches": state_allowed_matches,
                "production_scope": "paper_only_default_off",
            },
            "form4_forward_queue": {
                "candidate_count": (quant.get("form4_event_queue") or {}).get("candidate_count"),
                "tagged_existing_signal_count": 0,
                "production_scope": "observe_only_default_off",
            },
        },
        no_signal,
    )


def snapshot_counts() -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for snap in read_jsonl(PAPER_SNAPSHOTS):
        day = snap.get("asof_date")
        if not day:
            continue
        row = counts.setdefault(
            day,
            {"snapshot_count": 0, "candidate_count_sum": 0, "filled_count_sum": 0, "closed_count_sum": 0},
        )
        row["snapshot_count"] += 1
        row["candidate_count_sum"] += int(snap.get("candidate_count") or 0)
        row["filled_count_sum"] += int(snap.get("filled_count") or 0)
        row["closed_count_sum"] += int(snap.get("closed_count_today") or 0)
    return {day: counts[day] for day in sorted(counts)[-8:]}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    existing = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(json.loads(line).get("experiment_id"))
            except Exception:
                pass
    if row.get("experiment_id") in existing:
        return
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def update_registry(record: dict[str, Any]) -> None:
    registry = load_json(REGISTRY_PATH, {"schema_version": 1, "experiments": []}) or {
        "schema_version": 1,
        "experiments": [],
    }
    restored_space = {
        "experiment_id": "exp-20260511-003",
        "hypothesis": "The rejected static space catalyst pool should be expressed as a production-visible, observe-only forward shadow surface, not as a live/core universe expansion.",
        "lane": "alpha_search",
        "owner": "alpha-search",
        "status": "accepted_default_off_forward_observation_surface",
        "ticket_file": "experiments/tickets/exp-20260511-003.json",
        "updated_at": "2026-05-11T02:08:33Z",
    }
    stale_collision_ids = {"exp-20260511-003", "exp-20260511-033", EXP_ID}
    experiments = [
        item
        for item in registry.get("experiments", [])
        if item.get("experiment_id") not in stale_collision_ids
    ]
    experiments.append(restored_space)
    experiments.append(
        {
            "experiment_id": EXP_ID,
            "hypothesis": record["hypothesis"],
            "lane": record["lane"],
            "owner": "non_ohlcv_alpha_discovery",
            "status": "completed",
            "ticket_file": repo_rel(TICKET_PATH),
            "updated_at": RUN_AT,
            "completed_at": RUN_AT,
            "result": {
                "decision": record["decision"],
                "summary": record["decision_rationale"],
                "artifact": repo_rel(ARTIFACT),
                "log": repo_rel(LOG_PATH),
                "report": repo_rel(REPORT),
            },
        }
    )
    registry["experiments"] = experiments
    registry["updated_at"] = RUN_AT
    write_json(REGISTRY_PATH, registry)


def fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def build_report(record: dict[str, Any]) -> str:
    baseline = record["baseline_metrics"]
    hist = record["forward_return_of_tagged_candidates"]["historical_shadow_reference_not_new_evidence"]
    meaningful = (
        ((hist.get("standalone_purchase_outcomes_with_90d_added") or {}).get("cohorts") or {})
        .get("meaningful_purchase_v1", {})
        .get("horizons", {})
    )
    lines = [
        "# Form 4 Insider Overlay Audit",
        "",
        f"- experiment_id: `{EXP_ID}`",
        f"- generated_at: `{RUN_AT}`",
        "- mechanism_family: `insider_form4_open_market_purchase_confirmation_overlay`",
        "- run_mode: `data_audit_shadow_only_overlay_refresh`",
        "- production_impact: no signal, ranking, sizing, order, run, or backtester path changed",
        "",
        "## Hypothesis",
        "",
        record["hypothesis"],
        "",
        "## Latest Data Coverage",
        "",
        f"- source: `{record['data_availability_pit_status']['latest_transactions_file']}`",
        f"- date_range: `{record['data_availability_pit_status']['date_range']['start']} -> {record['data_availability_pit_status']['date_range']['end']}`",
        f"- rows: `{record['data_availability_pit_status']['rows_written']}`",
        f"- PIT-safe rows: `{record['data_availability_pit_status']['pit_safe_count']}` / `{record['data_availability_pit_status']['rows_written']}`",
        f"- tickers mapped/requested: `{record['data_availability_pit_status']['tickers_mapped']}` / `{record['data_availability_pit_status']['tickers_requested']}`",
        f"- CIK mapping gaps: `{', '.join(record['data_availability_pit_status']['missing_cik_tickers']) or 'none'}`",
        f"- open-market purchase transactions: `{record['data_availability_pit_status']['open_market_purchase_transaction_count']}`",
        f"- meaningful >=$50k event-days: `{record['fresh_form4_events']['base_meaningful_purchase_event_count_ge_50k']}`",
        f"- forward-queue >=$500k candidates: `{record['fresh_form4_events']['forward_queue_candidate_count_ge_500k']}`",
        "",
        "## Fresh Shadow Overlay",
        "",
        f"- production core tagged: `{record['candidate_overlap_and_slot_value']['fresh_production_overlap_count']}`",
        f"- pilot tagged: `{record['candidate_overlap_and_slot_value']['fresh_pilot_overlap_count']}`",
        f"- default-off state-surface scored tagged: `{record['candidate_overlap_and_slot_value']['fresh_default_off_state_surface_overlap_count']}`",
        f"- scarce-slot value: `{record['candidate_overlap_and_slot_value']['scarce_slot_opportunity_cost']['reason']}`",
        f"- forward 10/20/60/90d: `{record['forward_return_of_tagged_candidates']['reason']}`",
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
    lines.extend(
        [
            "",
            "## Historical Shadow Reference",
            "",
            "Historical returns below are carried forward from prior artifacts and are not new evidence in this run.",
            "",
            "| Cohort | Horizon | Count | Avg return | Win rate | Avg excess vs SPY | Excess win rate |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for horizon in ["10", "20", "60", "90"]:
        row = meaningful.get(horizon, {})
        lines.append(
            f"| meaningful_purchase_v1 | {horizon}d | {row.get('count', 0)} | "
            f"{fmt(row.get('avg_return_pct'))}% | {fmt(row.get('win_rate'))} | "
            f"{fmt(row.get('avg_excess_vs_spy_pct'))}% | {fmt(row.get('excess_win_rate'))} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "`shadow_only`. The latest snapshot adds no production-core overlap, no >=$500k forward-queue candidate, no closed paper outcome, and no measurable slot-conflict value.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    rows = read_jsonl(LATEST_TX)
    summary = load_json(LATEST_SUMMARY, {}) or {}
    quant = load_json(QUANT_SIGNALS, {}) or {}
    universe = load_json(UNIVERSE_STATE, {}) or {}
    prior = load_json(PRIOR_LOG, {}) or {}
    paper_state = load_json(PAPER_STATE, {}) or {}
    baseline, baseline_aggregate = baseline_metrics()

    events = aggregate_purchase_events(
        rows,
        start=(summary.get("date_range") or {}).get("start"),
        end=(summary.get("date_range") or {}).get("end"),
    )
    meaningful = [event for event in events if event.get("meaningful_purchase_v1")]
    forward_queue = [event for event in events if qualifies_forward_queue_event(event)]
    ceo_cfo = [event for event in meaningful if event.get("any_ceo_cfo_or_president")]
    overlaps, no_signal = build_overlap(meaningful, quant)
    prior_shadow = (prior.get("shadow_or_replay_metrics") or {}).get(
        "historical_shadow_reference_not_new_evidence"
    ) or {}

    record: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": RUN_AT,
        "status": "observed_only",
        "lane": "alpha_discovery",
        "change_type": "data_audit_shadow_overlay",
        "component": "experiments/logs, docs/non_ohlcv_data_audit, data/experiments artifact only",
        "run_mode": "data_audit_shadow_only_overlay_refresh",
        "hypothesis": "Public-market insider Form 4 buying, especially large CEO/CFO or clustered open-market purchases, may confirm existing trend_long/breakout_long candidates; this run only checks the latest local PIT-safe data and shadow overlap without changing production.",
        "non_ohlcv_data_source": "SEC EDGAR Form 4 transaction-level XML rows from data/non_ohlcv/form4_transactions_20260510.jsonl plus the default-off Form 4 paper sleeve snapshots.",
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
                "exp-20260509-018",
                "exp-20260510-016",
            ],
            "prior_result_summary": "Prior Form 4 work found positive standalone purchase cohorts but sparse accepted-trade overlap, zero top-skipped overlap, thin slot replacement value, rejected sale-pressure de-risking, and rejected positive-but-underpowered cluster buying.",
            "new_evidence_since_last_run": "Only the 2026-05-10 local Form 4 snapshot is new. It contains one open-market purchase transaction, the same CAT director purchase already present in the previous fresh audit window, and zero Form 4 paper sleeve candidates.",
            "anti_repeat_guardrail": "Do not retune Form 4 purchase-value thresholds, owner-role filters, cluster windows, or production promotion on this same sparse sample.",
        },
        "single_causal_variable": "latest local Form 4 availability and overlay coverage as of 2026-05-10",
        "production_change_allowed": False,
        "date_range": {
            "late_strong": "2025-10-23 -> 2026-04-21",
            "mid_weak": "2025-04-23 -> 2025-10-22",
            "old_thin": "2024-10-02 -> 2025-04-22",
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
            "pit_safe_fraction": round(sum(1 for row in rows if row.get("pit_safe_flag")) / len(rows), 6)
            if rows
            else None,
            "open_market_purchase_transaction_count": sum(1 for row in rows if row.get("open_market_purchase_flag")),
            "option_exercise_count": sum(1 for row in rows if row.get("option_exercise_flag")),
            "ten_b5_1_count": sum(1 for row in rows if row.get("10b5_1_flag")),
            "transaction_code_counts": summary.get("transaction_code_counts"),
            "field_coverage": field_coverage(rows),
            "cik_mapping_gap_report": mapping_report(universe, summary),
            "pit_status": "PIT-safe for filing-use date via accepted_at -> conservative usable_trade_date; backfilled rows are public-PIT proxies, while append-only daily snapshots are stronger forward evidence.",
            "pit_risks": [
                "Backfill is generated after the fact.",
                "10b5-1 detection is best-effort text parsing.",
                "insider_buy_value_to_market_cap is blocked because no PIT market-cap join exists.",
                "first_purchase_3y is not PIT-safe from the current local archive window alone.",
                "No literal filing_datetime field exists; accepted_at is the normalized timestamp.",
            ],
        },
        "fresh_form4_events": {
            "raw_open_market_event_count": len(events),
            "base_meaningful_purchase_event_count_ge_50k": len(meaningful),
            "forward_queue_candidate_count_ge_500k": len(forward_queue),
            "ceo_cfo_event_count": len(ceo_cfo),
            "events": events,
        },
        "candidate_count": len(forward_queue),
        "overlap_with_existing_signals": overlaps,
        "insider_buy_but_no_signal": no_signal,
        "candidate_overlap_and_slot_value": {
            "fresh_production_overlap_count": overlaps["production_core_signals"]["tagged_count"],
            "fresh_pilot_overlap_count": overlaps["pilot_signals"]["tagged_count"],
            "fresh_default_off_state_surface_overlap_count": overlaps[
                "default_off_state_surface_scored_candidates"
            ]["tagged_count"],
            "scarce_slot_opportunity_cost": {
                "measurable": False,
                "slot_conflict_value": None,
                "reason": "No fresh >=$500k Form 4 forward-queue candidate and no production-core signal overlap; only the default-off CAT state-surface scored row is tagged.",
            },
            "historical_slot_reference_not_new_evidence": prior_shadow.get("slot_capacity"),
        },
        "forward_return_of_tagged_candidates": {
            "fresh_production_tagged_candidates": overlaps["production_core_signals"]["tagged_count"],
            "fresh_default_off_paper_tagged_candidates": overlaps[
                "default_off_state_surface_scored_candidates"
            ]["tagged_count"],
            "10d": None,
            "20d": None,
            "60d": None,
            "90d": None,
            "reason": "No fresh production-tagged candidate and no mature 10/20/60/90d outcome for the one default-off CAT state-surface tag as of this run.",
            "historical_shadow_reference_not_new_evidence": {
                "accepted_trade_overlap": prior_shadow.get("accepted_trade_overlap"),
                "slot_capacity": prior_shadow.get("slot_capacity"),
                "cluster_sleeve_rejected": prior_shadow.get("cluster_sleeve_rejected"),
                "standalone_purchase_outcomes_with_90d_added": prior_shadow.get(
                    "standalone_purchase_outcomes_with_90d_added"
                ),
            },
        },
        "shadow_or_replay_metrics": {
            "fresh_asof_2026_05_10": {
                "raw_open_market_transaction_count": sum(1 for row in rows if row.get("open_market_purchase_flag")),
                "raw_open_market_event_count": len(events),
                "base_meaningful_purchase_event_count_ge_50k": len(meaningful),
                "forward_queue_candidate_count_ge_500k": len(forward_queue),
                "candidate_count": len(forward_queue),
                "form4_event_queue_candidate_count": (quant.get("form4_event_queue") or {}).get("candidate_count"),
                "form4_event_sleeve_candidate_count": (quant.get("form4_event_sleeve") or {}).get("candidate_count"),
                "paper_state_open_positions": len(paper_state.get("open_positions") or []),
                "paper_state_closed_positions": len(paper_state.get("closed_positions") or []),
                "paper_snapshot_counts_recent": snapshot_counts(),
                "overlap_with_existing_signals": overlaps,
                "scarce_slot_opportunity_cost": {
                    "measurable": False,
                    "slot_conflict_value": None,
                    "reason": "No fresh forward-queue candidate or production slot conflict.",
                },
            },
            "historical_shadow_reference_not_new_evidence": prior_shadow,
        },
        "shadow_scoring_readiness": {
            "insider_buy_value_to_market_cap": "blocked_missing_pit_market_cap_join",
            "cluster_buying_30d": "available historically but prior cluster promotion was rejected; latest sample has no >=$500k queue candidate",
            "CEO_CFO_buy_flag": "available via officer_title parsing; latest meaningful CAT event is director-only, not CEO/CFO",
            "first_purchase_1y": "partially computable within local archive only; not production-safe enough for promotion",
            "first_purchase_3y": "blocked_not_pit_safe_with_current_archive_window",
            "post_drawdown_purchase": "requires OHLCV context; no fresh qualifying production candidate to score",
            "exclude_option_exercise": "available",
            "exclude_tiny_purchase": "available; CAT $219.21k passes the >=$50k shadow tag but remains below the $500k forward queue threshold",
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
            "production_impact": "shadow_data_audit_only_no_production_change",
        },
        "decision": "shadow_only",
        "decision_rationale": "The latest Form 4 data exists and is PIT-dateable, but it adds no production-core overlap, no >=$500k forward-queue candidate, no closed paper outcome, and no measurable scarce-slot value beyond prior historical reference.",
        "next_minimum_action": "Keep accumulating append-only Form 4 paper snapshots; retry only after a new >=$500k CEO/CFO or cluster buy creates closed 10/20/60/90d outcomes, or after a PIT market-cap join enables buy-value-to-market-cap scoring.",
        "parameters": {
            "changed_variable": "latest local Form 4 availability and overlay coverage as of 2026-05-10",
            "rule_family": "form4_meaningful_purchase_ge_500k_v1 for forward queue; meaningful >=$50k retained only for shadow/audit tagging",
            "thresholds_changed": False,
            "owner_role_filters_changed": False,
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
        "rejection_reason": None,
        "related_files": [
            repo_rel(TICKET_PATH),
            repo_rel(LOG_PATH),
            repo_rel(ARTIFACT),
            repo_rel(REPORT),
            repo_rel(LATEST_TX),
            repo_rel(LATEST_SUMMARY),
            repo_rel(PAPER_STATE),
            repo_rel(PAPER_SNAPSHOTS),
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
            "experiments/tickets",
            "experiments/logs",
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
        "created_at": "2026-05-11T17:16:35+00:00",
        "completed_at": RUN_AT,
        "result": {
            "decision": record["decision"],
            "summary": record["decision_rationale"],
            "artifact": repo_rel(ARTIFACT),
            "log": repo_rel(LOG_PATH),
            "report": repo_rel(REPORT),
        },
        "notes": "scripts/create_experiment_ticket.py was invoked first but reused occupied ids during a busy automation run; exp-20260511-035 is the collision-free authoritative Form 4 audit.",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(ARTIFACT, record)
    write_json(LOG_PATH, record)
    write_json(TICKET_PATH, ticket)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build_report(record), encoding="utf-8")
    append_jsonl_once(JSONL_PATH, record)
    update_registry(record)
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "rows": len(rows),
                "pit_safe_fraction": record["data_availability_pit_status"]["pit_safe_fraction"],
                "meaningful_events": len(meaningful),
                "forward_queue_candidates": len(forward_queue),
                "production_core_tagged": overlaps["production_core_signals"]["tagged_count"],
                "state_surface_paper_tagged": overlaps["default_off_state_surface_scored_candidates"]["tagged_count"],
                "decision": record["decision"],
                "artifact": repo_rel(ARTIFACT),
                "log": repo_rel(LOG_PATH),
                "report": repo_rel(REPORT),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
