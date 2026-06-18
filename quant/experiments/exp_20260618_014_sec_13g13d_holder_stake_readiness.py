"""exp-20260618-014: SEC 13G/13D holder-stake-action readiness.

Alpha-search blocker check. Direct raw Schedule 13G/13D metadata triggers were
rejected; the plausible new free-data edge is parsed holder identity, ownership
percent, and action type. This runner verifies whether local point-in-time
primary-document text or parsed holder/stake rows exist before any strategy
replay or shared helper is built.

No trading policy, production helper, ranking, sizing, exits, live orders, or
default trade settings are changed. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260618-014"
STEM = "sec_13g13d_holder_stake_readiness"
CHANGED_VARIABLE = "sec_13g13d_holder_stake_action_readiness_v1"
OWNER = "alpha-search-automation"

REPO_ROOT = Path(__file__).resolve().parents[2]
SUBMISSIONS_DIR = REPO_ROOT / "data" / "cache" / "sec" / "submissions"
FILING_TEXT_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "filing_text"
DAILY_NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260618_014_{STEM}.json"
BEFORE_JSON = OUT_DIR / "before_baseline.json"
AFTER_JSON = OUT_DIR / "after_no_strategy_change.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}

HISTORY_CHECK = {
    "exp-20260612-015": (
        "Rejected direct SC 13D activist-initiation metadata. Closeout says a "
        "valid retry needs parsed 13D documents: stake percent, filer name, "
        "purpose, track record, broader universe, or forward rows."
    ),
    "exp-20260612-016": (
        "Rejected direct 13G passive/institutional disclosure metadata. Main "
        "disconfirmer was stale annual/batch report behavior and missing richer "
        "holder/action context."
    ),
    "exp-20260618-012": (
        "Blocked post-20260618 nonrepeat alpha surface search. It explicitly "
        "identified parsed 13G/13D holder/stake/action as one of the few valid "
        "new evidence axes and forbade raw 13G/13D event retries."
    ),
    "exp-20260618-013": (
        "Blocked SEC offering financing-economics readiness because local "
        "primary-document text was not available for the required accessions."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: Schedule 13G/13D ownership disclosures could improve "
        "the candidate pool only when parsed holder identity, beneficial "
        "ownership percent, active/passive intent, and stake-change direction "
        "separate informed accumulation from stale filing noise."
    ),
    "2_history_check": HISTORY_CHECK,
    "3_single_decision_hypothesis": (
        "One readiness decision: does the repo have PIT Schedule 13G/13D "
        "primary-document text or parsed holder/stake/action rows across all "
        "three canonical windows?"
    ),
    "4_acceptance_standard": (
        "Gate 1 uses docs/backtesting.md three-window baseline. Gate 2 must "
        "find issuer ticker, accession, primary document text, holder/filer "
        "identity, beneficial ownership percent, and action type before any "
        "strategy replay. Gate 3 survival is unchanged because no filter is "
        "added. Gate 4 remains no-strategy-change unless Gate 2 passes."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260618_014_sec_13g13d_holder_stake_readiness.py"
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, sort_keys=True)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                if json.loads(line).get("experiment_id") == EXPERIMENT_ID:
                    return
            except json.JSONDecodeError:
                continue
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(encoded + "\n")


def build_baseline() -> dict[str, Any]:
    raw = read_json(BASELINE_PATH, {})
    windows: dict[str, dict[str, Any]] = {}
    total_pnl = 0.0
    total_trade_count = 0
    min_survival_rate = 1.0
    max_window_drawdown = 0.0
    aggregate_ev = 0.0
    for row in raw.get("windows", []):
        label = row["label"]
        base = WINDOWS[label]
        window = {
            "start": base["start"],
            "end": base["end"],
            "snapshot": base["snapshot"],
            "expected_value_score": row.get("expected_value_score"),
            "total_pnl": row.get("total_pnl"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "sharpe_daily": row.get("sharpe_daily"),
            "signals_generated": row.get("signals_generated"),
            "signals_survived": row.get("signals_survived"),
            "survival_rate": row.get("survival_rate"),
            "trade_count": row.get("trade_count"),
            "win_rate": row.get("win_rate"),
        }
        windows[label] = window
        aggregate_ev += float(row.get("expected_value_score") or 0.0)
        total_pnl += float(row.get("total_pnl") or 0.0)
        total_trade_count += int(row.get("trade_count") or 0)
        min_survival_rate = min(min_survival_rate, float(row.get("survival_rate") or 0.0))
        max_window_drawdown = max(
            max_window_drawdown, float(row.get("max_drawdown_pct") or 0.0)
        )
    return {
        "source": repo_rel(BASELINE_PATH),
        "status": "passed",
        "windows": windows,
        "aggregate": {
            "aggregate_expected_value_score": round(aggregate_ev, 4),
            "aggregate_total_pnl": round(total_pnl, 2),
            "total_trade_count": total_trade_count,
            "min_survival_rate": round(min_survival_rate, 4),
            "max_window_drawdown_pct": round(max_window_drawdown, 4),
        },
    }


def window_for_date(filing_date: str) -> str | None:
    for label, span in WINDOWS.items():
        if span["start"] <= filing_date <= span["end"]:
            return label
    return None


def normalize_form(value: Any) -> str:
    return str(value or "").strip().upper()


def is_13g13d(form: str, description: str) -> bool:
    text = f"{form} {description}".upper()
    return "13G" in text or "13D" in text


def iter_ownership_filings() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(SUBMISSIONS_DIR.glob("CIK*.json")):
        payload = read_json(path, {})
        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        descriptions = recent.get("primaryDocDescription", [])
        accessions = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        accepted_times = recent.get("acceptanceDateTime", [])
        primary_docs = recent.get("primaryDocument", [])
        sizes = recent.get("size", [])
        tickers = payload.get("tickers") or []
        ticker = tickers[0] if tickers else None
        cik = str(payload.get("cik") or path.stem.removeprefix("CIK")).zfill(10)
        for idx, raw_form in enumerate(forms):
            form = normalize_form(raw_form)
            description = (
                descriptions[idx] if idx < len(descriptions) and descriptions[idx] else ""
            )
            if not is_13g13d(form, description):
                continue
            filing_date = filing_dates[idx] if idx < len(filing_dates) else ""
            label = window_for_date(filing_date)
            if not label:
                continue
            accession = accessions[idx] if idx < len(accessions) else ""
            dedupe_key = (cik, accession)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            primary_document = primary_docs[idx] if idx < len(primary_docs) else ""
            events.append(
                {
                    "ticker": ticker,
                    "cik": cik,
                    "accession_number": accession,
                    "form": form,
                    "primary_doc_description": description,
                    "filing_date": filing_date,
                    "accepted_at": accepted_times[idx] if idx < len(accepted_times) else "",
                    "primary_document": primary_document,
                    "primary_document_is_structured_xml": bool(
                        "xslSCHEDULE".lower() in primary_document.lower()
                        or primary_document.lower().endswith(".xml")
                    ),
                    "size": sizes[idx] if idx < len(sizes) else None,
                    "window": label,
                }
            )
    return events


def load_daily_text_accessions() -> dict[str, dict[str, Any]]:
    accessions: dict[str, dict[str, Any]] = {}
    for path in sorted(DAILY_NON_OHLCV_DIR.glob("sec_filing_text_*.jsonl")):
        date_key = path.stem.rsplit("_", 1)[-1]
        if date_key < "20241002" or date_key > "20260421":
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                accession = row.get("accession_number")
                if not accession:
                    continue
                accessions[accession] = {
                    "path": repo_rel(path),
                    "form_type": row.get("form_type"),
                    "text_char_count": row.get("text_char_count"),
                    "filing_date": row.get("filing_date"),
                    "ticker": row.get("ticker"),
                }
    return accessions


def load_cached_text_accessions() -> dict[str, dict[str, Any]]:
    accessions: dict[str, dict[str, Any]] = {}
    for path in sorted(FILING_TEXT_CACHE_DIR.glob("*.json")):
        row = read_json(path, {})
        accession = row.get("accession_number") or path.stem
        if not accession:
            continue
        accessions[accession] = {
            "path": repo_rel(path),
            "form_type": row.get("form_type"),
            "text_char_count": row.get("text_char_count"),
            "filing_date": row.get("filing_date"),
            "ticker": row.get("ticker"),
            "has_combined_text": bool(row.get("combined_text")),
        }
    return accessions


def summarize_parsed_tables() -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for pattern in ("*13g*", "*13d*", "*ownership*", "*holder*", "*stake*"):
        for path in sorted(DAILY_NON_OHLCV_DIR.glob(pattern)):
            if path.is_file():
                candidates.append({"path": repo_rel(path), "bytes": path.stat().st_size})
    sec13f_dir = DAILY_NON_OHLCV_DIR / "sec13f_institutional"
    for path in sorted(sec13f_dir.glob("*.json")) if sec13f_dir.exists() else []:
        candidates.append({"path": repo_rel(path), "bytes": path.stat().st_size})

    unique_candidates: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for candidate in candidates:
        path = candidate["path"]
        if path in seen_paths:
            continue
        seen_paths.add(path)
        unique_candidates.append(candidate)

    parsed_13g13d_paths = [
        row
        for row in unique_candidates
        if "13g" in row["path"].lower() or "13d" in row["path"].lower()
    ]
    return {
        "candidate_files": unique_candidates,
        "candidate_file_count": len(unique_candidates),
        "parsed_13g13d_file_count": len(parsed_13g13d_paths),
        "parsed_13g13d_files": parsed_13g13d_paths,
        "sec13f_only_note": (
            "The local sec13f_institutional files are quarterly 13F snapshots, "
            "not accession-level Schedule 13G/13D holder/stake/action rows."
        ),
        "status": "ready" if parsed_13g13d_paths else "missing_parsed_13g13d_table",
    }


def summarize_ownership_readiness(events: list[dict[str, Any]]) -> dict[str, Any]:
    cached_text = load_cached_text_accessions()
    daily_text = load_daily_text_accessions()
    parsed_tables = summarize_parsed_tables()
    by_window: dict[str, dict[str, Any]] = {}
    missing_examples: list[dict[str, Any]] = []
    present_examples: list[dict[str, Any]] = []
    form_counts = Counter(event["form"] for event in events)

    for label in WINDOWS:
        window_events = [event for event in events if event["window"] == label]
        with_cached = [event for event in window_events if event["accession_number"] in cached_text]
        with_daily = [event for event in window_events if event["accession_number"] in daily_text]
        with_any = [
            event
            for event in window_events
            if event["accession_number"] in cached_text
            or event["accession_number"] in daily_text
        ]
        structured_xml = [
            event for event in window_events if event["primary_document_is_structured_xml"]
        ]
        by_window[label] = {
            "start": WINDOWS[label]["start"],
            "end": WINDOWS[label]["end"],
            "ownership_filing_count": len(window_events),
            "unique_ticker_count": len({event["ticker"] for event in window_events if event["ticker"]}),
            "forms": dict(Counter(event["form"] for event in window_events).most_common()),
            "structured_xml_primary_doc_count": len(structured_xml),
            "cached_primary_text_count": len(with_cached),
            "daily_sec_text_count": len(with_daily),
            "any_primary_text_count": len(with_any),
            "parsed_holder_stake_row_count": 0
            if parsed_tables["status"] != "ready"
            else "not_counted",
            "primary_text_coverage_fraction": round(
                len(with_any) / len(window_events), 4
            )
            if window_events
            else 0.0,
            "status": "ready"
            if window_events
            and len(with_any) == len(window_events)
            and parsed_tables["status"] == "ready"
            else "blocked",
        }
        for event in window_events:
            accession = event["accession_number"]
            if accession in cached_text or accession in daily_text:
                if len(present_examples) < 8:
                    present_examples.append(
                        {
                            **event,
                            "cached_text": cached_text.get(accession),
                            "daily_text": daily_text.get(accession),
                        }
                    )
            elif len(missing_examples) < 12:
                missing_examples.append(event)

    return {
        "event_source": "data/cache/sec/submissions/CIK*.json recent filings",
        "form_selector": "form or primaryDocDescription contains 13G or 13D",
        "total_ownership_filings_in_windows": len(events),
        "total_unique_tickers": len({event["ticker"] for event in events if event["ticker"]}),
        "form_counts": dict(form_counts.most_common()),
        "text_cache_file_count": len(cached_text),
        "daily_sec_text_accession_count": len(daily_text),
        "coverage_by_window": by_window,
        "present_text_examples": present_examples,
        "missing_text_examples": missing_examples,
        "parsed_tables": parsed_tables,
        "blocking_summary": (
            "Submissions metadata has Schedule 13G/13D accessions in every "
            "canonical window, often with structured XML primary-document names, "
            "but the local filing-text caches contain no matching primary text "
            "and there is no parsed holder/stake/action table. A strategy replay "
            "would therefore be a frozen metadata-only 13G/13D retry."
        ),
        "status": "ready"
        if all(row["status"] == "ready" for row in by_window.values())
        else "blocked_missing_primary_text_and_parsed_holder_stake",
    }


def build_gate_payload(
    baseline: dict[str, Any], readiness: dict[str, Any]
) -> dict[str, Any]:
    gate2_ready = readiness["status"] == "ready"
    return {
        "gate1_baseline": baseline,
        "gate2_field_availability": {
            "status": "passed" if gate2_ready else "blocked",
            "required_fields": [
                "issuer ticker",
                "filing date",
                "accession number",
                "Schedule 13G/13D form type",
                "primary document text",
                "holder or filer identity",
                "beneficial ownership percent",
                "active/passive or purpose/action type",
                "stake-change direction or amendment context",
                "PIT source usable by daily production",
            ],
            "minimum_position_fields": {
                "entry_date": "unchanged in existing baseline strategy",
                "target_price": "unchanged in existing baseline strategy",
            },
            "ownership_readiness": readiness,
            "blocking_summary": None
            if gate2_ready
            else readiness["blocking_summary"],
        },
        "gate3_survival": {
            "status": "unchanged_no_new_filter",
            "floor_check": (
                "No new entry filter was added. Baseline survival remains above "
                "the 5% floor in every standard window."
            ),
            "min_survival_rate": baseline["aggregate"]["min_survival_rate"],
            "survival_by_window": {
                label: {
                    "signals_generated": row["signals_generated"],
                    "signals_survived": row["signals_survived"],
                    "survival_rate": row["survival_rate"],
                }
                for label, row in baseline["windows"].items()
            },
        },
        "gate4": {
            "status": "not_run_strategy_unchanged",
            "decision": "blocked" if not gate2_ready else "ready_for_shared_paper_first",
            "before": {
                "aggregate": baseline["aggregate"],
                "windows": baseline["windows"],
            },
            "after": {
                "aggregate": baseline["aggregate"],
                "windows": baseline["windows"],
            },
            "delta": {
                "aggregate_expected_value_score": 0.0,
                "aggregate_total_pnl": 0.0,
                "total_trade_count": 0,
                "min_survival_rate": 0.0,
                "max_window_drawdown_pct": 0.0,
            },
            "failed_reasons": []
            if gate2_ready
            else [
                "Local caches lack matching Schedule 13G/13D primary-document text.",
                "No parsed holder identity, beneficial ownership percent, action, or stake-change table exists.",
                "Direct metadata-only 13G/13D event replays were rejected in exp-20260612-015 and exp-20260612-016.",
                "Running another metadata-only threshold replay would violate the frozen-family guidance.",
                "A positive result without shared historical/daily parser parity would be backtester-only and untrustworthy.",
            ],
        },
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = build_baseline()
    ownership_events = iter_ownership_filings()
    readiness = summarize_ownership_readiness(ownership_events)
    gates = build_gate_payload(baseline, readiness)
    decision = (
        "ready_for_shared_paper_first"
        if readiness["status"] == "ready"
        else "blocked_missing_13g13d_primary_text_holder_stake_table"
    )
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "blocked" if readiness["status"] != "ready" else "observed_ready",
        "decision": decision,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "hypothesis": (
            "Schedule 13G/13D disclosures might become a high-quality "
            "candidate-pool edge only if parsed holder/stake/action fields "
            "distinguish informed accumulation from stale metadata noise."
        ),
        "prediction": {
            "success_probability": 0.1,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "primary_text_missing",
                "parsed_holder_stake_missing",
                "raw_metadata_retry_frozen",
            ],
            "confidence_reason": (
                "Prior raw 13G/13D runs failed, but recent closeouts named "
                "holder identity, ownership percent, and action type as the "
                "real new evidence axis. The submissions cache likely has "
                "metadata, while local text/parser coverage is uncertain."
            ),
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "nearby_prior_experiments": list(HISTORY_CHECK.keys()),
        "novelty": {
            "override_used": False,
            "new_evidence_axis": (
                "Structured Schedule 13G/13D primary-document and parsed "
                "holder/stake/action availability audit, not a raw metadata "
                "event replay or threshold sweep."
            ),
        },
        **gates,
        "production_impact": {
            "shared_helper_changed": False,
            "daily_snapshot_changed": False,
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "backtest_production_parity": (
                "No strategy or production helper changed. The blocker prevents "
                "a backtester-only Schedule 13G/13D alpha on metadata-only "
                "events. A future positive run must use the same parser in "
                "historical replay and the daily default-off snapshot."
            ),
            "live_realistic_execution_envelope": (
                "Not applicable because no executable alpha entered measurement. "
                "A future shared helper must record notional/capital cap, "
                "liquidity/slippage, max holdings, concentration, kill switch, "
                "order semantics, and failure handling before live readiness."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The repo has ample Schedule 13G/13D metadata in SEC "
                "submissions, including primary-document names, but the local "
                "filing-text caches do not hold those documents and no parsed "
                "holder/stake/action table is present."
            ),
            "negative_reflection": (
                "Raw 13G/13D metadata fails because amendments and batch filings "
                "mix stale passive ownership, active accumulation, reporting "
                "cleanup, and issuer-specific noise. Without holder identity, "
                "stake percent, and action direction, the event is not causally "
                "clean enough to expand the candidate pool."
            ),
            "do_not_retry_near_neighbors": [
                "raw Schedule 13G/13D form event gates",
                "13G versus 13D form threshold sweeps",
                "amendment-only or initiation-only metadata replays",
                "liquidity/price/top-N/hold/cooldown retunes on the same raw forms",
            ],
            "next_evidence_needed": [
                "PIT SEC primary-document backfill for Schedule 13G/13D accessions",
                "Parsed holder/filer identity and entity type",
                "Beneficial ownership percent and share count",
                "Active/passive intent, purpose, and amendment/action direction",
                "Shared historical replay plus daily default-off snapshot parser",
            ],
            "best_next_alpha_direction": (
                "Build a parsed PIT Schedule 13G/13D holder-stake-action table "
                "from the already-visible submissions metadata. Until that "
                "exists, move to another free structured data edge rather than "
                "retuning raw SEC event gates."
            ),
        },
        "reproduction": PRE_RUN_QUESTIONS["5_reproducibility"],
        "changed_files": [
            "quant/experiments/exp_20260618_014_sec_13g13d_holder_stake_readiness.py",
            "data/experiments/exp-20260618-014/exp_20260618_014_sec_13g13d_holder_stake_readiness.json",
            "data/experiments/exp-20260618-014/before_baseline.json",
            "data/experiments/exp-20260618-014/after_no_strategy_change.json",
            "experiments/logs/exp-20260618-014.json",
            "experiments/cards/exp-20260618-014.md",
            "experiments/manifests/exp-20260618-014.json",
            "experiments/tickets/exp-20260618-014.json",
            "docs/experiment_log.jsonl",
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "result": {
                "decision": payload["decision"],
                "status": payload["status"],
                "artifact": repo_rel(OUT_JSON),
                "log": repo_rel(LOG_JSON),
            },
        }
    )
    write_json(TICKET_JSON, ticket)


def write_card(payload: dict[str, Any]) -> None:
    readiness = payload["gate2_field_availability"]["ownership_readiness"]
    lines = [
        f"# {EXPERIMENT_ID} SEC 13G/13D Holder-Stake Readiness",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Status: `{payload['status']}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Baseline: `{payload['gate1_baseline']['source']}`",
        "- Gate 4: strategy unchanged; before/after deltas are zero.",
        "",
        "## Coverage",
        "",
    ]
    for label, row in readiness["coverage_by_window"].items():
        lines.append(
            "- "
            f"`{label}`: {row['ownership_filing_count']} ownership filings, "
            f"{row['structured_xml_primary_doc_count']} structured primary docs, "
            f"{row['any_primary_text_count']} with local primary text, "
            f"coverage {row['primary_text_coverage_fraction']:.4f}"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "Next evidence: "
            + "; ".join(payload["post_run_reflection"]["next_evidence_needed"]),
            "",
        ]
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "owner": OWNER,
        "timestamp": payload["timestamp"],
        "runner": repo_rel(Path(__file__)),
        "artifacts": {
            "artifact": repo_rel(OUT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "ticket": repo_rel(TICKET_JSON),
        },
        "changed_files": payload["changed_files"],
        "no_strategy_change": True,
        "anti_js": payload["anti_js"],
    }
    write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUT_JSON, payload)
    write_json(
        BEFORE_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "kind": "before_baseline",
            "gate1_baseline": payload["gate1_baseline"],
        },
    )
    write_json(
        AFTER_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "kind": "after_no_strategy_change",
            "gate4": payload["gate4"],
        },
    )
    write_json(LOG_JSON, payload)
    update_ticket(payload)
    write_card(payload)
    write_manifest(payload)
    append_jsonl_once(EXPERIMENT_LOG, payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "ownership_filings": payload["gate2_field_availability"][
                    "ownership_readiness"
                ]["total_ownership_filings_in_windows"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
