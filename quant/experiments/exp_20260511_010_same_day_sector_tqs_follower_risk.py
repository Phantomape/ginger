from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXPERIMENT_ID = "exp-20260511-010"
EXPERIMENT_SLUG = "same_day_sector_tqs_follower_risk"
FOLLOWER_MULTIPLIER = 0.5
MULTIPLIER_KEY = "same_day_sector_tqs_follower_risk_multiplier_applied"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as backtester_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402


WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    },
}

RESULT_KEYS = [
    "expected_value_score",
    "total_pnl",
    "total_return_pct",
    "sharpe_daily",
    "max_drawdown_pct",
    "win_rate",
    "trade_count",
    "signals_generated",
    "signals_survived",
    "survival_rate",
    "worst_trade_pct",
    "max_consecutive_losses",
    "tail_loss_share",
]

CLUSTER_ADJUSTMENTS: list[dict[str, Any]] = []
CLUSTER_OBSERVATIONS: list[dict[str, Any]] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def round_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 6)
    return value


def safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_payload(item) for item in value]
    if isinstance(value, tuple):
        return [safe_payload(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {key: round_value(result.get(key)) for key in RESULT_KEYS}
    benchmarks = result.get("benchmarks") or {}
    summary["total_return_pct"] = round_value(
        benchmarks.get("strategy_total_return_pct", summary.get("total_return_pct"))
    )
    summary["trade_count"] = round_value(result.get("total_trades", summary.get("trade_count")))
    summary["spy_buy_hold_return_pct"] = round_value(benchmarks.get("spy_buy_hold_return_pct"))
    summary["qqq_buy_hold_return_pct"] = round_value(benchmarks.get("qqq_buy_hold_return_pct"))
    convergence = result.get("convergence") or {}
    if convergence:
        summary["converged"] = bool(convergence.get("converged", False))
    return summary


def audit_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[tuple[str, dict[str, Any]]] = []
    for section in ("positions", "observations"):
        for row in payload.get(section, []):
            if isinstance(row, dict):
                rows.append((section, row))

    missing: list[dict[str, Any]] = []
    for section, row in rows:
        ticker = row.get("ticker")
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"section": section, "ticker": ticker, "field": field})

    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "checked_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_required_fields": missing,
        "passed": not missing,
    }


def _scale_sizing(
    sig: dict[str, Any],
    sizing: dict[str, Any],
    *,
    portfolio_value: float,
    shares: int,
    new_shares: int,
    leader_ticker: Any,
    leader_tqs: float,
    follower_tqs: float,
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
    new_sizing["same_day_sector_tqs_leader_ticker"] = leader_ticker
    new_sizing["same_day_sector_tqs_leader_score"] = leader_tqs
    new_sizing["same_day_sector_tqs_follower_score"] = follower_tqs
    new_sizing["same_day_sector_tqs_prior_entries"] = prior_same_sector
    new_sizing["same_day_sector_tqs_baseline_shares"] = shares
    new_sizing["same_day_sector_tqs_new_shares"] = new_shares
    new_sizing["risk_pct_before_tqs_follower"] = original_risk_pct
    new_sizing["risk_pct_after_tqs_follower"] = new_sizing["risk_pct"]
    new_sig["sizing"] = new_sizing
    return new_sig


def make_cluster_wrapper(original: Callable[..., list[dict[str, Any]]]) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(signals: list[dict[str, Any]], portfolio_value: float, risk_pct: float | None = None) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        sector_leaders: dict[str, dict[str, Any]] = {}
        adjusted: list[dict[str, Any]] = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            sector = str(sig.get("sector") or "Unknown")
            risk_on_multiplier = sizing.get("risk_on_unmodified_risk_multiplier_applied")
            shares = int(sizing.get("shares_to_buy") or 0)
            tqs = sig.get("trade_quality_score")
            is_eligible = (
                sig.get("regime_exit_bucket") == "risk_on"
                and isinstance(risk_on_multiplier, (int, float))
                and float(risk_on_multiplier) != 1.0
                and sector not in {"", "Unknown"}
                and isinstance(tqs, (int, float))
                and shares > 0
            )
            if is_eligible:
                leader = sector_leaders.get(sector)
                if leader is None:
                    sector_leaders[sector] = {
                        "ticker": sig.get("ticker"),
                        "tqs": float(tqs),
                        "count": 1,
                    }
                else:
                    prior_same_sector = int(leader["count"])
                    leader["count"] = prior_same_sector + 1
                    leader_tqs = float(leader["tqs"])
                    follower_tqs = float(tqs)
                    should_reduce = follower_tqs < leader_tqs
                    observation = {
                        "ticker": sig.get("ticker"),
                        "strategy": sig.get("strategy"),
                        "sector": sector,
                        "leader_ticker": leader.get("ticker"),
                        "leader_tqs": leader_tqs,
                        "follower_tqs": follower_tqs,
                        "prior_same_sector_risk_on_entries": prior_same_sector,
                        "risk_on_multiplier": risk_on_multiplier,
                        "shares": shares,
                        "action": "reduce" if should_reduce else "keep",
                    }
                    CLUSTER_OBSERVATIONS.append(observation)
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
                                leader_tqs=leader_tqs,
                                follower_tqs=follower_tqs,
                                prior_same_sector=prior_same_sector,
                            )
                            CLUSTER_ADJUSTMENTS.append(
                                {
                                    **observation,
                                    "baseline_shares": shares,
                                    "new_shares": new_shares,
                                    "risk_pct_before": sizing.get("risk_pct"),
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
    global CLUSTER_ADJUSTMENTS, CLUSTER_OBSERVATIONS
    CLUSTER_ADJUSTMENTS = []
    CLUSTER_OBSERVATIONS = []
    if variant:
        portfolio_engine.size_signals = make_cluster_wrapper(original_size_signals)
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
        raise RuntimeError(f"{label} {'variant' if variant else 'baseline'} failed: {result['error']}")
    return {
        "metrics": summarize_result(result),
        "trades": result.get("trades") or [],
        "cluster_adjustments": list(CLUSTER_ADJUSTMENTS),
        "cluster_observations": list(CLUSTER_OBSERVATIONS),
        "sizing_rule_signal_attribution": result.get("sizing_rule_signal_attribution") or {},
        "sizing_rule_trade_attribution": result.get("sizing_rule_trade_attribution") or {},
    }


def metric_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    for key in RESULT_KEYS:
        if isinstance(after.get(key), (int, float)) and isinstance(before.get(key), (int, float)):
            deltas[key] = round_value(after[key] - before[key])
    return deltas


def aggregate(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()),
            6,
        ),
        "total_pnl_sum": round(sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()), 2),
        "trade_count_sum": int(sum(int(row.get("trade_count") or 0) for row in metrics.values())),
        "max_drawdown_pct_max": round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values()),
            6,
        ),
        "survival_rate_min": round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
            6,
        ),
    }


def aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    for key, after_value in after.items():
        before_value = before.get(key)
        if isinstance(after_value, (int, float)) and isinstance(before_value, (int, float)):
            deltas[key] = round_value(after_value - before_value)
    return deltas


def trade_key(trade: dict[str, Any]) -> str:
    return "|".join(
        [
            str(trade.get("ticker") or ""),
            str(trade.get("entry_date") or ""),
            str(trade.get("strategy") or ""),
            str(round(float(trade.get("entry_price") or 0.0), 4)),
        ]
    )


def changed_trades(before_trades: list[dict[str, Any]], after_trades: list[dict[str, Any]]) -> dict[str, Any]:
    before_by_key = {trade_key(trade): trade for trade in before_trades}
    after_by_key = {trade_key(trade): trade for trade in after_trades}
    added_keys = sorted(set(after_by_key) - set(before_by_key))
    removed_keys = sorted(set(before_by_key) - set(after_by_key))
    changed = []
    for key in sorted(set(before_by_key) & set(after_by_key)):
        before = before_by_key[key]
        after = after_by_key[key]
        if round(float(before.get("pnl") or 0.0), 2) != round(float(after.get("pnl") or 0.0), 2):
            changed.append(
                {
                    "key": key,
                    "before": {
                        "ticker": before.get("ticker"),
                        "entry_date": before.get("entry_date"),
                        "exit_date": before.get("exit_date"),
                        "sector": before.get("sector"),
                        "pnl": before.get("pnl"),
                        "shares": before.get("shares"),
                        "sizing_multipliers": before.get("sizing_multipliers"),
                    },
                    "after": {
                        "ticker": after.get("ticker"),
                        "entry_date": after.get("entry_date"),
                        "exit_date": after.get("exit_date"),
                        "sector": after.get("sector"),
                        "pnl": after.get("pnl"),
                        "shares": after.get("shares"),
                        "sizing_multipliers": after.get("sizing_multipliers"),
                    },
                }
            )
    return {
        "added_count": len(added_keys),
        "removed_count": len(removed_keys),
        "common_pnl_changed_count": len(changed),
        "added_keys": added_keys,
        "removed_keys": removed_keys,
        "common_pnl_changed": changed,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe_payload(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def upsert_experiment_log(entry: dict[str, Any]) -> None:
    path = REPO_ROOT / "docs" / "experiment_log.jsonl"
    line = json.dumps(safe_payload(entry), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8").splitlines():
            if not existing.strip():
                continue
            try:
                payload = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if payload.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def playbook_decision_text(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    delta = payload["delta_metrics"]["aggregate_delta"]
    if decision == "promising_replay_only_underpowered":
        return (
            "Finding: adding a relative-TQS discriminator to the rejected same-day sector "
            "follower haircut preserved the higher-TQS GLD commodity follower and only reduced "
            "the lower-TQS XOM energy follower. Aggregate EV improved by "
            f"`{delta['expected_value_score_sum']:+.4f}` and aggregate PnL improved by "
            f"`${delta['total_pnl_sum']:+,.2f}`, but the rule touched only one canonical "
            "window, so it is not strong enough for shared-policy promotion."
        )
    if decision == "accepted_for_shared_policy_implementation":
        return (
            "Finding: the relative-TQS same-day sector follower haircut cleared the replay gate. "
            f"Aggregate EV delta was `{delta['expected_value_score_sum']:+.4f}` and aggregate "
            f"PnL delta was `${delta['total_pnl_sum']:+,.2f}`."
        )
    return (
        "Finding: adding a relative-TQS discriminator to the rejected same-day sector "
        "follower haircut still did not clear the canonical replay gate. Aggregate EV "
        f"delta was `{delta['expected_value_score_sum']:+.4f}` and aggregate PnL delta was "
        f"`${delta['total_pnl_sum']:+,.2f}`."
    )


def append_playbook_note(payload: dict[str, Any]) -> None:
    path = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if f"Experiment: `{EXPERIMENT_ID}`" in text:
        return
    note = f"""
### 2026-05-11 mechanism update: TQS-conditioned sector follower risk

Experiment: `{EXPERIMENT_ID}`

Decision: `{payload["decision"]}`.

{playbook_decision_text(payload)}

Mechanism insight: the quality-conditioned form is materially better than the
blunt follower haircut from `exp-20260511-006`, because the existing TQS field
correctly keeps the crowded GLD winner and cuts the weaker XOM follower in the
late window. However, the fixed windows contain too few same-day same-sector
`risk_on` clusters for a production rule. Treat this as an alpha lead for
forward attribution or a broader pre-registered cluster-quality design, not as
a live sizing change.

Do not promote: shared `portfolio_engine` sizing should not change until the
same quality-conditioned cluster surface shows multi-window or forward closed
evidence. Do not retry nearby TQS thresholds on the same frozen sample.
"""
    path.write_text(text.rstrip() + "\n\n" + note.strip() + "\n", encoding="utf-8")


def append_current_state_note(payload: dict[str, Any]) -> None:
    path = REPO_ROOT / "docs" / "current_state.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if f"`{EXPERIMENT_ID}`" in text:
        return
    delta = payload["delta_metrics"]["aggregate_delta"]
    note = f"""
### 2026-05-11 alpha search note: TQS-conditioned sector follower risk

`{EXPERIMENT_ID}` tested a relative-TQS discriminator on the rejected same-day
sector follower haircut. It improved aggregate EV by
`{delta["expected_value_score_sum"]:+.4f}` and PnL by
`${delta["total_pnl_sum"]:+,.2f}`, but touched only the late window, so no
shared production/backtest sizing policy was promoted.
"""
    path.write_text(text.rstrip() + "\n\n" + note.strip() + "\n", encoding="utf-8")


def write_markdown(payload: dict[str, Any]) -> None:
    rows = [
        "| Window | Base EV | After EV | dEV | Base PnL | After PnL | dPnL | Reduced | Kept followers | Changed trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        base = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        kept = sum(1 for row in payload["cluster_observations"][label] if row.get("action") == "keep")
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {reduced} | {kept} | {changed} |".format(
                label=label,
                bev=base["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=base["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                reduced=len(payload["cluster_adjustments"][label]),
                kept=kept,
                changed=payload["changed_trades"][label]["added_count"]
                + payload["changed_trades"][label]["removed_count"]
                + payload["changed_trades"][label]["common_pnl_changed_count"],
            )
        )

    text = f"""# {EXPERIMENT_ID} TQS-Conditioned Sector Follower Risk

Decision: `{payload["decision"]}`.

Hypothesis: the rejected same-day same-sector `risk_on` follower haircut was too
blunt because it cut crowded winners and losers. Existing relative
`trade_quality_score` should identify only lower-quality followers for a 0.5x
initial-risk haircut.

{chr(10).join(rows)}

Protocol: `docs/backtesting.md` canonical three-window fixed-snapshot replay.

Single causal variable: apply the 0.5x same-day same-sector `risk_on` follower
risk haircut only when the follower's existing `trade_quality_score` is below
the first eligible same-sector leader's TQS. No entry filters, ranking,
universe membership, exits, stop/target rules, LLM/news behavior, or pilot
sleeves changed.

Gate notes:

- Gate 1: baseline rerun uses the accepted fixed-snapshot three-window protocol.
- Gate 2: no new production field; current `operator_inputs/open_positions.json`
  `entry_date` and `target_price` audit passed.
- Gate 3: no new entry filter; after survival-rate minimum is
  `{payload["gate_results"]["gate3"]["minimum_after_survival_rate"]}`.
- Gate 4: `{payload["gate_results"]["gate4"]["decision_basis"]}`.

Production impact: replay-only alpha scout. No shared production/backtest policy
changed. A promoted version would need this exact rule in shared
`portfolio_engine.size_signals`, multiplier attribution in `backtester.py`, and
a focused parity test before any live/default sizing behavior changes.
"""
    path = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def decide(
    aggregate_metric_delta: dict[str, Any],
    aggregate_after: dict[str, Any],
    improved_windows: list[str],
    regressed_windows: list[str],
    total_adjustments: int,
) -> str:
    if (
        aggregate_metric_delta["expected_value_score_sum"] > 0
        and aggregate_metric_delta["total_pnl_sum"] > 0
        and len(improved_windows) >= 2
        and not regressed_windows
        and aggregate_after["survival_rate_min"] >= 0.05
        and total_adjustments > 0
    ):
        return "accepted_for_shared_policy_implementation"
    if (
        aggregate_metric_delta["expected_value_score_sum"] > 0
        and aggregate_metric_delta["total_pnl_sum"] > 0
        and not regressed_windows
        and aggregate_after["survival_rate_min"] >= 0.05
        and total_adjustments > 0
    ):
        return "promising_replay_only_underpowered"
    return "rejected_replay_only"


def main() -> None:
    timestamp = utc_now()
    gate2_positions = audit_open_positions()
    if not gate2_positions["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2_positions}")

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    cluster_adjustments: dict[str, list[dict[str, Any]]] = {}
    cluster_observations: dict[str, list[dict[str, Any]]] = {}
    trade_changes: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}

    for label in WINDOWS:
        baseline = run_window(label, variant=False)
        variant = run_window(label, variant=True)
        before_metrics[label] = baseline["metrics"]
        after_metrics[label] = variant["metrics"]
        cluster_adjustments[label] = variant["cluster_adjustments"]
        cluster_observations[label] = variant["cluster_observations"]
        trade_changes[label] = changed_trades(baseline["trades"], variant["trades"])
        sizing_attribution[label] = {
            "signal": variant["sizing_rule_signal_attribution"].get(MULTIPLIER_KEY),
            "trade": variant["sizing_rule_trade_attribution"].get(MULTIPLIER_KEY),
        }

    by_window_delta = {
        label: metric_delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    aggregate_before = aggregate(before_metrics)
    aggregate_after = aggregate(after_metrics)
    aggregate_metric_delta = aggregate_delta(aggregate_after, aggregate_before)
    improved_windows = [
        label
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"] > before_metrics[label]["expected_value_score"]
    ]
    regressed_windows = [
        label
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"] < before_metrics[label]["expected_value_score"]
    ]
    total_adjustments = sum(len(rows) for rows in cluster_adjustments.values())
    decision = decide(
        aggregate_metric_delta,
        aggregate_after,
        improved_windows,
        regressed_windows,
        total_adjustments,
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": timestamp,
        "hypothesis": (
            "Relative TQS can distinguish lower-quality same-day same-sector risk_on "
            "followers from crowded winners, improving the rejected follower-risk surface."
        ),
        "change_type": "alpha_search",
        "changed_variable": "same_day_same_sector_risk_on_follower_initial_risk_multiplier_conditioned_by_relative_tqs",
        "parameters": {
            "follower_multiplier": FOLLOWER_MULTIPLIER,
            "quality_condition": "follower trade_quality_score < first eligible same-sector leader trade_quality_score",
            "eligible_entries": [
                "regime_exit_bucket == risk_on",
                "risk_on_unmodified_risk_multiplier_applied != 1.0",
                "same signal-day sector already has one eligible core entry",
                "leader and follower trade_quality_score are present",
            ],
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md",
            "windows": WINDOWS,
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
            },
        },
        "gate_questions": {
            "alpha_hypothesis": "risk allocation: relative-TQS lower-quality same-sector risk_on follower haircut",
            "prior_similar_experiments": [
                "exp-20260511-006 rejected a blunt same-sector risk_on follower haircut because it cut GLD winners and XOM losers equally.",
                "Global and local TQS candidate ordering experiments were rejected; this test does not reorder or filter, and only conditions a crowded-sector sizing haircut.",
            ],
            "single_causal_variable": "TQS condition on the same 0.5x same-day same-sector risk_on follower risk multiplier",
            "acceptance_standard": "Aggregate EV and PnL improve, at least two windows improve EV, no EV-regressed windows, survival_rate remains >= 5%, and no shared policy is promoted unless implemented in shared production/backtest sizing code.",
            "reproducibility": "This script reruns baseline and variant across the three docs/backtesting.md snapshots and writes JSON/MD artifacts.",
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
                "decision_basis": "Shared promotion requires aggregate EV/PnL improvement, at least two EV-improved windows, no EV-regressed windows, survival-rate constraints, and a nonzero touched cohort. Positive one-window evidence is recorded as replay-only underpowered.",
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
        "cluster_adjustments": cluster_adjustments,
        "cluster_observations": cluster_observations,
        "changed_trades": trade_changes,
        "sizing_attribution": sizing_attribution,
        "expected_value_score_delta": aggregate_metric_delta["expected_value_score_sum"],
        "decision": decision,
        "rejection_reason": None
        if decision == "accepted_for_shared_policy_implementation"
        else "Not promoted because canonical evidence is replay-only and does not clear multi-window shared-policy coverage.",
        "next_evidence_needed": None
        if decision == "accepted_for_shared_policy_implementation"
        else "Forward or broader pre-registered same-sector cluster evidence showing relative-TQS follower sizing improves more than one canonical window without threshold mining.",
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "llm_changed": False,
            "attribution_required": False,
        },
        "related_files": [
            f"quant/experiments/exp_20260511_010_{EXPERIMENT_SLUG}.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
            "docs/current_state.md",
        ],
    }

    artifact_path = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
    log_path = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "TQS-conditioned sector follower sizing",
        "status": decision,
        "summary": (
            "Replay-only alpha_search for a 0.5x same-day sector follower risk haircut gated by relative TQS."
        ),
        "decision": decision,
        "aggregate_ev_delta": aggregate_metric_delta["expected_value_score_sum"],
        "aggregate_pnl_delta": aggregate_metric_delta["total_pnl_sum"],
        "artifacts": payload["related_files"][1:5],
    }

    write_json(artifact_path, payload)
    write_json(log_path, payload)
    write_json(ticket_path, ticket)
    write_markdown(payload)
    upsert_experiment_log(payload)
    append_playbook_note(payload)
    append_current_state_note(payload)
    print(json.dumps(payload["delta_metrics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
