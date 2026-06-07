"""exp-20260607-019: volatility-relief stock-leadership shared adapter.

Alpha search with production consistency validation. This promotes the
positive exp-20260607-018 replay lead into a shared default-off paper adapter:
on days where VIXY sells off while SPY and QQQ confirm risk relief, admit the
two strongest liquid stock leaders as next-open, 10-trading-day paper
candidates.

The adapter is still paper-only. It changes no live/default orders, ranking,
sizing, exits, LLM/news path, or production watchlist behavior. No JavaScript is
used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import exp_20260607_018_volatility_relief_stock_leadership as previous
import volatility_relief_stock_leadership_paper_sleeve as shared_vol


framework = previous.framework

EXPERIMENT_ID = "exp-20260607-019"
STEM = "volatility_relief_stock_leadership_shared_adapter"
TRIAL_FAMILY = "volatility_relief_stock_leadership_shared_adapter"
TRIAL_VARIANT_ID = "volatility_relief_stock_leadership_shared_adapter_v1"
CHANGED_VARIABLE = "volatility_relief_stock_leadership_shared_default_off_adapter_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260607_019_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = shared_vol.BASE_NOTIONAL_USD
HOLD_DAYS = shared_vol.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = shared_vol.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = shared_vol.SAME_TICKER_COOLDOWN_DAYS

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.55,
    "expected_ev_delta": 0.5732,
    "expected_pnl_delta": 11934.79,
    "main_failure_modes": [
        "shared_helper_replay_drift",
        "broad_momentum_relabel",
        "window_regression",
        "drawdown_drift",
        "concentration_failed",
    ],
    "confidence_reason": (
        "exp-20260607-018 passed all three windows as a replay lead with "
        "+0.5732 aggregate EV and +$11,934.79 PnL; accepted macro relief "
        "leadership supports cross-asset risk-relief leadership, but shared "
        "paper promotion can still fail if helper semantics drift or the "
        "source is just broad beta."
    ),
    "recorded_at": "2026-06-07T16:41:59+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "default_off_shared_paper_adapter",
    "shared_policy_changed": True,
    "backtester_adapter_changed": True,
    "run_adapter_changed": True,
    "replay_only": False,
    "parity_test_added": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "requires_separate_activation": True,
    "live_realism_evaluated": False,
    "live_ready": False,
    "activation_envelope": {
        "intended_notional": "$4,000 default-off paper notional per candidate",
        "capital_cap": "paper-only; live cap requires separate activation envelope",
        "liquidity_slippage_model": "next-open entry slippage, target-side exit slippage, and ROUND_TRIP_COST_PCT included",
        "portfolio_displacement": "observe-only replacement value versus cash/core alternatives; no live displacement",
        "kill_switch": "forward gate blocks activation until closed trades, PnL, win-rate, and concentration checks pass",
        "order_semantics": "no live orders; trade_enabled=False",
    },
    "parity_note": (
        "The same shared adapter exposes VIXY/SPY/QQQ volatility-relief "
        "context, broad-market sector-known liquid stock universe, stock "
        "leadership fields, same-ticker core-overlap exclusion, top-2/day "
        "selection, next-open paper entry, 10-trading-day exit, costs, "
        "cooldown, and concentration controls in replay and daily production. "
        "The daily adapter is default-off and paper-only; it cannot alter "
        "candidate priority, sizing, watchlists, or orders without a separate "
        "activation experiment."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    return previous._load_window_snapshot(cfg=cfg, eligible_tickers=eligible_tickers)


def _candidate_universe(sector_entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "broad_market_sector_map",
        "tickers": sorted(sector_entries),
        "records": sector_entries,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    return shared_vol.candidate_rows_for_dates(
        rows_by_ticker=shared_vol.leader._normalise_ohlcv_by_ticker(snapshot),
        dates=dates,
        candidate_universe=_candidate_universe(sector_entries),
        core_entries_by_date=entries_by_date,
    )


def _select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return shared_vol.select_paper_trades(
        rows_by_ticker=shared_vol.leader._normalise_ohlcv_by_ticker(snapshot),
        candidates=candidates,
    )


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = previous._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "accepted_volatility_relief_stock_leadership_shared_default_off_adapter"
        if gate["passed"]
        else "rejected_volatility_relief_stock_leadership_shared_adapter"
    )
    gate["target_trade_count_min"] = MIN_TARGET_TRADES
    gate["target_window_count_min"] = MIN_TARGET_WINDOWS
    return gate


def _build_payload() -> dict[str, Any]:
    payload = previous._build_payload()
    aggregate = payload["delta_metrics"]["aggregate"]
    accepted = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Promote the positive VIXY volatility-relief stock leadership "
                "replay lead into a shared default-off paper adapter so "
                "historical replay and daily snapshots use the same "
                "production-visible OHLCV policy."
            ),
            "change_type": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "new_evidence_type": "shared_helper_reproduction_of_positive_replay_lead",
            "nearby_prior_experiments": [
                "exp-20260607-018",
                "exp-20260606-019",
                "exp-20260606-020",
                "exp-20260606-027",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "minimal",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "decision": payload["gate4"]["decision"],
            "status": "accepted" if accepted else "rejected",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The shared default-off helper reproduced the positive "
                "volatility-relief stock-leadership replay lead while exposing "
                "the same observe-only daily snapshot semantics."
                if accepted
                else (
                    "The shared helper failed to reproduce the replay lead or "
                    "failed Gate 4; do not promote or retune nearby VIXY/SPY/QQQ "
                    "thresholds on the frozen windows."
                )
            ),
            "rejection_reason": None if accepted else "; ".join(payload["gate4"]["failed_reasons"]),
            "post_run_reflection": {
                "why_result_happened": (
                    "Shared replay matched the exp-20260607-018 lead because "
                    "the alpha came from a distinct VIXY volatility-compression "
                    "state plus liquid stock leadership, not runner-only "
                    "implementation details."
                    if accepted
                    else (
                        "The shared adapter did not preserve the replay edge "
                        "after production-visible lifecycle constraints."
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping VIXY return, VIXY close-location, "
                    "SPY/QQQ relief, stock close-location, volume, ret20/ret60, "
                    "top-N, hold-day, cooldown, or paper notional thresholds on "
                    "these frozen windows."
                ),
                "new_evidence_required": (
                    "A future live activation requires closed forward "
                    "replacement-value rows from this shared adapter plus a "
                    "narrow activation-envelope Gate 1-4 with explicit capital "
                    "cap, liquidity/slippage, displacement, exposure, and kill "
                    "switch constraints."
                ),
            },
            "next_evidence_needed": (
                "Collect closed forward replacement-value rows from the shared "
                "daily default-off adapter; live activation is not ready."
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(REPO_ROOT / "quant" / "volatility_relief_stock_leadership_paper_sleeve.py"),
                _repo_rel(REPO_ROOT / "quant" / "test_volatility_relief_stock_leadership_paper_sleeve.py"),
                _repo_rel(REPO_ROOT / "quant" / "run.py"),
                _repo_rel(REPO_ROOT / "quant" / "default_off_alpha_attribution.py"),
                _repo_rel(REPO_ROOT / "quant" / "report_generator.py"),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(EXPERIMENT_LOG),
                _repo_rel(REGISTRY_JSON),
                _repo_rel(REPO_ROOT / "docs" / "production_backtest_parity.md"),
                _repo_rel(REPO_ROOT / "docs" / "alpha-optimization-playbook.md"),
                _repo_rel(REPO_ROOT / "docs" / "data_edge_context_layers.md"),
                _repo_rel(REPO_ROOT / "data" / "meta_research_report_latest.json"),
            ],
        }
    )
    payload["parameters"].update(
        {
            "shared_rule_version": shared_vol.RULE_VERSION,
            "source_rule_version": shared_vol.SOURCE_RULE_VERSION,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["gate_questions"]["3_single_causal_variable"] = CHANGED_VARIABLE
    payload["gate_questions"]["5_reproducibility"] = (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260607_019_volatility_relief_stock_leadership_shared_adapter.py"
    )
    payload["pre_run_questions"] = payload["gate_questions"]
    return payload


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = previous._build_log_record(payload)
    record.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "accepted": payload["gate4"]["passed"],
            "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "post_run_reflection": payload["post_run_reflection"],
        }
    )
    return record


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(REPO_ROOT / "quant" / "volatility_relief_stock_leadership_paper_sleeve.py"),
            _repo_rel(REPO_ROOT / "quant" / "test_volatility_relief_stock_leadership_paper_sleeve.py"),
            _repo_rel(REPO_ROOT / "quant" / "run.py"),
            _repo_rel(REPO_ROOT / "quant" / "default_off_alpha_attribution.py"),
            _repo_rel(REPO_ROOT / "quant" / "report_generator.py"),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
            _repo_rel(REPO_ROOT / "docs" / "production_backtest_parity.md"),
            _repo_rel(REPO_ROOT / "docs" / "alpha-optimization-playbook.md"),
            _repo_rel(REPO_ROOT / "docs" / "data_edge_context_layers.md"),
            _repo_rel(REPO_ROOT / "data" / "meta_research_report_latest.json"),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(REPO_ROOT / "quant" / "volatility_relief_stock_leadership_paper_sleeve.py"): framework._sha256(
                REPO_ROOT / "quant" / "volatility_relief_stock_leadership_paper_sleeve.py"
            ),
            _repo_rel(REPO_ROOT / "quant" / "test_volatility_relief_stock_leadership_paper_sleeve.py"): framework._sha256(
                REPO_ROOT / "quant" / "test_volatility_relief_stock_leadership_paper_sleeve.py"
            ),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
            _repo_rel(REPO_ROOT / "docs" / "production_backtest_parity.md"): framework._sha256(
                REPO_ROOT / "docs" / "production_backtest_parity.md"
            ),
            _repo_rel(REPO_ROOT / "docs" / "alpha-optimization-playbook.md"): framework._sha256(
                REPO_ROOT / "docs" / "alpha-optimization-playbook.md"
            ),
            _repo_rel(REPO_ROOT / "docs" / "data_edge_context_layers.md"): framework._sha256(
                REPO_ROOT / "docs" / "data_edge_context_layers.md"
            ),
            _repo_rel(REPO_ROOT / "data" / "meta_research_report_latest.json"): framework._sha256(
                REPO_ROOT / "data" / "meta_research_report_latest.json"
            ),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _build_artifact_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Volatility Relief Shared Adapter",
            "",
            f"Decision: `{payload['decision']}`",
            f"Status: `{payload['status']}`",
            "",
            "## Gate 4",
            "",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Target trades: `{aggregate.get('target_trade_count_sum')}`",
            f"- Failed reasons: `{payload['gate4'].get('failed_reasons') or 'none'}`",
            "",
            "## Parity",
            "",
            "- Historical replay uses `quant/volatility_relief_stock_leadership_paper_sleeve.py`.",
            "- Daily run exposes the same helper as a default-off paper snapshot.",
            "- `trade_enabled=False`; no live/default orders, ranking, sizing, exits, LLM/news, or watchlist behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _build_card(payload: dict[str, Any]) -> str:
    card = previous._build_card(payload)
    return card.replace(
        (
            "Replay-only and default-off paper only. No shared policy, run "
            "adapter, backtester adapter, production watchlist, order path, "
            "core entry, ranking, sizing, or exit behavior changed."
        ),
        (
            "Accepted shared default-off paper adapter. Historical replay and "
            "daily production snapshots use the same helper; "
            "`trade_enabled=False`, and no live/default orders, ranking, "
            "sizing, exits, LLM/news, or watchlist behavior changed."
        ),
    )


def persist(payload: dict[str, Any]) -> None:
    previous.BASE_PERSIST(payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_build_artifact_markdown(payload), encoding="utf-8")
    _write_manifest(payload)


def _patch_framework() -> None:
    for module in (previous, framework):
        module.EXPERIMENT_ID = EXPERIMENT_ID
        module.STEM = STEM
        module.TRIAL_FAMILY = TRIAL_FAMILY
        module.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
        module.CHANGED_VARIABLE = CHANGED_VARIABLE
        module.RULE_VERSION = RULE_VERSION
        module.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
        module.HOLD_DAYS = HOLD_DAYS
        module.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
        module.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
        module.MIN_TARGET_TRADES = MIN_TARGET_TRADES
        module.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
        module.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
        module.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
        module.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
        module.PREDICTION = PREDICTION
        module.PRODUCTION_IMPACT = PRODUCTION_IMPACT
        module.OUT_DIR = OUT_DIR
        module.OUT_JSON = OUT_JSON
        module.LOG_JSON = LOG_JSON
        module.TICKET_JSON = TICKET_JSON
        module.CARD_MD = CARD_MD
        module.MANIFEST_JSON = MANIFEST_JSON
        module.EXPERIMENT_LOG = EXPERIMENT_LOG
        module.REGISTRY_JSON = REGISTRY_JSON
    previous.ARTIFACT_MD = ARTIFACT_MD
    framework._load_window_snapshot = _load_window_snapshot
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._select_paper_trades = _select_paper_trades
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._write_manifest = _write_manifest
    framework.persist = persist


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
