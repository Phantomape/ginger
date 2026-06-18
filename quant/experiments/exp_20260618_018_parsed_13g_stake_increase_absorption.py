"""exp-20260618-018: parsed 13G/A stake-increase readiness blocker.

Alpha-search experiment for a predeclared candidate-pool hypothesis: parsed
Schedule 13G/A amendments where a non-Big3 holder increases beneficial
ownership versus the prior PIT 13G row could identify fresh institutional
accumulation. The repo currently has parsed initial 13G rows, but this runner
verifies whether 13G/A amendment XML is cached and parsed before any replay.

No strategy logic, shared helper, ranking, sizing, exits, live orders, LLM/news
behavior, watchlist, or default trade settings are changed. No JavaScript is
used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402
from quant import sec_13d13g_ingest as ingest  # noqa: E402


EXPERIMENT_ID = "exp-20260618-018"
STEM = "parsed_13g_stake_increase_absorption"
CHANGED_VARIABLE = "parsed_13g_amend_stake_increase_absorption_candidate_pool_v1"
TRIAL_FAMILY = "parsed_13g_amend_stake_increase_absorption_candidate_pool"
TRIAL_VARIANT_ID = "parsed_13g_stake_increase_absorption_top1_next_open_10d_v1"
OWNER = "alpha-search-automation"

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260618_018_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PREDICTION = {
    "success_probability": 0.13,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "thin_sample",
        "old_thin_coverage_gap",
        "stale_13g_amendment_noise",
        "priced_before_next_open",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "exp-20260618-016 explicitly left 13G/A stake-change direction as a "
        "valid new evidence axis after static 13G subsets were not clean; "
        "exp-20260618-017 only tested 13D/A stake increases. The main risk is "
        "that 13G amendments are still passive batch updates or old_thin "
        "coverage remains weak."
    ),
    "recorded_at": "2026-06-18T17:55:32+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: parsed Schedule 13G/A amendments where a non-Big3 "
        "reporting holder's beneficial ownership percent increases versus its "
        "prior PIT parsed 13G row may identify fresh institutional accumulation "
        "distinct from stale initial passive filings; same-day liquid "
        "SPY-relative absorption tests whether demand accepted the disclosure "
        "before next-open paper entry."
    ),
    "2_history_check": {
        "exp-20260612-016": (
            "Rejected direct 13G passive/institutional disclosure metadata. "
            "Failure pointed to stale annual or batch filings and missing "
            "holder/action context."
        ),
        "exp-20260618-014": (
            "Blocked until parsed holder/stake/action rows existed. It did not "
            "test parsed 13G/A direction."
        ),
        "exp-20260618-016": (
            "Observed-only parsed 13D/13G diagnostic found no clean static "
            "holder/stake subset and explicitly named 13G/A stake-change "
            "direction as next evidence."
        ),
        "exp-20260618-017": (
            "Rejected parsed 13D/A stake-increase absorption; this run tests "
            "13G/A amendment direction instead of 13D/A direction."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Gate 2 must find parsed 13G/A amendment rows with prior same "
        "issuer-holder 13G rows before replay. If replay runs, Gate 4 requires "
        "positive aggregate EV/PnL, no EV/PnL window regression, at least 20 "
        "paper trades across all 3 windows, survival >=5%, drawdown drift "
        "<=0.5pp, concentration pass, and beating accepted compression and "
        "distribution comparators. Replay-only positives are not accepted alpha "
        "until shared helper parity exists."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260618_018_parsed_13g_stake_increase_absorption.py"
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                if json.loads(line).get("experiment_id") == EXPERIMENT_ID:
                    return
            except json.JSONDecodeError:
                continue
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def build_baseline() -> dict[str, Any]:
    raw = read_json(BASELINE_PATH, {})
    windows: dict[str, dict[str, Any]] = {}
    agg_ev = 0.0
    total_pnl = 0.0
    total_trades = 0
    min_survival = 1.0
    max_dd = 0.0
    for row in raw.get("windows", []):
        label = str(row["label"])
        windows[label] = {
            "start": row.get("start"),
            "end": row.get("end"),
            "snapshot": row.get("source") or row.get("path"),
            "expected_value_score": row.get("expected_value_score"),
            "sharpe_daily": row.get("sharpe_daily"),
            "total_pnl": row.get("total_pnl"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "win_rate": row.get("win_rate"),
            "trade_count": row.get("trade_count"),
            "signals_generated": row.get("signals_generated"),
            "signals_survived": row.get("signals_survived"),
            "survival_rate": row.get("survival_rate"),
        }
        agg_ev += float(row.get("expected_value_score") or 0.0)
        total_pnl += float(row.get("total_pnl") or 0.0)
        total_trades += int(row.get("trade_count") or 0)
        min_survival = min(min_survival, float(row.get("survival_rate") or 0.0))
        max_dd = max(max_dd, float(row.get("max_drawdown_pct") or 0.0))
    return {
        "source": repo_rel(BASELINE_PATH),
        "status": "passed",
        "windows": windows,
        "aggregate": {
            "aggregate_expected_value_score": round(agg_ev, 4),
            "aggregate_total_pnl": round(total_pnl, 2),
            "total_trade_count": total_trades,
            "min_survival_rate": round(min_survival, 4),
            "max_window_drawdown_pct": round(max_dd, 4),
        },
    }


def _holder_key(row: dict[str, Any]) -> str:
    names: list[str] = []
    for person in row.get("reporting_persons") or []:
        name = str(person.get("reporting_person_name") or "").lower()
        normalized = " ".join(
            name.replace(",", " ").replace(".", " ").replace("&", " and ").split()
        )
        if normalized:
            names.append(normalized)
    return "|".join(sorted(names)) or str(row.get("accession_number") or "")


def summarize_13g_amendment_surface() -> dict[str, Any]:
    init_events = ingest.iter_ownership_filings(
        families=("13G",), include_amendments=False
    )
    all_events = ingest.iter_ownership_filings(
        families=("13G",), include_amendments=True
    )
    all_parsed = ingest.build_parsed_rows(all_events, fetch=False, refresh=False)
    rows = all_parsed["rows"]

    events_by_window = Counter(ev.get("window") for ev in all_events)
    amend_events_by_window = Counter(
        ev.get("window") for ev in all_events if ev.get("is_amendment")
    )
    parsed_by_window = Counter(row.get("window") for row in rows)
    parsed_amend_by_window = Counter(
        row.get("window") for row in rows if row.get("is_amendment")
    )
    parsed_init_by_window = Counter(
        row.get("window") for row in rows if not row.get("is_amendment")
    )

    current_by_holder: dict[tuple[str, str], dict[str, Any]] = {}
    positive_direction_rows: list[dict[str, Any]] = []
    direction_counter: Counter[str] = Counter()
    for row in sorted(
        rows,
        key=lambda item: (
            str(item.get("ticker") or ""),
            _holder_key(item),
            str(item.get("filing_date") or ""),
            str(item.get("accepted_at") or ""),
            str(item.get("accession_number") or ""),
        ),
    ):
        ticker = str(row.get("ticker") or "").upper()
        holder = _holder_key(row)
        current_pct = row.get("max_class_percent")
        key = (ticker, holder)
        prior = current_by_holder.get(key)
        if row.get("is_amendment"):
            direction_counter["parsed_13g_amendment_rows"] += 1
            if (
                current_pct is not None
                and prior
                and prior.get("max_class_percent") is not None
                and not bool(row.get("is_big3"))
            ):
                delta = float(current_pct) - float(prior["max_class_percent"])
                if delta > 0:
                    positive_direction_rows.append(
                        {
                            "ticker": ticker,
                            "window": row.get("window"),
                            "filing_date": row.get("filing_date"),
                            "accession_number": row.get("accession_number"),
                            "holder_key": holder,
                            "current_class_percent": current_pct,
                            "prior_class_percent": prior.get("max_class_percent"),
                            "stake_delta_pct_points": round(delta, 4),
                        }
                    )
                    direction_counter["positive_non_big3_stake_increases"] += 1
                elif delta < 0:
                    direction_counter["negative_non_big3_stake_changes"] += 1
                else:
                    direction_counter["flat_non_big3_stake_changes"] += 1
        if current_pct is not None:
            current_by_holder[key] = row

    missing_amendment_examples = [
        {
            "ticker": ev.get("ticker"),
            "issuer_cik": ev.get("issuer_cik"),
            "accession_number": ev.get("accession_number"),
            "form": ev.get("form"),
            "filing_date": ev.get("filing_date"),
            "accepted_at": ev.get("accepted_at"),
            "primary_document": ev.get("primary_document"),
            "structured_xml": ev.get("structured_xml"),
            "window": ev.get("window"),
        }
        for ev in all_events
        if ev.get("is_amendment")
    ][:12]

    by_window: dict[str, dict[str, Any]] = {}
    for label in ingest.WINDOWS:
        amend_count = amend_events_by_window.get(label, 0)
        parsed_amend_count = parsed_amend_by_window.get(label, 0)
        by_window[label] = {
            "total_13g_events": events_by_window.get(label, 0),
            "13g_amendment_events": amend_count,
            "parsed_13g_initial_rows": parsed_init_by_window.get(label, 0),
            "parsed_13g_amendment_rows": parsed_amend_count,
            "parsed_13g_rows_total": parsed_by_window.get(label, 0),
            "amendment_parse_fraction": round(
                parsed_amend_count / amend_count, 4
            )
            if amend_count
            else 0.0,
        }

    return {
        "status": "blocked_missing_parsed_13g_amendment_rows"
        if not positive_direction_rows
        else "direction_rows_ready",
        "xml_cache_dir": repo_rel(ingest.XML_CACHE_DIR),
        "rows_json": repo_rel(ingest.OUT_ROWS),
        "initial_13g_events": len(init_events),
        "all_13g_events_including_amendments": len(all_events),
        "13g_amendment_events": sum(1 for ev in all_events if ev.get("is_amendment")),
        "parsed_13g_rows_total": len(rows),
        "parsed_13g_amendment_rows": sum(1 for row in rows if row.get("is_amendment")),
        "parsed_positive_non_big3_stake_increase_rows": len(positive_direction_rows),
        "fetch_status": all_parsed["fetch_status"],
        "coverage_by_window": by_window,
        "direction_counter": dict(direction_counter),
        "positive_direction_sample": positive_direction_rows[:12],
        "missing_amendment_examples": missing_amendment_examples,
        "blocking_summary": (
            "The SEC submissions cache has 13G/A amendment events, but the "
            "local structured XML cache only contains initial 13G documents. "
            "Without parsed amendment rows, the predeclared stake-increase "
            "direction cannot be computed point-in-time. A metadata-only replay "
            "would repeat the frozen raw 13G family and violate parity."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = build_baseline()
    surface = summarize_13g_amendment_surface()
    gate2_passed = surface["status"] == "direction_rows_ready"
    failed_reasons = [] if gate2_passed else [
        "parsed_13g_amendment_rows_missing",
        "cannot_compute_sequential_13g_stake_change_direction",
        "metadata_only_13g_amendment_replay_frozen",
        "shared_historical_daily_parser_parity_missing_for_13g_a_direction",
    ]
    decision = (
        "ready_for_parsed_13g_stake_direction_replay"
        if gate2_passed
        else "blocked_missing_parsed_13g_amendment_stake_direction_surface"
    )
    status = "observed_ready" if gate2_passed else "blocked"
    aggregate = baseline["aggregate"]

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_replay_scout",
        "mechanism_family": "production_visible_sec_ownership_holder_stake_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "parsed_13g_amend_stake_direction",
            "historical_replay_scout",
            "standard_three_window_gate",
            "execution_envelope",
            "closeout_record",
        ],
        "nearby_prior_experiments": [
            "exp-20260612-016",
            "exp-20260618-014",
            "exp-20260618-016",
            "exp-20260618-017",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "parsed_sequential_13g_amend_stake_change_direction",
        "prediction": PREDICTION,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1_baseline": baseline,
        "gate2_field_availability": {
            "status": "passed" if gate2_passed else "blocked",
            "required_fields": [
                "parsed 13G/A accession number",
                "parsed 13G/A filing date",
                "parsed reporting-person names",
                "parsed max_class_percent",
                "prior same issuer-holder parsed 13G max_class_percent",
                "Big-3 passive holder flag",
                "warehouse OHLCV for any later replay",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "minimum_position_fields": {
                "entry_date": "unchanged in existing baseline strategy",
                "target_price": "unchanged in existing baseline strategy",
            },
            "surface": surface,
            "blocking_summary": None if gate2_passed else surface["blocking_summary"],
        },
        "gate3_survival": {
            "status": "unchanged_no_new_filter",
            "min_survival_rate": aggregate["min_survival_rate"],
            "survival_by_window": {
                label: {
                    "signals_generated": row.get("signals_generated"),
                    "signals_survived": row.get("signals_survived"),
                    "survival_rate": row.get("survival_rate"),
                }
                for label, row in baseline["windows"].items()
            },
            "floor_check": (
                "No entry filter or strategy replay was added; baseline "
                "survival stays above the 5% floor in every standard window."
            ),
        },
        "gate4": {
            "status": "not_run_strategy_unchanged",
            "decision": "blocked" if not gate2_passed else "ready_for_replay",
            "before": baseline,
            "after": baseline,
            "delta": {
                "aggregate_expected_value_score": 0.0,
                "aggregate_total_pnl": 0.0,
                "total_trade_count": 0,
                "min_survival_rate": 0.0,
                "max_window_drawdown_pct": 0.0,
            },
            "failed_reasons": failed_reasons,
        },
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "min_survival_rate": 0.0,
            "max_window_drawdown_pct": 0.0,
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 0,
            "actual_gate4_passed": False,
            "brier_score": round(PREDICTION["success_probability"] ** 2, 6),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "failure_modes_observed": failed_reasons,
            "predicted_failure_mode_hit": False,
            "realized_failure_mode": (
                "parsed_13g_amendment_xml_not_cached_or_parsed"
                if not gate2_passed
                else "gate2_ready_no_replay_executed"
            ),
            "surprise_note": (
                "The exact amendment direction surface was not present: 13G/A "
                "metadata exists, but local parsed XML rows are initial 13G only."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "uses_free_sec_submissions": True,
            "uses_parsed_sec_13d13g": True,
            "uses_llm": False,
            "parity_note": (
                "No strategy or production helper changed. A future replay must "
                "first backfill/cache parsed 13G/A XML and then use the same "
                "parser in historical replay and daily default-off snapshot."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The proposed 13G/A stake-direction edge could not enter replay "
                "because Gate 2 failed: submissions enumerate 13G/A amendments, "
                "but parsed XML rows are missing for amendments, so prior-versus-"
                "current holder stake direction cannot be computed without "
                "falling back to frozen metadata-only 13G events."
            ),
            "negative_reflection": (
                "This does not reject the economic idea. It rejects running it "
                "today with incomplete PIT data. A metadata-only amendment gate "
                "would mix passive batch updates, reporting cleanup, and stale "
                "ownership changes, recreating the raw 13G failure mode."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry 13G/A by sweeping form lists, Big-3 exclusions, "
                "classPercent levels, event age, signal excess, close-location, "
                "volume, volatility, ret20, price/ADV, top-N, hold, cooldown, or "
                "notional until parsed 13G/A amendment XML rows exist."
            ),
            "new_evidence_required": (
                "Backfill/cache structured primary_doc.xml for 13G/A amendments "
                "across all canonical windows and parse holder identity plus "
                "classPercent, then test the exact sequential non-Big3 stake-"
                "increase rule through a shared historical/daily helper."
            ),
            "best_next_alpha_direction": (
                "If 13G/A XML backfill is practical, rerun the same fixed "
                "direction surface after cache completion. Otherwise shift to "
                "13D Item-4 purpose text or another genuinely new structured PIT "
                "data edge, not another raw SEC metadata rule."
            ),
        },
        "reproduction": PRE_RUN_QUESTIONS["5_reproducibility"],
        "changed_files": [
            repo_rel(Path(__file__)),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": repo_rel(Path(__file__)),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1_baseline": payload["gate1_baseline"],
        "gate2_field_availability": payload["gate2_field_availability"],
        "gate3_survival": payload["gate3_survival"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "reproduction": payload["reproduction"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    surface = payload["gate2_field_availability"]["surface"]
    lines = [
        f"# {EXPERIMENT_ID} Parsed 13G/A Stake-Increase Absorption",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Parsed 13G rows: `{surface['parsed_13g_rows_total']}`",
        f"- Parsed 13G/A amendment rows: `{surface['parsed_13g_amendment_rows']}`",
        f"- 13G/A amendment events in submissions: `{surface['13g_amendment_events']}`",
        "- Gate 4: not run; strategy unchanged.",
        "",
        "## Gate 2",
        "",
        surface["blocking_summary"],
        "",
        "| Window | 13G events | 13G/A events | Parsed init | Parsed amend | Amend parse fraction |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in surface["coverage_by_window"].items():
        lines.append(
            "| {label} | {events} | {amends} | {init} | {parsed_amend} | {frac:.4f} |".format(
                label=label,
                events=row["total_13g_events"],
                amends=row["13g_amendment_events"],
                init=row["parsed_13g_initial_rows"],
                parsed_amend=row["parsed_13g_amendment_rows"],
                frac=row["amendment_parse_fraction"],
            )
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def write_manifest(payload: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "owner": OWNER,
            "timestamp": payload["timestamp"],
            "runner": repo_rel(Path(__file__)),
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "ticket": repo_rel(TICKET_JSON),
            "changed_files": payload["changed_files"],
            "no_strategy_change": True,
            "anti_js": payload["anti_js"],
        },
    )


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "result": {
                "accepted": False,
                "accepted_alpha": False,
                "decision": payload["decision"],
                "artifact": repo_rel(OUT_JSON),
                "log": repo_rel(LOG_JSON),
                "runner": repo_rel(Path(__file__)),
                "gate2": payload["gate2_field_availability"],
                "gate4": payload["gate4"],
                "summary": payload["post_run_reflection"]["why_result_happened"],
            },
            "calibration": payload["calibration"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        }
    )
    write_json(TICKET_JSON, ticket)


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, payload)
    write_text(CARD_MD, build_card(payload))
    write_manifest(payload)
    append_jsonl_once(EXPERIMENT_LOG, build_log_record(payload))
    result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": repo_rel(Path(__file__)),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate2": payload["gate2_field_availability"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "ticket_file": repo_rel(TICKET_JSON),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields=fields,
    )
    update_ticket(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    surface = payload["gate2_field_availability"]["surface"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "13g_amendment_events": surface["13g_amendment_events"],
                "parsed_13g_amendment_rows": surface["parsed_13g_amendment_rows"],
                "aggregate_ev_delta": 0.0,
                "aggregate_pnl_delta": 0.0,
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
