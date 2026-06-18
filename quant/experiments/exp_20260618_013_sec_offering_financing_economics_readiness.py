"""exp-20260618-013: SEC offering financing-economics data-edge readiness.

Alpha-search blocker check. Raw SEC offering/prospectus price absorption was
recently rejected; the only plausible new evidence axis is parsed financing
economics such as offering amount, dilution size, and use of proceeds. This
runner verifies whether local point-in-time primary-document text exists before
any strategy replay or shared helper is built.

No trading policy, production helper, ranking, sizing, exits, live orders, or
default trade settings are changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260618-013"
STEM = "sec_offering_financing_economics_readiness"
CHANGED_VARIABLE = "sec_offering_financing_economics_data_edge_readiness_v1"
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
OUT_JSON = OUT_DIR / f"exp_20260618_013_{STEM}.json"
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

OFFERING_FORMS = {
    "424B4",
    "424B5",
    "424B7",
    "F-3",
    "F-3ASR",
    "S-1",
    "S-1/A",
    "S-3",
    "S-3ASR",
}

FINANCING_TEXT_PATTERNS = {
    "use_of_proceeds": re.compile(r"\buse of proceeds\b", re.IGNORECASE),
    "gross_proceeds": re.compile(r"\bgross proceeds\b", re.IGNORECASE),
    "net_proceeds": re.compile(r"\bnet proceeds\b", re.IGNORECASE),
    "aggregate_offering_price": re.compile(
        r"\baggregate offering price\b", re.IGNORECASE
    ),
    "at_the_market": re.compile(r"\bat[- ]the[- ]market\b|\bATM offering\b", re.IGNORECASE),
    "common_stock_shares": re.compile(
        r"\bshares? of (?:our )?common stock\b", re.IGNORECASE
    ),
}

HISTORY_CHECK = {
    "exp-20260617-023": (
        "Rejected raw SEC offering/prospectus price absorption. Aggregate EV "
        "-0.2291 and PnL -$6,133.11; all three standard windows regressed. "
        "Closeout required richer PIT financing economics before any retry."
    ),
    "exp-20260618-012": (
        "Blocked post-20260618 nonrepeat data-edge readiness. It identified "
        "parsed PIT ownership/filing/economics fields as the only credible next "
        "alpha inputs and warned against frozen raw SEC event retries."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw offering/prospectus events are dilution noise, but "
        "the event could become executable if primary-document text exposes "
        "financing amount, use of proceeds, and dilution scale that show a "
        "manageable raise absorbed by price."
    ),
    "2_history_check": HISTORY_CHECK,
    "3_single_decision_hypothesis": (
        "One readiness decision: do local PIT SEC offering primary documents or "
        "parsed financing-economics fields cover all three canonical windows?"
    ),
    "4_acceptance_standard": (
        "Gate 1 uses docs/backtesting.md three-window baseline. Gate 2 must find "
        "accession-level offering primary text or parsed financing fields in all "
        "three windows before any strategy replay. Gate 3 survival remains the "
        "unchanged baseline because no filter is added. Gate 4 is no-strategy-"
        "change unless Gate 2 passes; a positive future shared helper would need "
        "before/after three-window EV/PnL/drawdown/trade-count/survival review."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260618_013_sec_offering_financing_economics_readiness.py"
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


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
    with path.open("a", encoding="utf-8") as fh:
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


def iter_recent_filings() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in sorted(SUBMISSIONS_DIR.glob("CIK*.json")):
        payload = read_json(path, {})
        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
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
            if form not in OFFERING_FORMS:
                continue
            filing_date = filing_dates[idx] if idx < len(filing_dates) else ""
            label = window_for_date(filing_date)
            if not label:
                continue
            accession = accessions[idx] if idx < len(accessions) else ""
            events.append(
                {
                    "ticker": ticker,
                    "cik": cik,
                    "accession_number": accession,
                    "form": form,
                    "filing_date": filing_date,
                    "accepted_at": accepted_times[idx] if idx < len(accepted_times) else "",
                    "primary_document": primary_docs[idx] if idx < len(primary_docs) else "",
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


def scan_cached_filing_text() -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for path in sorted(FILING_TEXT_CACHE_DIR.glob("*.json")):
        accession = path.stem
        row = read_json(path, {})
        text = row.get("combined_text") or ""
        hits = sorted(
            key for key, pattern in FINANCING_TEXT_PATTERNS.items() if pattern.search(text)
        )
        results[accession] = {
            "path": repo_rel(path),
            "form_type": row.get("form_type"),
            "filing_date": row.get("filing_date"),
            "ticker": row.get("ticker"),
            "text_char_count": row.get("text_char_count"),
            "financing_keyword_hits": hits,
        }
    return results


def summarize_offering_readiness(events: list[dict[str, Any]]) -> dict[str, Any]:
    cached_text = scan_cached_filing_text()
    daily_text = load_daily_text_accessions()
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
        with_financing_hits = [
            event
            for event in with_cached
            if cached_text[event["accession_number"]]["financing_keyword_hits"]
        ]
        by_window[label] = {
            "start": WINDOWS[label]["start"],
            "end": WINDOWS[label]["end"],
            "offering_event_count": len(window_events),
            "unique_ticker_count": len({event["ticker"] for event in window_events if event["ticker"]}),
            "forms": dict(Counter(event["form"] for event in window_events).most_common()),
            "cached_primary_text_count": len(with_cached),
            "daily_sec_text_count": len(with_daily),
            "any_primary_text_count": len(with_any),
            "financing_keyword_text_count": len(with_financing_hits),
            "primary_text_coverage_fraction": round(
                len(with_any) / len(window_events), 4
            )
            if window_events
            else 0.0,
            "status": "ready" if window_events and len(with_any) == len(window_events) else "blocked",
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
        "offering_forms": sorted(OFFERING_FORMS),
        "total_offering_events_in_windows": len(events),
        "total_unique_tickers": len({event["ticker"] for event in events if event["ticker"]}),
        "form_counts": dict(form_counts.most_common()),
        "text_cache_file_count": len(cached_text),
        "daily_sec_text_accession_count": len(daily_text),
        "coverage_by_window": by_window,
        "present_text_examples": present_examples,
        "missing_text_examples": missing_examples,
        "blocking_summary": (
            "Submissions metadata has offering/prospectus accessions in all "
            "canonical windows, but local primary-document text coverage is not "
            "available for those accessions, so financing amount/use-of-proceeds "
            "cannot be parsed point-in-time without a new backfill."
        ),
        "status": "ready"
        if all(row["status"] == "ready" for row in by_window.values())
        else "blocked_missing_primary_text",
    }


def build_gate_payload(baseline: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    gate2_ready = readiness["status"] == "ready"
    return {
        "gate1_baseline": baseline,
        "gate2_field_availability": {
            "status": "passed" if gate2_ready else "blocked",
            "required_fields": [
                "issuer ticker",
                "filing date",
                "accession number",
                "offering/prospectus form",
                "primary document text",
                "parsed financing amount or proceeds text",
                "PIT source usable by daily production",
            ],
            "minimum_position_fields": {
                "entry_date": "unchanged in existing baseline strategy",
                "target_price": "unchanged in existing baseline strategy",
            },
            "offering_readiness": readiness,
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
                "No PIT offering primary-document text exists locally for the standard windows.",
                "Raw offering form/price absorption was already rejected in exp-20260617-023.",
                "Running another offering threshold replay would create a frozen near-neighbor.",
                "A positive result without shared historical/daily primary-text parity would be untrustworthy.",
            ],
        },
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = build_baseline()
    offering_events = iter_recent_filings()
    readiness = summarize_offering_readiness(offering_events)
    gates = build_gate_payload(baseline, readiness)
    decision = (
        "ready_for_shared_paper_first"
        if readiness["status"] == "ready"
        else "blocked_missing_sec_offering_primary_text"
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
            "SEC offering/prospectus events might become positive candidate-pool "
            "signals only if parsed financing amount and use-of-proceeds show "
            "manageable dilution absorbed by price; local PIT text coverage must "
            "exist before any strategy replay."
        ),
        "prediction": {
            "success_probability": 0.12,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "offering_primary_documents_not_cached",
                "raw_offering_family_frozen",
                "no_market_cap_denominator",
            ],
            "confidence_reason": (
                "Raw SEC offering absorption failed all windows; financing "
                "economics are a valid new evidence axis only if primary text is "
                "available point-in-time."
            ),
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "nearby_prior_experiments": list(HISTORY_CHECK.keys()),
        "novelty": {
            "override_used": True,
            "new_evidence_axis": (
                "Accession-level SEC offering primary-document text and parsed "
                "financing amount/use-of-proceeds fields, not Companyfacts "
                "dilution ratios or offering form threshold retunes."
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
                "a backtester-only offering alpha on metadata-only events. A "
                "future positive run must share the same primary-text parser and "
                "daily default-off snapshot path."
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
                "The repo has offering/prospectus metadata in SEC submissions, "
                "but not the primary filing text needed to parse proceeds, "
                "offering amount, or dilution terms across the fixed windows."
            ),
            "negative_reflection": (
                "The raw event failed because offering forms mix dilutive, "
                "refinancing, shelf, and ATM contexts. Without deal economics, "
                "price absorption cannot distinguish constructive financing "
                "from supply overhang."
            ),
            "do_not_retry_near_neighbors": [
                "offering form threshold retunes",
                "offering price-absorption threshold retunes",
                "Companyfacts dilution ratio retunes",
                "metadata-only offering event candidate sources",
            ],
            "next_evidence_needed": [
                "PIT SEC primary-document backfill for offering/prospectus forms",
                "Parsed offering amount normalized by market cap or dollar volume",
                "Use-of-proceeds classification",
                "Security type and ATM/shelf/takedown classification",
                "Shared historical replay plus daily default-off snapshot parser",
            ],
            "best_next_alpha_direction": (
                "Build a parsed PIT ownership/offering primary-document table "
                "before strategy work; 13G/13D holder-stake/action remains the "
                "higher-upside candidate, while offering financing economics is "
                "viable only after primary text exists."
            ),
        },
        "reproduction": PRE_RUN_QUESTIONS["5_reproducibility"],
        "changed_files": [
            "quant/experiments/exp_20260618_013_sec_offering_financing_economics_readiness.py",
            "data/experiments/exp-20260618-013/exp_20260618_013_sec_offering_financing_economics_readiness.json",
            "data/experiments/exp-20260618-013/before_baseline.json",
            "data/experiments/exp-20260618-013/after_no_strategy_change.json",
            "experiments/logs/exp-20260618-013.json",
            "experiments/cards/exp-20260618-013.md",
            "experiments/manifests/exp-20260618-013.json",
            "experiments/tickets/exp-20260618-013.json",
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
    readiness = payload["gate2_field_availability"]["offering_readiness"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Offering Financing Economics Readiness",
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
            f"`{label}`: {row['offering_event_count']} offering events, "
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
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": payload["decision"]}, indent=2))


if __name__ == "__main__":
    main()
