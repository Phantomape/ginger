"""Shadow-only SEC / earnings filing-shock availability audit.

This runner checks the latest local SEC filing refresh after exp-20260513-006.
It creates a PIT-timestamped shadow event table and structured audit artifacts,
but it does not connect any SEC field to signal generation, ranking, sizing, or
orders.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXP_ID = "exp-20260514-005"
ASOF_DATE = "2026-05-12"
DATE_KEY = "20260512"
RUN_DATE_KEY = "20260514"

NON_ROOT = REPO_ROOT / "data" / "non_ohlcv"
EVENTS_PATH = NON_ROOT / f"sec_filing_events_{DATE_KEY}.jsonl"
TEXT_PATH = NON_ROOT / f"sec_filing_text_{DATE_KEY}.jsonl"
FEATURES_PATH = NON_ROOT / f"sec_filing_features_{DATE_KEY}.jsonl"
EARNINGS_PATH = REPO_ROOT / "data" / f"earnings_snapshot_{DATE_KEY}.json"
QUANT_SIGNALS_PATH = REPO_ROOT / "data" / f"quant_signals_{DATE_KEY}.json"
PRIOR_LOG_PATH = REPO_ROOT / "docs" / "experiments" / "logs" / "exp-20260513-006.json"

SHADOW_PATH = NON_ROOT / f"sec_earnings_filing_shock_shadow_events_{EXP_ID}.json"
AUDIT_JSON_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXP_ID
    / "sec_earnings_filing_shock_latest_data_audit.json"
)
AUDIT_MD_PATH = (
    REPO_ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / f"sec_earnings_filing_shock_latest_{EXP_ID}_{RUN_DATE_KEY}.md"
)
TICKET_PATH = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
LOG_PATH = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
EXPERIMENT_LOG_PATH = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_PATH = REPO_ROOT / "docs" / "experiment_registry.json"


ACCEPTED_CORE_BASELINE = {
    "source": "data/experiments/exp-20260513-036/clean_spy_leader_signal_day_risk.json",
    "aggregate": {
        "expected_value_score_sum": 6.4848,
        "total_pnl_sum": 193903.95,
        "trade_count_sum": 62,
        "signals_generated_sum": 164,
        "signals_survived_sum": 138,
    },
    "by_window": {
        "late_strong": {
            "period": "2025-10-23 -> 2026-04-21",
            "expected_value_score": 4.3768,
            "total_pnl": 99695.99,
            "total_return_pct": 0.9970,
            "sharpe_daily": 4.39,
            "max_drawdown_pct": 0.0602,
            "win_rate": 0.7895,
            "trade_count": 19,
            "signals_generated": 51,
            "signals_survived": 41,
            "survival_rate": 0.8039,
            "spy_buy_hold_return_pct": 0.05408,
            "qqq_buy_hold_return_pct": 0.057967,
            "vs_spy_pct": 0.94292,
            "vs_qqq_pct": 0.939033,
        },
        "mid_weak": {
            "period": "2025-04-23 -> 2025-10-22",
            "expected_value_score": 1.6788,
            "total_pnl": 62644.67,
            "total_return_pct": 0.6264,
            "sharpe_daily": 2.68,
            "max_drawdown_pct": 0.0970,
            "win_rate": 0.5238,
            "trade_count": 21,
            "signals_generated": 53,
            "signals_survived": 42,
            "survival_rate": 0.7925,
            "spy_buy_hold_return_pct": 0.254401,
            "qqq_buy_hold_return_pct": 0.335077,
            "vs_spy_pct": 0.371999,
            "vs_qqq_pct": 0.291323,
        },
        "old_thin": {
            "period": "2024-10-02 -> 2025-04-22",
            "expected_value_score": 0.4292,
            "total_pnl": 31563.29,
            "total_return_pct": 0.3156,
            "sharpe_daily": 1.36,
            "max_drawdown_pct": 0.0836,
            "win_rate": 0.4091,
            "trade_count": 22,
            "signals_generated": 60,
            "signals_survived": 55,
            "survival_rate": 0.9167,
            "spy_buy_hold_return_pct": -0.067229,
            "qqq_buy_hold_return_pct": -0.074882,
            "vs_spy_pct": 0.382829,
            "vs_qqq_pct": 0.390482,
        },
    },
}


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
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
    experiment_id = payload["experiment_id"]
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
    if experiment_id in existing_ids:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def finite_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, str) and value.strip():
        try:
            value = float(value)
        except ValueError:
            return None
        return value if math.isfinite(value) else None
    return None


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


def classify(row: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    positive, negative = directional_fields(row)
    if positive and not negative:
        return "B_positive_filing_shock", positive, negative
    if negative and not positive:
        return "C_negative_filing_shock", positive, negative
    return "D_unclear_or_missing_data", positive, negative


def most_common(counter: Counter[Any]) -> dict[str, int]:
    return {str(key): int(value) for key, value in counter.most_common()}


def pct(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def summarize_earnings_snapshot() -> dict[str, Any]:
    if not EARNINGS_PATH.exists():
        rows: list[dict[str, Any]] = []
    else:
        payload = load_json(EARNINGS_PATH)
        raw = payload.get("earnings") if isinstance(payload, dict) else None
        if isinstance(raw, dict):
            rows = [row for row in raw.values() if isinstance(row, dict)]
        elif isinstance(raw, list):
            rows = [row for row in raw if isinstance(row, dict)]
        else:
            rows = []
    return {
        "path": rel(EARNINGS_PATH),
        "tickers_total": len(rows),
        "tickers_with_next_earnings_date": sum(1 for row in rows if row.get("next_earnings_date")),
        "tickers_with_days_to_earnings": sum(1 for row in rows if row.get("days_to_earnings") is not None),
        "tickers_with_eps_estimate": sum(1 for row in rows if row.get("eps_estimate") is not None),
        "tickers_with_eps_actual_last": sum(1 for row in rows if row.get("eps_actual_last") is not None),
        "tickers_with_surprise_history": sum(
            1
            for row in rows
            if row.get("avg_historical_surprise_pct") is not None
            or row.get("historical_surprise_pct")
        ),
        "missing_for_filing_shock": [
            "current EPS surprise vs PIT consensus",
            "revenue surprise",
            "structured guidance raise/cut",
            f"same-accession financial-quality deltas for {ASOF_DATE} filings",
        ],
        "pit_note": "Replayable repo snapshot, not vendor-grade PIT consensus surprise evidence.",
    }


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
        tag, positive, negative = classify(merged)
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
                or "SEC public accepted_at is a PIT proxy, not proof local production observed it."
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
    for row in texts:
        text_chars += len(str(row.get("combined_text") or row.get("text") or row.get("filing_text") or ""))
        for doc in row.get("documents") or []:
            if isinstance(doc, dict) and row.get("combined_text") is None:
                text_chars += int(doc.get("text_char_count") or 0)
    coverage = {
        f"sec_filing_events_{DATE_KEY}": {
            "path": rel(EVENTS_PATH),
            "rows": len(events),
            "tickers": len({str(row.get("ticker") or "").upper() for row in events if row.get("ticker")}),
            "accepted_datetime_rows": sum(1 for row in events if row.get("accepted_at")),
            "usable_trade_date_rows": sum(1 for row in events if row.get("usable_trade_date")),
            "pit_safe_rows": sum(
                1 for row in events
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
                "report_date/fiscal_period_end is not used as tradable date."
            ),
        },
        f"sec_filing_text_{DATE_KEY}": {
            "path": rel(TEXT_PATH),
            "rows": len(texts),
            "forms": most_common(Counter(row.get("form_type") or row.get("form") or "unknown" for row in texts)),
            "status_counts": most_common(Counter(row.get("status") or "unknown" for row in texts)),
            "text_char_count": text_chars,
            "coverage_note": (
                "Text rows are replayable public-filing text, but this run has "
                "no structured guidance/surprise extraction adapter."
            ),
        },
        f"sec_filing_features_{DATE_KEY}": {
            "path": rel(FEATURES_PATH),
            "exists": FEATURES_PATH.exists(),
            "rows": len(features),
            "pit_safe_rows": sum(1 for row in features if row.get("pit_safe")),
            "feature_event_coverage_vs_events": pct(len(features), len(events)),
            "same_accession_rows": len(same_accession),
            "directional_rows": len(directional),
            "eps_surprise_rows": field_counts["eps_surprise"],
            "revenue_surprise_rows": field_counts["revenue_surprise"],
            "guidance_raise_cut_rows": field_counts["guidance_raise_cut"],
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


def current_overlap(shadow_rows: list[dict[str, Any]], features: list[dict[str, Any]]) -> dict[str, Any]:
    quant = load_json(QUANT_SIGNALS_PATH) if QUANT_SIGNALS_PATH.exists() else {}
    event_tickers = {str(row.get("ticker") or "").upper() for row in shadow_rows if row.get("ticker")}
    feature_tickers = {str(row.get("ticker") or "").upper() for row in features if row.get("ticker")}
    core_signals = quant.get("signals") or []
    pilot_signals = quant.get("pilot_signals") or []
    open_tickers = {
        str(row.get("ticker") or "").upper()
        for row in ((quant.get("portfolio_heat") or {}).get("position_breakdown") or [])
        if row.get("ticker")
    }
    queues: dict[str, Any] = {}
    for key in (
        "sec_event_queue",
        "sec_governance_event_queue",
        "sec_financial_report_t1_queue",
        "event_sleeve_bundle",
        "space_catalyst_observation_slot",
    ):
        value = quant.get(key) or {}
        queues[key] = {
            "candidate_count": value.get("candidate_count"),
            "raw_candidate_count": value.get("raw_candidate_count"),
            "selected_count": value.get("selected_count"),
            "data_source": value.get("data_source"),
        }
    return {
        "asof_date": ASOF_DATE,
        "fresh_event_rows": len(shadow_rows),
        "fresh_event_tickers": len(event_tickers),
        "feature_event_rows": len(features),
        "feature_event_tickers": len(feature_tickers),
        "current_core_signal_count": len(core_signals),
        "current_core_signal_overlap_rows": sum(
            1 for sig in core_signals
            if str(sig.get("ticker") or "").upper() in event_tickers
        ),
        "current_core_signal_overlap_tickers": sorted({
            str(sig.get("ticker") or "").upper()
            for sig in core_signals
            if str(sig.get("ticker") or "").upper() in event_tickers
        }),
        "current_pilot_signal_count": len(pilot_signals),
        "current_pilot_signal_overlap_rows": sum(
            1 for sig in pilot_signals
            if str(sig.get("ticker") or "").upper() in event_tickers
        ),
        "current_pilot_signal_overlap_tickers": sorted({
            str(sig.get("ticker") or "").upper()
            for sig in pilot_signals
            if str(sig.get("ticker") or "").upper() in event_tickers
        }),
        "open_position_overlap_rows": len(open_tickers.intersection(event_tickers)),
        "open_position_overlap_tickers": sorted(open_tickers.intersection(event_tickers)),
        "queue_counts": queues,
    }


def prior_shadow_metrics() -> dict[str, Any]:
    prior = load_json(PRIOR_LOG_PATH)
    carried = prior.get("shadow_or_replay_metrics") or {}
    historical_overlap = prior.get("overlap_with_existing_signals", {}).get("historical_overlap")
    if historical_overlap is None:
        historical_overlap = prior.get("shadow_metrics", {}).get("overlap_with_existing_signals")
    forward_returns = carried.get("tagged_candidate_forward_returns_carried_forward_from_exp_20260511_001")
    if forward_returns is None:
        forward_returns = (
            prior.get("shadow_metrics", {})
            .get("historical_candidate_overlap_and_slot_value_carried_forward", {})
            .get("tagged_candidate_forward_returns")
        )
    return {
        "candidate_count": prior.get("candidate_count"),
        "overlap_with_existing_signals": historical_overlap,
        "scarce_slot_opportunity_cost": prior.get("scarce_slot_opportunity_cost"),
        "tagged_candidate_forward_returns": forward_returns,
        "source": rel(PRIOR_LOG_PATH),
        "freshness_note": (
            "Carried forward only; 2026-05-12 SEC refresh is post-canonical-window "
            "and not linked to closed forward candidate outcomes."
        ),
    }


def update_registry(ticket: dict[str, Any], timestamp: str) -> None:
    registry = load_json(REGISTRY_PATH) if REGISTRY_PATH.exists() else {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
    }
    experiments = registry.setdefault("experiments", [])
    entry = {
        "experiment_id": EXP_ID,
        "status": "data_gap",
        "lane": "alpha_discovery",
        "owner": "codex-alpha-discovery",
        "hypothesis": ticket["hypothesis"],
        "ticket_file": rel(TICKET_PATH),
        "updated_at": timestamp,
    }
    for index, existing in enumerate(experiments):
        if existing.get("experiment_id") == EXP_ID:
            experiments[index] = {**existing, **entry}
            break
    else:
        experiments.append(entry)
    registry["updated_at"] = timestamp
    write_json(REGISTRY_PATH, registry)


def fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def forward_avg(forward: dict[str, Any], tag: str, horizon: int) -> str:
    tag_row = forward.get(tag) or {}
    value = ((tag_row.get("forward_returns") or {}).get(f"{horizon}d") or {}).get("avg_pct")
    return fmt(value)


def markdown_report(row: dict[str, Any], shadow_rows: list[dict[str, Any]]) -> str:
    coverage = row["coverage"]
    historical = row["shadow_metrics"]["historical_candidate_overlap_and_slot_value_carried_forward"]
    forward = historical.get("tagged_candidate_forward_returns") or {}
    current = row["shadow_metrics"]["fresh_current_overlap"]
    slot = historical.get("scarce_slot_opportunity_cost") or {}
    slot_dist = slot.get("overall_delta_20d_distribution") or {}
    events_key = f"sec_filing_events_{DATE_KEY}"
    text_key = f"sec_filing_text_{DATE_KEY}"
    features_key = f"sec_filing_features_{DATE_KEY}"
    earnings_key = f"earnings_snapshot_{DATE_KEY}"

    lines = [
        f"# SEC / earnings / filing shock latest data audit ({EXP_ID})",
        "",
        f"- timestamp: `{row['timestamp']}`",
        "- mode: `data_audit_shadow_only`",
        "- mechanism_family: `SEC / earnings / filing shock event-confirmation overlay`",
        f"- single_causal_variable: `{row['single_causal_variable']}`",
        "- production_change_allowed: `false`",
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
        "## PIT status",
        "",
        "- `accepted_at` and `usable_trade_date` are present on SEC event rows.",
        "- `report_date` / `fiscal_period_end` was not used as a tradable date.",
        "- Companyfacts filed dates remain public-availability proxies, not proof of local production observation.",
        "- Earnings snapshots are replayable repo artifacts, not vendor-grade PIT consensus surprise evidence.",
        "",
        "## Shadow table",
        "",
        f"- shadow_event_table: `{rel(SHADOW_PATH)}`",
        f"- rows: `{len(shadow_rows)}`",
        f"- PIT-safe rows: `{sum(1 for item in shadow_rows if item.get('pit_safe'))}`",
        f"- feature-present rows: `{sum(1 for item in shadow_rows if item.get('feature_present'))}`",
        f"- same-accession rows: `{coverage[features_key]['same_accession_rows']}`",
        f"- directional rows: `{coverage[features_key]['directional_rows']}`",
        f"- tag_counts: `{json.dumps(row['shadow_event_table']['tag_counts'], sort_keys=True)}`",
        "",
        "## Tagged candidate forward returns",
        "",
        (
            "Fresh 2026-05-12 rows are not mature for 5/10/20/60d candidate "
            "returns and are not linked to canonical-window candidates. "
            "Carried-forward historical candidate tags from `exp-20260511-001`:"
        ),
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
        "## Overlap and slot value",
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


def main() -> int:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    events = load_jsonl(EVENTS_PATH)
    texts = load_jsonl(TEXT_PATH)
    features = load_jsonl(FEATURES_PATH)
    shadow_rows = build_shadow_rows(events, features)
    coverage, directional_rows, same_accession_rows = build_coverage(events, texts, features)
    overlap = current_overlap(shadow_rows, features)
    historical_shadow = prior_shadow_metrics()
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
    tag_counts = most_common(Counter(row["filing_shock_tag"] for row in shadow_rows))
    events_key = f"sec_filing_events_{DATE_KEY}"
    features_key = f"sec_filing_features_{DATE_KEY}"
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
            "event confirmation, but only if the 2026-05-12 SEC refresh adds "
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
        "single_causal_variable": "post_exp_20260513_006_sec_filing_20260512_feature_availability",
        "change_type": "non_ohlcv_data_audit_shadow_tagging",
        "changed_variable": "2026-05-12 SEC filing feature availability only",
        "production_change_allowed": False,
        "historical_experiment_check": {
            "docs_alpha_optimization_playbook": (
                "SEC filing shock remains blocked by missing directional "
                "same-accession fields; accepted SEC T+1 paper sleeve should "
                "not be retuned here."
            ),
            "exp-20260510-002": (
                "Refreshed 2026-05-07/08 SEC filing-shock rows were all "
                "D_unclear_or_missing_data with zero same-accession rows and "
                "zero directional numeric rows."
            ),
            "exp-20260511-001": (
                "Full current audit: 138 A/B candidates, B/C filing-shock "
                "cohorts empty, no earnings_event_long candidates, and raw "
                "filing-presence slot value negative."
            ),
            "exp-20260512-003": (
                "2026-05-10 refresh added timestamp/text coverage but no "
                "feature file or directional fields."
            ),
            "exp-20260513-006": (
                "2026-05-11 refresh had events/text/features and 1 pilot "
                "overlap, but zero same-accession rows, zero directional rows, "
                "and no B/C candidate-touch cohort."
            ),
            "exp-20260512-020": (
                "Separate SEC financial-report T+1 sleeve accepted as "
                "default-off risk allocation; this run does not change or "
                "retune it."
            ),
        },
        "field_check": {
            "backtester_earnings_snapshot_disclosure": (
                "quant/backtester.py loads P-ERN earnings_snapshot_YYYYMMDD "
                "files and reports earnings_event_long coverage under known_biases."
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
            "missing_for_this_hypothesis": [
                "current EPS surprise vs PIT consensus",
                "revenue_surprise",
                "guidance_raise_cut",
                "same-accession financial-quality deltas on 2026-05-12 feature rows",
                "candidate-touch B/C tags",
            ],
        },
        "baseline_metrics": ACCEPTED_CORE_BASELINE,
        "before_metrics": ACCEPTED_CORE_BASELINE,
        "after_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "same_as_baseline": True,
            "reason": (
                "Data audit and shadow table only; no replay, queue, ranking, "
                "sizing, signal, or order path changed."
            ),
        },
        "expected_value_score_delta": 0.0,
        "expected_value_score_delta_reason": "No strategy or default-off replay path changed.",
        "data_availability_pit_status": {
            "event_timestamp_status": (
                "Fresh SEC rows have accepted_at, accession_number, and "
                "usable_trade_date; period/report date was not used as a tradable date."
            ),
            "feature_status": (
                "sec_filing_features_20260512 exists, but same-accession and "
                "directional rows must be nonzero before candidate-touch testing."
            ),
            "text_status": (
                "8-K text exists and has replayable text content, but no "
                "structured guidance/surprise extraction adapter is present."
            ),
            "earnings_snapshot_status": (
                "earnings_snapshot_20260512 has EPS estimate/history coverage "
                "but not current EPS/revenue surprise vs PIT consensus."
            ),
            "do_not_use_as_production_evidence": True,
            "biased_or_blocked_fields": [
                "eps_surprise",
                "revenue_surprise",
                "guidance_raise_cut",
                "fresh same-accession Companyfacts fields",
                "B/C candidate-touch cohorts",
            ],
        },
        "coverage": coverage,
        "shadow_event_table": {
            "path": rel(SHADOW_PATH),
            "rows": len(shadow_rows),
            "pit_safe_rows": sum(1 for item in shadow_rows if item.get("pit_safe")),
            "feature_present_rows": sum(1 for item in shadow_rows if item.get("feature_present")),
            "same_accession_rows": len(same_accession_rows),
            "directional_rows": len(directional_rows),
            "tag_counts": tag_counts,
            "forward_returns_status": (
                "Fresh 2026-05-12 refresh is post-canonical-window and not "
                "mature for 5/10/20/60d candidate returns."
            ),
        },
        "shadow_metrics": {
            "fresh_current_overlap": overlap,
            "historical_candidate_overlap_and_slot_value_carried_forward": historical_shadow,
        },
        "shadow_or_replay_metrics": {
            "fresh_forward_returns_status": (
                "not_mature_for_5_10_20_60d_windows_and_not_candidate_linked"
            ),
            "tagged_candidate_forward_returns_carried_forward_from_exp_20260511_001": (
                historical_shadow.get("tagged_candidate_forward_returns")
            ),
            "candidate_overlap_and_slot_value": historical_shadow.get("scarce_slot_opportunity_cost"),
            "current_overlap": overlap,
        },
        "candidate_count": historical_shadow.get("candidate_count"),
        "overlap_with_existing_signals": {
            "fresh_current_core_signal_overlap_rows": overlap["current_core_signal_overlap_rows"],
            "fresh_current_core_signal_count": overlap["current_core_signal_count"],
            "fresh_current_core_signal_overlap_tickers": overlap["current_core_signal_overlap_tickers"],
            "fresh_pilot_signal_overlap_rows": overlap["current_pilot_signal_overlap_rows"],
            "fresh_pilot_signal_overlap_tickers": overlap["current_pilot_signal_overlap_tickers"],
            "historical_overlap": historical_shadow.get("overlap_with_existing_signals"),
        },
        "scarce_slot_opportunity_cost": historical_shadow.get("scarce_slot_opportunity_cost"),
        "answers_to_key_questions": {
            "filing_shock_improves_breakout_quality": (
                "Not testable as a true filing shock in this delta: fresh rows "
                "do not create a candidate-linked B/C directional shock cohort."
            ),
            "filing_shock_filters_fake_c_trades": (
                "Not testable: prior persisted candidate set had zero "
                "earnings_event_long candidates and the fresh refresh is not "
                "candidate-linked to closed C trades."
            ),
            "event_confirmation_vs_standalone": (
                "If this branch advances, it should remain event confirmation "
                "or C-strategy grading. Standalone SEC T+1 drift is already a "
                "separate default-off paper sleeve."
            ),
            "data_gap_type": (
                "Field gap, not timestamp gap: accepted_datetime and usable_trade_date "
                "exist, but directional surprise/guidance and same-accession "
                "financial-quality fields do not touch candidates."
            ),
            "default_off_c_strategy_grading_harness": (
                "Not ready; B/C cohorts remain empty for candidate-touch "
                "purposes and there is no closed C-strategy sample to replay."
            ),
        },
        "decision": "data_gap",
        "decision_rationale": (
            "`data_gap`: the 2026-05-12 SEC refresh has timestamp/text/feature "
            "coverage, but it still does not produce a PIT-safe directional "
            "same-accession shock cohort that touches existing trend/breakout/C "
            "candidates. Do not enter a default-off C grading harness yet."
        ),
        "rejection_reason": "No fresh PIT directional filing-shock candidate-touch cohort.",
        "next_minimal_action": (
            "Repair same-accession Companyfacts joins for 2026-05-12 10-Q/10-K "
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
    }
    row["coverage_delta_vs_exp_20260513_006"] = {
        "events_rows_delta": coverage[events_key]["rows"] - 65,
        "features_rows_delta": coverage[features_key]["rows"] - 41,
        "directional_rows_delta": len(directional_rows),
        "same_accession_rows_delta": len(same_accession_rows),
        "current_core_signal_overlap_delta": overlap["current_core_signal_overlap_rows"],
    }
    ticket = load_json(TICKET_PATH) if TICKET_PATH.exists() else {
        "experiment_id": EXP_ID,
        "lane": "alpha_discovery",
        "owner": "codex-alpha-discovery",
        "hypothesis": row["hypothesis"],
        "change_type": row["change_type"],
        "single_causal_variable": row["single_causal_variable"],
    }
    ticket.update({
        "status": "data_gap",
        "completed_at": timestamp,
        "result": {
            "decision": "data_gap",
            "reason": row["decision_rationale"],
            "artifact_file": rel(AUDIT_JSON_PATH),
            "audit_report": rel(AUDIT_MD_PATH),
            "shadow_event_table": rel(SHADOW_PATH),
        },
    })

    write_json(SHADOW_PATH, shadow_rows)
    write_json(AUDIT_JSON_PATH, row)
    write_json(TICKET_PATH, ticket)
    write_json(LOG_PATH, row)
    AUDIT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD_PATH.write_text(markdown_report(row, shadow_rows), encoding="utf-8")
    append_jsonl_once(EXPERIMENT_LOG_PATH, row)
    update_registry(ticket, timestamp)
    print(json.dumps({
        "experiment_id": EXP_ID,
        "decision": "data_gap",
        "shadow_rows": len(shadow_rows),
        "feature_rows": len(features),
        "directional_rows": len(directional_rows),
        "same_accession_rows": len(same_accession_rows),
        "current_core_signal_overlap_rows": overlap["current_core_signal_overlap_rows"],
        "current_pilot_signal_overlap_rows": overlap["current_pilot_signal_overlap_rows"],
        "files": row["related_files"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
