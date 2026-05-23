"""exp-20260523-010: BTC miner/HPC specialist core-pool scout.

Alpha search on one causal variable: add the production-governed
`btc_miner_hpc` specialist / full-history cohort to the core replay universe.
This uses the canonical-window observation-universe OHLCV snapshots from
exp-20260519-029, keeps all signal/ranking/sizing/exit rules fixed, and does
not change production watchlists or live orders.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260523_009_ai_power_datacenter_core_pool as base


EXPERIMENT_ID = "exp-20260523-010"
STEM = "btc_miner_hpc_core_pool"
TRIAL_FAMILY = "governed_btc_miner_hpc_candidate_pool"
TARGET_THEME = "btc_miner_hpc"
TARGET_SEGMENT = None
SOURCE_UNIVERSE_STATE = base.SOURCE_UNIVERSE_STATE
SOURCE_OHLCV_EXPERIMENT_ID = base.SOURCE_OHLCV_EXPERIMENT_ID

TARGET_SECTOR_MAP = {
    "CIFR": "Financials",
    "CORZ": "Financials",
    "IREN": "Financials",
    "MARA": "Financials",
    "RIOT": "Financials",
    "WULF": "Financials",
}

OUT_DIR = base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = base.REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = base.REPO_ROOT / "docs" / "experiment_log.jsonl"
WINDOWS = base.WINDOWS


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _target_universe() -> dict[str, Any]:
    state = base._load_json(SOURCE_UNIVERSE_STATE)
    core = {str(ticker).upper() for ticker in state.get("core_trade_universe") or []}
    records = state.get("records") or {}
    selected: list[str] = []
    selected_records: dict[str, Any] = {}
    excluded: dict[str, list[str]] = {}

    for ticker, record in sorted(records.items()):
        if not isinstance(record, dict):
            continue
        symbol = str(ticker).upper()
        reasons: list[str] = []
        if record.get("theme") != TARGET_THEME:
            reasons.append("not_target_theme")
        if record.get("status") != "specialist":
            reasons.append("not_specialist_status")
        if record.get("history_class") != "full_history":
            reasons.append("not_full_history")
        if record.get("liquidity_tier") not in {"watch", "ok"}:
            reasons.append("liquidity_not_watch_or_ok")
        if symbol in core:
            reasons.append("already_core")

        if reasons:
            if record.get("theme") == TARGET_THEME:
                excluded[symbol] = reasons
            continue

        selected.append(symbol)
        selected_records[symbol] = {
            key: record.get(key)
            for key in (
                "status",
                "theme",
                "theme_segment",
                "liquidity_tier",
                "history_class",
                "first_trade_allowed_as_of",
                "max_capital_scalar",
                "max_risk_scalar",
                "requires_event_guard",
                "event_guard_profile",
                "pilot_sleeve",
                "source",
                "source_reason",
                "notes",
            )
        }
        selected_records[symbol]["sector_patch"] = TARGET_SECTOR_MAP.get(symbol, "Unknown")

    return {
        "source_universe_state": _repo_rel(SOURCE_UNIVERSE_STATE),
        "as_of": state.get("as_of"),
        "selection_rule": (
            "records.theme == btc_miner_hpc and status == specialist and "
            "history_class == full_history and liquidity_tier in {watch, ok} "
            "and not already in core"
        ),
        "target_tickers": selected,
        "target_records": selected_records,
        "excluded_related_records": excluded,
    }


def _apply_btc_overrides() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TARGET_THEME = TARGET_THEME
    base.TARGET_SEGMENT = TARGET_SEGMENT
    base.TARGET_SECTOR_MAP = TARGET_SECTOR_MAP
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base._target_universe = _target_universe


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "positive_replay_deferred_requires_shared_universe"
        if gate4_passed
        else "rejected_btc_miner_hpc_core_pool"
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Production-governed BTC miner/HPC specialist names may add a "
                "distinct high-convexity candidate-pool alpha when the existing "
                "trend/breakout engine already finds valid setups. This is tested "
                "as a standalone specialist cohort because prior broad AI-infra "
                "basket tests mixed miners with power, optical, and compute names."
            ),
            "change_type": "candidate_pool_shadow",
            "changed_variable": "btc_miner_hpc_core_universe_membership",
            "trial_family": TRIAL_FAMILY,
            "prior_trial_count": 2,
            "nearby_prior_experiments": [
                "exp-20260501-008",
                "exp-20260519-011",
                "exp-20260519-014",
                "exp-20260523-003",
                "exp-20260523-009",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "canonical_aligned_observation_universe_ohlcv_current_governed_specialist_records",
        }
    )
    payload["parameters"].update(
        {
            "target_theme": TARGET_THEME,
            "target_segment": TARGET_SEGMENT,
            "target_sector_map": TARGET_SECTOR_MAP,
            "source_ohlcv_experiment_id": SOURCE_OHLCV_EXPERIMENT_ID,
            "locked_variables": [
                "signal rules",
                "ranking",
                "sizing policy",
                "exits",
                "portfolio heat",
                "slot rules",
                "LLM/news replay",
                "all non-target ticker membership",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: governed BTC miner/HPC specialist names may "
            "add replacement-value opportunities as a distinct high-beta specialist "
            "cohort rather than as part of noisy broad AI-infra expansion."
        ),
        "2_history_check": {
            "exp-20260501-008": (
                "Broad user AI infra expansion included BTC miners and was "
                "observed-positive/deferred, but it mixed many themes and was not "
                "promotion-safe."
            ),
            "exp-20260519-011": (
                "History-covered governed non-core expansion was positive in aggregate "
                "but rejected because broad variants regressed old_thin and failed "
                "replacement-value gates."
            ),
            "exp-20260519-014": (
                "Pilot segment shadow did not isolate BTC miner/HPC; it focused on "
                "APLD/BE/INTC/LITE pilot segments."
            ),
            "exp-20260523-003": "AI optical-connectivity current-universe cohort was rejected.",
            "exp-20260523-009": "AI power/datacenter cohort was rejected.",
        },
        "3_single_causal_variable": (
            "Membership of one production-visible BTC miner/HPC specialist cohort "
            "in the replay core universe."
        ),
        "4_acceptance_standard": (
            "Canonical three-window before/after with positive aggregate EV/PnL, "
            "at least two improved windows, zero EV-regressed windows, >=6 target "
            "trades across >=2 windows, drawdown drift <=0.5pp, survival >=5%, "
            "and target concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260523_010_btc_miner_hpc_core_pool.py"
        ),
    }
    payload["production_impact"].update(
        {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "promotion_requirement": (
                "If accepted later, implement through shared universe governance, "
                "sector taxonomy, and specialist risk constraints visible to both "
                "run.py and backtester.py, add parity coverage, then rerun canonical "
                "windows."
            ),
        }
    )
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking due sparse attribution; skipped SEC/event "
        "near-neighbor scalars after recent rejected no-5.03, reaction, and "
        "confirmation variants; skipped state-surface and broad-market profile "
        "retunes due strict gates. This tests a governed specialist candidate-pool "
        "cohort instead of adding arbitrary tickers."
    )
    payload["known_risks"] = [
        "BTC miner/HPC records are specialist/watch-liquidity names, so live promotion would need a separate sleeve/risk constraint rather than raw core admission.",
        "The cohort came from earlier AI-infra expansion research, so multiple-testing risk is high.",
        "Sector taxonomy is patched in replay only and would need shared implementation if promoted.",
    ]
    payload["interpretation"] = (
        "The cohort cleared replay gates but is not production-enabled; implement "
        "shared specialist universe/taxonomy/risk constraints before any live behavior."
        if gate4_passed
        else "The cohort did not clear the direct core-pool gate; keep BTC miner/HPC names in specialist observation paths."
    )
    payload["rejection_reason"] = (
        None
        if gate4_passed
        else (
            "BTC miner/HPC specialist cohort did not clear the direct candidate-pool "
            "gate: requires positive aggregate EV/PnL, at least two improved windows, "
            "no EV-regressed window, >=6 target trades across >=2 windows, drawdown "
            "drift <=0.5pp, survival >=5%, and target positive-PnL concentration "
            "within guardrails."
        )
    )
    payload["next_evidence_needed"] = (
        "Implement shared specialist universe/taxonomy/risk constraints and rerun canonical replay before promotion."
        if gate4_passed
        else "Collect forward BTC miner/HPC replacement-value outcomes or a BTC/power-regime control field before retrying this cohort."
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(EXPERIMENT_LOG),
    ]
    payload["anti_js"] = "No JavaScript was used."
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {target_trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                target_trades=len(payload["target_trades_by_window"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} BTC Miner/HPC Specialist Core-Pool Scout",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: add the governed BTC miner/HPC specialist cohort to the core replay universe.",
            "",
            "## Trial Accounting",
            "",
            f"- trial_family: `{payload['trial_family']}`",
            f"- changed_variable: `{payload['changed_variable']}`",
            f"- prior_trial_count: `{payload['prior_trial_count']}`",
            f"- multiple_testing_risk_bucket: `{payload['multiple_testing_risk_bucket']}`",
            f"- new_evidence_type: `{payload['new_evidence_type']}`",
            "",
            "## Target Cohort",
            "",
            ", ".join(f"`{ticker}`" for ticker in payload["parameters"]["target_tickers"]),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only. No production watchlist, shared policy, run adapter, or order path changed. A positive replay would still need shared specialist universe, sector taxonomy, risk constraints, and parity tests before any live/default behavior changes.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "BTC miner/HPC specialist core-pool scout",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _apply_btc_overrides()
    payload = _patch_payload(base.build_payload())
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4": payload["gate4"],
                "target_trade_summary": payload["target_trade_summary"],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
