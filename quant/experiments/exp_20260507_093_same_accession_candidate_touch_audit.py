"""exp-20260507-092 same-accession Companyfacts candidate-touch audit.

Replay-only diagnostic:
- starts from exp-20260507-006 persisted post-gate candidate events;
- checks every PIT-safe SEC filing in the candidate lookback, not only the
  latest filing chosen by the conservative filing-shock classifier;
- explains why same-accession Companyfacts did not produce B/C cohorts.

No signal generation, ranking, sizing, exit, order, risk, or production adapter
logic is changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_DIR = Path(__file__).resolve().parent
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from exp_20260507_006_full_candidate_filing_shock_shadow import (  # noqa: E402
    RECENT_FILING_LOOKBACK_TRADING_DAYS,
    WINDOWS,
    _directional_field_counts,
    _load_json,
    _load_sec_features,
    _load_snapshot,
    _market_trading_day_distance,
    _safe_ratio,
    _summarize_values,
)


EXPERIMENT_ID = "exp-20260507-093"
SOURCE_EXPERIMENT_ID = "exp-20260507-006"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "same_accession_candidate_touch_audit.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
AUDIT_MD = (
    REPO_ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / "sec_same_accession_candidate_touch_exp-20260507-093_20260507.md"
)

HORIZONS = (5, 10, 20, 60)
TAGS = (
    "A_no_recent_filing_event",
    "B_positive_filing_shock",
    "C_negative_filing_shock",
    "D_unclear_or_missing_data",
)
SLOT_CONFLICT_DECISIONS = {"slot_sliced", "scarce_slot_breakout_deferred"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_tagged_candidates(window_name: str) -> list[dict[str, Any]]:
    path = (
        REPO_ROOT
        / "data"
        / "experiments"
        / SOURCE_EXPERIMENT_ID
        / f"tagged_entry_candidates_{window_name}.json"
    )
    payload = _load_json(path)
    return list(payload.get("rows") or [])


def _is_same_accession(row: dict[str, Any]) -> bool:
    return (row.get("field_availability") or {}).get("same_accession_facts") == "derived"


def _is_directional(row: dict[str, Any]) -> bool:
    positive, negative = _directional_field_counts(row)
    return bool(positive or negative)


def _field_values(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "gross_margin_delta": row.get("gross_margin_delta"),
        "fcf_to_net_income_gap": row.get("fcf_to_net_income_gap"),
        "inventory_growth": row.get("inventory_growth"),
        "receivables_growth": row.get("receivables_growth"),
        "eps_surprise": row.get("eps_surprise"),
        "revenue_surprise": row.get("revenue_surprise"),
        "guidance_raise_cut": row.get("guidance_raise_cut"),
    }


def _event_ref(row: dict[str, Any], distance: int | None = None) -> dict[str, Any]:
    positive, negative = _directional_field_counts(row)
    return {
        "ticker": row.get("ticker"),
        "form_type": row.get("form_type"),
        "usable_trade_date": row.get("usable_trade_date"),
        "accepted_datetime": row.get("accepted_datetime"),
        "source_accession": row.get("source_accession"),
        "eight_k_item_type": row.get("eight_k_item_type"),
        "distance_trading_days": distance,
        "same_accession_facts": _is_same_accession(row),
        "positive_evidence_fields": positive,
        "negative_evidence_fields": negative,
        "values": _field_values(row),
    }


def _sort_recent(events: list[tuple[int, dict[str, Any]]]) -> list[tuple[int, dict[str, Any]]]:
    return sorted(
        events,
        key=lambda item: (
            item[0],
            str(item[1].get("usable_trade_date") or ""),
            str(item[1].get("accepted_datetime") or ""),
        ),
    )


def _recent_events_for_candidate(
    *,
    events_by_ticker: dict[str, list[dict[str, Any]]],
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    candidate_date: str,
) -> list[tuple[int, dict[str, Any]]]:
    recent: list[tuple[int, dict[str, Any]]] = []
    for row in events_by_ticker.get(ticker.upper(), []):
        usable = str(row.get("usable_trade_date") or "")[:10]
        if not usable or usable > candidate_date or not row.get("pit_safe", False):
            continue
        distance = _market_trading_day_distance(snapshot, usable, candidate_date)
        if (
            distance is None
            or distance < 0
            or distance > RECENT_FILING_LOOKBACK_TRADING_DAYS
        ):
            continue
        recent.append((distance, row))
    return _sort_recent(recent)


def _nearest_directional_context(
    *,
    directional_by_ticker: dict[str, list[dict[str, Any]]],
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    candidate_date: str,
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_abs_distance: int | None = None
    for row in directional_by_ticker.get(ticker.upper(), []):
        usable = str(row.get("usable_trade_date") or "")[:10]
        if not usable:
            continue
        if usable <= candidate_date:
            distance = _market_trading_day_distance(snapshot, usable, candidate_date)
            direction = "before_or_on_candidate"
        else:
            distance = _market_trading_day_distance(snapshot, candidate_date, usable)
            direction = "after_candidate_not_tradable"
        if distance is None or distance < 0:
            continue
        if best_abs_distance is None or distance < best_abs_distance:
            best_abs_distance = distance
            best = {
                "direction": direction,
                "abs_distance_trading_days": distance,
                "event": _event_ref(row, distance),
            }
    return best


def _classify_touch_reason(
    recent: list[tuple[int, dict[str, Any]]],
    nearest_directional: dict[str, Any] | None,
) -> str:
    if not recent:
        if nearest_directional:
            if nearest_directional["direction"] == "before_or_on_candidate":
                return "no_recent_filing_directional_event_outside_lookback"
            return "no_recent_filing_directional_event_after_candidate_not_tradable"
        return "no_recent_filing_no_directional_event_for_ticker"

    same_accession = [row for _, row in recent if _is_same_accession(row)]
    directional = [row for _, row in recent if _is_directional(row)]
    if not same_accession:
        return "recent_filings_without_same_accession_companyfacts"
    if not directional:
        return "same_accession_recent_but_no_directional_fields"
    pure_positive = []
    pure_negative = []
    mixed = []
    for row in directional:
        positive, negative = _directional_field_counts(row)
        if positive and not negative:
            pure_positive.append(row)
        elif negative and not positive:
            pure_negative.append(row)
        else:
            mixed.append(row)
    if mixed and not pure_positive and not pure_negative:
        return "same_accession_recent_directional_but_mixed_signs"
    if pure_positive or pure_negative:
        return "directional_recent_available_classifier_should_have_tagged"
    return "recent_filing_unknown_gap"


def _coverage_by_feature_rows(sec_features: list[dict[str, Any]]) -> dict[str, Any]:
    same_accession = [row for row in sec_features if _is_same_accession(row)]
    directional = [row for row in sec_features if _is_directional(row)]
    form_counts = Counter(str(row.get("form_type") or "unknown") for row in sec_features)
    same_accession_form_counts = Counter(str(row.get("form_type") or "unknown") for row in same_accession)
    directional_form_counts = Counter(str(row.get("form_type") or "unknown") for row in directional)
    return {
        "sec_feature_rows": len(sec_features),
        "pit_safe_rows": sum(1 for row in sec_features if row.get("pit_safe", False)),
        "same_accession_rows": len(same_accession),
        "directional_rows": len(directional),
        "form_counts": dict(form_counts.most_common()),
        "same_accession_form_counts": dict(same_accession_form_counts.most_common()),
        "directional_form_counts": dict(directional_form_counts.most_common()),
    }


def _summarize_candidates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_reason = Counter(row["touch_failure_reason"] for row in rows)
    by_tag = Counter(row.get("filing_shock_tag") or "unknown" for row in rows)
    by_decision = Counter(row.get("decision") or "unknown" for row in rows)
    recent_forms = Counter()
    latest_forms = Counter()
    for row in rows:
        latest = row.get("latest_recent_filing")
        if latest:
            latest_forms[str(latest.get("form_type") or "unknown")] += 1
        for form_type, count in (row.get("recent_filing_form_counts") or {}).items():
            recent_forms[str(form_type)] += int(count)

    same_accession_touches = [row for row in rows if row["recent_same_accession_count"] > 0]
    directional_touches = [row for row in rows if row["recent_directional_count"] > 0]
    slot_rows = [row for row in rows if row.get("decision") in SLOT_CONFLICT_DECISIONS]
    return {
        "candidate_count": len(rows),
        "entered_count": sum(1 for row in rows if row.get("decision") == "entered"),
        "tag_counts": dict(sorted(by_tag.items())),
        "decision_counts": dict(sorted(by_decision.items())),
        "touch_failure_reason_counts": dict(sorted(by_reason.items())),
        "recent_filing_candidate_count": sum(1 for row in rows if row["recent_filing_count"] > 0),
        "recent_same_accession_candidate_count": len(same_accession_touches),
        "recent_directional_candidate_count": len(directional_touches),
        "slot_candidate_count": len(slot_rows),
        "slot_same_accession_candidate_count": sum(
            1 for row in slot_rows if row["recent_same_accession_count"] > 0
        ),
        "slot_directional_candidate_count": sum(
            1 for row in slot_rows if row["recent_directional_count"] > 0
        ),
        "entered_same_accession_candidate_count": sum(
            1 for row in rows
            if row.get("decision") == "entered" and row["recent_same_accession_count"] > 0
        ),
        "entered_directional_candidate_count": sum(
            1 for row in rows
            if row.get("decision") == "entered" and row["recent_directional_count"] > 0
        ),
        "recent_filing_form_counts": dict(recent_forms.most_common()),
        "latest_recent_filing_form_counts": dict(latest_forms.most_common()),
        "nearest_directional_context_counts": dict(Counter(
            (
                (row.get("nearest_directional_context") or {}).get("direction")
                if row.get("nearest_directional_context")
                else "no_directional_event_for_ticker"
            )
            for row in rows
        ).most_common()),
    }


def _candidate_diagnostics_for_window(window_name: str, window: dict[str, str]) -> dict[str, Any]:
    snapshot = _load_snapshot(REPO_ROOT / window["snapshot"])
    tagged = _load_tagged_candidates(window_name)
    sec_features = _load_sec_features(window["start"], window["end"])

    events_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    directional_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sec_features:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker or not row.get("pit_safe", False):
            continue
        events_by_ticker[ticker].append(row)
        if _is_directional(row):
            directional_by_ticker[ticker].append(row)

    for rows in events_by_ticker.values():
        rows.sort(key=lambda item: (str(item.get("usable_trade_date") or ""), str(item.get("accepted_datetime") or "")))
    for rows in directional_by_ticker.values():
        rows.sort(key=lambda item: (str(item.get("usable_trade_date") or ""), str(item.get("accepted_datetime") or "")))

    diagnostics = []
    for row in tagged:
        ticker = str(row.get("ticker") or "").upper()
        candidate_date = str(row.get("candidate_date") or row.get("date") or "")[:10]
        recent = _recent_events_for_candidate(
            events_by_ticker=events_by_ticker,
            snapshot=snapshot,
            ticker=ticker,
            candidate_date=candidate_date,
        )
        latest = recent[0] if recent else None
        same_accession = [(distance, event) for distance, event in recent if _is_same_accession(event)]
        directional = [(distance, event) for distance, event in recent if _is_directional(event)]
        nearest_directional = _nearest_directional_context(
            directional_by_ticker=directional_by_ticker,
            snapshot=snapshot,
            ticker=ticker,
            candidate_date=candidate_date,
        )
        recent_form_counts = Counter(str(event.get("form_type") or "unknown") for _, event in recent)
        touch_failure_reason = _classify_touch_reason(recent, nearest_directional)
        diagnostics.append({
            "window": window_name,
            "ticker": ticker,
            "strategy": row.get("strategy"),
            "candidate_date": candidate_date,
            "decision": row.get("decision"),
            "candidate_rank": row.get("candidate_rank"),
            "filing_shock_tag": row.get("filing_shock_tag"),
            "classification_reason": row.get("classification_reason"),
            "recent_filing_count": len(recent),
            "recent_same_accession_count": len(same_accession),
            "recent_directional_count": len(directional),
            "recent_filing_form_counts": dict(sorted(recent_form_counts.items())),
            "latest_recent_filing": _event_ref(latest[1], latest[0]) if latest else None,
            "same_accession_recent_events": [
                _event_ref(event, distance) for distance, event in same_accession[:10]
            ],
            "directional_recent_events": [
                _event_ref(event, distance) for distance, event in directional[:10]
            ],
            "nearest_directional_context": nearest_directional,
            "touch_failure_reason": touch_failure_reason,
            "ret_5d": row.get("ret_5d"),
            "ret_10d": row.get("ret_10d"),
            "ret_20d": row.get("ret_20d"),
            "ret_60d": row.get("ret_60d"),
        })

    return {
        "feature_coverage": _coverage_by_feature_rows(sec_features),
        "candidate_summary": _summarize_candidates(diagnostics),
        "diagnostic_rows": diagnostics,
        "sample_recent_without_same_accession": [
            row for row in diagnostics
            if row["touch_failure_reason"] == "recent_filings_without_same_accession_companyfacts"
        ][:30],
        "sample_nearest_directional_misses": [
            row for row in diagnostics
            if row.get("nearest_directional_context")
        ][:30],
    }


def _aggregate_summary(by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    all_rows = [
        row
        for window_payload in by_window.values()
        for row in window_payload["diagnostic_rows"]
    ]
    feature_rows = [window_payload["feature_coverage"] for window_payload in by_window.values()]
    return {
        "candidate_count": len(all_rows),
        "recent_filing_candidate_count": sum(
            row["candidate_summary"]["recent_filing_candidate_count"]
            for row in by_window.values()
        ),
        "recent_same_accession_candidate_count": sum(
            row["candidate_summary"]["recent_same_accession_candidate_count"]
            for row in by_window.values()
        ),
        "recent_directional_candidate_count": sum(
            row["candidate_summary"]["recent_directional_candidate_count"]
            for row in by_window.values()
        ),
        "b_positive_candidate_count": sum(
            row["candidate_summary"]["tag_counts"].get("B_positive_filing_shock", 0)
            for row in by_window.values()
        ),
        "c_negative_candidate_count": sum(
            row["candidate_summary"]["tag_counts"].get("C_negative_filing_shock", 0)
            for row in by_window.values()
        ),
        "touch_failure_reason_counts": dict(Counter(
            row["touch_failure_reason"] for row in all_rows
        ).most_common()),
        "feature_same_accession_rows": sum(row["same_accession_rows"] for row in feature_rows),
        "feature_directional_rows": sum(row["directional_rows"] for row in feature_rows),
        "candidate_touch_rate": _safe_ratio(
            sum(
                row["candidate_summary"]["recent_same_accession_candidate_count"]
                for row in by_window.values()
            ),
            len(all_rows),
        ),
        "directional_candidate_touch_rate": _safe_ratio(
            sum(
                row["candidate_summary"]["recent_directional_candidate_count"]
                for row in by_window.values()
            ),
            len(all_rows),
        ),
        "forward_returns_by_touch_reason_20d": {
            reason: _summarize_values([
                row.get("ret_20d")
                for row in all_rows
                if row["touch_failure_reason"] == reason
            ])
            for reason in sorted(set(row["touch_failure_reason"] for row in all_rows))
        },
    }


def _append_or_replace_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") != record.get("experiment_id"):
                lines.append(json.dumps(existing, ensure_ascii=False))
    lines.append(json.dumps(record, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_registry(ticket: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON)
    entry = {
        "experiment_id": EXPERIMENT_ID,
        "status": ticket["status"],
        "lane": ticket.get("lane"),
        "owner": ticket.get("owner"),
        "hypothesis": ticket.get("hypothesis"),
        "ticket_file": f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
        "updated_at": _utc_now_iso(),
    }
    experiments = registry.setdefault("experiments", [])
    for idx, existing in enumerate(experiments):
        if existing.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = {**existing, **entry}
            break
    else:
        experiments.append(entry)
    registry["updated_at"] = entry["updated_at"]
    _write_json(REGISTRY_JSON, registry)


def _write_audit_md(payload: dict[str, Any]) -> None:
    aggregate = payload["aggregate_summary"]
    lines = [
        f"# SEC Same-Accession Candidate Touch Audit ({EXPERIMENT_ID})",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Decision",
        payload["decision"],
        "",
        "## Aggregate",
        f"- candidate_count: `{aggregate['candidate_count']}`",
        f"- recent_filing_candidate_count: `{aggregate['recent_filing_candidate_count']}`",
        f"- recent_same_accession_candidate_count: `{aggregate['recent_same_accession_candidate_count']}`",
        f"- recent_directional_candidate_count: `{aggregate['recent_directional_candidate_count']}`",
        f"- feature_same_accession_rows: `{aggregate['feature_same_accession_rows']}`",
        f"- feature_directional_rows: `{aggregate['feature_directional_rows']}`",
        f"- B/C candidate counts: `{aggregate['b_positive_candidate_count']}` / `{aggregate['c_negative_candidate_count']}`",
        "",
        "## Window Table",
        "| window | candidates | recent filing | same-accession touch | directional touch | feature same-accession rows | feature directional rows | top failure reason |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, row in payload["by_window"].items():
        summary = row["candidate_summary"]
        coverage = row["feature_coverage"]
        top_reason = next(iter(summary["touch_failure_reason_counts"]), "")
        lines.append(
            "| {name} | {candidate_count} | {recent} | {same_accession} | {directional} | "
            "{feature_same_accession} | {feature_directional} | {top_reason} |".format(
                name=name,
                candidate_count=summary["candidate_count"],
                recent=summary["recent_filing_candidate_count"],
                same_accession=summary["recent_same_accession_candidate_count"],
                directional=summary["recent_directional_candidate_count"],
                feature_same_accession=coverage["same_accession_rows"],
                feature_directional=coverage["directional_rows"],
                top_reason=top_reason,
            )
        )
    lines.extend([
        "",
        "## Interpretation",
        (
            "The repaired same-accession Companyfacts rows exist in the SEC feature table, "
            "but none are inside the 20-trading-day lookback of persisted A/B entry candidates. "
            "The current B/C cohort failure is therefore a candidate-touch/source-coverage gap, "
            "not evidence that a looser classifier should be promoted."
        ),
        "",
        "## Production Impact",
        json.dumps(payload["production_impact"], indent=2),
        "",
        "## Next Action",
        payload["next_action"],
        "",
    ])
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> dict[str, Any]:
    ticket = _load_json(TICKET_JSON)
    ticket.update({
        "status": "observed_only",
        "completed_at": _utc_now_iso(),
        "result": "candidate_touch_data_gap",
        "decision": payload["decision"],
        "allowed_write_scope": [
            f"quant/experiments/exp_20260507_093_same_accession_candidate_touch_audit.py",
            f"data/experiments/{EXPERIMENT_ID}",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/non_ohlcv_data_audit/sec_same_accession_candidate_touch_{EXPERIMENT_ID}_20260507.md",
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "must_not_touch": [
            "quant/signal_engine.py",
            "quant/risk_engine.py",
            "quant/portfolio_engine.py",
        ],
        "locked_variables": [
            "OHLCV thresholds",
            "technical entries",
            "production signal path",
            "signal ranking",
            "risk sizing",
            "exits",
            "LLM prompts",
            "SEC event thresholds",
        ],
        "artifacts": payload["related_files"],
    })
    _write_json(TICKET_JSON, ticket)
    return ticket


def main() -> None:
    source_payload = _load_json(
        REPO_ROOT
        / "data"
        / "experiments"
        / SOURCE_EXPERIMENT_ID
        / "full_candidate_filing_shock_shadow.json"
    )
    by_window = OrderedDict()
    for window_name, window in WINDOWS.items():
        by_window[window_name] = _candidate_diagnostics_for_window(window_name, window)
    aggregate = _aggregate_summary(by_window)

    decision = "data_gap"
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "parity_test_added": False,
        "replay_only": True,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "production_signal_path_changed": False,
    }
    next_action = (
        "Do not loosen filing-shock classification yet. The next valid repair is a source/coverage "
        "step: collect same-day/same-accession earnings XBRL that actually touches A/B candidates, "
        "or add a PIT guidance/consensus source that can produce directional rows on candidate dates."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now_iso(),
        "status": "observed_only",
        "decision": decision,
        "lane": "alpha_discovery",
        "change_type": "same_accession_candidate_touch_diagnostic",
        "mechanism_family": "earnings_sec_filing_shock_event_confirmation_overlay",
        "hypothesis": (
            "Same-accession SEC Companyfacts may be absent from existing A/B candidate lookbacks; "
            "if so, filing-shock B/C cohort failure is a candidate-touch data gap rather than a "
            "classifier threshold problem."
        ),
        "single_causal_variable": "same_accession_companyfacts_candidate_touch_diagnostic",
        "non_ohlcv_data_source": (
            "Existing SEC filing features rebuilt from SEC submissions/text and selected Companyfacts, "
            "joined to exp-20260507-006 persisted A/B entry candidates."
        ),
        "date_range": {
            name: f"{window['start']} -> {window['end']}"
            for name, window in WINDOWS.items()
        },
        "historical_experiment_check": {
            "exp-20260507-031": (
                "Same-accession auto-discovery partially repaired feature rows "
                "(25 same_accession_facts, 18 directional rows) but B/C candidate cohorts stayed empty."
            ),
            "exp-20260507-006": (
                "Full candidate persistence made the current touch diagnostic possible; prior summary "
                "only showed B/C=0."
            ),
            "exp-20260507-003": (
                "Recent SEC breakout risk sizing failed; do not retry broad filing recency multipliers."
            ),
            "exp-20260504-014": (
                "Latest-prior Companyfacts was too stale for SEC reaction grading; this audit uses "
                "only same-accession touch, not stale background buckets."
            ),
        },
        "baseline_metrics": source_payload.get("baseline_metrics"),
        "source_shadow_field_availability": source_payload.get("field_availability"),
        "aggregate_summary": aggregate,
        "by_window": {
            name: {
                "feature_coverage": row["feature_coverage"],
                "candidate_summary": row["candidate_summary"],
                "sample_recent_without_same_accession": row["sample_recent_without_same_accession"],
                "sample_nearest_directional_misses": row["sample_nearest_directional_misses"],
            }
            for name, row in by_window.items()
        },
        "expected_value_score_delta": 0.0,
        "candidate_overlap_and_slot_value": {
            name: {
                "candidate_count": row["candidate_summary"]["candidate_count"],
                "entered_count": row["candidate_summary"]["entered_count"],
                "recent_same_accession_candidate_count": row["candidate_summary"]["recent_same_accession_candidate_count"],
                "recent_directional_candidate_count": row["candidate_summary"]["recent_directional_candidate_count"],
                "slot_same_accession_candidate_count": row["candidate_summary"]["slot_same_accession_candidate_count"],
                "slot_directional_candidate_count": row["candidate_summary"]["slot_directional_candidate_count"],
            }
            for name, row in by_window.items()
        },
        "production_impact": production_impact,
        "decision_rationale": (
            "The feature table contains same-accession directional rows, but none touch persisted "
            "A/B candidates inside the 20-trading-day filing lookback. This blocks B/C filing-shock "
            "alpha evidence and makes classifier loosening premature."
        ),
        "next_action": next_action,
        "related_files": [
            "quant/experiments/exp_20260507_093_same_accession_candidate_touch_audit.py",
            f"data/experiments/{EXPERIMENT_ID}/same_accession_candidate_touch_audit.json",
            f"docs/non_ohlcv_data_audit/sec_same_accession_candidate_touch_{EXPERIMENT_ID}_20260507.md",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            "docs/experiment_log.jsonl",
            "data/experiments/exp-20260507-006/full_candidate_filing_shock_shadow.json",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_audit_md(payload)
    ticket = _update_ticket(payload)
    _update_registry(ticket)
    _append_or_replace_jsonl(EXPERIMENT_LOG, {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "single_causal_variable": payload["single_causal_variable"],
        "non_ohlcv_data_source": payload["non_ohlcv_data_source"],
        "date_range": payload["date_range"],
        "aggregate_summary": payload["aggregate_summary"],
        "candidate_overlap_and_slot_value": payload["candidate_overlap_and_slot_value"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "production_impact": payload["production_impact"],
        "decision_rationale": payload["decision_rationale"],
        "next_action": payload["next_action"],
        "related_files": payload["related_files"],
    })
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "aggregate_summary": aggregate,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
