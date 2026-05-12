from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXPERIMENT_ID = "exp-20260512-018"
EXPERIMENT_SLUG = "same_day_sector_rs20_follower_risk"
FOLLOWER_MULTIPLIER = 0.5
MULTIPLIER_KEY = "same_day_sector_rs20_follower_risk_multiplier_applied"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (str(QUANT_DIR), str(EXPERIMENT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import backtester as backtester_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import exp_20260511_010_same_day_sector_tqs_follower_risk as prior  # noqa: E402
import portfolio_engine  # noqa: E402


WINDOWS = prior.WINDOWS
RESULT_KEYS = prior.RESULT_KEYS
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

ADJUSTMENTS: list[dict[str, Any]] = []
OBSERVATIONS: list[dict[str, Any]] = []


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe(value: Any) -> Any:
    return prior.safe_payload(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8").splitlines():
            if not existing.strip():
                continue
            try:
                existing_payload = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if existing_payload.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _scale_sizing(
    sig: dict[str, Any],
    sizing: dict[str, Any],
    *,
    portfolio_value: float,
    shares: int,
    new_shares: int,
    leader_ticker: Any,
    leader_score: float,
    follower_score: float,
    prior_same_sector: int,
) -> dict[str, Any]:
    new_sig = dict(sig)
    new_sizing = dict(sizing)
    entry = float(new_sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    net_risk_per_share = float(new_sizing.get("net_risk_per_share") or 0.0)
    position_value = entry * new_shares
    risk_amount = net_risk_per_share * new_shares
    original_risk_pct = new_sizing.get("risk_pct")
    new_sizing["shares_to_buy"] = new_shares
    new_sizing["position_value_usd"] = round(position_value, 2)
    new_sizing["position_pct_of_portfolio"] = (
        round(position_value / portfolio_value, 4) if portfolio_value else 0.0
    )
    new_sizing["risk_amount_usd"] = round(risk_amount, 2)
    new_sizing["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    new_sizing[MULTIPLIER_KEY] = FOLLOWER_MULTIPLIER
    new_sizing["same_day_sector_rs20_leader_ticker"] = leader_ticker
    new_sizing["same_day_sector_rs20_leader_score"] = leader_score
    new_sizing["same_day_sector_rs20_follower_score"] = follower_score
    new_sizing["same_day_sector_rs20_prior_entries"] = prior_same_sector
    new_sizing["same_day_sector_rs20_baseline_shares"] = shares
    new_sizing["same_day_sector_rs20_new_shares"] = new_shares
    new_sizing["risk_pct_before_rs20_follower"] = original_risk_pct
    new_sizing["risk_pct_after_rs20_follower"] = new_sizing["risk_pct"]
    new_sig["sizing"] = new_sizing
    return new_sig


def make_rs20_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        sector_leaders: dict[str, dict[str, Any]] = {}
        adjusted: list[dict[str, Any]] = []

        for sig in sized:
            sizing = sig.get("sizing") or {}
            sector = str(sig.get("sector") or "Unknown")
            strategy = str(sig.get("strategy") or "")
            shares = int(sizing.get("shares_to_buy") or 0)
            score = sig.get("ticker_ret20_minus_spy_pct")
            risk_pct_after_existing = sizing.get("risk_pct")
            is_core_entry = strategy in {"trend_long", "breakout_long"}
            is_eligible = (
                is_core_entry
                and sector not in {"", "Unknown"}
                and isinstance(score, (int, float))
                and shares > 0
                and isinstance(risk_pct_after_existing, (int, float))
                and float(risk_pct_after_existing) > 0
            )

            if is_eligible:
                leader = sector_leaders.get(sector)
                if leader is None:
                    sector_leaders[sector] = {
                        "ticker": sig.get("ticker"),
                        "score": float(score),
                        "count": 1,
                    }
                else:
                    prior_same_sector = int(leader["count"])
                    leader["count"] = prior_same_sector + 1
                    leader_score = float(leader["score"])
                    follower_score = float(score)
                    should_reduce = follower_score < leader_score
                    observation = {
                        "ticker": sig.get("ticker"),
                        "strategy": strategy,
                        "sector": sector,
                        "leader_ticker": leader.get("ticker"),
                        "leader_ret20_minus_spy": leader_score,
                        "follower_ret20_minus_spy": follower_score,
                        "prior_same_sector_entries": prior_same_sector,
                        "shares": shares,
                        "risk_pct_before": risk_pct_after_existing,
                        "action": "reduce" if should_reduce else "keep",
                    }
                    OBSERVATIONS.append(observation)
                    if should_reduce:
                        new_shares = max(1, int(math.floor(shares * FOLLOWER_MULTIPLIER)))
                        if new_shares < shares:
                            sig = _scale_sizing(
                                sig,
                                sizing,
                                portfolio_value=portfolio_value,
                                shares=shares,
                                new_shares=new_shares,
                                leader_ticker=leader.get("ticker"),
                                leader_score=leader_score,
                                follower_score=follower_score,
                                prior_same_sector=prior_same_sector,
                            )
                            ADJUSTMENTS.append(
                                {
                                    **observation,
                                    "baseline_shares": shares,
                                    "new_shares": new_shares,
                                    "risk_pct_after": sig["sizing"]["risk_pct"],
                                }
                            )
            adjusted.append(sig)
        return adjusted

    return wrapped


def run_window(label: str, *, variant: bool) -> dict[str, Any]:
    spec = WINDOWS[label]
    universe = get_universe()
    original_size_signals = portfolio_engine.size_signals
    original_multiplier_keys = backtester_module.SIZING_MULTIPLIER_KEYS
    global ADJUSTMENTS, OBSERVATIONS
    ADJUSTMENTS = []
    OBSERVATIONS = []
    if variant:
        portfolio_engine.size_signals = make_rs20_wrapper(original_size_signals)
        if MULTIPLIER_KEY not in backtester_module.SIZING_MULTIPLIER_KEYS:
            backtester_module.SIZING_MULTIPLIER_KEYS = (
                *backtester_module.SIZING_MULTIPLIER_KEYS,
                MULTIPLIER_KEY,
            )
    try:
        engine = BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config={
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
            },
            ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        )
        result = engine.run()
    finally:
        portfolio_engine.size_signals = original_size_signals
        backtester_module.SIZING_MULTIPLIER_KEYS = original_multiplier_keys

    if result.get("error"):
        raise RuntimeError(
            f"{label} {'variant' if variant else 'baseline'} failed: {result['error']}"
        )
    return {
        "metrics": prior.summarize_result(result),
        "trades": result.get("trades") or [],
        "adjustments": list(ADJUSTMENTS),
        "observations": list(OBSERVATIONS),
        "sizing_rule_signal_attribution": result.get("sizing_rule_signal_attribution")
        or {},
        "sizing_rule_trade_attribution": result.get("sizing_rule_trade_attribution")
        or {},
    }


def _decide(
    aggregate_delta: dict[str, Any],
    aggregate_after: dict[str, Any],
    improved_windows: list[str],
    regressed_windows: list[str],
    max_drawdown_worsening: float,
    total_adjustments: int,
) -> str:
    if (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved_windows) >= 2
        and not regressed_windows
        and max_drawdown_worsening <= 0.02
        and aggregate_after["survival_rate_min"] >= 0.05
        and total_adjustments > 0
    ):
        return "accepted_candidate_needs_shared_policy_promotion"
    if (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and not regressed_windows
        and aggregate_after["survival_rate_min"] >= 0.05
        and total_adjustments > 0
    ):
        return "promising_replay_only_underpowered"
    return "rejected_replay_only"


def _write_markdown(payload: dict[str, Any]) -> None:
    rows = [
        "| Window | Base EV | After EV | dEV | Base PnL | After PnL | dPnL | Reduced | Kept | Changed trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        base = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        kept = sum(
            1 for row in payload["observations"][label] if row.get("action") == "keep"
        )
        changed = payload["changed_trades"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {reduced} | {kept} | {changed_count} |".format(
                label=label,
                bev=base["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=base["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                reduced=len(payload["adjustments"][label]),
                kept=kept,
                changed_count=(
                    changed["added_count"]
                    + changed["removed_count"]
                    + changed["common_pnl_changed_count"]
                ),
            )
        )

    aggregate_delta = payload["delta_metrics"]["aggregate_delta"]
    text = f"""# {EXPERIMENT_ID}: Same-Day Sector RS20 Follower Risk

Decision: `{payload["decision"]}`.

Hypothesis: in same-day same-sector core A/B clusters, the native first candidate
should keep its current sizing, but a later same-sector candidate whose
20-trading-day return versus SPY is lower than that first candidate may deserve
a smaller initial risk budget.

{chr(10).join(rows)}

Aggregate EV delta: `{aggregate_delta["expected_value_score_sum"]:+.4f}`.
Aggregate PnL delta: `${aggregate_delta["total_pnl_sum"]:+,.2f}`.

Protocol: `docs/backtesting.md` canonical three-window fixed-snapshot replay.

Single causal variable: apply a 0.5x share/risk haircut to second-and-later
same-day same-sector `trend_long` / `breakout_long` signals only when the
follower's existing `ticker_ret20_minus_spy_pct` is below that sector's first
same-day core signal. No entry generation, ranking, universe membership, exits,
stops, targets, add-ons, event sleeves, or LLM/news behavior changed.

Gate notes:

- Gate 1: baseline and variant reran all three fixed windows.
- Gate 2: `operator_inputs/open_positions.json` required-field audit passed.
- Gate 3: no new entry filter; minimum after survival rate was `{payload["gate_results"]["gate3"]["minimum_after_survival_rate"]}`.
- Gate 4: `{payload["gate_results"]["gate4"]["decision_basis"]}`

Production impact: replay-only. If a future version is accepted, the rule must
be moved into shared production/backtest sizing policy before it can affect
orders.
"""
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(text, encoding="utf-8")


def main() -> None:
    timestamp = utc_now()
    gate2_positions = prior.audit_open_positions()
    if not gate2_positions["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2_positions}")

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    observations: dict[str, list[dict[str, Any]]] = {}
    trade_changes: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}

    for label in WINDOWS:
        print(f"baseline {label}")
        baseline = run_window(label, variant=False)
        print(f"variant {label}")
        variant = run_window(label, variant=True)
        before_metrics[label] = baseline["metrics"]
        after_metrics[label] = variant["metrics"]
        adjustments[label] = variant["adjustments"]
        observations[label] = variant["observations"]
        trade_changes[label] = prior.changed_trades(
            baseline["trades"],
            variant["trades"],
        )
        sizing_attribution[label] = {
            "signal": variant["sizing_rule_signal_attribution"].get(MULTIPLIER_KEY),
            "trade": variant["sizing_rule_trade_attribution"].get(MULTIPLIER_KEY),
        }

    by_window_delta = {
        label: prior.metric_delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    aggregate_before = prior.aggregate(before_metrics)
    aggregate_after = prior.aggregate(after_metrics)
    aggregate_metric_delta = prior.aggregate_delta(aggregate_after, aggregate_before)
    improved_windows = [
        label
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed_windows = [
        label
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    max_drawdown_worsening = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in WINDOWS
    )
    total_adjustments = sum(len(rows) for rows in adjustments.values())
    decision = _decide(
        aggregate_metric_delta,
        aggregate_after,
        improved_windows,
        regressed_windows,
        max_drawdown_worsening,
        total_adjustments,
    )

    rejection_reason = None
    if decision != "accepted_candidate_needs_shared_policy_promotion":
        rejection_reason = (
            "The RS20 same-sector follower haircut did not clear the required "
            "multi-window materiality/stability gate, so production policy stays "
            "unchanged."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": timestamp,
        "lane": "alpha_search",
        "change_type": "replay_only_risk_allocation_discriminator",
        "changed_variable": "same_day_same_sector_relative_rs20_follower_initial_risk_multiplier",
        "single_causal_variable": "relative RS20 0.5x same-day same-sector follower risk multiplier",
        "hypothesis": (
            "Same-day same-sector core A/B clusters may be useful when the "
            "follower is also leading SPY, but followers that are weaker than "
            "the first same-sector candidate on 20-day relative strength should "
            "receive a 0.5x initial risk haircut."
        ),
        "backtest_protocol": {
            "source": "docs/backtesting.md",
            "windows": WINDOWS,
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
            },
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}"
            for label, spec in WINDOWS.items()
        },
        "gate_questions": {
            "alpha_hypothesis": "risk allocation: relative-RS20 same-day sector follower haircut",
            "prior_similar_experiments": [
                "exp-20260511-006 rejected a blunt same-sector risk_on follower haircut.",
                "exp-20260511-010 was promising but underpowered using TQS only on risk_on clusters.",
                "exp-20260511-013 rejected the all-core TQS follower extension.",
            ],
            "single_causal_variable": "0.5x risk multiplier for lower-relative-RS20 same-sector followers",
            "acceptance_standard": (
                "Aggregate EV/PnL improve, at least two EV-improved windows, no "
                "EV-regressed windows, survival_rate >= 5%, max drawdown damage "
                "<= 2 pp, then promote only through shared production/backtest policy."
            ),
            "reproducibility": (
                "This runner reruns baseline and variant across all canonical "
                "fixed snapshots and writes JSON, ticket, markdown, and JSONL artifacts."
            ),
        },
        "parameters": {
            "follower_multiplier": FOLLOWER_MULTIPLIER,
            "quality_condition": (
                "follower ticker_ret20_minus_spy_pct < first same-sector core "
                "signal ticker_ret20_minus_spy_pct"
            ),
            "eligible_entries": [
                "strategy in trend_long, breakout_long",
                "same signal-day sector already has one eligible core entry",
                "leader and follower ticker_ret20_minus_spy_pct are present",
                "sizing shares_to_buy > 0",
            ],
            "locked_variables": [
                "signal generation",
                "entry filters",
                "entry ranking",
                "universe membership",
                "existing sizing multipliers",
                "stop and target rules",
                "exits",
                "add-ons",
                "event sleeves",
                "LLM/news replay",
            ],
        },
        "gate_results": {
            "gate1": {
                "baseline_protocol": "docs/backtesting.md canonical fixed-snapshot three-window replay",
                "baseline_metrics": before_metrics,
            },
            "gate2": gate2_positions,
            "gate3": {
                "new_filter_added": False,
                "minimum_after_survival_rate": aggregate_after["survival_rate_min"],
                "passed": aggregate_after["survival_rate_min"] >= 0.05,
            },
            "gate4": {
                "improved_windows": improved_windows,
                "regressed_windows": regressed_windows,
                "total_adjusted_signals": total_adjustments,
                "max_drawdown_worsening": max_drawdown_worsening,
                "decision_basis": (
                    "Shared promotion requires aggregate EV/PnL improvement, at "
                    "least two EV-improved windows, no EV-regressed windows, "
                    "survival-rate constraints, max drawdown damage <= 2 pp, "
                    "and a nonzero touched cohort."
                ),
                "passed": decision == "accepted_candidate_needs_shared_policy_promotion",
            },
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_metric_delta,
        },
        "adjustments": adjustments,
        "observations": observations,
        "changed_trades": trade_changes,
        "sizing_attribution": sizing_attribution,
        "expected_value_score_delta": aggregate_metric_delta["expected_value_score_sum"],
        "decision": decision,
        "rejection_reason": rejection_reason,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains production-replay sample limited; this "
                "uses deterministic existing RS20 fields instead."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If later accepted, implement the sizing rule in shared "
                "portfolio_engine and add focused parity coverage before live "
                "orders change."
            ),
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG.relative_to(REPO_ROOT)),
        ],
    }

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Same-day sector RS20 follower risk",
        "decision": decision,
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
        "expected_value_score_delta": aggregate_metric_delta[
            "expected_value_score_sum"
        ],
        "summary": (
            "Replay-only RS20 same-sector follower haircut across canonical "
            "three-window backtests."
        ),
        "next_step": (
            "Do not promote unless future evidence gives multi-window or forward "
            "support for this relative-RS20 cluster discriminator."
        ),
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _write_markdown(payload)
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(_safe(ticket), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
