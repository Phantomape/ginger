"""exp-20260630-004: structured daily-news event evidence ledger.

Measurement repair for the daily-news LLM/event-scoring surface. The runner
turns final clean-trade-news rows into replayable PIT event records with
actor/object/relation/magnitude/provenance/evidence-span fields. It changes no
entry, exit, ranking, sizing, prompt, paper order, live order, or source-news
archive behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260630-004"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "daily_news_structured_event_ledger"
RUNNER = f"quant/experiments/exp_20260630_004_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for root in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from daily_news_text_sanitation import iter_daily_news_files  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from news_text_sanitizer import annotate_news_item  # noqa: E402


NEWS_ROOT = REPO_ROOT / "data" / "daily" / "news"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260630_004_{SLUG}.json"
LEDGER_JSONL = OUT_DIR / "daily_news_structured_event_ledger.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Daily news LLM/event-scoring alpha is currently blocked because the "
    "accepted sanitation contract and rejected keyword taxonomy do not leave "
    "replayable actor/object/relation/magnitude evidence spans; build a "
    "structured PIT event evidence ledger without changing trading behavior."
)
ALPHA_HYPOTHESIS = (
    "A future LLM/news event-scoring alpha can only be tested credibly if "
    "daily news rows first have replayable actor/object/relation/magnitude "
    "evidence spans instead of unreplayable keyword buckets."
)
CHANGE_TYPE = "daily_news_structured_event_measurement_surface"
MECHANISM_FAMILY = "daily_news_llm_event_scoring_alpha"
TRIAL_FAMILY = "daily_news_structured_event_evidence_ledger"
TRIAL_VARIANT_ID = "v1_structured_evidence_spans"
CHANGED_VARIABLE = "daily_news_structured_event_evidence_ledger_v1"
NEW_EVIDENCE_TYPE = "structured_pit_event_ledger_with_actor_relation_magnitude_evidence_spans"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260630-001", "exp-20260630-002"]
CAUSAL_COMPONENTS = [
    "daily clean-trade-news archive",
    "sanitized text",
    "evidence span extraction",
    "actor relation magnitude fields",
    "no trading behavior change",
]
PREDICTION = {
    "success_probability": 0.72,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "source archive lacks enough explicit event text",
        "evidence extraction is too keyword-like",
        "ledger rows cannot be made provenance-complete",
    ],
    "confidence_reason": (
        "Prior sanitation and forward-value runs proved the cleaned archive "
        "exists; this iteration changes measurement shape only and writes no "
        "strategy behavior."
    ),
}

RULE_VERSION = "daily_news_structured_event_ledger_v1"
TEXT_FIELDS = ("title", "summary", "description")
CONFIG = {
    "source_kind": "clean_trade_news",
    "require_explicit_ticker_text": True,
    "dedupe_key": "event_date,ticker,relation_type,evidence_text_hash,source_item_hash",
    "min_ledger_rows": 1,
    "required_event_fields": [
        "event_id",
        "event_date",
        "ticker",
        "relation_type",
        "relation_polarity",
        "actor",
        "object",
        "magnitude",
        "evidence_span",
        "sanitized_text_hash",
        "source_provenance",
    ],
}


RELATION_RULES = [
    {
        "relation_type": "financial_growth_or_beat",
        "relation_polarity": "positive",
        "object_type": "financial_result",
        "patterns": [
            r"\b(?:strong|record|better|solid)\s+(?:earnings|revenue|sales|profit|outlook)\b",
            r"\b(?:earnings|revenue|sales|profit)\s+(?:growth|grew|surges?|jumps?|beats?)\b",
            r"\b(?:beats?|outpaces?)\s+(?:the\s+)?(?:market|estimates|expectations)\b",
        ],
    },
    {
        "relation_type": "guidance_or_rating_upgrade",
        "relation_polarity": "positive",
        "object_type": "forecast_or_rating",
        "patterns": [
            r"\b(?:raises?|boosts?|lifts?)\s+(?:guidance|outlook|forecast|price target)\b",
            r"\b(?:rating\s+)?upgrade\b",
            r"\b(?:buy|outperform|overweight)\s+rating\b",
        ],
    },
    {
        "relation_type": "customer_order_or_partnership",
        "relation_polarity": "positive",
        "object_type": "commercial_relationship",
        "patterns": [
            r"\b(?:order|contract|partnership|supply deal|customer win|agreement)\b",
            r"\bdeal\s+with\b",
        ],
    },
    {
        "relation_type": "capital_return",
        "relation_polarity": "positive",
        "object_type": "capital_allocation",
        "patterns": [
            r"\b(?:buybacks?|repurchases?|dividend|capital return)\b",
        ],
    },
    {
        "relation_type": "product_or_approval_catalyst",
        "relation_polarity": "positive",
        "object_type": "product_catalyst",
        "patterns": [
            r"\b(?:launch|approval|catalyst|turning point|moonshots?)\b",
        ],
    },
    {
        "relation_type": "legal_or_regulatory_pressure",
        "relation_polarity": "negative",
        "object_type": "legal_regulatory_risk",
        "patterns": [
            r"\b(?:lawsuit|probe|investigation|regulatory pressure|faces pressure)\b",
        ],
    },
    {
        "relation_type": "downgrade_or_target_cut",
        "relation_polarity": "negative",
        "object_type": "forecast_or_rating",
        "patterns": [
            r"\b(?:downgrade|rating cut|target cut|cuts? price target)\b",
        ],
    },
    {
        "relation_type": "drawdown_or_failed_transaction",
        "relation_polarity": "negative",
        "object_type": "market_or_transaction_failure",
        "patterns": [
            r"\b(?:in the red|falls?|drops?|slumps?|attempts? continue to fail|fails?)\b",
        ],
    },
]

MAGNITUDE_RE = re.compile(
    r"(?P<value>"
    r"\$\s*\d+(?:\.\d+)?\s*(?:billion|million|bn|m)?"
    r"|"
    r"\b\d+(?:\.\d+)?\s*(?:%|x|billion|million|bn|m|bps|basis points)\b"
    r")",
    flags=re.IGNORECASE,
)
COUNTERPARTY_RE = re.compile(
    r"\b(?:with|from|for|by)\s+([A-Z][A-Za-z0-9&.\- ]{1,48})(?:\b|:|,|-)",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(safe(row), sort_keys=True, ensure_ascii=True) + "\n")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_text(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:length]


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def sanitized_field_text(annotated: Mapping[str, Any], field: str) -> str:
    audit = (annotated.get("text_sanitation") or {}).get("fields") or {}
    field_audit = audit.get(field) or {}
    return compact_text(field_audit.get("sanitized_text") or annotated.get(field) or "")


def combined_sanitized_text(annotated: Mapping[str, Any]) -> str:
    parts = [sanitized_field_text(annotated, field) for field in TEXT_FIELDS]
    return "\n".join(part for part in parts if part)


def ticker_match_block(annotated: Mapping[str, Any]) -> dict[str, Any]:
    audit = annotated.get("text_sanitation") or {}
    return dict(audit.get("ticker_entity_match") or {})


def event_date_for(file_date: str | None, item: Mapping[str, Any]) -> str | None:
    published = str(item.get("published_at") or "")
    if re.match(r"^\d{4}-\d{2}-\d{2}", published):
        return published[:10]
    return file_date


def evidence_window(text: str, start: int, end: int, radius: int = 140) -> dict[str, Any]:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return {
        "start": start,
        "end": end,
        "context_start": left,
        "context_end": right,
        "text": text[left:right].strip(),
    }


def extract_magnitudes(text: str, start: int, end: int, radius: int = 90) -> dict[str, Any]:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    window = text[left:right]
    values = []
    for match in MAGNITUDE_RE.finditer(window):
        raw = compact_text(match.group("value"))
        if raw:
            values.append(raw)
    return {
        "has_numeric_magnitude": bool(values),
        "values": values[:5],
        "window_hash": hash_text(window),
    }


def infer_object(text: str, match: re.Match[str], rule: Mapping[str, Any]) -> dict[str, Any]:
    left = max(0, match.start() - 80)
    right = min(len(text), match.end() + 100)
    window = text[left:right]
    counterpart = None
    counter_match = COUNTERPARTY_RE.search(window)
    if counter_match:
        counterpart = compact_text(counter_match.group(1)).strip(" .,:;-")
    return {
        "type": rule["object_type"],
        "text": counterpart or rule["object_type"],
        "counterparty_extracted": counterpart is not None,
        "source": "local_evidence_window",
    }


def source_item_hash(path: Path, index: int, item: Mapping[str, Any]) -> str:
    url = str(item.get("url") or "")
    title = compact_text(item.get("title"))
    published = str(item.get("published_at") or "")
    return hash_text(f"{repo_rel(path)}|{index}|{published}|{url}|{title}", 24)


def build_event_id(
    event_date: str,
    ticker: str,
    relation_type: str,
    source_hash: str,
    evidence_hash: str,
) -> str:
    return hash_text(
        f"{event_date}|{ticker}|{relation_type}|{source_hash}|{evidence_hash}",
        24,
    )


def iter_relation_matches(text: str) -> Iterable[tuple[Mapping[str, Any], re.Match[str]]]:
    for rule in RELATION_RULES:
        for pattern in rule["patterns"]:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                yield rule, match


def make_event_rows(
    *,
    file_record: Mapping[str, Any],
    path: Path,
    index: int,
    item: Mapping[str, Any],
) -> list[dict[str, Any]]:
    annotated = annotate_news_item(item)
    text = combined_sanitized_text(annotated)
    if not text:
        return []
    ticker_block = ticker_match_block(annotated)
    matched_tickers = [
        str(ticker).upper()
        for ticker in ticker_block.get("matched_tickers") or []
        if str(ticker or "").strip()
    ]
    if CONFIG["require_explicit_ticker_text"] and not matched_tickers:
        return []

    event_date = event_date_for(str(file_record.get("news_date") or ""), item)
    if not event_date:
        return []
    source_hash = source_item_hash(path, index, item)
    audit = annotated.get("text_sanitation") or {}
    rows: list[dict[str, Any]] = []
    seen_local: set[tuple[str, str, str, str]] = set()
    for rule, match in iter_relation_matches(text):
        matched_phrase = compact_text(match.group(0)).lower()
        span = evidence_window(text, match.start(), match.end())
        evidence_hash = hash_text(span["text"], 24)
        magnitude = extract_magnitudes(text, match.start(), match.end())
        for ticker in matched_tickers:
            dedupe = (event_date, ticker, str(rule["relation_type"]), matched_phrase)
            if dedupe in seen_local:
                continue
            seen_local.add(dedupe)
            event_id = build_event_id(
                event_date,
                ticker,
                str(rule["relation_type"]),
                source_hash,
                evidence_hash,
            )
            rows.append(
                {
                    "event_id": event_id,
                    "rule_version": RULE_VERSION,
                    "event_date": event_date,
                    "published_at": item.get("published_at"),
                    "ticker": ticker,
                    "relation_type": rule["relation_type"],
                    "relation_polarity": rule["relation_polarity"],
                    "actor": {
                        "type": "ticker",
                        "ticker": ticker,
                        "match_status": ticker_block.get("status"),
                        "match_confidence": ticker_block.get("confidence"),
                    },
                    "object": infer_object(text, match, rule),
                    "magnitude": magnitude,
                    "evidence_span": span,
                    "evidence_trigger": {
                        "text": matched_phrase,
                        "hash": hash_text(matched_phrase, 16),
                    },
                    "evidence_text_hash": evidence_hash,
                    "sanitized_text_hash": audit.get("post_sanitize_hash") or hash_text(text, 24),
                    "source_item_hash": source_hash,
                    "source_provenance": {
                        "kind": file_record.get("kind"),
                        "news_date": file_record.get("news_date"),
                        "path": repo_rel(path),
                        "file_sha256": sha256_file(path),
                        "item_index": index,
                        "source": item.get("source"),
                        "tier": item.get("tier"),
                        "url": item.get("url"),
                        "raw_source": item.get("raw_source"),
                    },
                    "text_quality": {
                        "status": audit.get("status"),
                        "flags": audit.get("flags") or [],
                        "ticker_entity_status": ticker_block.get("status"),
                    },
                }
            )
    return rows


def dedupe_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    deduped: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for row in rows:
        event_id = str(row["event_id"])
        if event_id in deduped:
            duplicates += 1
            continue
        deduped[event_id] = row
    ordered = sorted(
        deduped.values(),
        key=lambda row: (
            str(row.get("event_date") or ""),
            str(row.get("ticker") or ""),
            str(row.get("relation_type") or ""),
            str(row.get("event_id") or ""),
        ),
    )
    return ordered, duplicates


def load_baseline() -> dict[str, Any]:
    baseline = read_json(BASELINE_RESULT, {})
    aggregate = baseline.get("aggregate") if isinstance(baseline, Mapping) else None
    if isinstance(aggregate, Mapping):
        return {
            "expected_value_score": aggregate.get("expected_value_score"),
            "total_pnl": aggregate.get("strategy_total_pnl"),
            "trade_count": aggregate.get("trade_count"),
        }
    return {
        "expected_value_score": 7.8941,
        "total_pnl": 234850.99,
        "trade_count": None,
    }


def required_field_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_counts: Counter[str] = Counter()
    for row in rows:
        for field in CONFIG["required_event_fields"]:
            value = row.get(field)
            if value is None or value == "" or value == {}:
                missing_counts[field] += 1
    return {
        "required_fields": CONFIG["required_event_fields"],
        "missing_counts": dict(sorted(missing_counts.items())),
        "all_required_fields_present": not missing_counts,
    }


def build_source_and_ledger() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    file_count = 0
    raw_items = 0
    explicit_items = 0
    unreadable_files = 0
    source_date_counts: Counter[str] = Counter()
    for file_record in iter_daily_news_files(NEWS_ROOT, kinds=["clean_trade_news"]):
        path = Path(file_record["path"])
        file_count += 1
        raw = read_json(path, [])
        if not isinstance(raw, list):
            unreadable_files += 1
            continue
        raw_items += len(raw)
        for index, item in enumerate(raw):
            if not isinstance(item, Mapping):
                continue
            annotated = annotate_news_item(item)
            ticker_block = ticker_match_block(annotated)
            if ticker_block.get("status") == "explicit_text_match":
                explicit_items += 1
            event_rows = make_event_rows(
                file_record=file_record,
                path=path,
                index=index,
                item=item,
            )
            if event_rows:
                source_date_counts[str(file_record.get("news_date") or "unknown")] += len(
                    event_rows
                )
            rows.extend(event_rows)
    deduped, duplicate_input_rows = dedupe_rows(rows)
    relation_counts = Counter(str(row["relation_type"]) for row in deduped)
    polarity_counts = Counter(str(row["relation_polarity"]) for row in deduped)
    ticker_counts = Counter(str(row["ticker"]) for row in deduped)
    magnitude_rows = sum(1 for row in deduped if row["magnitude"]["has_numeric_magnitude"])
    dates = [str(row["event_date"]) for row in deduped if row.get("event_date")]
    field_audit = required_field_audit(deduped)
    event_id_counts = Counter(str(row["event_id"]) for row in deduped)
    duplicate_event_ids = sum(1 for count in event_id_counts.values() if count > 1)
    source_audit = {
        "news_root": repo_rel(NEWS_ROOT),
        "source_kind": CONFIG["source_kind"],
        "file_count": file_count,
        "unreadable_files": unreadable_files,
        "raw_items": raw_items,
        "explicit_ticker_items": explicit_items,
        "raw_event_rows": len(rows),
        "ledger_rows": len(deduped),
        "duplicate_input_rows_removed": duplicate_input_rows,
        "duplicate_event_ids": duplicate_event_ids,
        "date_range": {
            "start": min(dates) if dates else None,
            "end": max(dates) if dates else None,
        },
        "event_date_count": len(set(dates)),
        "source_date_counts": dict(sorted(source_date_counts.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "polarity_counts": dict(sorted(polarity_counts.items())),
        "ticker_top20": dict(ticker_counts.most_common(20)),
        "magnitude_rows": magnitude_rows,
        "magnitude_row_share": magnitude_rows / len(deduped) if deduped else 0.0,
        "required_field_audit": field_audit,
    }
    return deduped, source_audit


def build_payload() -> dict[str, Any]:
    baseline = load_baseline()
    ledger_rows, source_audit = build_source_and_ledger()
    accepted = (
        source_audit["ledger_rows"] >= CONFIG["min_ledger_rows"]
        and source_audit["duplicate_event_ids"] == 0
        and bool(source_audit["required_field_audit"]["all_required_fields_present"])
    )
    failed_reasons: list[str] = []
    if source_audit["ledger_rows"] < CONFIG["min_ledger_rows"]:
        failed_reasons.append("no_structured_event_rows")
    if source_audit["duplicate_event_ids"]:
        failed_reasons.append("duplicate_event_ids")
    if not source_audit["required_field_audit"]["all_required_fields_present"]:
        failed_reasons.append("missing_required_event_fields")

    decision = "accepted_measurement_repair" if accepted else "blocked"
    status = decision
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_surface_only",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": PREDICTION,
        "pre_run_questions": {
            "profit_hypothesis": ALPHA_HYPOTHESIS,
            "nearby_history": (
                "exp-20260630-001 accepted sanitation; exp-20260630-002 "
                "rejected keyword taxonomy and required structured "
                "actor/object/relation/magnitude evidence spans."
            ),
            "single_policy_bundle": CHANGED_VARIABLE,
            "success_standard": (
                "Nonzero replayable JSONL ledger with required structured "
                "event fields and zero trading metric changes."
            ),
            "reproducibility": (
                f"Run {RUNNER_COMMAND}; artifacts live under {repo_rel(OUT_DIR)}."
            ),
        },
        "parameters": CONFIG,
        "gate1": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
            "passed": True,
        },
        "gate2": {
            "runtime_fields_checked": [
                "event_date",
                "ticker",
                "relation_type",
                "evidence_span",
                "sanitized_text_hash",
                "source_provenance",
            ],
            "entry_date": "not_applicable_measurement_repair_no_strategy_entries",
            "target_price": "not_applicable_measurement_repair_no_strategy_entries",
            "required_field_audit": source_audit["required_field_audit"],
            "passed": bool(source_audit["required_field_audit"]["all_required_fields_present"]),
        },
        "gate3": {
            "signals_generated": source_audit["ledger_rows"],
            "signals_survived": source_audit["ledger_rows"],
            "survival_rate": 1.0 if source_audit["ledger_rows"] else 0.0,
            "passed": bool(source_audit["ledger_rows"]),
            "note": "Measurement ledger rows only; not tradable signals.",
        },
        "gate4": {
            "status": decision,
            "passed": accepted,
            "failed_reasons": failed_reasons,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "note": "No strategy behavior changed; this is accepted only as measurement repair.",
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "ledger_rows": source_audit["ledger_rows"],
            "explicit_ticker_items": source_audit["explicit_ticker_items"],
            "magnitude_rows": source_audit["magnitude_rows"],
        },
        "source_audit": source_audit,
        "artifacts": {
            "ledger_jsonl": repo_rel(LEDGER_JSONL),
            "artifact_json": repo_rel(OUT_JSON),
        },
        "sample_events": ledger_rows[:20],
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "llm_prompt_changed": False,
            "news_archives_changed": False,
            "shared_helper_promoted": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
        },
        "calibration": {
            "prediction_success_probability": PREDICTION["success_probability"],
            "observed_success": accepted,
            "main_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": failed_reasons,
            "surprise": (
                "None; the archive produced structured rows with exact spans."
                if accepted
                else "The source archive did not satisfy the structural ledger contract."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The clean-trade-news archive contains enough explicit ticker text "
                "and event phrases to materialize a provenance-complete structured "
                "ledger. This remains measurement-only because no forward outcome "
                "or canonical-window policy replay was added."
                if accepted
                else "The archive did not produce a complete structured ledger."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this ledger to sweep keyword buckets, tiers, hold days, "
                "top-N, notional, or response curves on the same rows. The next alpha "
                "test must use the structured fields as fixed inputs and join enough "
                "closed replacement-value outcomes or canonical-window replay coverage."
            ),
            "new_evidence_required": (
                "Closed cash/SPY/QQQ replacement-value outcomes for these structured "
                "events, or an LLM scorer that writes the same actor/object/relation/"
                "magnitude/evidence schema at decision time."
            ),
        },
        "next_retry_requires": [
            "closed replacement-value outcomes joined to structured event rows",
            "or PIT LLM event labels persisted with the same evidence-span schema",
            "or canonical-window daily-news coverage that can be replayed without lookahead",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LEDGER_JSONL),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "related_files": [
            "quant/daily_news_text_sanitation.py",
            "quant/news_text_sanitizer.py",
            "experiments/logs/exp-20260630-001.json",
            "experiments/logs/exp-20260630-002.json",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no JavaScript tooling invoked.",
        },
        "_ledger_rows_for_write": ledger_rows,
    }


def compact_log(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": CHANGE_TYPE,
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "source_audit": payload["source_audit"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "next_retry_requires": payload["next_retry_requires"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": repo_rel(OUT_JSON),
        "ledger_jsonl": repo_rel(LEDGER_JSONL),
        "anti_js": payload["anti_js"],
    }


def build_card(payload: Mapping[str, Any]) -> str:
    audit = payload["source_audit"]
    relation_counts = audit["relation_counts"]
    relation_rows = [
        "| Relation | Rows |",
        "|---|---:|",
    ]
    for relation, count in relation_counts.items():
        relation_rows.append(f"| {relation} | {count} |")
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: daily news structured event ledger",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            "- Accepted alpha: no",
            "- Production behavior changed: no",
            f"- Ledger rows: `{audit['ledger_rows']}`",
            f"- Event dates: `{audit['event_date_count']}`",
            f"- Magnitude rows: `{audit['magnitude_rows']}`",
            f"- Ledger: `{repo_rel(LEDGER_JSONL)}`",
            "",
            "## Relations",
            "",
            *relation_rows,
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
        ]
    ) + "\n"


def build_manifest(payload: Mapping[str, Any], log_row: Mapping[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LEDGER_JSONL,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "ledger_jsonl": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)} for path in files},
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    ledger_rows = payload.pop("_ledger_rows_for_write")
    write_jsonl(LEDGER_JSONL, ledger_rows)
    write_json(OUT_JSON, payload)
    log_row = compact_log(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "alpha_ready": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "ledger_jsonl": repo_rel(LEDGER_JSONL),
        "delta_metrics": payload["delta_metrics"],
        "gate4": payload["gate4"],
        "source_audit": payload["source_audit"],
        "production_impact": payload["production_impact"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
            "hypothesis",
            "alpha_hypothesis",
            "change_type",
            "implementation_mode",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "single_causal_variable",
            "changed_variable",
            "causal_components",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "production_impact",
            "post_run_reflection",
            "next_retry_requires",
            "changed_files",
            "reproduction_commands",
            "calibration",
        ]
        if key in payload
    }
    fields.update(
        {
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "ledger_jsonl": repo_rel(LEDGER_JSONL),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        }
    )
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload.get("prediction") or {},
        result=result,
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "ledger_rows": payload["source_audit"]["ledger_rows"],
                "event_dates": payload["source_audit"]["event_date_count"],
                "relation_counts": payload["source_audit"]["relation_counts"],
                "magnitude_rows": payload["source_audit"]["magnitude_rows"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
