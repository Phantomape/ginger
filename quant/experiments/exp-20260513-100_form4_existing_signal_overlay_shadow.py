from __future__ import annotations

import json
import re
import sys
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.form4_event_queue import aggregate_purchase_events, qualifies_forward_queue_event


EXP_ID = "exp-20260513-100"
RUN_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")
DATA_DIR = ROOT / "data"
OUT_DIR = DATA_DIR / "experiments" / EXP_ID
ARTIFACT = OUT_DIR / "form4_existing_signal_overlay_shadow.json"
LOG_PATH = ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
REPORT = ROOT / "docs" / "non_ohlcv_data_audit" / f"form4_existing_signal_overlay_{EXP_ID}_20260513.md"
JSONL_PATH = ROOT / "docs" / "experiment_log.jsonl"
BASELINE_ARTIFACT = DATA_DIR / "experiments" / "exp-20260513-036" / "clean_spy_leader_signal_day_risk.json"
HISTORICAL_OUTCOMES = DATA_DIR / "non_ohlcv" / "form4_purchase_shadow_outcomes_20241002_20260421.json"
SEC_COMPANY_TICKERS_CANDIDATES = [
    DATA_DIR / "reference" / "sec_company_tickers.json",
    DATA_DIR / "sec_company_tickers.json",
]

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


def configure_run(
    *,
    experiment_id: str = EXP_ID,
    report_date: str = "20260513",
    baseline_artifact: str | Path | None = None,
) -> None:
    global EXP_ID, OUT_DIR, ARTIFACT, LOG_PATH, TICKET_PATH, REPORT, BASELINE_ARTIFACT

    EXP_ID = experiment_id
    OUT_DIR = DATA_DIR / "experiments" / EXP_ID
    ARTIFACT = OUT_DIR / "form4_existing_signal_overlay_shadow.json"
    LOG_PATH = ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
    TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
    REPORT = ROOT / "docs" / "non_ohlcv_data_audit" / f"form4_existing_signal_overlay_{EXP_ID}_{report_date}.md"
    if baseline_artifact:
        path = Path(baseline_artifact)
        BASELINE_ARTIFACT = path if path.is_absolute() else ROOT / path


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            row = json.loads(text)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    try:
        return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def latest_tagged_file(prefix: str, suffix: str = ".jsonl") -> tuple[str, Path] | None:
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d{{8}}){re.escape(suffix)}$")
    candidates: list[tuple[str, Path]] = []
    for path in (DATA_DIR / "non_ohlcv").glob(f"{prefix}_*{suffix}"):
        match = pattern.match(path.name)
        if match:
            candidates.append((match.group(1), path))
    return sorted(candidates)[-1] if candidates else None


def companion_json(tag: str, stem: str) -> Path:
    return DATA_DIR / "non_ohlcv" / f"{stem}_{tag}.json"


def daily_json(tag: str, stem: str) -> Path:
    current_paths = {
        "quant_signals": DATA_DIR / "daily" / "signals" / "quant" / f"quant_signals_{tag}.json",
        "trend_signals": DATA_DIR / "daily" / "signals" / "trend" / f"trend_signals_{tag}.json",
        "universe_state": DATA_DIR / "daily" / "universe" / f"universe_state_{tag}.json",
    }
    current_path = current_paths.get(stem)
    if current_path is not None and current_path.exists():
        return current_path
    return DATA_DIR / f"{stem}_{tag}.json"


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
    map_path = next((path for path in SEC_COMPANY_TICKERS_CANDIDATES if path.exists()), SEC_COMPANY_TICKERS_CANDIDATES[-1])
    payload = load_json(map_path, {}) or {}
    rows = payload.values() if isinstance(payload, dict) else payload
    mapping: dict[str, str] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        cik = row.get("cik_str") or row.get("cik")
        if ticker and cik:
            mapping[ticker] = str(cik).zfill(10)
    return mapping


def mapping_report(universe: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    mapping = load_sec_map()
    map_path = next((path for path in SEC_COMPANY_TICKERS_CANDIDATES if path.exists()), SEC_COMPANY_TICKERS_CANDIDATES[-1])

    def segment(key: str) -> dict[str, Any]:
        tickers = [str(ticker).upper() for ticker in universe.get(key, [])]
        companies = [ticker for ticker in tickers if ticker not in NON_COMPANY]
        return {
            "segment_key": key,
            "ticker_count": len(tickers),
            "company_ticker_count": len(companies),
            "mapped_company_ticker_count": sum(1 for ticker in companies if ticker in mapping),
            "missing_company_tickers": sorted(ticker for ticker in companies if ticker not in mapping),
            "non_company_excluded": sorted(ticker for ticker in tickers if ticker in NON_COMPANY),
        }

    pilot_key = "pilot_trade_universe" if universe.get("pilot_trade_universe") else "governance_tradeable_universe"
    return {
        "mapping_source": repo_rel(map_path),
        "core_trade_universe": segment("core_trade_universe"),
        "pilot_universe": segment(pilot_key),
        "observation_universe": segment("observation_universe"),
        "latest_backfill_missing_cik_tickers": summary.get("missing_cik_tickers") or [],
    }


def accepted_baseline() -> tuple[dict[str, Any], dict[str, Any]]:
    payload = load_json(BASELINE_ARTIFACT, {}) or {}
    windows = {}
    for label, metrics in (payload.get("after_metrics") or {}).items():
        row = dict(metrics)
        row["vs_spy_pct"] = round(float(row.get("total_return_pct") or 0.0) - float(row.get("spy_buy_hold_return_pct") or 0.0), 4)
        row["vs_qqq_pct"] = round(float(row.get("total_return_pct") or 0.0) - float(row.get("qqq_buy_hold_return_pct") or 0.0), 4)
        windows[label] = row
    aggregate = {
        "expected_value_score_sum": round(sum(float(row.get("expected_value_score") or 0.0) for row in windows.values()), 6),
        "total_pnl_sum": round(sum(float(row.get("total_pnl") or 0.0) for row in windows.values()), 2),
        "trade_count_sum": sum(int(row.get("trade_count") or 0) for row in windows.values()),
        "min_survival_rate": min(float(row.get("survival_rate") or 0.0) for row in windows.values()) if windows else None,
        "max_drawdown_pct_max": max(float(row.get("max_drawdown_pct") or 0.0) for row in windows.values()) if windows else None,
    }
    return windows, aggregate


def surface_rows(quant: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    state_surface = quant.get("state_surface_queue") or {}
    form4_queue = quant.get("form4_event_queue") or {}
    form4_sleeve = quant.get("form4_event_sleeve") or {}
    event_bundle = quant.get("event_sleeve_bundle") or {}
    return {
        "production_core_signals": list(quant.get("signals") or []),
        "pilot_signals": list(quant.get("pilot_signals") or []),
        "heat_blocked_signals": list(quant.get("heat_blocked_signals") or []),
        "default_off_state_surface_scored_candidates": list(state_surface.get("scored_candidates") or []),
        "default_off_state_surface_allowed_candidates": list(state_surface.get("candidates") or []),
        "form4_event_queue_candidates": list(form4_queue.get("candidates") or []),
        "form4_event_sleeve_new_pending": list(form4_sleeve.get("new_pending_entries") or []),
        "form4_event_sleeve_open_positions": list(form4_sleeve.get("open_positions") or []),
        "event_sleeve_bundle_candidates": list(event_bundle.get("candidates") or []),
    }


def overlap(events: list[dict[str, Any]], quant: dict[str, Any]) -> dict[str, Any]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        ticker = str(event.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker].append(event)

    out: dict[str, Any] = {}
    for surface, rows in surface_rows(quant).items():
        matches = []
        for row in rows:
            ticker = str(row.get("ticker") or row.get("symbol") or "").upper()
            if ticker not in by_ticker:
                continue
            matches.append({
                "ticker": ticker,
                "surface": surface,
                "signal_date": row.get("date") or row.get("created_asof") or row.get("usable_trade_date") or row.get("entry_date") or row.get("asof_date"),
                "strategy": row.get("strategy") or row.get("source") or row.get("surface") or row.get("sleeve"),
                "trade_enabled": bool(row.get("trade_enabled") or row.get("pilot_trade_enabled")),
                "matched_form4_events": by_ticker[ticker],
            })
        out[surface] = {
            "candidate_count": len(rows),
            "tagged_count": len(matches),
            "matches": matches,
        }
    return out


def days_between(start: str, end: str) -> int:
    start_dt = datetime.strptime(start[:10], "%Y-%m-%d")
    end_dt = datetime.strptime(end[:10], "%Y-%m-%d")
    return (end_dt - start_dt).days


def add_fresh_event_context(events: list[dict[str, Any]], historical_events: list[dict[str, Any]]) -> None:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in sorted(historical_events + events, key=lambda row: (row.get("usable_trade_date") or "", row.get("ticker") or "")):
        ticker = str(event.get("ticker") or "").upper()
        event_date = str(event.get("usable_trade_date") or "")[:10]
        if not ticker or not event_date:
            continue
        prior = [row for row in by_ticker[ticker] if str(row.get("usable_trade_date") or "")[:10] < event_date]
        event["cluster_buying_30d_partial"] = (
            int(event.get("owner_count") or 0) >= 2
            or any(0 < days_between(str(row.get("usable_trade_date")), event_date) <= 30 for row in prior)
        )
        event["first_purchase_1y_local_archive"] = not any(
            0 < days_between(str(row.get("usable_trade_date")), event_date) <= 366
            for row in prior
        )
        event["first_purchase_3y_status"] = "blocked_local_archive_starts_2024"
        by_ticker[ticker].append(event)


def historical_reference() -> dict[str, Any]:
    outcomes = load_json(HISTORICAL_OUTCOMES, {}) or {}
    prior_overlay = load_json(ROOT / "experiments" / "logs" / "exp-20260513-100.json", {}) or {}
    prior_single_owner = load_json(DATA_DIR / "experiments" / "exp-20260512-108" / "form4_single_owner_preentry_rs.json", {}) or {}
    prior_cluster = load_json(ROOT / "experiments" / "logs" / "exp-20260512-017.json", {}) or {}
    overlay_hist = (
        (prior_overlay.get("forward_return_of_tagged_candidates") or {})
        .get("historical_reference_not_new_evidence")
        or (prior_overlay.get("forward_return_of_tagged_candidates") or {})
        .get("historical_shadow_reference_not_new_evidence")
        or {}
    )
    return {
        "prior_overlay_refresh": {
            "experiment_id": prior_overlay.get("experiment_id"),
            "decision": prior_overlay.get("decision"),
            "summary": prior_overlay.get("decision_rationale"),
        },
        "prior_cluster_preentry_rs": {
            "experiment_id": prior_cluster.get("experiment_id"),
            "decision": prior_cluster.get("decision"),
            "gate4": prior_cluster.get("gate4"),
        },
        "prior_single_owner_preentry_rs": {
            "experiment_id": prior_single_owner.get("experiment_id"),
            "decision": prior_single_owner.get("decision"),
            "aggregate_delta_vs_core": prior_single_owner.get("aggregate_delta_vs_core"),
            "aggregate_delta_vs_single_owner": prior_single_owner.get("aggregate_delta_vs_single_owner"),
            "gate4": prior_single_owner.get("gate4"),
        },
        "standalone_purchase_forward_outcomes": {
            "source": overlay_hist.get("source") or repo_rel(HISTORICAL_OUTCOMES),
            "cohorts": overlay_hist.get("cohorts") or outcomes.get("cohorts") or {},
        },
    }


def latest_price_status(tag: str, ticker: str) -> dict[str, Any]:
    features = load_json(daily_json(tag, "quant_signals"), {}) or {}
    ticker_features = (features.get("features") or {}).get(ticker)
    return {
        "has_latest_feature_row": bool(ticker_features),
        "post_drawdown_purchase_status": "blocked_for_fresh_overlay_no_mature_forward_outcome" if not ticker_features else "requires_dedicated_shadow_join",
    }


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    existing_ids = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                existing_ids.add(json.loads(line).get("experiment_id"))
            except Exception:
                continue
    if row["experiment_id"] in existing_ids:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.4f}"


def build_report(record: dict[str, Any]) -> str:
    lines = [
        "# Form 4 Existing-Signal Overlay Shadow",
        "",
        f"- experiment_id: `{EXP_ID}`",
        f"- generated_at: `{RUN_AT}`",
        "- mechanism_family: `insider_form4_open_market_purchase_confirmation_overlay`",
        "- run_mode: `data_audit_shadow_only`",
        "- production_impact: no signal, ranking, sizing, order, run, or backtest path changed",
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
        metrics = record["baseline_metrics"].get(label, {})
        lines.append(
            f"| {label} | {metrics.get('expected_value_score', 0):.4f} | {metrics.get('total_return_pct', 0):.4f} | "
            f"${metrics.get('total_pnl', 0):,.2f} | {metrics.get('sharpe_daily', 0):.2f} | "
            f"{metrics.get('max_drawdown_pct', 0):.4f} | {metrics.get('win_rate', 0):.4f} | "
            f"{int(metrics.get('trade_count', 0))} | {int(metrics.get('signals_generated', 0))} | "
            f"{int(metrics.get('signals_survived', 0))} | {metrics.get('survival_rate', 0):.4f} | "
            f"{metrics.get('vs_spy_pct', 0):.4f} | {metrics.get('vs_qqq_pct', 0):.4f} |"
        )
    lines.extend([
        "",
        "## Fresh Shadow Overlay",
        "",
        f"- production-core tagged candidates: `{record['candidate_overlap_and_slot_value']['fresh_production_core_overlap_count']}`",
        f"- pilot tagged candidates: `{record['candidate_overlap_and_slot_value']['fresh_pilot_overlap_count']}`",
        f"- default-off state-surface tagged candidates: `{record['candidate_overlap_and_slot_value']['fresh_state_surface_overlap_count']}`",
        f"- insider buy but no production signal: `{record['insider_buy_but_no_signal']['count']}`",
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
    meaningful = (
        record["historical_experiment_check"]["historical_shadow_reference"]["standalone_purchase_forward_outcomes"]
        .get("cohorts", {})
        .get("meaningful_purchase_v1", {})
        .get("horizons", {})
    )
    for horizon in ["5", "10", "20", "60", "90"]:
        row = meaningful.get(horizon, {})
        lines.append(
            f"| meaningful_purchase_v1 | {horizon}d | {row.get('count', 0)} | "
            f"{pct(row.get('avg_return_pct'))}% | {pct(row.get('win_rate'))} | "
            f"{pct(row.get('avg_excess_vs_spy_pct'))}% | {pct(row.get('excess_win_rate'))} |"
        )
    lines.extend([
        "",
        "## Decision",
        "",
        f"`{record['decision']}`. {record['decision_rationale']}",
        "",
    ])
    return "\n".join(lines)


def build_record() -> dict[str, Any]:
    latest = latest_tagged_file("form4_transactions")
    if latest is None:
        raise FileNotFoundError("No data/non_ohlcv/form4_transactions_YYYYMMDD.jsonl file found")
    tag, tx_path = latest
    summary_path = companion_json(tag, "form4_backfill_summary")
    quant_path = daily_json(tag, "quant_signals")
    universe_path = daily_json(tag, "universe_state")

    rows = read_jsonl(tx_path)
    summary = load_json(summary_path, {}) or {}
    quant = load_json(quant_path, {}) or {}
    universe = load_json(universe_path, {}) or {}
    start = (summary.get("date_range") or {}).get("start")
    end = (summary.get("date_range") or {}).get("end")
    events = aggregate_purchase_events(rows, start=start, end=end)
    meaningful = [event for event in events if event.get("meaningful_purchase_v1")]
    forward_queue = [event for event in events if qualifies_forward_queue_event(event)]
    historical_payload = load_json(HISTORICAL_OUTCOMES, {}) or {}
    historical_events = [event for event in historical_payload.get("events") or [] if event.get("meaningful_purchase_v1")]
    add_fresh_event_context(meaningful, historical_events)
    for event in meaningful:
        event.update(latest_price_status(tag, str(event.get("ticker") or "")))

    overlaps = overlap(meaningful, quant)
    baseline, baseline_aggregate = accepted_baseline()
    historical = historical_reference()
    production_core_overlap = overlaps["production_core_signals"]["tagged_count"]
    tagged_surface_count = sum(row["tagged_count"] for row in overlaps.values())
    tagged_tickers = {
        match["ticker"]
        for surface in overlaps.values()
        for match in surface["matches"]
    }
    buy_no_signal = [
        event for event in meaningful
        if str(event.get("ticker") or "").upper() not in tagged_tickers
    ]

    return {
        "experiment_id": EXP_ID,
        "timestamp": RUN_AT,
        "status": "observed_only",
        "lane": "alpha_discovery",
        "change_type": "data_audit_shadow_overlay",
        "component": "quant/experiments isolated runner plus docs/data experiment outputs",
        "hypothesis": (
            "Public-market insider Form 4 buying, especially CEO/CFO large buys, "
            "cluster buying, first buys, and post-drawdown buys, may confirm existing "
            "trend_long/breakout_long candidates. This run only audits local PIT-safe "
            "availability and tags existing signal surfaces; it does not create entries."
        ),
        "non_ohlcv_data_source": repo_rel(tx_path),
        "mechanism_family": "insider_form4_open_market_purchase_confirmation_overlay",
        "historical_experiment_check": {
            "exact_or_near_prior_experiments": [
                "exp-20260503-017",
                "exp-20260504-034",
                "exp-20260505-010",
                "exp-20260508-028",
                "exp-20260510-016",
                "exp-20260511-035",
                "exp-20260512-017",
                "exp-20260512-042",
                "exp-20260512-101",
                "exp-20260512-108",
                "exp-20260513-100",
            ],
            "prior_result_summary": (
                "Form 4 data is available and PIT-dateable. Historical meaningful buys "
                "were positive as standalone shadow events, but production overlap was "
                "sparse; sale pressure was rejected; cluster and pre-entry RS variants "
                "were positive or core-positive but rejected for sample/materiality."
            ),
            "why_not_simple_repeat": (
                "This does not retune purchase thresholds, owner roles, cluster windows, "
                "notional, holding period, or live scope. It refreshes the existing-signal "
                "overlay coverage after the latest local Form 4 snapshot."
            ),
            "historical_shadow_reference": historical,
        },
        "single_causal_variable": "latest PIT-safe Form 4 meaningful insider-buy overlay coverage on existing signals",
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
            "latest_transactions_file": repo_rel(tx_path),
            "latest_summary_file": repo_rel(summary_path),
            "latest_quant_signals_file": repo_rel(quant_path),
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
            "pit_status": "PIT-safe for filing-use date via accepted_at to conservative usable_trade_date; backfilled historical files are public-PIT proxies, while daily snapshots are stronger forward evidence.",
            "pit_risks": [
                "Backfilled rows are generated after the fact.",
                "10b5-1 detection is best-effort text parsing.",
                "insider_buy_value_to_market_cap is blocked because no PIT market-cap join exists.",
                "first_purchase_3y is not PIT-safe because the local Form 4 archive starts in 2024.",
                "No information before filing/usable_trade_date is used.",
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
                "meaningful_events": meaningful,
                "overlap_with_existing_signals": overlaps,
                "form4_event_queue_candidate_count": (quant.get("form4_event_queue") or {}).get("candidate_count"),
                "form4_event_sleeve_candidate_count": (quant.get("form4_event_sleeve") or {}).get("candidate_count"),
            },
            "historical_reference_not_new_evidence": historical,
        },
        "candidate_count": len(forward_queue),
        "overlap_with_existing_signals": overlaps,
        "insider_buy_but_no_signal": {
            "count": len(buy_no_signal),
            "events": buy_no_signal,
            "definition": "fresh meaningful Form 4 event whose ticker did not appear on any current production/pilot/default-off candidate surface checked",
        },
        "candidate_overlap_and_slot_value": {
            "fresh_production_core_overlap_count": production_core_overlap,
            "fresh_pilot_overlap_count": overlaps["pilot_signals"]["tagged_count"],
            "fresh_state_surface_overlap_count": overlaps["default_off_state_surface_scored_candidates"]["tagged_count"],
            "fresh_any_surface_overlap_count": tagged_surface_count,
            "scarce_slot_opportunity_cost": {
                "measurable": False,
                "slot_conflict_value": None,
                "reason": "No fresh production-core Form 4 overlay hit and no trade-enabled Form 4 queue candidate; slot conflict value is not measurable this run.",
            },
        },
        "forward_return_of_tagged_candidates": {
            "fresh_production_tagged_candidates": production_core_overlap,
            "fresh_default_off_paper_tagged_candidates": overlaps["default_off_state_surface_scored_candidates"]["tagged_count"],
            "10d": None,
            "20d": None,
            "60d": None,
            "90d": None,
            "reason": "Fresh overlay candidates do not have mature 10/20/60/90d outcomes, and there is no production-core tagged signal.",
            "historical_reference_not_new_evidence": historical["standalone_purchase_forward_outcomes"],
        },
        "shadow_scoring_readiness": {
            "insider_buy_value_to_market_cap": "blocked_missing_pit_market_cap_join",
            "cluster_buying_30d": "partially computable from local Form 4 archive; use as shadow only",
            "CEO_CFO_buy_flag": "available via officer_title parsing",
            "first_purchase_1y": "locally computable as shadow archive feature",
            "first_purchase_3y": "blocked_not_pit_safe_with_current_archive_window",
            "post_drawdown_purchase": "requires OHLCV context and a production-core overlap sample",
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
        "decision_rationale": (
            "Data is present and PIT-dateable, but the latest snapshot adds no "
            "production-core overlay hit, no mature tagged-candidate forward return, "
            "and no measurable scarce-slot value. Prior Form 4 promotion variants "
            "remain rejected for sample and materiality."
        ),
        "next_minimum_action": (
            "Keep accumulating append-only Form 4 paper snapshots; retry only after a "
            "new >=$500k CEO/CFO or cluster buy overlaps a production/pilot candidate "
            "with closed 10/20/60/90d outcomes, or after a PIT market-cap join enables "
            "buy-value-to-market-cap scoring."
        ),
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
                "core_universe",
            ],
        },
        "related_files": [
            repo_rel(TICKET_PATH),
            repo_rel(LOG_PATH),
            repo_rel(ARTIFACT),
            repo_rel(REPORT),
            repo_rel(tx_path),
            repo_rel(summary_path),
            repo_rel(Path(__file__)),
        ],
    }


def finalize_ticket(record: dict[str, Any]) -> dict[str, Any]:
    ticket = load_json(TICKET_PATH, {}) or {}
    ticket.update({
        "status": "observed_only",
        "completed_at": RUN_AT,
        "result": {
            "decision": record["decision"],
            "summary": record["decision_rationale"],
            "artifact": repo_rel(ARTIFACT),
            "log": repo_rel(LOG_PATH),
            "report": repo_rel(REPORT),
            "candidate_count": record["candidate_count"],
            "production_core_overlap_count": record["candidate_overlap_and_slot_value"]["fresh_production_core_overlap_count"],
        },
    })
    return ticket


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Form 4 existing-signal overlay shadow audit.")
    parser.add_argument("--experiment-id", default=EXP_ID)
    parser.add_argument("--report-date", default="20260513")
    parser.add_argument("--baseline-artifact", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_run(
        experiment_id=args.experiment_id,
        report_date=args.report_date,
        baseline_artifact=args.baseline_artifact,
    )
    record = build_record()
    write_json(ARTIFACT, record)
    write_json(LOG_PATH, record)
    write_json(TICKET_PATH, finalize_ticket(record))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build_report(record) + "\n", encoding="utf-8")
    append_jsonl_once(JSONL_PATH, record)
    print(json.dumps({
        "experiment_id": EXP_ID,
        "rows": record["data_availability_pit_status"]["rows_written"],
        "pit_safe_fraction": record["data_availability_pit_status"]["pit_safe_fraction"],
        "meaningful_events": record["shadow_or_replay_metrics"]["fresh"]["meaningful_purchase_event_count_ge_50k"],
        "forward_queue_candidates": record["shadow_or_replay_metrics"]["fresh"]["forward_queue_candidate_count_ge_500k"],
        "production_core_tagged": record["candidate_overlap_and_slot_value"]["fresh_production_core_overlap_count"],
        "pilot_tagged": record["candidate_overlap_and_slot_value"]["fresh_pilot_overlap_count"],
        "state_surface_tagged": record["candidate_overlap_and_slot_value"]["fresh_state_surface_overlap_count"],
        "decision": record["decision"],
        "artifact": repo_rel(ARTIFACT),
        "log": repo_rel(LOG_PATH),
        "report": repo_rel(REPORT),
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
