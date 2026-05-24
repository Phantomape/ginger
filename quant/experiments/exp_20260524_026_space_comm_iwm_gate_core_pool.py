"""exp-20260524-026: Space communications IWM-gated core-pool scout.

Alpha search on one causal variable: the governed full-history Space
communications / satcom cohort may only participate in the replay candidate
pool when IWM 20-day momentum leads SPY 20-day momentum. This tests whether
the rejected all-state cohort from exp-20260524-025 becomes robust when the
existing production-visible small-cap risk-appetite state confirms.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260524_025_space_comm_core_pool as prior


EXPERIMENT_ID = "exp-20260524-026"
STEM = "space_comm_iwm_gate_core_pool"
TRIAL_FAMILY = "governed_space_comm_iwm_gate_candidate_pool"
CHANGED_VARIABLE = "space_comm_iwm_leader_core_universe_membership"
TARGET_TICKERS = prior.TARGET_TICKERS
TARGET_SECTOR_MAP = prior.TARGET_SECTOR_MAP
SOURCE_OHLCV_EXPERIMENT_ID = prior.SOURCE_OHLCV_EXPERIMENT_ID
WINDOWS = prior.WINDOWS

OUT_DIR = prior.base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = prior.base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = prior.base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    prior.base.REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = prior.base.REPO_ROOT / "docs" / "experiment_log.jsonl"

IWM_TICKER = "IWM"
SPY_TICKER = "SPY"
MOMENTUM_FIELD = "momentum_20d_pct"

_ORIGINAL_RUN_WINDOW = prior.base._run_window
_GATE_STATS_BY_WINDOW: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _repo_rel(path: Path | str) -> str:
    return prior.base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> Any:
    return prior.base._round(value, digits)


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _new_gate_stats() -> dict[str, Any]:
    return {
        "days_with_target_features": 0,
        "gate_open_days": 0,
        "gate_closed_days": 0,
        "missing_iwm_or_spy_momentum_days": 0,
        "target_feature_rows_removed": 0,
        "sample_gate_open_dates": [],
        "sample_gate_closed_dates": [],
    }


@contextmanager
def _space_comm_iwm_gate(stats: dict[str, Any]):
    import signal_engine

    original_generate = signal_engine.generate_signals
    target_set = set(TARGET_TICKERS)

    def gated_generate_signals(
        features_dict,
        market_context=None,
        enabled_strategies=None,
        breakout_max_pullback_from_52w_high=None,
    ):
        if not isinstance(features_dict, dict):
            return original_generate(
                features_dict,
                market_context=market_context,
                enabled_strategies=enabled_strategies,
                breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
            )

        target_present = sorted(target_set.intersection(features_dict))
        if not target_present:
            return original_generate(
                features_dict,
                market_context=market_context,
                enabled_strategies=enabled_strategies,
                breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
            )

        iwm_momentum = _as_float((features_dict.get(IWM_TICKER) or {}).get(MOMENTUM_FIELD))
        spy_momentum = _as_float((features_dict.get(SPY_TICKER) or {}).get(MOMENTUM_FIELD))
        date_key = None
        for features in features_dict.values():
            if isinstance(features, dict) and features.get("date"):
                date_key = str(features.get("date"))
                break

        stats["days_with_target_features"] += 1
        gate_open = (
            iwm_momentum is not None
            and spy_momentum is not None
            and iwm_momentum > spy_momentum
        )
        if gate_open:
            stats["gate_open_days"] += 1
            if date_key and len(stats["sample_gate_open_dates"]) < 5:
                stats["sample_gate_open_dates"].append(date_key)
            gated_features = features_dict
        else:
            stats["gate_closed_days"] += 1
            if iwm_momentum is None or spy_momentum is None:
                stats["missing_iwm_or_spy_momentum_days"] += 1
            if date_key and len(stats["sample_gate_closed_dates"]) < 5:
                stats["sample_gate_closed_dates"].append(date_key)
            stats["target_feature_rows_removed"] += len(target_present)
            gated_features = {
                ticker: features
                for ticker, features in features_dict.items()
                if ticker not in target_set
            }

        return original_generate(
            gated_features,
            market_context=market_context,
            enabled_strategies=enabled_strategies,
            breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
        )

    signal_engine.generate_signals = gated_generate_signals
    try:
        yield
    finally:
        signal_engine.generate_signals = original_generate


def _run_window_with_iwm_gate(label: str, universe: list[str]) -> dict[str, Any]:
    if not set(TARGET_TICKERS).intersection({str(ticker).upper() for ticker in universe}):
        return _ORIGINAL_RUN_WINDOW(label, universe)
    stats = _new_gate_stats()
    with _space_comm_iwm_gate(stats):
        result = _ORIGINAL_RUN_WINDOW(label, universe)
    _GATE_STATS_BY_WINDOW[label] = stats
    return result


def _target_universe() -> dict[str, Any]:
    payload = prior._target_universe()
    payload["selection_rule"] = (
        "target ticker in ASTS/GSAT/IRDM/SATS/VSAT; record is research or pilot, "
        "liquidity_tier in {ok, watch}, history_class full_history, not already in "
        "core, and candidate generation is enabled only when IWM 20d momentum > "
        "SPY 20d momentum"
    )
    payload["why_this_cohort_is_not_noise"] = (
        "These are governed universe-state Space communications records with full "
        "OHLCV history. The added state is the already accepted Space small-cap "
        "risk-appetite confirmation field, not a new noisy ticker list."
    )
    payload["admission_gate"] = {
        "field": MOMENTUM_FIELD,
        "condition": "IWM momentum_20d_pct > SPY momentum_20d_pct",
        "reference_tickers": [IWM_TICKER, SPY_TICKER],
    }
    return payload


def _apply_overrides() -> None:
    prior.base.EXPERIMENT_ID = EXPERIMENT_ID
    prior.base.STEM = STEM
    prior.base.TRIAL_FAMILY = TRIAL_FAMILY
    prior.base.TARGET_THEME = prior.TARGET_THEME
    prior.base.TARGET_SEGMENT = prior.TARGET_SEGMENT
    prior.base.TARGET_SECTOR_MAP = TARGET_SECTOR_MAP
    prior.base.OUT_DIR = OUT_DIR
    prior.base.OUT_JSON = OUT_JSON
    prior.base.LOG_JSON = LOG_JSON
    prior.base.TICKET_JSON = TICKET_JSON
    prior.base.ARTIFACT_MD = ARTIFACT_MD
    prior.base.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior.base._target_universe = _target_universe
    prior.base._run_window = _run_window_with_iwm_gate


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "positive_replay_deferred_requires_shared_iwm_gate"
        if gate4_passed
        else "rejected_space_comm_iwm_gate_core_pool"
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Governed Space communications and mature satcom names may add "
                "candidate-pool alpha only when small-cap risk appetite confirms "
                "the theme. Gating the exp-20260524-025 cohort by IWM 20d "
                "momentum leading SPY should retain the high-convexity windows "
                "while avoiding old-thin all-state satcom losses."
            ),
            "change_type": "candidate_pool_shadow",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "prior_trial_count": 7,
            "nearby_prior_experiments": [
                "exp-20260512-031",
                "exp-20260513-020",
                "exp-20260521-017",
                "exp-20260522-019",
                "exp-20260523-007",
                "exp-20260524-025",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": (
                "materially_different_production_visible_small_cap_risk_appetite_"
                "gate_on_governed_space_comm_candidate_pool"
            ),
        }
    )
    payload["parameters"].update(
        {
            "target_theme": prior.TARGET_THEME,
            "target_segment": prior.TARGET_SEGMENT,
            "target_sector_map": TARGET_SECTOR_MAP,
            "target_tickers": list(TARGET_TICKERS),
            "source_ohlcv_experiment_id": SOURCE_OHLCV_EXPERIMENT_ID,
            "iwm_gate": {
                "field": MOMENTUM_FIELD,
                "condition": "IWM momentum_20d_pct > SPY momentum_20d_pct",
                "target_tickers_removed_when_closed": list(TARGET_TICKERS),
            },
            "locked_variables": [
                "signal rules",
                "ranking",
                "sizing policy",
                "exits",
                "portfolio heat",
                "slot rules",
                "LLM/news replay",
                "all non-target ticker membership",
                "target ticker list",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: Space comm/satcom full-history records may be "
            "valid only when the small-cap tape confirms risk appetite, so "
            "IWM-leading-SPY should be the candidate-pool admission state."
        ),
        "2_history_check": {
            "exp-20260512-031": (
                "Accepted IWM>SPY as a Space official-catalyst risk-appetite "
                "state across all three windows."
            ),
            "exp-20260513-020": (
                "Accepted IWM plus peer-leader trend allocation inside Space; "
                "this test applies only the IWM leg to a different candidate pool."
            ),
            "exp-20260521-017": (
                "Rejected same-theme leader pool restriction; this does not use "
                "same-theme forward rows or prune the official catalyst pool."
            ),
            "exp-20260522-019": "Rejected forward-consistency scalar due sparse support.",
            "exp-20260523-007": "Rejected confidence/TQS disagreement scalar.",
            "exp-20260524-025": (
                "Rejected all-state Space comm core-pool admission because old_thin "
                "EV regressed despite strong aggregate PnL."
            ),
        },
        "3_single_causal_variable": (
            "The only changed causal variable is conditional membership of the "
            "same governed Space comm/satcom cohort when IWM 20d momentum exceeds "
            "SPY 20d momentum."
        ),
        "4_acceptance_standard": (
            "Canonical three-window before/after with positive aggregate EV/PnL, "
            "at least two improved windows, zero EV-regressed windows, >=6 target "
            "trades across >=2 windows, drawdown drift <=0.5pp, survival >=5%, "
            "and target concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260524_026_space_comm_iwm_gate_core_pool.py"
        ),
    }
    payload["gate2"]["runtime_fields"].extend(
        [
            "feature_layer momentum_20d_pct for IWM",
            "feature_layer momentum_20d_pct for SPY",
        ]
    )
    payload["gate2"]["iwm_gate"] = {
        "passed": all(
            stats.get("missing_iwm_or_spy_momentum_days", 0) == 0
            for stats in _GATE_STATS_BY_WINDOW.values()
        ),
        "by_window": _GATE_STATS_BY_WINDOW,
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
                "If accepted later, implement the IWM>SPY gate through shared "
                "Space universe/pilot governance and expose the same metadata in "
                "run.py before any live/default behavior changes."
            ),
        }
    )
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking because attribution remains sparse; skipped "
        "adjacent Space allocation scalars after recent strict-gate failures; "
        "skipped arbitrary ticker expansion. This tests a production-visible "
        "small-cap risk-appetite gate on the governed Space communications pool "
        "that just failed only because all-state admission was too broad."
    )
    payload["known_risks"] = [
        "Space remains observe-only/default-off; live promotion would need separate slot/risk governance.",
        "Candidate-pool expansion uses current governed universe records, so live/default promotion still needs PIT universe governance.",
        "Sector taxonomy for target names is patched in replay only and would need shared implementation if promoted.",
        "The IWM gate is a known Space state, but this candidate-pool application still has high multiple-testing risk.",
    ]
    payload["interpretation"] = (
        "The IWM-gated cohort cleared replay gates but is not production-enabled; implement shared Space universe/taxonomy/gate constraints and rerun canonical replay before promotion."
        if gate4_passed
        else "The IWM-gated Space communications cohort did not clear the direct candidate-pool gate; keep the cohort in governed research/observe-only paths."
    )
    payload["rejection_reason"] = (
        None
        if gate4_passed
        else (
            "IWM-gated Space communications core-pool admission did not clear "
            "the direct candidate-pool gate across the three canonical windows."
        )
    )
    payload["next_evidence_needed"] = (
        "Implement shared Space universe/taxonomy/IWM-gate constraints and rerun canonical replay before promotion."
        if gate4_passed
        else (
            "Collect forward Space communications replacement-value outcomes, "
            "or find a stronger production-visible event-quality field, before "
            "retrying this cohort."
        )
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
            f"# {EXPERIMENT_ID} Space Communications IWM-Gated Core-Pool Scout",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: allow the governed Space comm/satcom cohort into replay candidate generation only when IWM 20d momentum leads SPY.",
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
            "## IWM Gate",
            "",
            "```json",
            json.dumps(payload["gate2"]["iwm_gate"], indent=2, sort_keys=True),
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
            "Replay-only. No production watchlist, shared policy, run adapter, or order path changed. A positive replay still requires shared Space universe/taxonomy/IWM-gate constraints and parity tests before any live/default behavior changes.",
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
            "title": "Space comm IWM-gated core-pool scout",
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
    _apply_overrides()
    payload = _patch_payload(prior.base.build_payload())
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
                "iwm_gate": payload["gate2"]["iwm_gate"],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
