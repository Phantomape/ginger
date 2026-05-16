"""Shadow-only SEC / earnings filing-shock audit for the 2026-05-14 refresh.

This runner only measures local non-OHLCV data availability and writes a shadow
event table. It does not connect SEC or earnings fields to entry, ranking,
sizing, exits, portfolio slots, or orders.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXP_ID = "exp-20260516-003"
DATE_KEY = "20260514"
ASOF_DATE = "2026-05-14"
RUN_DATE_KEY = "20260515"

NON_ROOT = REPO_ROOT / "data" / "non_ohlcv"
EVENTS_PATH = NON_ROOT / f"sec_filing_events_{DATE_KEY}.jsonl"
TEXT_PATH = NON_ROOT / f"sec_filing_text_{DATE_KEY}.jsonl"
FEATURES_PATH = NON_ROOT / f"sec_filing_features_{DATE_KEY}.jsonl"
EARNINGS_PATHS = [
    REPO_ROOT / "data" / f"earnings_snapshot_{DATE_KEY}.json",
    REPO_ROOT / "data" / "daily" / "snapshots" / "earnings" / f"earnings_snapshot_{DATE_KEY}.json",
]
QUANT_SIGNAL_PATHS = [
    REPO_ROOT / "data" / f"quant_signals_{DATE_KEY}.json",
    REPO_ROOT / "data" / "daily" / "signals" / "quant" / f"quant_signals_{DATE_KEY}.json",
]
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260515-028"
    / "current_stack_core_confirmed_quality_risk.json"
)
PRIOR_LOG_PATH = REPO_ROOT / "docs" / "experiments" / "logs" / "exp-20260515-002.json"
TICKET_PATH = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
LOG_PATH = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
REGISTRY_PATH = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG_PATH = REPO_ROOT / "docs" / "experiment_log.jsonl"

SHADOW_PATH = NON_ROOT / f"sec_earnings_filing_shock_shadow_events_{EXP_ID}.json"
AUDIT_JSON_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXP_ID
    / "sec_earnings_filing_shock_20260514_data_audit.json"
)
AUDIT_MD_PATH = (
    REPO_ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / f"sec_earnings_filing_shock_latest_{EXP_ID}_{RUN_DATE_KEY}.md"
)

REQUIRED_FIELD_GAPS = [
    "current EPS surprise vs PIT consensus",
    "revenue_surprise",
    "guidance_raise_cut",
    "same-accession financial-quality deltas",
    "candidate-touch B/C directional filing-shock cohorts",
]


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def existing_path(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    existing_ids: set[str] = set()
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    existing_ids.add(str(json.loads(line).get("experiment_id")))
                except json.JSONDecodeError:
                    continue
    if payload["experiment_id"] in existing_ids:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def finite_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str) and value.strip():
        try:
            number = float(value)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def pct(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def most_common(counter: Counter[Any]) -> dict[str, int]:
    return {str(key): int(value) for key, value in counter.most_common()}


def event_items(row: dict[str, Any]) -> list[str]:
    items = row.get("eight_k_item_codes")
    if isinstance(items, list):
        return [str(item) for item in items if str(item)]
    raw = row.get("eight_k_item_type") or row.get("items_raw") or ""
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def directional_fields(row: dict[str, Any]) -> tuple[list[str], list[str]]:
    positive: list[str] = []
    negative: list[str] = []
    for field in (
        "eps_surprise",
        "revenue_surprise",
        "gross_margin_delta",
        "fcf_to_net_income_gap",
        "inventory_growth",
        "receivables_growth",
    ):
        value = finite_float(row.get(field))
        if value is None:
            continue
        if value > 0:
            positive.append(field)
        elif value < 0:
            negative.append(field)
    guidance = str(row.get("guidance_raise_cut") or "").strip().lower()
    if guidance in {"raise", "raised", "guidance_raise"}:
        positive.append("guidance_raise_cut")
    elif guidance in {"cut", "lowered", "guidance_cut"}:
        negative.append("guidance_raise_cut")
    return positive, negative


def filing_shock_tag(row: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    positive, negative = directional_fields(row)
    if positive and not negative:
        return "B_positive_filing_shock", positive, negative
    if negative and not positive:
        return "C_negative_filing_shock", positive, negative
    return "D_unclear_or_missing_data", positive, negative


def build_shadow_rows(
    events: list[dict[str, Any]],
    features: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    features_by_accession = {
        str(row.get("source_accession") or row.get("accession_number")): row
        for row in features
        if row.get("source_accession") or row.get("accession_number")
    }
    rows: list[dict[str, Any]] = []
    for event in events:
        accession = str(event.get("accession_number") or "")
        feature = features_by_accession.get(accession, {})
        merged = {**event, **feature}
        tag, positive, negative = filing_shock_tag(merged)
        accepted = event.get("accepted_at") or feature.get("accepted_datetime")
        usable = event.get("usable_trade_date") or feature.get("usable_trade_date")
        sources = [rel(EVENTS_PATH)]
        if accession in features_by_accession:
            sources.append(rel(FEATURES_PATH))
        if str(event.get("form_base") or event.get("form_type")) == "8-K":
            sources.append(rel(TEXT_PATH))
        rows.append({
            "ticker": event.get("ticker") or feature.get("ticker"),
            "event_date": str(accepted or "")[:10] or event.get("filing_date"),
            "usable_trade_date": usable,
            "form_type": event.get("form_type") or feature.get("form_type"),
            "accepted_datetime": accepted,
            "fiscal_period_end": event.get("report_date") or feature.get("fiscal_period_end"),
            "eps_surprise": feature.get("eps_surprise"),
            "revenue_surprise": feature.get("revenue_surprise"),
            "gross_margin_delta": feature.get("gross_margin_delta"),
            "fcf_to_net_income_gap": feature.get("fcf_to_net_income_gap"),
            "inventory_growth": feature.get("inventory_growth"),
            "receivables_growth": feature.get("receivables_growth"),
            "guidance_raise_cut": feature.get("guidance_raise_cut"),
            "eight_k_item_type": event_items(event) or event_items(feature),
            "accession_number": accession or feature.get("source_accession"),
            "data_source": sources,
            "feature_present": accession in features_by_accession,
            "filing_shock_tag": tag,
            "positive_evidence_fields": positive,
            "negative_evidence_fields": negative,
            "pit_safe": bool(event.get("pit_safe_flag") and accepted and usable),
            "pit_caveat": (
                event.get("pit_caveat")
                or "SEC accepted_at is a public PIT proxy, not proof local production observed it."
            ),
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_orders": False,
            },
        })
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("usable_trade_date") or ""),
            str(row.get("ticker") or ""),
            str(row.get("accession_number") or ""),
        ),
    )


def summarize_earnings_snapshot() -> dict[str, Any]:
    path = existing_path(EARNINGS_PATHS)
    if not path.exists():
        return {
            "path": rel(path),
            "exists": False,
            "tickers_total": 0,
            "missing_for_filing_shock": REQUIRED_FIELD_GAPS,
        }
    payload = load_json(path)
    coverage = payload.get("coverage") if isinstance(payload, dict) else {}
    earnings = payload.get("earnings") if isinstance(payload, dict) else None
    if isinstance(earnings, dict):
        rows = [row for row in earnings.values() if isinstance(row, dict)]
    elif isinstance(earnings, list):
        rows = [row for row in earnings if isinstance(row, dict)]
    else:
        rows = []
    return {
        "path": rel(path),
        "exists": True,
        "tickers_total": int(coverage.get("tickers_total") or len(rows)),
        "tickers_persisted": coverage.get("tickers_persisted"),
        "tickers_with_next_earnings_date": coverage.get("tickers_with_next_earnings_date")
        or sum(1 for row in rows if row.get("next_earnings_date")),
        "tickers_with_days_to_earnings": coverage.get("tickers_with_days_to_earnings")
        or sum(1 for row in rows if row.get("days_to_earnings") is not None),
        "tickers_with_eps_estimate": coverage.get("tickers_with_eps_estimate")
        or sum(1 for row in rows if row.get("eps_estimate") is not None),
        "tickers_with_eps_actual_last": coverage.get("tickers_with_eps_actual_last")
        or sum(1 for row in rows if row.get("eps_actual_last") is not None),
        "tickers_with_surprise_history": coverage.get("tickers_with_surprise_history")
        or sum(1 for row in rows if row.get("avg_historical_surprise_pct") is not None),
        "missing_for_filing_shock": REQUIRED_FIELD_GAPS[:4],
        "pit_note": "Replayable repo snapshot, not vendor-grade PIT consensus surprise evidence.",
    }


def build_coverage(
    events: list[dict[str, Any]],
    texts: list[dict[str, Any]],
    features: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    directional = [
        row for row in features
        if directional_fields(row)[0] or directional_fields(row)[1]
    ]
    same_accession = [
        row for row in features
        if (row.get("field_availability") or {}).get("same_accession_facts") == "derived"
    ]
    field_counts = {
        field: sum(1 for row in features if row.get(field) is not None)
        for field in (
            "eps_surprise",
            "revenue_surprise",
            "gross_margin_delta",
            "fcf_to_net_income_gap",
            "inventory_growth",
            "receivables_growth",
            "guidance_raise_cut",
        )
    }
    field_availability = Counter()
    for row in features:
        for field, state in (row.get("field_availability") or {}).items():
            field_availability[f"{field}:{state}"] += 1
    text_chars = 0
    text_status = Counter()
    text_forms = Counter()
    for row in texts:
        text_status[row.get("status") or "unknown"] += 1
        text_forms[row.get("form_type") or row.get("form") or "unknown"] += 1
        text_chars += len(str(row.get("combined_text") or row.get("text") or row.get("filing_text") or ""))
        for doc in row.get("documents") or []:
            if isinstance(doc, dict) and row.get("combined_text") is None:
                text_chars += int(doc.get("text_char_count") or 0)

    coverage = {
        f"sec_filing_events_{DATE_KEY}": {
            "path": rel(EVENTS_PATH),
            "exists": EVENTS_PATH.exists(),
            "rows": len(events),
            "tickers": len({str(row.get("ticker") or "").upper() for row in events if row.get("ticker")}),
            "accepted_datetime_rows": sum(1 for row in events if row.get("accepted_at")),
            "usable_trade_date_rows": sum(1 for row in events if row.get("usable_trade_date")),
            "pit_safe_rows": sum(
                1
                for row in events
                if row.get("pit_safe_flag") and row.get("accepted_at") and row.get("usable_trade_date")
            ),
            "form_counts": most_common(Counter(row.get("form_type") or "unknown" for row in events)),
            "usable_trade_date_counts": most_common(
                Counter(row.get("usable_trade_date") or "missing" for row in events)
            ),
            "eight_k_item_counts": most_common(
                Counter(item for row in events for item in (event_items(row) or ["none"]))
            ),
            "pit_caveat": (
                "accepted_at/usable_trade_date are public-availability PIT proxies; "
                "report_date/fiscal_period_end was not used as a tradable date."
            ),
        },
        f"sec_filing_text_{DATE_KEY}": {
            "path": rel(TEXT_PATH),
            "exists": TEXT_PATH.exists(),
            "rows": len(texts),
            "forms": most_common(text_forms),
            "status_counts": most_common(text_status),
            "text_char_count": text_chars,
            "coverage_note": "Replayable 8-K text exists, but no structured guidance/surprise extraction adapter is present.",
        },
        f"sec_filing_features_{DATE_KEY}": {
            "path": rel(FEATURES_PATH),
            "exists": FEATURES_PATH.exists(),
            "rows": len(features),
            "pit_safe_rows": sum(1 for row in features if row.get("pit_safe")),
            "feature_event_coverage_vs_events": pct(len(features), len(events)),
            "same_accession_rows": len(same_accession),
            "directional_rows": len(directional),
            "field_counts": field_counts,
            "form_counts": most_common(Counter(row.get("form_type") or "unknown" for row in features)),
            "field_availability_top": most_common(field_availability),
            "gap_reasons_top": most_common(
                Counter(reason for row in features for reason in (row.get("gap_reasons") or []))
            ),
        },
        f"earnings_snapshot_{DATE_KEY}": summarize_earnings_snapshot(),
    }
    return coverage, directional, same_accession


def aggregate_by_window(metrics: dict[str, Any]) -> dict[str, Any]:
    rows = list(metrics.values())
    return {
        "expected_value_score_sum": round(sum(float(row.get("expected_value_score") or 0) for row in rows), 4),
        "total_pnl_sum": round(sum(float(row.get("total_pnl") or 0) for row in rows), 2),
        "trade_count_sum": int(sum(int(row.get("trade_count") or 0) for row in rows)),
        "signals_generated_sum": int(sum(int(row.get("signals_generated") or 0) for row in rows)),
        "signals_survived_sum": int(sum(int(row.get("signals_survived") or 0) for row in rows)),
        "survival_rate_min": min((row.get("survival_rate") for row in rows if row.get("survival_rate") is not None), default=None),
        "max_drawdown_pct_max": max((row.get("max_drawdown_pct") for row in rows if row.get("max_drawdown_pct") is not None), default=None),
    }


def accepted_core_baseline() -> dict[str, Any]:
    payload = load_json(BASELINE_PATH)
    after = payload.get("after_metrics") or {}
    return {
        "source": rel(BASELINE_PATH),
        "aggregate": aggregate_by_window(after),
        "by_window": after,
    }


def prior_shadow_metrics() -> dict[str, Any]:
    prior = load_json(PRIOR_LOG_PATH)
    carried = prior.get("shadow_or_replay_metrics") or {}
    return {
        "source": rel(PRIOR_LOG_PATH),
        "candidate_count": prior.get("candidate_count"),
        "overlap_with_existing_signals": prior.get("overlap_with_existing_signals"),
        "tagged_candidate_forward_returns": carried.get(
            "tagged_candidate_forward_returns_carried_forward_from_exp_20260511_001"
        ),
        "scarce_slot_opportunity_cost": prior.get("scarce_slot_opportunity_cost")
        or carried.get("candidate_overlap_and_slot_value"),
    }


def current_overlap(shadow_rows: list[dict[str, Any]], features: list[dict[str, Any]]) -> dict[str, Any]:
    quant_path = existing_path(QUANT_SIGNAL_PATHS)
    quant = load_json(quant_path) if quant_path.exists() else {}
    event_tickers = {str(row.get("ticker") or "").upper() for row in shadow_rows if row.get("ticker")}
    feature_tickers = {str(row.get("ticker") or "").upper() for row in features if row.get("ticker")}
    core_signals = quant.get("signals") or []
    pilot_signals = quant.get("pilot_signals") or []
    position_rows = (quant.get("portfolio_heat") or {}).get("position_breakdown") or []
    open_tickers = {str(row.get("ticker") or "").upper() for row in position_rows if row.get("ticker")}
    queues: dict[str, Any] = {}
    for key in (
        "sec_event_queue",
        "sec_governance_event_queue",
        "sec_financial_report_t1_queue",
        "event_sleeve_bundle",
        "space_catalyst_observation_slot",
    ):
        value = quant.get(key) or {}
        data_source = value.get("data_source") if isinstance(value, dict) else None
        queues[key] = {
            "candidate_count": value.get("candidate_count") if isinstance(value, dict) else None,
            "raw_candidate_count": value.get("raw_candidate_count") if isinstance(value, dict) else None,
            "selected_count": value.get("selected_count") if isinstance(value, dict) else None,
            "data_source": data_source,
        }
    return {
        "asof_date": ASOF_DATE,
        "quant_signals_path": rel(quant_path),
        "fresh_event_rows": len(shadow_rows),
        "fresh_event_tickers": len(event_tickers),
        "feature_event_rows": len(features),
        "feature_event_tickers": len(feature_tickers),
        "current_core_signal_count": len(core_signals),
        "current_core_signal_overlap_rows": sum(
            1 for signal in core_signals if str(signal.get("ticker") or "").upper() in event_tickers
        ),
        "current_core_signal_overlap_tickers": sorted({
            str(signal.get("ticker") or "").upper()
            for signal in core_signals
            if str(signal.get("ticker") or "").upper() in event_tickers
        }),
        "current_pilot_signal_count": len(pilot_signals),
        "current_pilot_signal_overlap_rows": sum(
            1 for signal in pilot_signals if str(signal.get("ticker") or "").upper() in event_tickers
        ),
        "current_pilot_signal_overlap_tickers": sorted({
            str(signal.get("ticker") or "").upper()
            for signal in pilot_signals
            if str(signal.get("ticker") or "").upper() in event_tickers
        }),
        "open_position_overlap_rows": len(open_tickers.intersection(event_tickers)),
        "open_position_overlap_tickers": sorted(open_tickers.intersection(event_tickers)),
        "queue_counts": queues,
    }


def forward_avg(forward: dict[str, Any], tag: str, horizon: int) -> str:
    value = ((forward.get(tag) or {}).get("forward_returns") or {}).get(f"{horizon}d", {}).get("avg_pct")
    if value is None:
        return "n/a"
    return f"{float(value):.4f}"


def markdown_report(row: dict[str, Any]) -> str:
    coverage = row["coverage"]
    events_key = f"sec_filing_events_{DATE_KEY}"
    text_key = f"sec_filing_text_{DATE_KEY}"
    features_key = f"sec_filing_features_{DATE_KEY}"
    earnings_key = f"earnings_snapshot_{DATE_KEY}"
    current = row["shadow_metrics"]["fresh_current_overlap"]
    prior = row["shadow_metrics"]["historical_candidate_overlap_and_slot_value_carried_forward"]
    forward = prior.get("tagged_candidate_forward_returns") or {}
    slot = row["scarce_slot_opportunity_cost"] or {}
    slot_dist = slot.get("overall_delta_20d_distribution") or {}

    lines = [
        f"# SEC / earnings / filing shock latest data audit ({EXP_ID})",
        "",
        f"- run_timestamp: `{row['timestamp']}`",
        f"- source_refresh_date: `{ASOF_DATE}`",
        "- mode: `data_audit_shadow_only`",
        "- mechanism_family: `SEC / earnings / filing shock event-confirmation overlay`",
        f"- single_causal_variable: `{row['single_causal_variable']}`",
        "- production_change_allowed: `false`",
        "- anti_js: `No JavaScript was used.`",
        "",
        "## Hypothesis",
        "",
        row["hypothesis"],
        "",
        "## Historical experiment check",
        "",
    ]
    for key, value in row["historical_experiment_check"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend([
        "",
        "## Coverage table",
        "",
        "| source | rows | PIT/timestamp rows | directional rows | missing blocker |",
        "|---|---:|---:|---:|---|",
        (
            f"| SEC events {ASOF_DATE} | {coverage[events_key]['rows']} | "
            f"{coverage[events_key]['pit_safe_rows']} | n/a | semantic fields absent from raw metadata |"
        ),
        (
            f"| SEC text {ASOF_DATE} | {coverage[text_key]['rows']} | n/a | n/a | "
            "unstructured text; no guidance/surprise adapter |"
        ),
        (
            f"| SEC features {ASOF_DATE} | {coverage[features_key]['rows']} | "
            f"{coverage[features_key]['pit_safe_rows']} | "
            f"{coverage[features_key]['directional_rows']} | "
            "same-accession / EPS / revenue / guidance rows still absent |"
        ),
        (
            f"| Earnings snapshot {ASOF_DATE} | {coverage[earnings_key]['tickers_total']} | "
            "replayable snapshot | n/a | no current EPS/revenue surprise vs PIT consensus |"
        ),
        "",
        "## Shadow table",
        "",
        f"- shadow_event_table: `{row['shadow_event_table']['path']}`",
        f"- rows: `{row['shadow_event_table']['rows']}`",
        f"- PIT-safe rows: `{row['shadow_event_table']['pit_safe_rows']}`",
        f"- feature-present rows: `{row['shadow_event_table']['feature_present_rows']}`",
        f"- same-accession rows: `{row['shadow_event_table']['same_accession_rows']}`",
        f"- directional rows: `{row['shadow_event_table']['directional_rows']}`",
        f"- tag_counts: `{json.dumps(row['shadow_event_table']['tag_counts'], sort_keys=True)}`",
        "",
        "## Tagged candidate forward returns",
        "",
        "Fresh 2026-05-14 rows are not mature for 5/10/20/60d returns. "
        "Mature candidate-touch metrics are carried forward from `exp-20260511-001` via `exp-20260515-002`:",
        "",
        "| tag | candidates | 5d avg | 10d avg | 20d avg | 60d avg |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for tag in (
        "A_no_recent_filing_event",
        "B_positive_filing_shock",
        "C_negative_filing_shock",
        "D_unclear_or_missing_data",
    ):
        tag_row = forward.get(tag) or {}
        lines.append(
            f"| `{tag}` | {tag_row.get('candidate_count', 0)} | "
            f"{forward_avg(forward, tag, 5)} | {forward_avg(forward, tag, 10)} | "
            f"{forward_avg(forward, tag, 20)} | {forward_avg(forward, tag, 60)} |"
        )
    lines.extend([
        "",
        "## Candidate overlap and slot value",
        "",
        (
            f"- current core signals: `{current['current_core_signal_count']}`; "
            f"fresh SEC overlap: `{current['current_core_signal_overlap_rows']}` "
            f"({', '.join(current['current_core_signal_overlap_tickers']) or 'none'})"
        ),
        (
            f"- current pilot signals: `{current['current_pilot_signal_count']}`; "
            f"fresh SEC overlap: `{current['current_pilot_signal_overlap_rows']}` "
            f"({', '.join(current['current_pilot_signal_overlap_tickers']) or 'none'})"
        ),
        (
            "- open-position event overlap tickers: `"
            + (", ".join(current["open_position_overlap_tickers"]) or "none")
            + "`"
        ),
        (
            f"- carried-forward scarce-slot value: avg 20d delta `{slot_dist.get('avg_pct')}`, "
            f"win_rate `{slot_dist.get('win_rate')}`, comparable_count `{slot.get('same_day_comparable_count')}`"
        ),
        "",
        "## Baseline metrics",
        "",
        f"- baseline: `{row['baseline_metrics']['source']}`",
        f"- aggregate EV: `{row['baseline_metrics']['aggregate']['expected_value_score_sum']}`",
        f"- aggregate PnL: `{row['baseline_metrics']['aggregate']['total_pnl_sum']}`",
        f"- min survival: `{row['baseline_metrics']['aggregate']['survival_rate_min']}`",
        f"- expected_value_score_delta: `{row['expected_value_score_delta']}`",
        "",
        "## Decision",
        "",
        row["decision_rationale"],
        "",
        "## Next minimal action",
        "",
        row["next_minimal_action"],
        "",
        "## Production impact",
        "",
        "```json",
        json.dumps(row["production_impact"], indent=2, sort_keys=True),
        "```",
        "",
    ])
    return "\n".join(lines)


def update_registry_and_ticket(ticket: dict[str, Any], row: dict[str, Any]) -> None:
    ticket.update({
        "status": "data_gap",
        "completed_at": row["timestamp"],
        "log_file": rel(LOG_PATH),
        "result": {
            "decision": row["decision"],
            "summary": row["decision_rationale"],
            "artifact": rel(AUDIT_JSON_PATH),
            "report": rel(AUDIT_MD_PATH),
            "shadow_event_table": rel(SHADOW_PATH),
        },
    })
    write_json(TICKET_PATH, ticket)
    if not REGISTRY_PATH.exists():
        return
    registry = load_json(REGISTRY_PATH)
    for entry in registry.get("experiments", []):
        if entry.get("experiment_id") == EXP_ID:
            entry.update({
                "status": "data_gap",
                "owner": "codex-alpha-discovery",
                "updated_at": row["timestamp"],
                "log_file": rel(LOG_PATH),
                "result": ticket["result"],
            })
            break
    registry["updated_at"] = row["timestamp"]
    write_json(REGISTRY_PATH, registry)


def main() -> int:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    events = load_jsonl(EVENTS_PATH)
    texts = load_jsonl(TEXT_PATH)
    features = load_jsonl(FEATURES_PATH)
    shadow_rows = build_shadow_rows(events, features)
    coverage, directional_rows, same_accession_rows = build_coverage(events, texts, features)
    baseline = accepted_core_baseline()
    prior = prior_shadow_metrics()
    overlap = current_overlap(shadow_rows, features)
    tag_counts = most_common(Counter(row["filing_shock_tag"] for row in shadow_rows))
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "production_signal_path_changed": False,
        "default_off_harness_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_orders": False,
        "must_not_touch_respected": [
            "quant/signal_engine.py",
            "quant/risk_engine.py",
            "quant/portfolio_engine.py",
        ],
    }

    features_key = f"sec_filing_features_{DATE_KEY}"
    events_key = f"sec_filing_events_{DATE_KEY}"
    row = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": "data_gap",
        "lane": "alpha_discovery",
        "run_type": "data_audit_plus_fresh_shadow_event_table",
        "mode": "data_audit_shadow_only",
        "hypothesis": (
            "SEC filing shock, financial surprise, 8-K/10-Q/10-K event type, "
            "and post-earnings drift may improve C-strategy grading or A/B "
            "event confirmation, but only if the 2026-05-14 SEC refresh adds "
            "PIT directional fields that touch candidates."
        ),
        "alpha_hypothesis": (
            "A PIT-safe filing shock quality layer could improve breakout_long/"
            "trend_long event confirmation or C-strategy grading if directional "
            "financial surprise or guidance fields touch candidates."
        ),
        "non_ohlcv_data_source": [
            "SEC submissions / filing events",
            "SEC filing text archive",
            "SEC filing feature rows",
            "existing earnings snapshots",
            "prior same-accession Companyfacts selected rows",
        ],
        "mechanism_family": "SEC / earnings / filing shock event-confirmation overlay",
        "single_causal_variable": "post_exp_20260515_002_sec_filing_20260514_feature_availability",
        "change_type": "non_ohlcv_data_audit_shadow_tagging",
        "changed_variable": "2026-05-14 SEC filing feature availability only",
        "production_change_allowed": False,
        "historical_experiment_check": {
            "docs_alpha_optimization_playbook": (
                "SEC earnings semantic expansion is the top field-building item, "
                "but the playbook says fresh PIT directional filing-shock fields "
                "are still missing; SEC retunes without new semantic fields are invalid."
            ),
            "exp-20260511-001": (
                "138 historical A/B candidates: A=67, D=71, B/C=0, no "
                "earnings_event_long sample, raw filing-presence slot value negative."
            ),
            "exp-20260513-006": (
                "2026-05-11 refresh had event/text/feature rows and one pilot "
                "overlap, but zero same-accession rows and zero directional rows."
            ),
            "exp-20260514-005": (
                "2026-05-12 refresh remained a data gap: zero same-accession rows, "
                "zero directional rows, and zero production-core overlap."
            ),
            "exp-20260515-002": (
                "2026-05-13 refresh remained a data gap: 60 PIT-safe event rows, "
                "40 feature rows, zero directional rows, and no B/C candidate-touch cohort."
            ),
            "exp-20260512-020": (
                "Separate SEC financial-report T+1 sleeve is accepted default-off; "
                "this run does not retune or promote it."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "PIT-safe SEC filing-shock semantic fields may improve C-strategy "
                "grading or A/B event confirmation."
            ),
            "2_history_check": "Same branch has repeatedly stopped at data_gap; see historical_experiment_check.",
            "3_single_causal_variable": "Only 2026-05-14 SEC filing feature availability is newly audited.",
            "4_acceptance_standard": (
                "Data audit standard: coverage, PIT risk, missingness, shadow tags, "
                "candidate overlap, slot value, and next evidence. No production change."
            ),
            "5_reproducibility": rel(Path(__file__)),
        },
        "field_check": {
            "backtester_earnings_snapshot_disclosure": (
                "quant/backtester.py loads daily P-ERN earnings snapshots and "
                "discloses earnings_event_long coverage; this audit did not change that path."
            ),
            "data_layer_fields": [
                "next_earnings_date",
                "days_to_earnings",
                "eps_estimate",
                "eps_actual_last",
                "historical_surprise_pct",
                "avg_historical_surprise_pct",
            ],
            "feature_layer_fields": [
                "days_to_earnings",
                "next_earnings_date",
                "eps_estimate",
                "avg_historical_surprise_pct",
                "positive_surprise_history",
                "earnings_event_window",
            ],
            "missing_for_this_hypothesis": REQUIRED_FIELD_GAPS,
        },
        "baseline_metrics": baseline,
        "before_metrics": baseline,
        "after_metrics": {
            "same_as_baseline": True,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "reason": "Data audit and shadow table only; no replay, queue, ranking, sizing, signal, or order path changed.",
        },
        "expected_value_score_delta": 0.0,
        "expected_value_score_delta_reason": "No strategy or default-off replay path changed.",
        "coverage": coverage,
        "coverage_delta_vs_exp_20260515_002": {
            "events_rows_delta": coverage[events_key]["rows"] - 60,
            "features_rows_delta": coverage[features_key]["rows"] - 40,
            "directional_rows_delta": len(directional_rows),
            "same_accession_rows_delta": len(same_accession_rows),
            "current_core_signal_overlap_delta": overlap["current_core_signal_overlap_rows"],
        },
        "data_availability_pit_status": {
            "event_timestamp_status": (
                "Fresh SEC rows have accepted_at, accession_number, and usable_trade_date; "
                "period/report date was not used as a tradable date."
            ),
            "feature_status": (
                "sec_filing_features_20260514 exists, but same-accession and "
                "directional rows must be nonzero before candidate-touch testing."
            ),
            "text_status": (
                "8-K text exists and is replayable, but no structured guidance/"
                "surprise extraction adapter is present."
            ),
            "earnings_snapshot_status": (
                "earnings_snapshot_20260514 has EPS estimate/history coverage "
                "but not current EPS/revenue surprise vs PIT consensus."
            ),
            "do_not_use_as_production_evidence": True,
            "biased_or_blocked_fields": REQUIRED_FIELD_GAPS,
        },
        "shadow_event_table": {
            "path": rel(SHADOW_PATH),
            "rows": len(shadow_rows),
            "pit_safe_rows": sum(1 for item in shadow_rows if item.get("pit_safe")),
            "feature_present_rows": sum(1 for item in shadow_rows if item.get("feature_present")),
            "same_accession_rows": len(same_accession_rows),
            "directional_rows": len(directional_rows),
            "tag_counts": tag_counts,
            "forward_returns_status": "Fresh 2026-05-14 refresh is not mature for 5/10/20/60d candidate returns.",
        },
        "shadow_metrics": {
            "fresh_current_overlap": overlap,
            "historical_candidate_overlap_and_slot_value_carried_forward": prior,
        },
        "shadow_or_replay_metrics": {
            "fresh_forward_returns_status": "not_mature_for_5_10_20_60d_windows_and_not_candidate_linked",
            "tagged_candidate_forward_returns_carried_forward_from_exp_20260511_001": prior.get(
                "tagged_candidate_forward_returns"
            ),
            "candidate_overlap_and_slot_value": prior.get("scarce_slot_opportunity_cost"),
            "current_overlap": overlap,
        },
        "candidate_count": prior.get("candidate_count"),
        "overlap_with_existing_signals": {
            "fresh_current_core_signal_count": overlap["current_core_signal_count"],
            "fresh_current_core_signal_overlap_rows": overlap["current_core_signal_overlap_rows"],
            "fresh_current_core_signal_overlap_tickers": overlap["current_core_signal_overlap_tickers"],
            "fresh_pilot_signal_overlap_rows": overlap["current_pilot_signal_overlap_rows"],
            "fresh_pilot_signal_overlap_tickers": overlap["current_pilot_signal_overlap_tickers"],
            "fresh_open_position_overlap_rows": overlap["open_position_overlap_rows"],
            "fresh_open_position_overlap_tickers": overlap["open_position_overlap_tickers"],
            "historical_overlap": (prior.get("overlap_with_existing_signals") or {}).get("historical_overlap"),
        },
        "scarce_slot_opportunity_cost": prior.get("scarce_slot_opportunity_cost"),
        "answers_to_key_questions": {
            "filing_shock_improves_breakout_quality": (
                "Not testable as true filing shock: fresh rows still do not "
                "create candidate-linked B/C directional cohorts."
            ),
            "filing_shock_filters_fake_c_trades": (
                "Not testable: prior persisted candidate set had zero "
                "earnings_event_long candidates and the fresh refresh is not "
                "linked to closed C trades."
            ),
            "event_confirmation_vs_standalone": (
                "If advanced, use as event confirmation or C grading; standalone "
                "SEC T+1 drift remains a separate default-off sleeve."
            ),
            "data_gap_type": (
                "Field gap, not timestamp gap: accepted_datetime and usable_trade_date "
                "exist, but directional surprise/guidance and same-accession "
                "financial-quality fields do not touch candidates."
            ),
            "default_off_c_strategy_grading_harness": (
                "Not ready; B/C cohorts remain empty and there is no closed C-strategy sample to replay."
            ),
        },
        "parameters": {
            "allowed_mode": "data_audit_shadow_only",
            "anti_js": "No JavaScript was used.",
            "fresh_snapshot_date": ASOF_DATE,
            "tagging_rule": "A/B/C/D shadow schema retained; fresh rows are D unless directional PIT-safe fields exist.",
        },
        "decision": "data_gap",
        "decision_rationale": (
            "`data_gap`: the 2026-05-14 SEC refresh has PIT timestamp/text/"
            "feature coverage and two more feature rows than the prior audit, "
            "but still has zero same-accession rows, zero directional rows, "
            "and no B/C candidate-touch cohort. Do not enter a default-off C "
            "grading harness yet."
        ),
        "rejection_reason": "No fresh PIT directional filing-shock candidate-touch cohort.",
        "next_minimal_action": (
            "Repair same-accession Companyfacts joins for 2026-05-14 10-Q/10-K "
            "accessions or ingest PIT consensus/guidance fields, then rerun "
            "candidate-touch tagging before any default-off C-strategy grading harness."
        ),
        "next_evidence_needed": [
            "PIT-safe EPS/revenue surprise",
            "structured guidance raise/cut",
            "same-accession financial-quality deltas that touch A/B or earnings_event_long candidates",
            "closed forward replacement value before promotion",
        ],
        "production_impact": production_impact,
        "must_not_touch_respected": production_impact["must_not_touch_respected"],
        "related_files": [
            rel(Path(__file__)),
            rel(SHADOW_PATH),
            rel(AUDIT_JSON_PATH),
            rel(AUDIT_MD_PATH),
            rel(TICKET_PATH),
            rel(LOG_PATH),
            "docs/experiment_log.jsonl",
        ],
        "llm_metrics": {"used_llm": False},
    }

    ticket = load_json(TICKET_PATH) if TICKET_PATH.exists() else {
        "experiment_id": EXP_ID,
        "lane": "alpha_discovery",
        "owner": "codex-alpha-discovery",
        "hypothesis": row["hypothesis"],
        "change_type": row["change_type"],
        "single_causal_variable": row["single_causal_variable"],
    }

    write_json(SHADOW_PATH, shadow_rows)
    write_json(AUDIT_JSON_PATH, row)
    write_json(LOG_PATH, row)
    AUDIT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD_PATH.write_text(markdown_report(row), encoding="utf-8")
    append_jsonl_once(EXPERIMENT_LOG_PATH, row)
    update_registry_and_ticket(ticket, row)

    print(json.dumps({
        "experiment_id": EXP_ID,
        "decision": row["decision"],
        "shadow_rows": len(shadow_rows),
        "pit_safe_rows": row["shadow_event_table"]["pit_safe_rows"],
        "feature_rows": len(features),
        "directional_rows": len(directional_rows),
        "same_accession_rows": len(same_accession_rows),
        "current_core_signal_overlap_rows": overlap["current_core_signal_overlap_rows"],
        "open_position_overlap_tickers": overlap["open_position_overlap_tickers"],
        "files": row["related_files"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
