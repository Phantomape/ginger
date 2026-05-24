"""Replay-only SLV trend target compression scout.

The experiment changes one causal variable: the target ATR multiplier for
existing SLV trend_long signals in the Commodities sleeve. It does not change
entries, ranking, sizing, candidate pools, LLM behavior, or production code.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from constants import ATR_STOP_MULT  # noqa: E402
from data_layer import get_universe  # noqa: E402
import risk_engine as risk_engine_module  # noqa: E402


EXPERIMENT_ID = "exp-20260524-021"
SLUG = "slv_trend_target_compression"
RESULT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
LOG_DIR = REPO_ROOT / "experiments" / "logs"
TICKET_DIR = REPO_ROOT / "experiments" / "tickets"
ARTIFACT_DIR = REPO_ROOT / "experiments" / "artifacts"
EXPERIMENT_LOG_PATH = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS: "OrderedDict[str, Dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

VARIANTS: "OrderedDict[str, Optional[float]]" = OrderedDict(
    [
        ("baseline_current_policy", None),
        ("slv_target_6_5_atr", 6.5),
        ("slv_target_6_0_atr", 6.0),
        ("slv_target_5_5_atr", 5.5),
        ("slv_target_5_0_atr", 5.0),
    ]
)

CONTROL_LABEL = "baseline_current_policy"
_PATCH_STATE = {"eligible": 0, "adjusted": 0}


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _metric(result: Dict[str, Any], key: str, default: float = 0.0) -> float:
    if key in result:
        value = result.get(key, default)
    else:
        value = result.get("benchmarks", {}).get(key, default)
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default


def _signals_metric(result: Dict[str, Any], key: str) -> int:
    value = result.get(key)
    if value is None:
        value = result.get("metrics", {}).get(key)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _survival_rate(result: Dict[str, Any]) -> float:
    survived = _signals_metric(result, "signals_survived")
    generated = _signals_metric(result, "signals_generated")
    if generated <= 0:
        return 0.0
    return survived / generated


def _eligible_signal(signal: Dict[str, Any]) -> bool:
    return (
        str(signal.get("ticker", "")).upper() == "SLV"
        and str(signal.get("strategy", "")) == "trend_long"
        and str(signal.get("sector", "")) == "Commodities"
    )


def _retarget_signal(signal: Dict[str, Any], target_atr_mult: float) -> Dict[str, Any]:
    updated = dict(signal)
    try:
        entry = float(updated.get("entry_price") or updated.get("price") or 0.0)
        stop = float(updated.get("stop_price") or updated.get("stop_loss") or 0.0)
    except (TypeError, ValueError):
        return updated
    if entry <= 0.0 or stop <= 0.0 or entry <= stop:
        return updated

    atr = (entry - stop) / ATR_STOP_MULT
    if atr <= 0.0:
        return updated

    target = entry + target_atr_mult * atr
    risk_per_share = entry - stop
    reward_per_share = target - entry
    updated["target_price"] = target
    updated["reward_per_share"] = reward_per_share
    updated["risk_reward_ratio"] = reward_per_share / risk_per_share if risk_per_share > 0.0 else 0.0
    updated["slv_trend_target_compression"] = {
        "experiment_id": EXPERIMENT_ID,
        "baseline_target_atr_mult": 7.0,
        "target_atr_mult": target_atr_mult,
        "entry_price": entry,
        "stop_price": stop,
    }
    return updated


@contextmanager
def _patched_slv_target(target_atr_mult: Optional[float]) -> Iterable[None]:
    if target_atr_mult is None:
        yield
        return

    original_enrich_signals: Callable[..., List[Dict[str, Any]]] = risk_engine_module.enrich_signals

    def patched_enrich_signals(signals: List[Dict[str, Any]], *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        enriched = original_enrich_signals(signals, *args, **kwargs)
        out: List[Dict[str, Any]] = []
        for signal in enriched:
            if not _eligible_signal(signal):
                out.append(signal)
                continue
            _PATCH_STATE["eligible"] += 1
            adjusted = _retarget_signal(signal, target_atr_mult)
            if adjusted.get("slv_trend_target_compression"):
                _PATCH_STATE["adjusted"] += 1
            out.append(adjusted)
        return out

    risk_engine_module.enrich_signals = patched_enrich_signals
    try:
        yield
    finally:
        risk_engine_module.enrich_signals = original_enrich_signals


def _run_window(window_name: str, window: Dict[str, str], target_atr_mult: Optional[float]) -> Dict[str, Any]:
    _PATCH_STATE["eligible"] = 0
    _PATCH_STATE["adjusted"] = 0
    engine = BacktestEngine(
        universe=sorted(get_universe()),
        start=window["start"],
        end=window["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    )
    with _patched_slv_target(target_atr_mult):
        result = engine.run()

    trades = result.get("trades", []) or []
    slv_trend_trades = [
        trade
        for trade in trades
        if str(trade.get("ticker", "")).upper() == "SLV"
        and str(trade.get("strategy", "")) == "trend_long"
    ]
    adjusted_slv_trades = [
        trade for trade in slv_trend_trades if trade.get("slv_trend_target_compression")
    ]

    metrics = {
        "expected_value_score": _metric(result, "expected_value_score"),
        "strategy_total_return_pct": _metric(result, "strategy_total_return_pct"),
        "sharpe_daily": _metric(result, "sharpe_daily"),
        "total_pnl": _metric(result, "total_pnl"),
        "max_drawdown_pct": _metric(result, "max_drawdown_pct"),
        "win_rate": _metric(result, "win_rate"),
        "total_trades": int(_metric(result, "total_trades")),
        "signals_generated": _signals_metric(result, "signals_generated"),
        "signals_survived": _signals_metric(result, "signals_survived"),
        "survival_rate": _survival_rate(result),
        "eligible_slv_trend_signal_count": int(_PATCH_STATE["eligible"]),
        "adjusted_slv_trend_signal_count": int(_PATCH_STATE["adjusted"]),
        "slv_trend_trade_count": len(slv_trend_trades),
        "adjusted_slv_trend_trade_count": len(adjusted_slv_trades),
        "slv_trend_total_pnl": sum(float(trade.get("pnl") or 0.0) for trade in slv_trend_trades),
    }
    return {
        "window": window_name,
        "start": window["start"],
        "end": window["end"],
        "snapshot": window["snapshot"],
        "metrics": metrics,
        "slv_trend_trades": [
            {
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date") or trade.get("date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "entry_price": trade.get("entry_price"),
                "exit_price": trade.get("exit_price"),
                "target_price": trade.get("target_price"),
                "pnl": trade.get("pnl"),
                "return_pct": trade.get("return_pct"),
            }
            for trade in slv_trend_trades
        ],
    }


def _round(value: float, digits: int = 6) -> float:
    return round(float(value or 0.0), digits)


def _summarize_variant(label: str, windows: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    metrics_by_window = {name: payload["metrics"] for name, payload in windows.items()}
    return {
        "label": label,
        "aggregate_expected_value_score": _round(
            sum(metric["expected_value_score"] for metric in metrics_by_window.values())
        ),
        "aggregate_total_pnl": _round(sum(metric["total_pnl"] for metric in metrics_by_window.values()), 2),
        "aggregate_total_trades": int(sum(metric["total_trades"] for metric in metrics_by_window.values())),
        "aggregate_signals_generated": int(sum(metric["signals_generated"] for metric in metrics_by_window.values())),
        "aggregate_signals_survived": int(sum(metric["signals_survived"] for metric in metrics_by_window.values())),
        "aggregate_survival_rate": _round(
            sum(metric["signals_survived"] for metric in metrics_by_window.values())
            / max(1, sum(metric["signals_generated"] for metric in metrics_by_window.values()))
        ),
        "aggregate_slv_trend_trades": int(sum(metric["slv_trend_trade_count"] for metric in metrics_by_window.values())),
        "aggregate_eligible_slv_trend_signals": int(
            sum(metric["eligible_slv_trend_signal_count"] for metric in metrics_by_window.values())
        ),
        "aggregate_adjusted_slv_trend_signals": int(
            sum(metric["adjusted_slv_trend_signal_count"] for metric in metrics_by_window.values())
        ),
        "aggregate_adjusted_slv_trend_trades": int(
            sum(metric["adjusted_slv_trend_trade_count"] for metric in metrics_by_window.values())
        ),
        "aggregate_slv_trend_total_pnl": _round(
            sum(metric["slv_trend_total_pnl"] for metric in metrics_by_window.values()), 2
        ),
        "windows": metrics_by_window,
    }


def _delta_summary(summary: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    deltas_by_window: Dict[str, Dict[str, float]] = {}
    improved_windows = 0
    regressed_windows = 0
    pnl_improved_windows = 0
    pnl_regressed_windows = 0
    for window_name, metrics in summary["windows"].items():
        base_metrics = baseline["windows"][window_name]
        ev_delta = metrics["expected_value_score"] - base_metrics["expected_value_score"]
        pnl_delta = metrics["total_pnl"] - base_metrics["total_pnl"]
        if ev_delta > 1e-9:
            improved_windows += 1
        elif ev_delta < -1e-9:
            regressed_windows += 1
        if pnl_delta > 1e-9:
            pnl_improved_windows += 1
        elif pnl_delta < -1e-9:
            pnl_regressed_windows += 1
        deltas_by_window[window_name] = {
            "expected_value_score_delta": _round(ev_delta),
            "total_pnl_delta": _round(pnl_delta, 2),
            "max_drawdown_pct_delta": _round(metrics["max_drawdown_pct"] - base_metrics["max_drawdown_pct"]),
            "survival_rate_delta": _round(metrics["survival_rate"] - base_metrics["survival_rate"]),
            "total_trades_delta": int(metrics["total_trades"] - base_metrics["total_trades"]),
            "slv_trend_total_pnl_delta": _round(
                metrics["slv_trend_total_pnl"] - base_metrics["slv_trend_total_pnl"], 2
            ),
        }

    return {
        "aggregate_expected_value_score_delta": _round(
            summary["aggregate_expected_value_score"] - baseline["aggregate_expected_value_score"]
        ),
        "aggregate_total_pnl_delta": _round(summary["aggregate_total_pnl"] - baseline["aggregate_total_pnl"], 2),
        "aggregate_survival_rate_delta": _round(
            summary["aggregate_survival_rate"] - baseline["aggregate_survival_rate"]
        ),
        "aggregate_total_trades_delta": int(
            summary["aggregate_total_trades"] - baseline["aggregate_total_trades"]
        ),
        "aggregate_slv_trend_total_pnl_delta": _round(
            summary["aggregate_slv_trend_total_pnl"] - baseline["aggregate_slv_trend_total_pnl"], 2
        ),
        "expected_value_windows_improved": improved_windows,
        "expected_value_windows_regressed": regressed_windows,
        "pnl_windows_improved": pnl_improved_windows,
        "pnl_windows_regressed": pnl_regressed_windows,
        "windows": deltas_by_window,
    }


def _gate_decision(summary: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
    adjusted_signals = int(summary["aggregate_adjusted_slv_trend_signals"])
    changed_windows = sum(
        1 for metrics in summary["windows"].values() if int(metrics["adjusted_slv_trend_signal_count"]) > 0
    )
    min_survival_rate = min(float(metrics["survival_rate"]) for metrics in summary["windows"].values())
    ev_delta = float(delta["aggregate_expected_value_score_delta"])
    pnl_delta = float(delta["aggregate_total_pnl_delta"])
    ev_regressed = int(delta["expected_value_windows_regressed"])
    ev_improved = int(delta["expected_value_windows_improved"])

    blockers: List[str] = []
    if adjusted_signals < 2:
        blockers.append("changed_signal_sample_lt_2")
    if changed_windows < 2:
        blockers.append("changed_window_sample_lt_2")
    if min_survival_rate < 0.05:
        blockers.append("survival_rate_below_gate3_floor")
    if ev_delta <= 0.0:
        blockers.append("aggregate_expected_value_not_positive")
    if pnl_delta <= 0.0:
        blockers.append("aggregate_pnl_not_positive")
    if ev_regressed > 0:
        blockers.append("one_or_more_windows_regressed_ev")
    if ev_improved < 2:
        blockers.append("fewer_than_two_windows_improved_ev")

    return {
        "status": "pass_candidate_requires_shared_policy_promotion" if not blockers else "reject",
        "blockers": blockers,
        "min_survival_rate": _round(min_survival_rate),
        "changed_signal_sample": adjusted_signals,
        "changed_window_sample": changed_windows,
        "acceptance_criteria": [
            "canonical_three_window_aggregate_expected_value_positive",
            "canonical_three_window_aggregate_pnl_positive",
            "no_window_expected_value_regression",
            "at_least_two_windows_improve_expected_value",
            "changed_signal_sample_at_least_two_across_at_least_two_windows",
            "survival_rate_not_below_5pct",
        ],
    }


def _select_variant(results: Dict[str, Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    candidates = {label: payload for label, payload in results.items() if label != CONTROL_LABEL}
    passing = {
        label: payload
        for label, payload in candidates.items()
        if payload["gate"]["status"] == "pass_candidate_requires_shared_policy_promotion"
    }
    pool = passing or candidates
    label = max(
        pool,
        key=lambda item: (
            pool[item]["delta"]["aggregate_expected_value_score_delta"],
            pool[item]["delta"]["aggregate_total_pnl_delta"],
        ),
    )
    return label, pool[label]


def _artifact_markdown(payload: Dict[str, Any]) -> str:
    selected_label = payload["selected_variant"]
    selected = payload["results"][selected_label]
    lines = [
        f"# {EXPERIMENT_ID} {SLUG}",
        "",
        "## Hypothesis",
        (
            "Compressing targets for existing SLV Commodities trend_long signals may capture "
            "mean-reverting silver exits sooner than the current 7 ATR commodity target, while "
            "leaving GLD/IAU and the rest of the commodity sleeve unchanged."
        ),
        "",
        "## Gate Answers",
        "- Type: alpha_search, exit/lifecycle.",
        "- Prior evidence: accepted commodity/gold target split helped, while prior wider commodity tests noted SLV drag.",
        "- Causal variable: SLV trend_long target ATR multiplier only.",
        "- Evaluation: canonical three non-overlapping windows from docs/backtesting.md.",
        "- Reproducibility: this artifact plus JSON payload record variants, windows, snapshots, and metrics.",
        "",
        "## Variant Summary",
        "| variant | agg EV | delta EV | agg PnL | delta PnL | EV windows +/- | gate |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for label, result in payload["results"].items():
        summary = result["summary"]
        delta = result.get("delta", {})
        gate_status = result.get("gate", {}).get("status", "control")
        lines.append(
            "| {label} | {ev:.6f} | {dev:.6f} | {pnl:.2f} | {dpnl:.2f} | {imp}/{reg} | {gate} |".format(
                label=label,
                ev=summary["aggregate_expected_value_score"],
                dev=delta.get("aggregate_expected_value_score_delta", 0.0),
                pnl=summary["aggregate_total_pnl"],
                dpnl=delta.get("aggregate_total_pnl_delta", 0.0),
                imp=delta.get("expected_value_windows_improved", 0),
                reg=delta.get("expected_value_windows_regressed", 0),
                gate=gate_status,
            )
        )

    lines.extend(
        [
            "",
            f"## Selected Variant: {selected_label}",
            f"- Decision: {selected['gate']['status']}",
            f"- Blockers: {', '.join(selected['gate']['blockers']) or 'none'}",
            f"- Aggregate EV delta: {selected['delta']['aggregate_expected_value_score_delta']:.6f}",
            f"- Aggregate PnL delta: {selected['delta']['aggregate_total_pnl_delta']:.2f}",
            "",
            "## Window Detail",
            "| window | EV delta | PnL delta | survival delta | trade delta | SLV PnL delta |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for window_name, delta in selected["delta"]["windows"].items():
        lines.append(
            "| {window} | {ev:.6f} | {pnl:.2f} | {surv:.6f} | {trades:d} | {slv:.2f} |".format(
                window=window_name,
                ev=delta["expected_value_score_delta"],
                pnl=delta["total_pnl_delta"],
                surv=delta["survival_rate_delta"],
                trades=delta["total_trades_delta"],
                slv=delta["slv_trend_total_pnl_delta"],
            )
        )

    lines.extend(
        [
            "",
            "## Production Parity",
            (
                "No production policy was changed. If a variant had passed, the shared "
                "risk_engine target policy would need the same ticker/strategy/sector condition "
                "before live use."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _write_outputs(payload: Dict[str, Any]) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TICKET_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    result_path = RESULT_DIR / f"{SLUG}.json"
    log_path = LOG_DIR / f"{EXPERIMENT_ID}.json"
    ticket_path = TICKET_DIR / f"{EXPERIMENT_ID}.json"
    artifact_path = ARTIFACT_DIR / f"{EXPERIMENT_ID}_{SLUG}.md"

    payload["artifacts"] = {
        "result_json": str(result_path.relative_to(REPO_ROOT)),
        "experiment_log": str(log_path.relative_to(REPO_ROOT)),
        "ticket": str(ticket_path.relative_to(REPO_ROOT)),
        "markdown": str(artifact_path.relative_to(REPO_ROOT)),
    }

    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")

    selected = payload["results"][payload["selected_variant"]]
    status = "accepted" if selected["gate"]["status"].startswith("pass_") else "rejected"
    log_payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": status,
        "category": "alpha_search",
        "hypothesis": payload["hypothesis"],
        "selected_variant": payload["selected_variant"],
        "baseline": payload["results"][CONTROL_LABEL]["summary"],
        "after": selected["summary"],
        "delta": selected["delta"],
        "gate": selected["gate"],
        "artifacts": payload["artifacts"],
        "production_backtest_parity": payload["production_backtest_parity"],
        "created_at": payload["created_at"],
    }
    log_path.write_text(json.dumps(log_payload, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")

    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": status,
        "type": "alpha_search",
        "claimed_by": "codex",
        "claimed_at": payload["created_at"],
        "hypothesis": payload["hypothesis"],
        "selected_variant": payload["selected_variant"],
        "result_json": payload["artifacts"]["result_json"],
        "gate": selected["gate"],
    }
    ticket_path.write_text(json.dumps(ticket_payload, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")

    artifact_path.write_text(_artifact_markdown(payload), encoding="utf-8")

    jsonl_record = {
        "ts": payload["created_at"],
        "experiment_id": EXPERIMENT_ID,
        "type": "alpha_search",
        "status": status,
        "hypothesis": payload["hypothesis"],
        "causal_variable": "SLV trend_long target ATR multiplier only",
        "selected_variant": payload["selected_variant"],
        "baseline_aggregate_expected_value_score": payload["results"][CONTROL_LABEL]["summary"][
            "aggregate_expected_value_score"
        ],
        "after_aggregate_expected_value_score": selected["summary"]["aggregate_expected_value_score"],
        "aggregate_expected_value_score_delta": selected["delta"]["aggregate_expected_value_score_delta"],
        "baseline_aggregate_total_pnl": payload["results"][CONTROL_LABEL]["summary"]["aggregate_total_pnl"],
        "after_aggregate_total_pnl": selected["summary"]["aggregate_total_pnl"],
        "aggregate_total_pnl_delta": selected["delta"]["aggregate_total_pnl_delta"],
        "gate_status": selected["gate"]["status"],
        "gate_blockers": selected["gate"]["blockers"],
        "artifacts": payload["artifacts"],
        "production_parity": payload["production_backtest_parity"]["status"],
        "conclusion": payload["conclusion"],
    }
    existing_lines: List[str] = []
    if EXPERIMENT_LOG_PATH.exists():
        for line in EXPERIMENT_LOG_PATH.read_text(encoding="utf-8").splitlines():
            if f'"experiment_id": "{EXPERIMENT_ID}"' not in line:
                existing_lines.append(line)
    existing_lines.append(json.dumps(jsonl_record, sort_keys=True, default=_json_default))
    EXPERIMENT_LOG_PATH.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")


def run_experiment() -> Dict[str, Any]:
    variant_windows: Dict[str, Dict[str, Any]] = {}
    for label, target_atr_mult in VARIANTS.items():
        windows: Dict[str, Dict[str, Any]] = OrderedDict()
        for window_name, window in WINDOWS.items():
            windows[window_name] = _run_window(window_name, window, target_atr_mult)
        variant_windows[label] = windows

    summaries = {
        label: {"summary": _summarize_variant(label, windows), "windows": windows}
        for label, windows in variant_windows.items()
    }
    baseline_summary = summaries[CONTROL_LABEL]["summary"]
    for label, payload in summaries.items():
        if label == CONTROL_LABEL:
            payload["delta"] = {
                "aggregate_expected_value_score_delta": 0.0,
                "aggregate_total_pnl_delta": 0.0,
                "aggregate_survival_rate_delta": 0.0,
                "aggregate_total_trades_delta": 0,
                "aggregate_slv_trend_total_pnl_delta": 0.0,
                "expected_value_windows_improved": 0,
                "expected_value_windows_regressed": 0,
                "pnl_windows_improved": 0,
                "pnl_windows_regressed": 0,
                "windows": {
                    name: {
                        "expected_value_score_delta": 0.0,
                        "total_pnl_delta": 0.0,
                        "max_drawdown_pct_delta": 0.0,
                        "survival_rate_delta": 0.0,
                        "total_trades_delta": 0,
                        "slv_trend_total_pnl_delta": 0.0,
                    }
                    for name in WINDOWS
                },
            }
            payload["gate"] = {"status": "control", "blockers": []}
            continue
        payload["delta"] = _delta_summary(payload["summary"], baseline_summary)
        payload["gate"] = _gate_decision(payload["summary"], payload["delta"])

    selected_label, selected_payload = _select_variant(summaries)
    status = "accepted" if selected_payload["gate"]["status"].startswith("pass_") else "rejected"
    conclusion = (
        "Rejected: the best SLV target compression variant did not satisfy the three-window "
        "EV/PnL/no-regression/sample gate, so no production policy change is warranted."
        if status == "rejected"
        else (
            "Candidate passed replay gates but no production code was changed in this scout; "
            "promotion requires implementing the identical condition in risk_engine and rerunning Gate 1-4."
        )
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "category": "alpha_search",
        "hypothesis": (
            "Existing SLV Commodities trend_long signals may have lower expected value under the "
            "current 7 ATR commodity target; compressing only the SLV target could improve exits "
            "without adding filters, ranking complexity, candidate tickers, or LLM dependence."
        ),
        "windows": copy.deepcopy(WINDOWS),
        "variants": copy.deepcopy(VARIANTS),
        "results": summaries,
        "selected_variant": selected_label,
        "status": status,
        "conclusion": conclusion,
        "production_backtest_parity": {
            "status": "parity_preserved_for_current_repo",
            "detail": (
                "Replay monkeypatch only; no production strategy code changed. A positive result "
                "would require the exact same ticker/strategy/sector condition in shared risk_engine "
                "before live activation."
            ),
        },
    }
    _write_outputs(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-summary", action="store_true", help="Print selected result summary.")
    args = parser.parse_args()
    payload = run_experiment()
    if args.print_summary:
        selected = payload["results"][payload["selected_variant"]]
        print(
            json.dumps(
                {
                    "experiment_id": payload["experiment_id"],
                    "status": payload["status"],
                    "selected_variant": payload["selected_variant"],
                    "delta": selected["delta"],
                    "gate": selected["gate"],
                    "artifacts": payload["artifacts"],
                },
                indent=2,
                sort_keys=True,
                default=_json_default,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
