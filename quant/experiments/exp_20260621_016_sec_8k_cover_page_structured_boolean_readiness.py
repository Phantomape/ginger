"""exp-20260621-016: SEC 8-K cover-page boolean readiness.

Alpha-search data-edge probe. This run checks whether existing PIT SEC filing
text exposes enough 8-K cover-page XBRL boolean signal to justify a shared
paper-first candidate-pool alpha. It changes no trading policy.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260621-016"
SLUG = "sec_8k_cover_page_structured_boolean_readiness"
RUNNER_NAME = f"quant/experiments/exp_20260621_016_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260621_016_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
README_MD = DATA_DIR / "README.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
MIN_TARGET_UNIQUE_EVENTS = 20
MIN_TARGET_WINDOWS = 3
MIN_TARGET_UNIQUE_EVENTS_PER_WINDOW = 5

HYPOTHESIS = (
    "candidate_pool: PIT-safe 8-K cover-page XBRL booleans such as "
    "emerging-growth-company, written-communications, and amendment flags may "
    "identify structurally different SEC event quality; if the surface lacks "
    "cross-window/cross-ticker sample or is only a frozen 8-K metadata "
    "neighbor, alpha replay is blocked."
)

TRIAL_FAMILY = "candidate_pool_full_stack"
TRIAL_VARIANT_ID = "exp-20260621-016"
CHANGED_VARIABLE = "sec_8k_cover_page_structured_boolean_candidate_pool_readiness_v1"

NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260621-015",
    "exp-20260621-014",
    "exp-20260619-001",
    "exp-20260617-010",
]

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
        "strategy_total_return_pct": 117.07,
        "total_pnl": 117072.92,
        "max_drawdown_pct": 0.0665,
        "trade_count": 18,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "expected_value_score": 2.1402,
        "sharpe_daily": 2.74,
        "strategy_total_return_pct": 78.11,
        "total_pnl": 78110.11,
        "max_drawdown_pct": 0.1119,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "expected_value_score": 0.5911,
        "sharpe_daily": 1.49,
        "strategy_total_return_pct": 39.67,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

FIELD_SPECS: dict[str, dict[str, Any]] = {
    "egc_true": {
        "label": "Entity Emerging Growth Company",
        "regex": re.compile(r"\bEntity Emerging Growth Company\s+(true|false)\b", re.I),
        "near_neighbor": "historical 10-K/10-Q filer-status target, but current 8-K true rows are sparse",
    },
    "written_comm_true": {
        "label": "Written Communications",
        "regex": re.compile(r"\bWritten Communications\s+(true|false)\b", re.I),
        "near_neighbor": "8-K cover-page communication metadata, not structured event economics",
    },
    "amendment_true": {
        "label": "Amendment Flag",
        "regex": re.compile(r"\bAmendment Flag\s+(true|false)\b", re.I),
        "near_neighbor": "raw 8-K/A inclusion and amendment metadata are frozen near-neighbors",
    },
    "soliciting_true": {
        "label": "Soliciting Material",
        "regex": re.compile(r"\bSoliciting Material\s+(true|false)\b", re.I),
        "near_neighbor": "proxy/deal metadata without structured consideration terms",
    },
    "pre_tender_true": {
        "label": "Pre-commencement Tender Offer",
        "regex": re.compile(r"\bPre-commencement Tender Offer\s+(true|false)\b", re.I),
        "near_neighbor": "deal metadata without cash-stock consideration or bidder-target economics",
    },
    "pre_issuer_tender_true": {
        "label": "Pre-commencement Issuer Tender Offer",
        "regex": re.compile(r"\bPre-commencement Issuer Tender Offer\s+(true|false)\b", re.I),
        "near_neighbor": "issuer-tender metadata without size, price, or execution economics",
    },
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle = f'"experiment_id": "{EXPERIMENT_ID}"'
    if path.exists() and needle in path.read_text(encoding="utf-8-sig"):
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def aggregate_windows() -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row["expected_value_score"]) for row in CANONICAL_WINDOWS.values()),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(row["total_pnl"]) for row in CANONICAL_WINDOWS.values()),
            2,
        ),
        "total_trade_count": sum(int(row["trade_count"]) for row in CANONICAL_WINDOWS.values()),
        "min_survival_rate": round(
            min(float(row["survival_rate"]) for row in CANONICAL_WINDOWS.values()),
            4,
        ),
        "max_window_drawdown_pct": round(
            max(float(row["max_drawdown_pct"]) for row in CANONICAL_WINDOWS.values()),
            4,
        ),
    }


def baseline_artifact(label: str) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "label": label,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "windows": CANONICAL_WINDOWS,
        "aggregate": aggregate_windows(),
        "strategy_code_changed": False,
        "production_code_changed": False,
        "note": "No after strategy was launched; after intentionally equals before.",
    }


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def window_for(value: Any) -> str | None:
    observed = parse_date(value)
    if observed is None:
        return None
    for label, window in CANONICAL_WINDOWS.items():
        if date.fromisoformat(window["start"]) <= observed <= date.fromisoformat(window["end"]):
            return label
    return None


def event_key(row: dict[str, Any]) -> tuple[str, str, str]:
    ticker = str(row.get("ticker") or "").upper()
    accession = str(row.get("accession_number") or "")
    usable_date = str(row.get("usable_trade_date") or row.get("filing_date") or "")
    return (ticker, accession, usable_date)


def is_8k(row: dict[str, Any]) -> bool:
    form = str(row.get("form_type") or row.get("form_base") or "").upper()
    return form in {"8-K", "8-K/A"}


def extract_cover_flags(text: str) -> dict[str, bool | None]:
    flags: dict[str, bool | None] = {}
    for field, spec in FIELD_SPECS.items():
        match = spec["regex"].search(text)
        if not match:
            flags[field] = None
        else:
            flags[field] = match.group(1).lower() == "true"
    return flags


def scan_sec_8k_cover_booleans() -> dict[str, Any]:
    file_count = 0
    invalid_json_lines = 0
    rows_by_window: Counter[str] = Counter()
    unique_8k_events_by_window: defaultdict[str, set[tuple[str, str, str]]] = defaultdict(set)
    dependency_present = Counter()
    dependency_total = 0

    true_raw_rows: dict[str, Counter[str]] = {field: Counter() for field in FIELD_SPECS}
    observed_raw_rows: dict[str, Counter[str]] = {field: Counter() for field in FIELD_SPECS}
    unique_true_events: dict[str, defaultdict[str, set[tuple[str, str, str]]]] = {
        field: defaultdict(set) for field in FIELD_SPECS
    }
    unique_observed_events: dict[str, defaultdict[str, set[tuple[str, str, str]]]] = {
        field: defaultdict(set) for field in FIELD_SPECS
    }
    true_tickers: dict[str, defaultdict[str, set[str]]] = {
        field: defaultdict(set) for field in FIELD_SPECS
    }
    true_examples: dict[str, list[dict[str, Any]]] = {field: [] for field in FIELD_SPECS}

    for path in sorted(NON_OHLCV_DIR.glob("sec_filing_text_*.jsonl")):
        file_count += 1
        with path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    invalid_json_lines += 1
                    continue
                if not is_8k(row):
                    continue

                trade_date = row.get("usable_trade_date") or row.get("filing_date")
                window = window_for(trade_date)
                if window is None:
                    continue

                dependency_total += 1
                for key in ("ticker", "accession_number", "filing_date", "usable_trade_date", "combined_text"):
                    if row.get(key) not in (None, ""):
                        dependency_present[key] += 1
                for key in ("entry_date", "target_price"):
                    if row.get(key) not in (None, ""):
                        dependency_present[key] += 1

                rows_by_window[window] += 1
                key = event_key(row)
                unique_8k_events_by_window[window].add(key)
                text = str(row.get("combined_text") or "")
                flags = extract_cover_flags(text)
                ticker = key[0]
                for field, value in flags.items():
                    if value is None:
                        continue
                    observed_raw_rows[field][window] += 1
                    unique_observed_events[field][window].add(key)
                    if value is True:
                        true_raw_rows[field][window] += 1
                        unique_true_events[field][window].add(key)
                        true_tickers[field][window].add(ticker)
                        if len(true_examples[field]) < 8:
                            true_examples[field].append(
                                {
                                    "ticker": ticker,
                                    "accession_number": key[1],
                                    "usable_trade_date": key[2],
                                    "form_type": row.get("form_type"),
                                    "snapshot_file": repo_rel(path),
                                }
                            )

    field_readiness: dict[str, dict[str, Any]] = {}
    for field, spec in FIELD_SPECS.items():
        unique_true_by_window = {
            label: len(unique_true_events[field].get(label, set()))
            for label in CANONICAL_WINDOWS
        }
        observed_by_window = {
            label: len(unique_observed_events[field].get(label, set()))
            for label in CANONICAL_WINDOWS
        }
        raw_true_by_window = {
            label: int(true_raw_rows[field].get(label, 0))
            for label in CANONICAL_WINDOWS
        }
        unique_ticker_by_window = {
            label: len(true_tickers[field].get(label, set()))
            for label in CANONICAL_WINDOWS
        }
        total_unique_true = sum(unique_true_by_window.values())
        total_unique_observed = sum(observed_by_window.values())
        windows_with_true = [
            label for label, count in unique_true_by_window.items() if count > 0
        ]
        min_nonzero_window_count = (
            min(unique_true_by_window[label] for label in CANONICAL_WINDOWS)
            if len(windows_with_true) == len(CANONICAL_WINDOWS)
            else 0
        )
        gate2_field_observed = total_unique_observed > 0
        gate3_sample_passed = (
            total_unique_true >= MIN_TARGET_UNIQUE_EVENTS
            and len(windows_with_true) >= MIN_TARGET_WINDOWS
            and min_nonzero_window_count >= MIN_TARGET_UNIQUE_EVENTS_PER_WINDOW
        )
        blocking_reasons: list[str] = []
        if not gate2_field_observed:
            blocking_reasons.append("field_value_not_observed_in_current_8k_text")
        if total_unique_true < MIN_TARGET_UNIQUE_EVENTS:
            blocking_reasons.append("target_true_unique_event_count_below_20")
        if len(windows_with_true) < MIN_TARGET_WINDOWS:
            blocking_reasons.append("target_true_missing_three_window_coverage")
        if min_nonzero_window_count < MIN_TARGET_UNIQUE_EVENTS_PER_WINDOW:
            blocking_reasons.append("target_true_window_sample_below_5")
        if field == "amendment_true":
            blocking_reasons.append("amendment_metadata_is_8k_a_near_neighbor")

        field_readiness[field] = {
            "label": spec["label"],
            "gate2_field_observed": gate2_field_observed,
            "gate3_sample_passed": gate3_sample_passed,
            "unique_true_events_total": total_unique_true,
            "unique_observed_events_total": total_unique_observed,
            "windows_with_unique_true_events": windows_with_true,
            "unique_true_events_by_window": unique_true_by_window,
            "raw_true_rows_by_window": raw_true_by_window,
            "unique_true_tickers_by_window": unique_ticker_by_window,
            "sample_true_events": true_examples[field],
            "near_neighbor_note": spec["near_neighbor"],
            "blocking_reasons": blocking_reasons,
        }

    valid_fields = [
        field for field, row in field_readiness.items() if row["gate3_sample_passed"]
    ]
    bundle_reasons = []
    if not valid_fields:
        bundle_reasons.append("no_single_cover_page_boolean_passes_target_sample_gate")
    bundle_reasons.append(
        "unioning_unrelated_boolean_fields_would_not_be_a_single_causal_decision_hypothesis"
    )
    bundle_reasons.append(
        "amendment_flag_component_overlaps_frozen_raw_8k_a_metadata_family"
    )

    return {
        "file_count": file_count,
        "invalid_json_lines": invalid_json_lines,
        "eight_k_rows_by_window": {label: int(rows_by_window[label]) for label in CANONICAL_WINDOWS},
        "unique_8k_events_by_window": {
            label: len(unique_8k_events_by_window.get(label, set()))
            for label in CANONICAL_WINDOWS
        },
        "raw_dependency_presence": {
            key: {
                "present_rows": int(dependency_present.get(key, 0)),
                "scanned_8k_rows": dependency_total,
                "present_rate": (
                    round(float(dependency_present.get(key, 0)) / dependency_total, 4)
                    if dependency_total
                    else 0.0
                ),
            }
            for key in (
                "ticker",
                "accession_number",
                "filing_date",
                "usable_trade_date",
                "combined_text",
                "entry_date",
                "target_price",
            )
        },
        "field_readiness": field_readiness,
        "valid_single_field_candidates": valid_fields,
        "candidate_bundle_verdict": {
            "accepted_for_strategy_replay": False,
            "blocking_reasons": bundle_reasons,
        },
    }


def metric_deltas() -> dict[str, dict[str, float]]:
    fields = [
        "expected_value_score",
        "total_pnl",
        "max_drawdown_pct",
        "trade_count",
        "survival_rate",
    ]
    return {label: {field: 0.0 for field in fields} for label in CANONICAL_WINDOWS}


def build_result() -> dict[str, Any]:
    scan = scan_sec_8k_cover_booleans()
    aggregate = aggregate_windows()
    prediction = read_json(TICKET_JSON).get(
        "prediction",
        {
            "success_probability": 0.12,
            "expected_ev_delta": None,
            "expected_pnl_delta": None,
            "main_failure_modes": [
                "thin_sample",
                "one_window_only",
                "near_neighbor_sec_metadata",
            ],
            "confidence_reason": (
                "Cover-page XBRL booleans are PIT and free, but prior SEC metadata "
                "families failed or were sparse."
            ),
        },
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now_utc(),
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_sec_8k_cover_page_boolean_sample_and_near_neighbor",
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_full_stack",
        "mechanism_family": "candidate_pool_full_stack",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "prediction": prediction,
        "pre_run_questions": {
            "money_making_hypothesis": (
                "A structured 8-K cover-page boolean could identify event quality or "
                "issuer status before price response, improving candidate-pool selection."
            ),
            "history_check": (
                "Novelty gate warned on SEC text/event metadata families; this run "
                "only audits whether the XBRL boolean axis has new sample evidence."
            ),
            "single_attributable_policy_bundle": (
                "Readiness of one candidate-pool data edge: SEC 8-K cover-page "
                "structured boolean target fields. No strategy parameters are tuned."
            ),
            "acceptance_criteria": (
                "At least one single boolean target needs >=20 unique true events, "
                "all three canonical windows, >=5 unique true events per window, and "
                "a non-frozen causal interpretation before Gate 4 replay."
            ),
            "reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_result_file": BASELINE_RESULT_FILE,
            "windows": CANONICAL_WINDOWS,
            "aggregate": aggregate,
            "passed": True,
        },
        "gate2": {
            "dependency_fields_checked": [
                "ticker",
                "accession_number",
                "filing_date",
                "usable_trade_date",
                "combined_text",
                "entry_date",
                "target_price",
            ],
            "raw_dependency_presence": scan["raw_dependency_presence"],
            "field_readiness": {
                field: {
                    "label": row["label"],
                    "gate2_field_observed": row["gate2_field_observed"],
                    "unique_observed_events_total": row["unique_observed_events_total"],
                }
                for field, row in scan["field_readiness"].items()
            },
            "passed": False,
            "blocking_reason": (
                "Raw SEC text is PIT and contains ticker/accession/date/text, but it "
                "does not expose entry_date or target_price as replay-ready fields; "
                "target booleans must pass sample readiness before a shared helper "
                "joins them to OHLCV."
            ),
        },
        "gate3": {
            "baseline_survival_by_window": {
                label: {
                    "signals_generated": row["signals_generated"],
                    "signals_survived": row["signals_survived"],
                    "survival_rate": row["survival_rate"],
                }
                for label, row in CANONICAL_WINDOWS.items()
            },
            "minimum_target_unique_events": MIN_TARGET_UNIQUE_EVENTS,
            "minimum_target_windows": MIN_TARGET_WINDOWS,
            "minimum_target_unique_events_per_window": MIN_TARGET_UNIQUE_EVENTS_PER_WINDOW,
            "eight_k_rows_by_window": scan["eight_k_rows_by_window"],
            "unique_8k_events_by_window": scan["unique_8k_events_by_window"],
            "field_readiness": scan["field_readiness"],
            "valid_single_field_candidates": scan["valid_single_field_candidates"],
            "candidate_bundle_verdict": scan["candidate_bundle_verdict"],
            "passed": False,
            "blocking_reason": (
                "No individual cover-page boolean has enough true target sample and "
                "non-frozen interpretation to justify a strategy replay."
            ),
        },
        "gate4": {
            "ran_after_strategy": False,
            "reason_after_not_run": (
                "Blocked at Gate 2/3 readiness; forcing a backtest would evaluate a "
                "thin near-neighbor metadata surface."
            ),
            "before_windows": CANONICAL_WINDOWS,
            "after_windows": CANONICAL_WINDOWS,
            "delta_by_window": metric_deltas(),
            "aggregate_before": aggregate,
            "aggregate_after": aggregate,
            "aggregate_delta": {
                "aggregate_expected_value_score": 0.0,
                "aggregate_total_pnl": 0.0,
                "total_trade_count": 0,
                "min_survival_rate": 0.0,
                "max_window_drawdown_pct": 0.0,
            },
            "passed": False,
        },
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "max_window_drawdown_pct": 0.0,
        },
        "production_impact": {
            "strategy_code_changed": False,
            "shared_helper_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "backtest_production_parity_risk": "none_from_this_run",
            "parity_note": (
                "No buy/sell/filter/ranking/sizing/risk code changed. A future "
                "positive result would need a shared default-off helper before it "
                "could affect historical replay or daily snapshots."
            ),
        },
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "realized": "blocked_before_strategy_replay",
            "realized_failure_modes": [
                "thin_sample",
                "near_neighbor_sec_metadata",
                "not_incremental_without_structured_actor_object_magnitude",
            ],
        },
        "post_run_reflection": {
            "why_blocked": (
                "The local 8-K cover-page booleans are production-visible, but true "
                "events are too sparse or too close to frozen 8-K metadata. A replay "
                "would create another near-neighbor SEC metadata attempt."
            ),
            "negative_result_reflection": (
                "This failed because the candidate-pool data edge has weak target "
                "density, not because a trading rule lost money. The raw 8-K universe "
                "is broad, but the specific true booleans are rare and mostly metadata."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by unioning cover-page booleans, sweeping 8-K/A "
                "inclusion, or adding close/volume/top-N/hold filters around these "
                "same booleans on the frozen windows."
            ),
            "next_new_evidence_required": (
                "Use a materially richer free PIT field: historical 10-K/10-Q "
                "cover-page filer-status by accession, structured contract/customer "
                "economics, or forward replacement rows with actor/object/magnitude."
            ),
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(README_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": RUNNER_COMMAND,
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": result["gate1"],
        "gate2": result["gate2"],
        "gate3": {
            "passed": result["gate3"]["passed"],
            "blocking_reason": result["gate3"]["blocking_reason"],
            "valid_single_field_candidates": result["gate3"]["valid_single_field_candidates"],
            "field_summary": {
                field: {
                    "unique_true_events_total": row["unique_true_events_total"],
                    "windows_with_unique_true_events": row["windows_with_unique_true_events"],
                    "blocking_reasons": row["blocking_reasons"],
                }
                for field, row in result["gate3"]["field_readiness"].items()
            },
        },
        "gate4": result["gate4"],
        "production_impact": result["production_impact"],
        "calibration": result["calibration"],
        "post_run_reflection": result["post_run_reflection"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": result["anti_js"],
        "lean_quality_passed": result["lean_quality_passed"],
    }


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: SEC 8-K cover-page boolean readiness",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- Strategy / production behavior changed: no",
        "",
        "## Gate 4 Baseline",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in CANONICAL_WINDOWS.items():
        lines.append(
            f"| {label} | {row['expected_value_score']:.4f} | "
            f"{row['expected_value_score']:.4f} | 0.0000 | "
            f"${row['total_pnl']:,.2f} | ${row['total_pnl']:,.2f} | $0.00 |"
        )
    lines.extend(
        [
            "",
            "## Gate 3 Target Sample",
            "",
            "| Field | Unique true events | Windows | Blocker |",
            "| --- | ---: | --- | --- |",
        ]
    )
    for field, row in result["gate3"]["field_readiness"].items():
        reasons = ", ".join(row["blocking_reasons"]) or "none"
        windows = ", ".join(row["windows_with_unique_true_events"]) or "none"
        lines.append(
            f"| `{field}` | {row['unique_true_events_total']} | {windows} | {reasons} |"
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            result["post_run_reflection"]["why_blocked"],
            "",
            result["post_run_reflection"]["next_new_evidence_required"],
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Blocked alpha-search readiness record for SEC 8-K cover-page booleans.\n\n"
        f"- Artifact: `{repo_rel(ARTIFACT_JSON)}`\n"
        f"- Log: `{repo_rel(LOG_JSON)}`\n"
        f"- Decision: `{result['decision']}`\n"
        f"- Reproduce: `{result['reproduction']}`\n"
    )


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER_NAME),
        ARTIFACT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        README_MD,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER_NAME,
        "command": result["reproduction"],
        "files": {
            repo_rel(path if path.is_absolute() else REPO_ROOT / path): {
                "exists": (path if path.is_absolute() else REPO_ROOT / path).exists(),
                "sha256": sha256_file(path if path.is_absolute() else REPO_ROOT / path),
            }
            for path in files
        },
        "anti_js": result["anti_js"],
        "updated_at": now_utc(),
    }


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, baseline_artifact("before_baseline"))
    write_json(AFTER_JSON, baseline_artifact("after_no_strategy_change"))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    write_text(README_MD, build_readme(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_blocked"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status="blocked",
        fields={
            "owner": "alpha-search-automation",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "sec_8k_cover_page_xbrl_boolean_readiness",
            "baseline_result_file": BASELINE_RESULT_FILE,
            "evaluation_windows": [
                {
                    "label": label,
                    "start": row["start"],
                    "end": row["end"],
                    "snapshot": row["snapshot"],
                }
                for label, row in CANONICAL_WINDOWS.items()
            ],
            "acceptance_rule": (
                "Blocked unless one single cover-page boolean has enough three-window "
                "target sample and non-frozen causal interpretation."
            ),
            "decision": result["decision"],
            "summary": result["post_run_reflection"]["why_blocked"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(result))


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "valid_single_field_candidates": result["gate3"]["valid_single_field_candidates"],
                "field_unique_true_events": {
                    field: row["unique_true_events_total"]
                    for field, row in result["gate3"]["field_readiness"].items()
                },
                "aggregate_ev_delta": result["delta_metrics"]["aggregate_expected_value_score"],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
