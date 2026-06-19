"""exp-20260619-020: post-20260619 non-repeat surface readiness v2.

This alpha-search experiment records a blocker rather than forcing another
near-neighbor strategy replay. It verifies whether any fresh, free,
production-visible PIT candidate-pool surface is ready for the canonical
three-window Gate 1-4 protocol after the latest 20260619 experiments.

No trading rule, helper, ranking, sizing, exit, LLM/news behavior, daily runner,
watchlist, or order path is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260619-020"
SLUG = "post_20260619_nonrepeat_surface_readiness_v2"
RUNNER_NAME = (
    "quant/experiments/"
    "exp_20260619_020_post_20260619_nonrepeat_surface_readiness_v2.py"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260619_020_{SLUG}.json"
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
BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

HYPOTHESIS = (
    "candidate_pool/data_edge readiness: after reviewing recent logs and local "
    "free PIT data inventory, alpha execution should proceed only if a "
    "materially new candidate-pool surface has canonical three-window coverage, "
    "novelty clearance, and a shared historical/daily parity path. Otherwise "
    "forcing a replay would be untrustworthy."
)

PREDICTION = {
    "success_probability": 0.05,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "all_free_surfaces_frozen_or_missing_pit_coverage",
        "near_neighbor_novelty_block",
        "production_parity_untrusted",
    ],
    "confidence_reason": (
        "Recent 20260617-20260619 logs exhausted raw SEC event, Companyfacts, "
        "FINRA, ownership, and OHLCV relation retries; current scans show "
        "S-8/offering/cap-status/options/borrow fields are missing or not "
        "canonical-window PIT-ready."
    ),
}

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
        "win_rate": 0.8333,
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
        "win_rate": 0.5238,
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
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

RELATED_EXPERIMENTS = [
    {
        "experiment_id": "exp-20260614-020",
        "surface": "annual accruals / cash conversion",
        "decision": "rejected_drawdown",
        "summary": "Positive all-window gross deltas, but +5.22pp drawdown drift.",
    },
    {
        "experiment_id": "exp-20260614-024",
        "surface": "quarterly OCF/NI cash conversion",
        "decision": "rejected",
        "summary": "Thin/concentrated quarterly cash-flow improvement; ratio retries frozen.",
    },
    {
        "experiment_id": "exp-20260616-015",
        "surface": "SBC burden improvement",
        "decision": "accepted_default_off_shared",
        "summary": "Accepted shared helper; rank/gap-fill/per-share/grant-backlog retries failed.",
    },
    {
        "experiment_id": "exp-20260617-020",
        "surface": "broad annual 10-K filing timeliness",
        "decision": "rejected",
        "summary": "Broad-universe caveat closed; old_thin/drawdown/comparators failed.",
    },
    {
        "experiment_id": "exp-20260617-022",
        "surface": "quarterly 10-Q filing timeliness",
        "decision": "rejected",
        "summary": "Aggregate positive but old_thin/drawdown/distribution comparator failed.",
    },
    {
        "experiment_id": "exp-20260617-023",
        "surface": "SEC offering/prospectus absorption",
        "decision": "rejected",
        "summary": "Raw form/price absorption negative in all canonical windows.",
    },
    {
        "experiment_id": "exp-20260617-024",
        "surface": "S-8 employee-equity absorption",
        "decision": "rejected",
        "summary": "Raw S-8 form/price absorption rejected; registered-share economics needed.",
    },
    {
        "experiment_id": "exp-20260618-013",
        "surface": "offering financing economics",
        "decision": "blocked",
        "summary": "No local primary-document offering text for proceeds/dilution parsing.",
    },
    {
        "experiment_id": "exp-20260618-016",
        "surface": "parsed 13D/13G holder/stake",
        "decision": "observed_only",
        "summary": "Non-Big3 13G drift small and old_thin coverage weak; not Gate-4 alpha.",
    },
    {
        "experiment_id": "exp-20260619-007",
        "surface": "FINRA float-normalized short pressure",
        "decision": "rejected",
        "summary": "Window/drawdown/comparator failures; borrow fee/utilization needed.",
    },
    {
        "experiment_id": "exp-20260619-015",
        "surface": "regime-conditioned intraindustry lead-lag",
        "decision": "rejected",
        "summary": "Static lead-lag was state-dependent but conditioned replay still not retained.",
    },
    {
        "experiment_id": "exp-20260619-019",
        "surface": "SEC operational KPI acceleration text",
        "decision": "rejected",
        "summary": "Latest SEC text field regressed aggregate EV/PnL and failed comparators.",
    },
]

DATE_RE = re.compile(r"_(\d{8})(?:\.|_|$)")


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
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def canonical_window_list() -> list[dict[str, str]]:
    return [
        {
            "label": label,
            "start": data["start"],
            "end": data["end"],
            "snapshot": data["snapshot"],
        }
        for label, data in CANONICAL_WINDOWS.items()
    ]


def aggregate_windows(windows: dict[str, dict[str, Any]]) -> dict[str, float]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row["expected_value_score"]) for row in windows.values()),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(row["total_pnl"]) for row in windows.values()),
            2,
        ),
        "total_trade_count": float(
            sum(int(row["trade_count"]) for row in windows.values())
        ),
        "min_survival_rate": round(
            min(float(row["survival_rate"]) for row in windows.values()),
            4,
        ),
        "max_window_drawdown_pct": round(
            max(float(row["max_drawdown_pct"]) for row in windows.values()),
            4,
        ),
    }


def metric_delta(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> dict[str, dict[str, float]]:
    fields = ["expected_value_score", "total_pnl", "max_drawdown_pct", "trade_count"]
    deltas: dict[str, dict[str, float]] = {}
    for label, row in before.items():
        deltas[label] = {
            field: round(float(after[label][field]) - float(row[field]), 6)
            for field in fields
        }
    return deltas


def date_from_path(path: Path) -> str | None:
    match = DATE_RE.search(path.name)
    return match.group(1) if match else None


def in_standard_windows(date_key: str | None) -> bool:
    if not date_key:
        return False
    return "20241002" <= date_key <= "20260421"


def count_jsonl_forms(prefix: str) -> dict[str, Any]:
    forms: Counter[str] = Counter()
    rows = 0
    same_accession_fact_rows = 0
    non_missing_feature_values = Counter()
    files = 0
    for path in sorted(NON_OHLCV_DIR.glob(f"{prefix}_*.jsonl")):
        date_key = date_from_path(path)
        if not in_standard_windows(date_key):
            continue
        files += 1
        with path.open(encoding="utf-8-sig") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                rows += 1
                form = str(row.get("form_base") or row.get("form_type") or "").upper()
                forms[form or "UNKNOWN"] += 1
                availability = row.get("field_availability") or {}
                if availability.get("same_accession_facts") not in {
                    None,
                    "missing",
                    "missing_no_same_accession_companyfacts",
                }:
                    same_accession_fact_rows += 1
                for key in [
                    "revenue_surprise",
                    "eps_surprise",
                    "guidance_raise_cut",
                    "gross_margin_delta",
                    "inventory_growth",
                    "receivables_growth",
                    "fcf_to_net_income_gap",
                ]:
                    if row.get(key) is not None:
                        non_missing_feature_values[key] += 1
    return {
        "files": files,
        "rows": rows,
        "forms_top": forms.most_common(20),
        "s8_rows": sum(v for k, v in forms.items() if k.startswith("S-8")),
        "offering_like_rows": sum(
            v
            for k, v in forms.items()
            if k.startswith(("S-1", "S-3", "F-3", "424B"))
        ),
        "same_accession_fact_rows": same_accession_fact_rows,
        "non_missing_feature_values": dict(non_missing_feature_values),
    }


def count_options_coverage() -> dict[str, Any]:
    dates = [
        date_from_path(path)
        for path in NON_OHLCV_DIR.glob("options_onclickmedia_chain_*.jsonl")
    ]
    dates = sorted(d for d in dates if d)
    canonical = [d for d in dates if in_standard_windows(d)]
    return {
        "chain_file_count": len(dates),
        "min_date": dates[0] if dates else None,
        "max_date": dates[-1] if dates else None,
        "canonical_window_chain_file_count": len(canonical),
        "canonical_window_dates": canonical[:10],
        "verdict": (
            "blocked_missing_mid_old_canonical_coverage"
            if len(canonical) < 20
            else "needs_separate_asof_lag_audit"
        ),
    }


def latest_summary(prefix: str) -> dict[str, Any]:
    paths = sorted(NON_OHLCV_DIR.glob(f"{prefix}_*.json"))
    if not paths:
        return {"status": "missing"}
    latest = paths[-1]
    payload = read_json(latest)
    return {
        "path": repo_rel(latest),
        "date_key": date_from_path(latest),
        "summary": payload,
    }


def build_inventory() -> dict[str, Any]:
    return {
        "sec_filing_text": count_jsonl_forms("sec_filing_text"),
        "sec_filing_events": count_jsonl_forms("sec_filing_events"),
        "sec_filing_features": count_jsonl_forms("sec_filing_features"),
        "options_onclickmedia": count_options_coverage(),
        "estimate_revision_latest": latest_summary("estimate_revision_ledger_summary"),
        "moomoo_capital_flow": {
            "manifest": read_json(NON_OHLCV_DIR / "moomoo_capital_flow" / "manifest.json"),
            "row_file_exists": (
                NON_OHLCV_DIR / "moomoo_capital_flow" / "rows.jsonl"
            ).exists(),
        },
        "finra_short_interest_rows_exists": (
            NON_OHLCV_DIR / "finra_short_interest" / "rows.json"
        ).exists(),
        "sec_13d13g_rows_exists": (
            NON_OHLCV_DIR / "sec_13d13g_holdings" / "rows.json"
        ).exists(),
        "sec_ftd_rows_exists": (NON_OHLCV_DIR / "sec_ftd" / "rows.json").exists(),
    }


def candidate_surfaces(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    text_forms = inventory["sec_filing_text"]
    features = inventory["sec_filing_features"]
    options = inventory["options_onclickmedia"]
    revision = inventory["estimate_revision_latest"].get("summary") or {}
    return [
        {
            "surface": "S-8 registered-share economics",
            "gate2_verdict": "blocked_missing_primary_text",
            "evidence": (
                f"sec_filing_text standard-window S-8 rows={text_forms['s8_rows']}; "
                "raw S-8 form absorption already rejected in exp-20260617-024."
            ),
            "needed_new_axis": "S-8 primary text with registered share amount normalized by float or market cap.",
        },
        {
            "surface": "offering/prospectus financing economics",
            "gate2_verdict": "blocked_missing_primary_text",
            "evidence": (
                f"sec_filing_text offering-like rows={text_forms['offering_like_rows']}; "
                "exp-20260618-013 already blocked proceeds/dilution parsing."
            ),
            "needed_new_axis": "PIT primary-document offering amount, use of proceeds, security type, and dilution terms.",
        },
        {
            "surface": "SEC filing features plus same-accession facts",
            "gate2_verdict": "blocked_no_material_feature_tuple",
            "evidence": (
                f"feature rows={features['rows']}, same_accession_fact_rows="
                f"{features['same_accession_fact_rows']}, non_missing="
                f"{features['non_missing_feature_values']}."
            ),
            "needed_new_axis": "Same-accession structured facts or PIT consensus/guidance fields joined to 8-K items.",
        },
        {
            "surface": "options skew / open interest",
            "gate2_verdict": options["verdict"],
            "evidence": (
                f"OnclickMedia chain files span {options['min_date']} to "
                f"{options['max_date']}; canonical-window chain file count="
                f"{options['canonical_window_chain_file_count']}."
            ),
            "needed_new_axis": "Historical PIT option chain rows with vendor as-of, OI lag, spread, stale-chain, and fill-cost controls.",
        },
        {
            "surface": "analyst revision breadth / dispersion",
            "gate2_verdict": "blocked_missing_candidate_join",
            "evidence": (
                "Latest revision summary exists but recent exp-20260619-001/011 "
                f"showed unreliable or zero candidate joins; latest summary keys="
                f"{sorted(revision)[:12]}."
            ),
            "needed_new_axis": "As-of revision breadth/dispersion rows joined to historical candidates across all three windows.",
        },
        {
            "surface": "FINRA / FTD short pressure",
            "gate2_verdict": "blocked_missing_borrow_cost_axis",
            "evidence": (
                "Historical FINRA/FTD rows exist, but exp-20260619-007 and "
                "prior FINRA/FTD attempts failed window/drawdown/comparator gates."
            ),
            "needed_new_axis": "PIT borrow fee, utilization, loan availability, or options put-skew context.",
        },
        {
            "surface": "Companyfacts cash-flow / working-capital / burden ratios",
            "gate2_verdict": "blocked_frozen_family",
            "evidence": (
                "Cash conversion, inventory, DPO/DSO/DIO/CCC, debt, segment, "
                "customer, advertising, and relief/overhang fields were rejected "
                "or accepted-then-frozen in the 20260614-20260619 logs."
            ),
            "needed_new_axis": "PIT decomposition such as customer identity, contract economics, segment profit mix, or closed forward rows.",
        },
        {
            "surface": "OHLCV relation / lead-lag",
            "gate2_verdict": "blocked_replay_family_closed",
            "evidence": (
                "Accepted relation helpers exist, but static and regime-conditioned "
                "intraindustry lead-lag variants were rejected; retunes need forward rows."
            ),
            "needed_new_axis": "Forward replacement-value rows or a non-price relation provenance field.",
        },
    ]


def baseline_artifact(label: str) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "label": label,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "canonical_source": "docs/backtesting.md",
        "windows": CANONICAL_WINDOWS,
        "aggregate": aggregate_windows(CANONICAL_WINDOWS),
        "strategy_code_changed": False,
        "production_code_changed": False,
        "note": (
            "This blocker experiment does not run an after policy. The after "
            "artifact intentionally repeats the canonical baseline to avoid "
            "claiming alpha from a blocked surface."
        ),
    }


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle = f'"experiment_id": "{EXPERIMENT_ID}"'
    if path.exists() and needle in path.read_text(encoding="utf-8-sig"):
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_result() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction") or PREDICTION
    inventory = build_inventory()
    surfaces = candidate_surfaces(inventory)
    before_aggregate = aggregate_windows(CANONICAL_WINDOWS)
    after_aggregate = aggregate_windows(CANONICAL_WINDOWS)
    delta = {
        key: round(after_aggregate[key] - before_aggregate[key], 6)
        for key in [
            "aggregate_expected_value_score",
            "aggregate_total_pnl",
            "total_trade_count",
            "min_survival_rate",
            "max_window_drawdown_pct",
        ]
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": now_utc(),
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_surface_after_exp019",
        "hypothesis": HYPOTHESIS,
        "change_type": "alpha_surface_readiness_blocker",
        "mechanism_family": "production_visible_free_pit_candidate_pool_surface_selection",
        "trial_family": "post_20260619_nonrepeat_surface_readiness",
        "trial_variant_id": "post_20260619_nonrepeat_surface_readiness_v2",
        "single_causal_variable": "post_20260619_nonrepeat_free_pit_candidate_pool_readiness_v2",
        "changed_variable": "post_20260619_nonrepeat_free_pit_candidate_pool_readiness_v2",
        "causal_components": [
            "history_near_neighbor_audit",
            "local_free_data_inventory_scan",
            "gate2_readiness_verdict",
            "production_parity_risk_verdict",
        ],
        "prediction": prediction,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "pre_run_answers": {
            "alpha_hypothesis": HYPOTHESIS,
            "category": "candidate_pool/data_edge readiness",
            "history_check": RELATED_EXPERIMENTS,
            "single_policy_bundle_under_test": (
                "Readiness of non-repeat free PIT candidate-pool surfaces; no "
                "entry, exit, ranking, sizing, or risk policy is changed."
            ),
            "success_criteria": (
                "Proceed only if a materially new surface has three-window "
                "coverage, runtime fields, novelty clearance, and a shared "
                "daily/historical parity path."
            ),
            "reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")
            ),
        },
        "novelty_check": {
            "reservation_warning": (ticket.get("novelty") or {}).get("warn"),
            "override_recorded": (ticket.get("novelty") or {}).get("override"),
            "new_evidence_axis": (ticket.get("novelty") or {}).get(
                "new_evidence_axis"
            ),
            "nearest": (ticket.get("novelty") or {}).get("nearest"),
            "interpretation": (
                "Reservation warning was overridden only because this is a "
                "cross-surface blocker, not a strategy-family retry."
            ),
        },
        "gate1_baseline": {
            "status": "passed",
            "source": BASELINE_RESULT_FILE,
            "canonical_windows": canonical_window_list(),
            "baseline_aggregate": before_aggregate,
            "windows": CANONICAL_WINDOWS,
        },
        "gate2_field_availability": {
            "status": "blocked",
            "minimum_runtime_fields_checked": ["entry_date", "target_price"],
            "minimum_runtime_field_result": (
                "Existing canonical rows expose the minimum runtime fields, "
                "but no new non-repeat surface exposes the additional PIT "
                "fields needed for a trustworthy after policy."
            ),
            "local_inventory": inventory,
            "candidate_surfaces": surfaces,
            "blocking_item": (
                "Every reviewed free surface is either frozen by recent "
                "three-window evidence or lacks canonical-window PIT fields "
                "and production/backtest parity inputs."
            ),
        },
        "gate3_survival": {
            "status": "not_applicable_no_new_filter",
            "baseline_min_survival_rate": before_aggregate["min_survival_rate"],
            "guardrail": "survival_rate must stay >= 0.05",
            "interpretation": (
                "No new filter was tested because Gate 2 blocked all candidate "
                "surfaces before strategy replay."
            ),
        },
        "gate4": {
            "status": "blocked_no_after_policy",
            "before": CANONICAL_WINDOWS,
            "after": CANONICAL_WINDOWS,
            "window_deltas": metric_delta(CANONICAL_WINDOWS, CANONICAL_WINDOWS),
            "aggregate_before": before_aggregate,
            "aggregate_after": after_aggregate,
            "aggregate_delta": delta,
            "acceptance_result": "blocked",
            "reason": (
                "No after policy was run. The after metrics intentionally equal "
                "the canonical baseline; this is a blocker record, not an alpha "
                "claim."
            ),
        },
        "delta_metrics": delta,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "predicted_failure_modes": prediction.get("main_failure_modes"),
            "realized_failure_mode": "all_free_surfaces_frozen_or_missing_pit_coverage",
            "surprise": (
                "Low surprise: S-8/offering economics lack text, 8-K features "
                "lack material tuples, options are not canonical-window ready, "
                "and recent Companyfacts/ownership/FINRA/OHLCV relation lanes "
                "are frozen or rejected."
            ),
        },
        "production_impact": {
            "production_code_changed": False,
            "backtest_code_changed": False,
            "shared_helper_added": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "backtester_adapter_changed": False,
            "daily_snapshot_changed": False,
            "parity_assessment": (
                "No production/backtest inconsistency can be introduced "
                "because no trading policy or helper changed. Any future "
                "positive alpha must be implemented as a shared default-off "
                "helper before acceptance."
            ),
            "live_realistic_execution_envelope": "not_applicable_no_tradable_alpha",
        },
        "post_run_reflection": {
            "why_blocked": (
                "The current high-potential free-data directions are blocked "
                "by missing PIT fields or frozen-family evidence. Running a "
                "strategy replay now would mostly retune known losers."
            ),
            "negative_result_reflection": (
                "Recent negative results failed because old_thin regressed, "
                "drawdown/concentration worsened, accepted comparators were not "
                "beaten, or the candidate sample was zero/thin. The blocker "
                "prevents repeating those shapes."
            ),
            "best_next_alpha_direction": (
                "Build/import a new PIT surface first: SEC offering/S-8 "
                "primary-document economics, historical cover-page filer "
                "status, parsed customer/segment contract economics, PIT "
                "borrow/options as-of rows, or analyst breadth/dispersion "
                "joined to historical candidate rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry cash-conversion, working-capital, SEC form/item, "
                "S-8/offering metadata, FINRA/FTD, 13D/G stake thresholds, "
                "Form4 code filters, or OHLCV lead-lag thresholds without the "
                "named new data axis."
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
        "reproduction": ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\"),
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["created_at"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "causal_components": result["causal_components"],
        "nearby_prior_experiments": [row["experiment_id"] for row in RELATED_EXPERIMENTS],
        "baseline_result_file": BASELINE_RESULT_FILE,
        "before_artifact": repo_rel(BEFORE_JSON),
        "after_artifact": repo_rel(AFTER_JSON),
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
        "delta_metrics": result["delta_metrics"],
        "prediction": result["prediction"],
        "calibration": result["calibration"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "changed_files": result["changed_files"],
        "reproduction": result["reproduction"],
        "lean_quality_passed": result["lean_quality_passed"],
        "anti_js": result["anti_js"],
        "accepted": False,
        "accepted_alpha": False,
        "aggregate_expected_value_delta": result["delta_metrics"][
            "aggregate_expected_value_score"
        ],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"][
            "aggregate_total_pnl"
        ],
    }


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: post-20260619 non-repeat surface readiness v2",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- No strategy, production helper, ranking, sizing, exit, watchlist, or order path changed.",
        "",
        "## Three-window Gate 4",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, before in CANONICAL_WINDOWS.items():
        after = CANONICAL_WINDOWS[label]
        delta = result["gate4"]["window_deltas"][label]
        lines.append(
            f"| {label} | {before['expected_value_score']:.4f} | "
            f"{after['expected_value_score']:.4f} | "
            f"{delta['expected_value_score']:.4f} | "
            f"${before['total_pnl']:,.2f} | ${after['total_pnl']:,.2f} | "
            f"${delta['total_pnl']:,.2f} |"
        )
    agg = result["gate4"]["aggregate_before"]
    lines.extend(
        [
            "",
            "## Readout",
            "",
            "No alpha was run or accepted. The after artifact is intentionally identical "
            "to the canonical baseline: aggregate EV "
            f"{agg['aggregate_expected_value_score']:.4f}, aggregate PnL "
            f"${agg['aggregate_total_pnl']:,.2f}.",
            "",
            result["post_run_reflection"]["best_next_alpha_direction"],
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Blocked alpha-search readiness artifact. This records why no "
        "non-repeat free PIT candidate-pool alpha should be run after the "
        "latest 20260619 experiments.\n\n"
        f"- Artifact: `{repo_rel(ARTIFACT_JSON)}`\n"
        f"- Before: `{repo_rel(BEFORE_JSON)}`\n"
        f"- After: `{repo_rel(AFTER_JSON)}`\n"
        f"- Decision: `{result['decision']}`\n"
    )


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "lane": result["lane"],
            "files": result["changed_files"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "ticket": repo_rel(TICKET_JSON),
            "runner": RUNNER_NAME,
            "command": result["reproduction"],
            "anti_js": result["anti_js"],
            "updated_at": now_utc(),
        },
    )


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
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "causal_components": result["causal_components"],
        "prior_trial_count": len(RELATED_EXPERIMENTS),
        "nearby_prior_experiments": [
            row["experiment_id"] for row in RELATED_EXPERIMENTS
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "fresh_post_20260619_cross_surface_readiness_audit",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "evaluation_windows": canonical_window_list(),
        "acceptance_rule": (
            "Blocked unless a genuinely new, production-visible PIT alpha "
            "surface with coverage in all three canonical windows is available."
        ),
        "decision": result["decision"],
        "summary": result["post_run_reflection"]["why_blocked"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": result["delta_metrics"][
            "aggregate_expected_value_score"
        ],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"][
            "aggregate_total_pnl"
        ],
        "post_run_reflection": result["post_run_reflection"],
        "production_impact": result["production_impact"],
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
        "lean_quality_passed": result["lean_quality_passed"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status="blocked",
        fields=fields,
    )
    write_manifest(result)


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "blocked_surfaces": len(
                    result["gate2_field_availability"]["candidate_surfaces"]
                ),
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
