"""exp-20260524-034: Compute-memory/storage governed-risk admission scout.

This alpha experiment follows the positive but rejected exp-20260524-033
compute-memory/storage candidate-pool result. The changed variable is a
governed-risk admission policy: the same current universe-state cohort is
allowed into replay, but each target ticker is capped by its production-visible
``max_risk_scalar`` from ``universe_state_20260522.json``.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260524_033_compute_memory_storage_core_pool as prior
import portfolio_engine


EXPERIMENT_ID = "exp-20260524-034"
STEM = "compute_memory_storage_governed_risk_cap"
TRIAL_FAMILY = "governed_compute_memory_storage_risk_capped_candidate_pool"
CHANGED_VARIABLE = "compute_memory_storage_governed_risk_capped_membership"

OUT_DIR = prior.base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = prior.base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = prior.base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    prior.base.REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = prior.base.REPO_ROOT / "docs" / "experiment_log.jsonl"


def _repo_rel(path: Path | str) -> str:
    return prior._repo_rel(path)


def _apply_experiment_overrides() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.ARTIFACT_MD = ARTIFACT_MD
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior._apply_compute_memory_overrides()


def _target_risk_scalars() -> dict[str, float]:
    target_universe = prior._target_universe()
    records = target_universe.get("target_records") or {}
    scalars: dict[str, float] = {}
    for ticker, record in records.items():
        value = 0.0
        if isinstance(record, dict):
            try:
                value = float(record.get("max_risk_scalar") or 0.0)
            except (TypeError, ValueError):
                value = 0.0
        scalars[str(ticker).upper()] = max(0.0, min(1.0, value))
    return scalars


@contextmanager
def _governed_risk_size_patch(risk_scalars: dict[str, float]):
    original = portfolio_engine.size_signals

    def patched_size_signals(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            ticker = str(sig.get("ticker") or "").upper()
            if ticker not in risk_scalars:
                continue
            sizing = sig.get("sizing") or {}
            old_shares = int(sizing.get("shares_to_buy") or 0)
            if old_shares <= 0:
                continue
            scalar = risk_scalars[ticker]
            new_shares = int(math.floor(old_shares * scalar))
            if new_shares >= old_shares:
                continue

            entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
            net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
            sizing["compute_memory_governed_risk_cap_baseline_shares"] = old_shares
            sizing["compute_memory_governed_risk_cap_new_shares"] = new_shares
            sizing["compute_memory_governed_risk_scalar_applied"] = scalar
            sizing["shares_to_buy"] = new_shares
            sizing["risk_amount_usd"] = round(new_shares * net_risk_per_share, 2)
            sizing["position_value_usd"] = round(new_shares * entry, 2)
            sizing["position_pct_of_portfolio"] = (
                round((new_shares * entry) / portfolio_value, 4)
                if portfolio_value
                else 0.0
            )
            sizing["risk_pct"] = (
                round((new_shares * net_risk_per_share) / portfolio_value, 6)
                if portfolio_value
                else 0.0
            )
            sig["sizing"] = sizing
        return sized

    portfolio_engine.size_signals = patched_size_signals
    try:
        yield
    finally:
        portfolio_engine.size_signals = original


def _patch_payload(payload: dict[str, Any], risk_scalars: dict[str, float]) -> dict[str, Any]:
    payload = prior._patch_payload(payload)
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "accepted_compute_memory_storage_governed_risk_cap"
        if gate4_passed
        else "rejected_compute_memory_storage_governed_risk_cap"
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "The compute-memory/storage cohort showed real candidate-pool alpha "
                "in exp-20260524-033, but raw core admission failed drawdown and "
                "concentration guards. Applying the existing production-visible "
                "universe governance risk caps may preserve replacement value while "
                "controlling the tail risk that blocked promotion."
            ),
            "change_type": "candidate_pool_governed_risk_admission",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "prior_trial_count": 6,
            "nearby_prior_experiments": [
                "exp-20260519-014",
                "exp-20260523-003",
                "exp-20260523-009",
                "exp-20260524-020",
                "exp-20260524-028",
                "exp-20260524-033",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": (
                "production_visible_universe_governance_risk_caps_applied_to_"
                "positive_compute_memory_storage_candidate_pool"
            ),
            "rejection_reason": None
            if gate4_passed
            else (
                "Governed-risk compute-memory/storage admission did not clear "
                "the same three-window candidate-pool gate."
            ),
            "interpretation": (
                "Governed risk caps made compute-memory/storage admission pass the "
                "three-window replay gate, but live promotion still requires a shared "
                "universe/risk policy and parity tests."
                if gate4_passed
                else (
                    "The production-visible governance caps did not make the "
                    "compute-memory/storage cohort promotion-grade; keep the cohort "
                    "in pilot/research observation until forward replacement value "
                    "or a stronger quality field arrives."
                )
            ),
            "next_evidence_needed": (
                "Implement shared universe/risk governance and rerun canonical replay "
                "before any live/default behavior changes."
                if gate4_passed
                else (
                    "Forward compute-memory/storage replacement-value outcomes or a "
                    "pre-specified memory/storage quality field that reduces "
                    "concentration without simply tuning ticker weights."
                )
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"].update(
        {
            "governed_risk_scalars": risk_scalars,
            "governed_risk_scalar_source": (
                "data/daily/universe/universe_state_20260522.json "
                "records[*].max_risk_scalar"
            ),
            "locked_variables": [
                "signal rules",
                "ranking",
                "exits",
                "portfolio heat",
                "slot rules",
                "LLM/news replay",
                "all non-target ticker membership",
                "target cohort definition from exp-20260524-033",
            ],
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool plus risk allocation: governed "
            "compute-memory/storage names may be useful only when admitted with "
            "their existing production-visible risk caps."
        ),
        "2_history_check": {
            "exp-20260524-033": (
                "Raw INTC/WDC/STX core admission improved all three windows but "
                "failed drawdown and concentration guards."
            ),
            "exp-20260524-020": (
                "Residual AI-infra APLD/INTC/WDC failed aggregate EV and "
                "concentration guards."
            ),
            "exp-20260523-009": (
                "AI power/datacenter direct admission was rejected and did not "
                "test compute-memory/storage risk-capped governance."
            ),
            "exp-20260524-028": (
                "Raw alpha_score monotonicity failed, so this run does not alter "
                "ranking."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same canonical three-window before/after protocol and candidate-pool "
            "Gate 4 used by exp-20260524-033: positive aggregate EV/PnL, at least "
            "two improved windows, no EV-regressed window, >=6 target trades across "
            ">=2 windows, drawdown drift <=0.5pp, survival >=5%, and target "
            "concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260524_034_compute_memory_storage_governed_risk_cap.py"
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
                "sector taxonomy, and a shared risk-cap policy visible to run.py "
                "and backtester.py before any live/default behavior changes."
            ),
        }
    )
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking because replay-safe attribution remains sparse; "
        "skipped SEC/event/state-surface/broad-market scalar retunes due recent "
        "anti-repeat gates; skipped raw candidate-pool retry because exp-20260524-033 "
        "already proved raw compute-memory admission is not promotion-safe."
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Compute-Memory/Storage Governed-Risk Admission",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: admit the governed compute-memory/storage cohort only with existing universe-state risk caps.",
            "",
            "## Risk Caps",
            "",
            "```json",
            json.dumps(payload["parameters"]["governed_risk_scalars"], indent=2, sort_keys=True),
            "```",
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
            "Replay-only. No production watchlist, shared policy, run adapter, or order path changed. Promotion would require shared universe governance, shared risk-cap logic, and parity tests.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    prior.base._write_json(OUT_JSON, payload)
    prior.base._write_json(LOG_JSON, payload)
    prior.base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Compute-memory/storage governed-risk admission",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    prior.base._write_text(ARTIFACT_MD, _build_report(payload))
    prior.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _apply_experiment_overrides()
    risk_scalars = _target_risk_scalars()
    with _governed_risk_size_patch(risk_scalars):
        payload = _patch_payload(prior.base.build_payload(), risk_scalars)
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
                "risk_scalars": risk_scalars,
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
