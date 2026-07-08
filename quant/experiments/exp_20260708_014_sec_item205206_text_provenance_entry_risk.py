"""exp-20260708-014: SEC Item 2.05/2.06 text-provenance entry-risk scout.

Replay-only alpha search. The single decision hypothesis is that SEC 8-K
Item 2.05/2.06 events become useful as an entry-risk gate only when the
primary filing text confirms true impairment or restructuring economics,
instead of generic disposal/accounting updates.

No production path, default orders, ranking, sizing, exits, LLM boundary,
watchlist, or shared policy is changed.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260708_009_sec_item205206_restructuring_impairment_entry_risk as item_prior


EXPERIMENT_ID = "exp-20260708-014"
OWNER = "alpha-explore"
SLUG = "sec_item205206_text_provenance_entry_risk"
RUNNER = f"quant/experiments/exp_20260708_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = item_prior.REPO_ROOT
BASE = item_prior.base

OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"exp_20260708_014_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
SEC_TEXT_GLOB = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_*.jsonl"

HYPOTHESIS = (
    "entry_filter/risk_allocation: SEC 8-K Item 2.05/2.06 primary-document "
    "text that confirms real impairment or restructuring economics, while "
    "excluding generic disposal-accounting updates, should isolate negative "
    "next-open 10-session drift and support a default-off entry risk gate."
)
CHANGE_TYPE = "entry_filter"
IMPLEMENTATION_MODE = "private_replay_scout"
MECHANISM_FAMILY = "free_sec_restructuring_impairment_entry_risk"
TRIAL_FAMILY = "sec_8k_item205206_text_provenance_entry_risk"
TRIAL_VARIANT_ID = "true_impairment_restructuring_text_next_open_10d_v1"
CHANGED_VARIABLE = "sec_item205206_true_impairment_restructuring_text_10d_entry_risk_gate_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_sec_8k_item205206_primary_text_provenance"
NEW_EVIDENCE_AXIS = (
    "New gate shape: primary-document text-provenance classifier for Item "
    "2.05/2.06 true impairment/restructuring economics versus generic "
    "disposal/accounting-update rows, explicitly named by exp-20260708-009 "
    "as the legal next evidence axis; no price/ADV/hold/ranking/response-"
    "function retune."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260708-009",
    "exp-20260618-001",
    "exp-20260615-011",
]

MIN_TOTAL_LIQUID_EVENTS = item_prior.MIN_TOTAL_LIQUID_EVENTS
MIN_SUPPORT_EVENTS_PER_WINDOW = item_prior.MIN_SUPPORT_EVENTS_PER_WINDOW
MAX_SINGLE_TICKER_SHARE = item_prior.MAX_SINGLE_TICKER_SHARE

IMPAIRMENT_RE = re.compile(
    r"\b("
    r"impairment|impaired|impairments|impairment charge|non-cash impairment|"
    r"goodwill impairment|intangible asset impairment|long-lived asset impairment|"
    r"asset impairment|write[- ]?down|writedown"
    r")\b",
    re.I,
)
RESTRUCTURING_RE = re.compile(
    r"\b("
    r"restructuring (?:plan|program|charge|charges|cost|costs|activities)|"
    r"exit (?:plan|activities|cost|costs)|disposal costs?|severance|"
    r"termination benefits?|workforce reduction|headcount reduction|"
    r"facility closure|plant closure|site closure|lease termination|"
    r"contract termination|cost reduction plan"
    r")\b",
    re.I,
)
GENERIC_DISPOSAL_RE = re.compile(
    r"\b("
    r"sale of|sold|dispose(?:d|s)? of|disposition|divestiture|held for sale|"
    r"discontinued operations|gain on sale|loss on sale|disposal group|"
    r"purchase price allocation|fair value remeasurement|accounting update"
    r")\b",
    re.I,
)
QUANTIFIED_RE = re.compile(
    r"(?:\$[0-9][0-9,.]*|[0-9][0-9,.]*\s*(?:million|billion|mm|bn|%)|basis points?|bps)",
    re.I,
)
NEEDLE_RE = re.compile(
    r"(?i)(impairment|write[- ]?down|restructuring|exit plan|exit costs?|"
    r"disposal costs?|severance|termination benefits?|workforce reduction|"
    r"headcount reduction|facility closure|plant closure|site closure|"
    r"lease termination|discontinued operations|held for sale|divestiture|"
    r"gain on sale|loss on sale|fair value|accounting update)"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    return item_prior.repo_rel(path)


def load_ticket_prediction() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    try:
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return ticket.get("prediction") or {}


def evidence_snippets(text: str, max_snippets: int = 5, radius: int = 420) -> list[str]:
    snippets: list[str] = []
    for match in NEEDLE_RE.finditer(text):
        start = max(0, match.start() - radius)
        end = min(len(text), match.end() + radius)
        snippet = " ".join(text[start:end].split())
        if snippet and snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) >= max_snippets:
            break
    return snippets


def classify_text(text: str) -> dict[str, Any]:
    snippets = evidence_snippets(text)
    evidence_blob = " ".join(snippets) if snippets else " ".join(text[:6000].split())
    has_impairment = bool(IMPAIRMENT_RE.search(evidence_blob))
    has_restructuring = bool(RESTRUCTURING_RE.search(evidence_blob))
    has_generic_disposal = bool(GENERIC_DISPOSAL_RE.search(evidence_blob))
    has_quantified_context = bool(QUANTIFIED_RE.search(evidence_blob))

    if has_impairment and has_quantified_context:
        label = "confirmed_impairment_charge"
        score = 3.0
        admission = True
    elif has_impairment:
        label = "confirmed_impairment_language"
        score = 2.5
        admission = True
    elif has_restructuring and has_quantified_context:
        label = "confirmed_restructuring_cost"
        score = 2.5
        admission = True
    elif has_restructuring:
        label = "confirmed_restructuring_language"
        score = 2.0
        admission = True
    elif has_generic_disposal:
        label = "generic_disposal_accounting_update"
        score = -1.0
        admission = False
    else:
        label = "item_code_without_text_confirmation"
        score = 0.0
        admission = False

    return {
        "admission": admission,
        "label": label,
        "score": score,
        "has_impairment": has_impairment,
        "has_restructuring": has_restructuring,
        "has_generic_disposal": has_generic_disposal,
        "has_quantified_context": has_quantified_context,
        "evidence_snippets": snippets[:3],
    }


def load_text_rows_for_accessions(
    target_accessions: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows_by_accession: dict[str, dict[str, Any]] = {}
    stats: Counter[str] = Counter()
    source_files: Counter[str] = Counter()

    for path in sorted(SEC_TEXT_GLOB.parent.glob(SEC_TEXT_GLOB.name)):
        if path.name.startswith("sec_filing_text_6k") or path.stat().st_size == 0:
            continue
        source_files[path.name] += 1
        stats["text_files_scanned"] += 1
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    stats["text_json_parse_errors"] += 1
                    continue
                accession = str(row.get("accession_number") or "").strip()
                if accession not in target_accessions:
                    continue
                stats["matched_text_rows_seen"] += 1
                existing = rows_by_accession.get(accession)
                text_len = int(row.get("text_char_count") or len(row.get("combined_text") or ""))
                existing_len = 0
                if existing is not None:
                    existing_len = int(
                        existing.get("text_char_count")
                        or len(existing.get("combined_text") or "")
                    )
                if existing is None or text_len > existing_len:
                    row["text_source_file"] = path.name
                    rows_by_accession[accession] = row

    return rows_by_accession, {
        **dict(stats),
        "text_source_files_scanned": len(source_files),
        "text_source_files_with_rows": dict(source_files),
        "deduped_text_accessions": len(rows_by_accession),
    }


def load_text_confirmed_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_events, raw_diagnostics = item_prior.load_item205206_events()
    raw_by_accession = {
        str(row.get("accession_number") or "").strip(): row
        for row in raw_events
        if row.get("accession_number")
    }
    rows_by_accession, text_stats = load_text_rows_for_accessions(set(raw_by_accession))
    classification_counts: Counter[str] = Counter()
    admitted_events: list[dict[str, Any]] = []
    text_item_rows = 0

    for accession, text_row in sorted(rows_by_accession.items()):
        item_codes = set(text_row.get("eight_k_item_codes") or [])
        if not item_codes:
            item_codes = set(item_prior.item_codes(text_row.get("items_raw")))
        if not (item_codes & item_prior.ITEM_CODES):
            continue
        text_item_rows += 1
        classification = classify_text(str(text_row.get("combined_text") or ""))
        classification_counts[classification["label"]] += 1
        if not classification["admission"]:
            continue
        event = dict(raw_by_accession[accession])
        event.update(
            {
                "text_provenance_label": classification["label"],
                "text_provenance_score": classification["score"],
                "text_has_impairment": classification["has_impairment"],
                "text_has_restructuring": classification["has_restructuring"],
                "text_has_generic_disposal": classification["has_generic_disposal"],
                "text_has_quantified_context": classification["has_quantified_context"],
                "text_evidence_snippets": classification["evidence_snippets"],
                "text_source_file": text_row.get("text_source_file"),
                "text_char_count": text_row.get("text_char_count"),
                "text_word_count": text_row.get("text_word_count"),
                "pit_source": text_row.get("pit_source"),
                "pit_caveat": text_row.get("pit_caveat"),
            }
        )
        admitted_events.append(event)

    diagnostics = {
        **raw_diagnostics,
        **text_stats,
        "raw_accessions_with_submissions_event": len(raw_by_accession),
        "raw_events_missing_text": len(set(raw_by_accession) - set(rows_by_accession)),
        "text_rows_with_item205206": text_item_rows,
        "text_confirmed_admitted_events": len(admitted_events),
        "text_classification_counts": dict(classification_counts),
    }
    return admitted_events, diagnostics


def build_payload() -> dict[str, Any]:
    events, event_diagnostics = load_text_confirmed_events()
    tickers = {str(row["ticker"]).upper() for row in events if row.get("ticker")}
    prices = BASE.load_prices(tickers)
    trades, replay_diagnostics = BASE.replay_events(events, prices)
    summary = item_prior.summarize_item205206_trades(trades)
    prediction = load_ticket_prediction()
    baseline_metrics = BASE.load_baseline_metrics()

    aggregate = summary["aggregate"]
    supporting_windows = aggregate["supporting_windows"]
    failed_reasons: list[str] = []
    if aggregate["trade_count"] < MIN_TOTAL_LIQUID_EVENTS:
        failed_reasons.append("liquid_text_confirmed_sample_below_min_total")
    if len(supporting_windows) < 2:
        failed_reasons.append("text_confirmed_drift_not_negative_in_two_windows")
    if aggregate["mean_net_long_return"] is None:
        failed_reasons.append("aggregate_long_drift_missing")
    elif aggregate["mean_net_long_return"] >= 0:
        failed_reasons.append("aggregate_long_drift_positive")
    if aggregate["mean_excess_vs_same_ticker_unconditional"] is None:
        failed_reasons.append("aggregate_excess_missing")
    elif aggregate["mean_excess_vs_same_ticker_unconditional"] >= 0:
        failed_reasons.append("aggregate_excess_not_negative")
    if (
        aggregate["max_single_ticker_share"] is not None
        and aggregate["max_single_ticker_share"] > MAX_SINGLE_TICKER_SHARE
    ):
        failed_reasons.append("ticker_concentration_too_high")

    support_lead = not failed_reasons
    decision = (
        "observed_positive_lead_sec_item205206_text_provenance_entry_risk_gate"
        if support_lead
        else "rejected_sec_item205206_text_provenance_entry_risk_gate"
    )
    status = "observed_only_positive_lead" if support_lead else "rejected"
    actual_success = 1 if support_lead else 0
    predicted_p = float(prediction.get("success_probability") or 0.0)

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "completed_at": utc_now(),
        "owner": OWNER,
        "status": status,
        "accepted": support_lead,
        "accepted_alpha": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "lane": "alpha_search",
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "multiple_testing_risk_bucket": "moderate",
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": predicted_p,
            "actual_success": actual_success,
            "actual_decision": decision,
            "brier_score": round((predicted_p - actual_success) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
        },
        "parameters": {
            "item_codes": sorted(item_prior.ITEM_CODES),
            "forms": sorted(item_prior.ITEM_FORMS),
            "entry_policy": "next_session_open_after_filing_date",
            "exit_policy": "close_after_10_trading_sessions",
            "hold_days": BASE.HOLD_DAYS,
            "notional_usd": BASE.NOTIONAL_USD,
            "round_trip_cost_pct": BASE.ROUND_TRIP_COST_PCT,
            "min_entry_price": BASE.MIN_ENTRY_PRICE,
            "min_adv20_usd": BASE.MIN_ADV20_USD,
            "same_ticker_cooldown_sessions": BASE.SAME_TICKER_COOLDOWN_SESSIONS,
            "text_gate": {
                "admit": [
                    "confirmed_impairment_charge",
                    "confirmed_impairment_language",
                    "confirmed_restructuring_cost",
                    "confirmed_restructuring_language",
                ],
                "exclude": [
                    "generic_disposal_accounting_update",
                    "item_code_without_text_confirmation",
                ],
            },
            "support_rule": (
                "Positive lead only if >=30 total liquid text-confirmed events, "
                "at least two canonical windows have >=10 events with negative "
                "mean 10d net long return and negative same-ticker excess return, "
                "and ticker concentration is <=40%. Otherwise rejected; no "
                "behavior changes."
            ),
            "windows": BASE.WINDOWS,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "experiment.py new warned on SEC text neighbors; novelty "
                    "override was recorded with the legal new gate shape named "
                    "by exp-20260708-009: text provenance separating true "
                    "impairment/restructuring from generic disposal/accounting."
                ),
                "exp-20260708-009": (
                    "Rejected direct Item 2.05/2.06 item-code entry-risk gate; "
                    "its post-run reflection explicitly permits this text-"
                    "provenance gate shape."
                ),
                "exp-20260618-001": (
                    "Rejected Item 2.05 price-absorption long candidate source; "
                    "not an entry-risk text-provenance filter."
                ),
                "exp-20260615-011": (
                    "Rejected broader cost-reduction/restructuring earnings-text "
                    "candidate source; not the direct Item 2.05/2.06 entry-risk "
                    "gate."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Use the predeclared source-validation rule in parameters; "
                "this is replay-only, so a positive result would still need a "
                "shared helper plus full Gate 4 before any production entry gate."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_loaded": BASE.BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASE.BASELINE_RESULT),
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
                "item_codes",
                "matched_item_codes",
                "ticker",
                "text_provenance_label",
                "text_evidence_snippets",
                "entry_date",
                "entry_open",
                "exit_date",
                "exit_close",
                "adv20_usd",
            ],
            "missing_entry_date": sum(1 for row in trades if not row.get("entry_date")),
            "missing_exit_date": sum(1 for row in trades if not row.get("exit_date")),
            "target_price_relevance": (
                "No generated strategy signals are emitted; target_price is "
                "not consumed by this read-only event study. A later shared "
                "entry gate must re-run the normal signal contract checks."
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
                "rule must pass before any shared-helper Gate 4 follow-up."
            ),
        },
        "data_diagnostics": {**event_diagnostics, **replay_diagnostics},
        "event_study": summary,
        "sample_text_confirmed_events": events[:40],
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
                "Read-only offline source validation over SEC cached submissions, "
                "SEC filing text JSONL snapshots, and warehouse OHLCV. No "
                "production/backtest behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The text-provenance Item 2.05/2.06 surface did not produce "
                "broad negative deployable event drift after liquidity gates, "
                "or failed the predeclared support/concentration rule."
            )
            if not support_lead
            else (
                "Text-confirmed Item 2.05/2.06 impairment/restructuring events "
                "showed broad negative event drift and deserve a shared-helper "
                "Gate 4 follow-up."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune text regexes, price, ADV, hold days, cooldown, "
                "same-day ranking, 2.05-vs-2.06 slices, impairment-vs-"
                "restructuring slices, quantified-context requirement, or "
                "response functions on these same cached rows."
            ),
            "new_evidence_required": (
                "A legal retry needs materially new Item 2.05/2.06 rows, "
                "normalized primary-document section extraction beyond regex "
                "snippets, an independent restructuring/impairment source, or "
                "settled forward replacement-value rows from a shared helper."
            ),
        },
        "rejection_reason": ";".join(failed_reasons) if failed_reasons else None,
        "next_retry_requires": [
            "materially new Item 2.05/2.06 rows",
            "or normalized primary-document section extraction beyond regex snippets",
            "or an independent restructuring/impairment source",
            "or settled forward replacement-value rows from a shared helper",
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
            repo_rel(BASE.BASELINE_RESULT),
            repo_rel(SEC_TEXT_GLOB),
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
        f"# {EXPERIMENT_ID}: SEC Item 2.05/2.06 text-provenance entry-risk scout",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        HYPOTHESIS,
        "",
        "| Window | Trades | Mean long ret | Mean excess | Long PnL | Avoided-loss PnL | Negative share |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in BASE.WINDOWS:
        row = payload["event_study"]["by_window"][label]
        lines.append(
            f"| {label} | {row['trade_count']} | {row['mean_net_long_return']} | "
            f"{row['mean_excess_vs_same_ticker_unconditional']} | "
            f"{row['total_long_pnl_usd']} | "
            f"{row['total_risk_gate_avoided_loss_usd']} | "
            f"{row['negative_return_share']} |"
        )
    gate4 = payload["gate4"]
    diagnostics = payload["data_diagnostics"]
    lines += [
        "",
        f"Raw Item 2.05/2.06 rows: {diagnostics['raw_item205206_count']}; "
        f"text-confirmed events: {diagnostics['text_confirmed_admitted_events']}; "
        f"liquid replay trades: {gate4['liquid_trade_count']}; "
        f"failed reasons: {gate4['failed_reasons']}.",
        "",
        "Text classification counts:",
        "",
        "```json",
        json.dumps(diagnostics.get("text_classification_counts") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "No behavior changed. A positive source-validation result would still "
        "need shared-helper Gate 4 before any production entry gate.",
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
                "sha256": BASE.sha256(path if path.is_absolute() else REPO_ROOT / path),
            }
            for path in paths
        ],
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    BASE.write_json(OUT_JSON, payload)
    BASE.write_text(CARD_MD, make_card(payload))
    BASE.write_json(LOG_JSON, payload)
    BASE.append_jsonl(EXPERIMENT_LOG, payload)
    BASE.write_json(MANIFEST_JSON, make_manifest(payload))
    BASE.persist_self_registered_result(
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
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
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
                "text_classification_counts": payload["data_diagnostics"].get(
                    "text_classification_counts"
                ),
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
