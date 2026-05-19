"""exp-20260510-013: RS20 fragility guard replay.

Alpha search. Tests one allocation variable: whether the accepted RS20
entry-state top-up should be skipped when the same entered A/B trade already
carries any sub-1 risk multiplier. This is a drawdown discriminator for the
accepted RS20 policy, not a nearby RS20 scalar sweep.

Replay only. A passing result would need promotion into shared
portfolio_engine.py policy plus parity coverage before production behavior
changes.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
import portfolio_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260510-013"
STEM = "rs20_fragility_guard"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

RS20_KEY = "rs20_entry_state_risk_multiplier_applied"
GUARD_KEY = "rs20_fragility_guard_applied"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if not path.exists():
        path.write_text(payload_line + "\n", encoding="utf-8")
        return

    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            out.append(line)
            continue
        if row.get("experiment_id") == payload["experiment_id"]:
            if not replaced:
                out.append(payload_line)
                replaced = True
            continue
        out.append(line)
    if not replaced:
        out.append(payload_line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    total_return = result.get("strategy_total_return_pct")
    if total_return is None:
        total_return = result.get("total_return_pct")
    if total_return is None:
        benchmarks = result.get("benchmarks") or {}
        if isinstance(benchmarks, dict):
            total_return = benchmarks.get("strategy_total_return_pct")
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "strategy_total_return_pct": _round(total_return, 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 6),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key in {"trade_count", "signals_generated", "signals_survived", "max_consecutive_losses"}:
                out[key] = int(after_value - before_value)
            else:
                out[key] = _round(after_value - before_value, 6)
    return out


def _has_subone_multiplier(sizing: dict[str, Any]) -> bool:
    for key, value in sizing.items():
        if key == RS20_KEY or not key.endswith("_multiplier_applied"):
            continue
        if isinstance(value, (int, float)) and value < 1.0:
            return True
    return False


def _remove_rs20_topup(sig: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    sizing = dict(sig.get("sizing") or {})
    if (sizing.get(RS20_KEY) or 1.0) <= 1.0:
        return sig, False
    if not _has_subone_multiplier(sizing):
        return sig, False

    baseline_shares = int(sizing.get("rs20_entry_state_baseline_shares") or 0)
    current_shares = int(sizing.get("shares_to_buy") or 0)
    if baseline_shares <= 0 or baseline_shares >= current_shares:
        return sig, False

    entry = sig.get("entry_price")
    portfolio_value = sizing.get("portfolio_value_usd")
    if not isinstance(portfolio_value, (int, float)) or portfolio_value <= 0:
        position_value = sizing.get("position_value_usd")
        position_pct = sizing.get("position_pct_of_portfolio")
        if isinstance(position_value, (int, float)) and isinstance(position_pct, (int, float)) and position_pct > 0:
            portfolio_value = position_value / position_pct
    if not isinstance(entry, (int, float)) or entry <= 0 or not isinstance(portfolio_value, (int, float)) or portfolio_value <= 0:
        return sig, False

    net_risk_per_share = sizing.get("net_risk_per_share") or 0.0
    risk_amount = baseline_shares * net_risk_per_share
    position_value = baseline_shares * entry
    sizing["shares_to_buy"] = baseline_shares
    sizing["position_value_usd"] = _round(position_value, 2)
    sizing["position_pct_of_portfolio"] = _round(position_value / portfolio_value, 4)
    sizing["risk_amount_usd"] = _round(risk_amount, 2)
    sizing["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    sizing[RS20_KEY] = 1.0
    sizing[GUARD_KEY] = 0.0
    return {**sig, "sizing": sizing}, True


def _patch_size_signals():
    original = portfolio_engine.size_signals
    guard_stats = {"signals_guarded": 0}

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for sig in sized:
            new_sig, guarded = _remove_rs20_topup(sig)
            if guarded:
                guard_stats["signals_guarded"] += 1
            out.append(new_sig)
        return out

    return original, patched, guard_stats


@contextmanager
def _variant_context(enabled: bool) -> Iterator[dict[str, int]]:
    if not enabled:
        yield {"signals_guarded": 0}
        return
    original, patched, guard_stats = _patch_size_signals()
    original_keys = bt.SIZING_MULTIPLIER_KEYS
    portfolio_engine.size_signals = patched
    if GUARD_KEY not in bt.SIZING_MULTIPLIER_KEYS:
        bt.SIZING_MULTIPLIER_KEYS = (*bt.SIZING_MULTIPLIER_KEYS, GUARD_KEY)
    try:
        yield guard_stats
    finally:
        portfolio_engine.size_signals = original
        bt.SIZING_MULTIPLIER_KEYS = original_keys


def _run_window(window: dict[str, str], guard_enabled: bool) -> tuple[dict[str, Any], dict[str, int]]:
    with _variant_context(guard_enabled) as guard_stats:
        result = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result, dict(guard_stats)


def _guarded_trade_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for trade in result.get("trades") or []:
        multipliers = trade.get("sizing_multipliers") or {}
        if not multipliers.get(GUARD_KEY):
            continue
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": _round(trade.get("pnl"), 2),
                "return_pct": _round(trade.get("return_pct"), 6),
                "sizing_multipliers": multipliers,
            }
        )
    return rows


def _aggregate(windows: dict[str, Any]) -> dict[str, Any]:
    before_sum = sum(row["before_metrics"]["expected_value_score"] or 0.0 for row in windows.values())
    after_sum = sum(row["after_metrics"]["expected_value_score"] or 0.0 for row in windows.values())
    before_pnl = sum(row["before_metrics"]["total_pnl"] or 0.0 for row in windows.values())
    after_pnl = sum(row["after_metrics"]["total_pnl"] or 0.0 for row in windows.values())
    ev_improved = sum(
        1 for row in windows.values() if (row["metric_deltas"].get("expected_value_score") or 0.0) > 0
    )
    ev_regressed = sum(
        1 for row in windows.values() if (row["metric_deltas"].get("expected_value_score") or 0.0) < 0
    )
    pnl_improved = sum(
        1 for row in windows.values() if (row["metric_deltas"].get("total_pnl") or 0.0) > 0
    )
    max_dd_worsening = max(
        (row["metric_deltas"].get("max_drawdown_pct") or 0.0) for row in windows.values()
    )
    return {
        "expected_value_score_before_sum": _round(before_sum, 4),
        "expected_value_score_after_sum": _round(after_sum, 4),
        "expected_value_score_delta_sum": _round(after_sum - before_sum, 4),
        "expected_value_score_delta_pct": _round((after_sum - before_sum) / before_sum if before_sum else None, 6),
        "total_pnl_before_sum": _round(before_pnl, 2),
        "total_pnl_after_sum": _round(after_pnl, 2),
        "total_pnl_delta_sum": _round(after_pnl - before_pnl, 2),
        "total_pnl_delta_pct": _round((after_pnl - before_pnl) / before_pnl if before_pnl else None, 6),
        "windows_ev_improved": ev_improved,
        "windows_ev_regressed": ev_regressed,
        "windows_pnl_improved": pnl_improved,
        "max_drawdown_worsening_max": _round(max_dd_worsening, 6),
        "guarded_trade_count_sum": sum(len(row["guarded_trades"]) for row in windows.values()),
        "guarded_signal_count_sum": sum(row["guard_stats"]["signals_guarded"] for row in windows.values()),
        "survival_rate_delta_min": min(
            (row["metric_deltas"].get("survival_rate") or 0.0) for row in windows.values()
        ),
        "trade_count_delta_sum": sum(
            row["metric_deltas"].get("trade_count") or 0 for row in windows.values()
        ),
    }


def _gate4(aggregate: dict[str, Any]) -> dict[str, Any]:
    passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["windows_ev_improved"] >= 2
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["trade_count_delta_sum"] == 0
        and aggregate["survival_rate_delta_min"] >= 0
        and aggregate["max_drawdown_worsening_max"] <= 0.01
    )
    return {
        "passed": passed,
        "basis": (
            "Replay-only three-window guard. Promotion requires positive EV/PnL "
            "without trade-count or survival regression, then shared policy implementation."
        ),
    }


def _artifact(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} RS20 Fragility Guard",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Aggregate",
        "",
        "| EV before | EV after | EV delta | PnL delta | EV windows +/- | Guarded signals | Guarded closed trades | DD worst drift |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        "| {evb} | {eva} | {evd} | {pnld} | {up}/{down} | {gs} | {gt} | {dd} |".format(
            evb=payload["delta_metrics"]["aggregate"]["expected_value_score_before_sum"],
            eva=payload["delta_metrics"]["aggregate"]["expected_value_score_after_sum"],
            evd=payload["delta_metrics"]["aggregate"]["expected_value_score_delta_sum"],
            pnld=payload["delta_metrics"]["aggregate"]["total_pnl_delta_sum"],
            up=payload["delta_metrics"]["aggregate"]["windows_ev_improved"],
            down=payload["delta_metrics"]["aggregate"]["windows_ev_regressed"],
            gs=payload["delta_metrics"]["aggregate"]["guarded_signal_count_sum"],
            gt=payload["delta_metrics"]["aggregate"]["guarded_trade_count_sum"],
            dd=payload["delta_metrics"]["aggregate"]["max_drawdown_worsening_max"],
        ),
        "",
        "## Windows",
        "",
        "| Window | EV before | EV after | EV delta | PnL delta | DD delta | Trades delta | Guarded signals | Guarded closed trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["windows"].items():
        lines.append(
            "| {label} | {evb} | {eva} | {evd} | {pnld} | {dd} | {td} | {gs} | {gt} |".format(
                label=label,
                evb=row["before_metrics"]["expected_value_score"],
                eva=row["after_metrics"]["expected_value_score"],
                evd=row["metric_deltas"].get("expected_value_score"),
                pnld=row["metric_deltas"].get("total_pnl"),
                dd=row["metric_deltas"].get("max_drawdown_pct"),
                td=row["metric_deltas"].get("trade_count"),
                gs=row["guard_stats"]["signals_guarded"],
                gt=len(row["guarded_trades"]),
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "Replay only. No shared policy, run adapter, entry, ranking, exit, add-on, LLM/news, or universe behavior changed.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    run_at = datetime.now(timezone.utc).isoformat()
    windows: dict[str, Any] = OrderedDict()
    for label, window in WINDOWS.items():
        baseline_result, _ = _run_window(window, guard_enabled=False)
        variant_result, guard_stats = _run_window(window, guard_enabled=True)
        before = _metrics(baseline_result)
        after = _metrics(variant_result)
        windows[label] = {
            "window": {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
                "state_note": window["state_note"],
            },
            "before_metrics": before,
            "after_metrics": after,
            "metric_deltas": _delta(after, before),
            "guard_stats": guard_stats,
            "guarded_trades": _guarded_trade_rows(variant_result),
        }

    aggregate = _aggregate(windows)
    gate4 = _gate4(aggregate)
    decision = "promising_replay_only_not_promoted" if gate4["passed"] else "rejected"
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": run_at,
        "run_at": run_at,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted RS20 entry-state 1.10x top-up may be over-stacking "
            "with existing fragility haircuts; skipping the top-up only when "
            "any other sub-1 risk multiplier is already present could preserve "
            "RS20 upside while reducing weak-window drawdown."
        ),
        "change_type": "replay_only_risk_allocation_discriminator",
        "changed_variable": "rs20_topup_skip_when_any_subone_multiplier_present",
        "component": "quant/portfolio_engine.py replay monkeypatch only",
        "single_causal_variable": "rs20_fragility_guard",
        "backtest_protocol": "Three fixed windows from docs/backtesting.md using canonical snapshots.",
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "parameters": {
            "guard_condition": "RS20 top-up applied and any non-RS20 sizing multiplier < 1.0",
            "rs20_multiplier_kept_when_clean": 1.10,
            "locked_variables": [
                "core universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "base sizing multipliers",
                "exits",
                "add-ons",
                "event sleeves",
                "LLM/news replay",
            ],
        },
        "before_metrics": {
            "aggregate": {
                "expected_value_score_sum": aggregate["expected_value_score_before_sum"],
                "total_pnl_sum": aggregate["total_pnl_before_sum"],
            },
            "windows": {label: row["before_metrics"] for label, row in windows.items()},
        },
        "after_metrics": {
            "aggregate": {
                "expected_value_score_sum": aggregate["expected_value_score_after_sum"],
                "total_pnl_sum": aggregate["total_pnl_after_sum"],
            },
            "windows": {label: row["after_metrics"] for label, row in windows.items()},
        },
        "delta_metrics": {
            "aggregate": aggregate,
            "windows": {label: row["metric_deltas"] for label, row in windows.items()},
        },
        "windows": windows,
        "gate1_baseline": {
            "source": "Current accepted RS20 shared sizing baseline, rerun in this script before applying the replay guard.",
            "expected_value_score_sum": aggregate["expected_value_score_before_sum"],
            "total_pnl_sum": aggregate["total_pnl_before_sum"],
        },
        "gate2_field_audit": {
            "path": "operator_inputs/open_positions.json",
            "required_fields": ["entry_date", "target_price"],
            "result": "checked before experiment; current file has both fields on open positions",
        },
        "gate3": {
            "new_filter_added": False,
            "note": "No entry filter was added; this only resizes already-entered RS20 trades in replay.",
            "survival_rates_after": {
                label: row["after_metrics"]["survival_rate"] for label, row in windows.items()
            },
        },
        "gate4": gate4,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM soft-ranking data is not needed for this deterministic sizing discriminator.",
        },
        "historical_experiment_check": {
            "exp-20260510-012": "Accepted RS20 1.10x shared top-up; stronger 1.25x/1.50x variants rejected for drawdown.",
            "nearby_rs20_scalars": "Not retried here; multiplier remains 1.10 and only a sub-1 fragility guard is tested.",
            "exp-20260509-005": "Clean mid-dispersion top-up used a similar non-haircut idea but on a different accepted signal family and was rejected as immaterial.",
        },
        "known_risks": [
            "Replay monkeypatch is not production policy.",
            "If positive, the exact guard must be implemented in shared portfolio_engine.py and rerun.",
        ],
        "rejection_reason": None if gate4["passed"] else "Guard did not improve the three-window north-star metrics cleanly enough for promotion.",
        "next_evidence_needed": (
            "If rejected, do not repeat RS20 fragility guards without forward attribution "
            "or a materially different non-overfit discriminator."
        ),
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(Path(__file__).relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG.relative_to(REPO_ROOT)),
        ],
        "why_not_other_changes": {
            "LLM_soft_ranking": "Still data-limited.",
            "candidate_pool": "MRVL-only expansion was just rejected; broad static expansion adds noise.",
            "event_ETF_surfaces": "Already default-off and waiting on forward paper outcomes.",
            "RS20_scalar": "Nearby scalar sweeps are explicitly disallowed without new evidence.",
        },
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": decision,
            "lane": "alpha_search",
            "changed_variable": payload["changed_variable"],
            "decision": decision,
            "artifact": str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(payload["delta_metrics"]["aggregate"], indent=2, sort_keys=True))
    print(f"decision={decision}")
    print(f"artifact={ARTIFACT_MD}")


if __name__ == "__main__":
    main()
