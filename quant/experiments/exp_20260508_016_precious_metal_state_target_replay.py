"""exp-20260508-016 precious-metals state target replay.

Alpha search, not infrastructure repair.  Prior commodity target sweeps found
that GLD/IAU could keep an 8 ATR trend target, while SLV dragged down broad
commodity target widening.  The playbook allows a retry only with a broader
precious-metals state map that explains when non-gold commodity continuation
should share the wider target.

This replay changes one causal variable: SLV trend target width becomes 8 ATR
only when a pre-registered precious-metals state condition is true.  Core
entries, ranking, sizing, stops, candidate universe, LLM/news behavior, and
production policy are unchanged.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
import risk_engine  # noqa: E402
from constants import TREND_COMMODITIES_TARGET_ATR_MULT, TREND_GOLD_TARGET_ATR_MULT  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260508-016"
STEM = "precious_metal_state_target_replay"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "slv_ret20_gt_gld_ret20",
            {
                "description": "SLV trend target = 8 ATR when SLV 20d momentum is greater than GLD 20d momentum.",
                "target_tickers": ("SLV",),
                "target_mult": float(TREND_GOLD_TARGET_ATR_MULT),
                "state_fn": lambda state: state["slv_ret20"] is not None
                and state["gld_ret20"] is not None
                and state["slv_ret20"] > state["gld_ret20"],
            },
        ),
        (
            "slv_ret20_gt_gld_ret20_by_2pp",
            {
                "description": "SLV trend target = 8 ATR when SLV 20d momentum beats GLD by at least 2pp.",
                "target_tickers": ("SLV",),
                "target_mult": float(TREND_GOLD_TARGET_ATR_MULT),
                "state_fn": lambda state: state["slv_minus_gld_ret20"] is not None
                and state["slv_minus_gld_ret20"] >= 0.02,
            },
        ),
        (
            "slv_and_gld_positive_slv_leads",
            {
                "description": "SLV trend target = 8 ATR when both SLV and GLD 20d momentum are positive and SLV leads.",
                "target_tickers": ("SLV",),
                "target_mult": float(TREND_GOLD_TARGET_ATR_MULT),
                "state_fn": lambda state: state["slv_ret20"] is not None
                and state["gld_ret20"] is not None
                and state["slv_ret20"] > 0
                and state["gld_ret20"] > 0
                and state["slv_ret20"] > state["gld_ret20"],
            },
        ),
    ]
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        try:
            return _safe(value.item())
        except (TypeError, ValueError):
            return str(value)
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_jsonl_dedup(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle_compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    needle_pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    kept = [line for line in lines if needle_compact not in line and needle_pretty not in line]
    kept.append(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _scalar(value: Any) -> float | None:
    try:
        if hasattr(value, "item"):
            value = value.item()
        if value is None or value == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _metric_slice(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_pnl": result.get("total_pnl"),
        "strategy_total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "win_rate": result.get("win_rate"),
        "total_trades": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
    }


def _deltas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "sharpe_daily",
        "max_drawdown_pct",
        "total_pnl",
        "strategy_total_return_pct",
        "win_rate",
        "total_trades",
        "survival_rate",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        if before.get(key) is None or after.get(key) is None:
            out[key] = None
        else:
            out[key] = round(float(after[key]) - float(before[key]), 6)
    return out


def _state(features_dict: dict[str, Any]) -> dict[str, float | None]:
    slv_ret20 = _scalar((features_dict.get("SLV") or {}).get("momentum_20d_pct"))
    gld_ret20 = _scalar((features_dict.get("GLD") or {}).get("momentum_20d_pct"))
    return {
        "slv_ret20": slv_ret20,
        "gld_ret20": gld_ret20,
        "slv_minus_gld_ret20": (
            round(slv_ret20 - gld_ret20, 6)
            if slv_ret20 is not None and gld_ret20 is not None
            else None
        ),
    }


def _run_engine(universe: list[str], spec: dict[str, Any]) -> dict[str, Any]:
    engine = bt.BacktestEngine(
        universe,
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=str(spec["snapshot"]),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"Backtest failed for {spec['start']} -> {spec['end']}: {result['error']}")
    return result


@contextmanager
def _patched_enrich(variant: dict[str, Any], touches: list[dict[str, Any]]):
    original = risk_engine.enrich_signals
    target_tickers = {str(ticker).upper() for ticker in variant["target_tickers"]}
    state_fn: Callable[[dict[str, float | None]], bool] = variant["state_fn"]
    target_mult = float(variant["target_mult"])

    def patched(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        state = _state(features_dict or {})
        state_pass = bool(state_fn(state))
        if not state_pass:
            return enriched

        adjusted = []
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            if (
                ticker in target_tickers
                and sig.get("strategy") == "trend_long"
                and sig.get("sector") == "Commodities"
            ):
                features = (features_dict or {}).get(ticker) or {}
                atr = _scalar(features.get("atr"))
                current_mult = _scalar(sig.get("target_mult_used"))
                if atr and atr > 0 and (current_mult is None or current_mult < target_mult):
                    retargeted = risk_engine._retarget_signal_with_atr_mult(
                        sig,
                        atr,
                        target_mult,
                    )
                    retargeted["precious_metal_state_target_width_applied"] = target_mult
                    retargeted["precious_metal_state_slv_ret20"] = state["slv_ret20"]
                    retargeted["precious_metal_state_gld_ret20"] = state["gld_ret20"]
                    retargeted["precious_metal_state_spread_ret20"] = state["slv_minus_gld_ret20"]
                    touches.append(
                        {
                            "ticker": ticker,
                            "strategy": sig.get("strategy"),
                            "base_target_mult": current_mult,
                            "target_mult": target_mult,
                            **state,
                        }
                    )
                    adjusted.append(retargeted)
                    continue
            adjusted.append(sig)
        return adjusted

    risk_engine.enrich_signals = patched
    try:
        yield
    finally:
        risk_engine.enrich_signals = original


def _slv_trade_summary(result: dict[str, Any]) -> dict[str, Any]:
    trades = [
        trade
        for trade in result.get("trades", [])
        if str(trade.get("ticker") or "").upper() == "SLV"
        and trade.get("strategy") == "trend_long"
    ]
    by_mult: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = str(trade.get("target_mult_used"))
        bucket = by_mult.setdefault(
            key,
            {
                "trades": 0,
                "wins": 0,
                "pnl": 0.0,
                "exit_reasons": Counter(),
            },
        )
        bucket["trades"] += 1
        pnl = float(trade.get("pnl") or 0.0)
        bucket["pnl"] += pnl
        if pnl > 0:
            bucket["wins"] += 1
        bucket["exit_reasons"][str(trade.get("exit_reason") or "unknown")] += 1
    return {
        key: {
            "trades": value["trades"],
            "wins": value["wins"],
            "win_rate": round(value["wins"] / value["trades"], 4) if value["trades"] else None,
            "pnl": round(value["pnl"], 2),
            "exit_reasons": dict(value["exit_reasons"]),
        }
        for key, value in by_mult.items()
    }


def _gate4_window_pass(before: dict[str, Any], after: dict[str, Any]) -> bool:
    ev_before = _scalar(before.get("expected_value_score"))
    ev_after = _scalar(after.get("expected_value_score"))
    sharpe_before = _scalar(before.get("sharpe_daily"))
    sharpe_after = _scalar(after.get("sharpe_daily"))
    dd_before = _scalar(before.get("max_drawdown_pct"))
    dd_after = _scalar(after.get("max_drawdown_pct"))
    pnl_before = _scalar(before.get("total_pnl"))
    pnl_after = _scalar(after.get("total_pnl"))
    trades_before = _scalar(before.get("total_trades"))
    trades_after = _scalar(after.get("total_trades"))
    win_before = _scalar(before.get("win_rate"))
    win_after = _scalar(after.get("win_rate"))

    return any(
        [
            ev_before is not None
            and ev_before != 0
            and ev_after is not None
            and (ev_after - ev_before) / abs(ev_before) > 0.10,
            sharpe_before is not None
            and sharpe_after is not None
            and sharpe_after - sharpe_before > 0.1,
            dd_before is not None
            and dd_after is not None
            and dd_before - dd_after > 0.01,
            pnl_before is not None
            and pnl_before != 0
            and pnl_after is not None
            and (pnl_after - pnl_before) / abs(pnl_before) > 0.05,
            trades_before is not None
            and trades_after is not None
            and trades_after > trades_before
            and win_before is not None
            and win_after is not None
            and win_after >= win_before,
        ]
    )


def _variant_decision(
    baseline: dict[str, dict[str, Any]],
    variant_windows: dict[str, dict[str, Any]],
    touch_counts: dict[str, int],
) -> dict[str, Any]:
    improved_ev_windows = []
    regressed_ev_windows = []
    gate4_windows = []
    severe_regressions = []
    for name, payload in variant_windows.items():
        before = baseline[name]
        after = payload["metrics"]
        delta = payload["delta"]
        if (delta.get("expected_value_score") or 0) > 0:
            improved_ev_windows.append(name)
        if (delta.get("expected_value_score") or 0) < 0:
            regressed_ev_windows.append(name)
        if _gate4_window_pass(before, after):
            gate4_windows.append(name)
        if (delta.get("expected_value_score") or 0) < -0.05:
            severe_regressions.append(name)

    touched_windows = [name for name, count in touch_counts.items() if count > 0]
    accepted = (
        len(improved_ev_windows) >= 2
        and len(gate4_windows) >= 2
        and not severe_regressions
        and len(touched_windows) >= 2
    )
    return {
        "decision": "accepted_for_shared_implementation" if accepted else "rejected",
        "improved_ev_windows": improved_ev_windows,
        "regressed_ev_windows": regressed_ev_windows,
        "gate4_pass_windows": gate4_windows,
        "severe_regressions": severe_regressions,
        "touched_windows": touched_windows,
        "reason": (
            "majority-window EV and Gate 4 improvement with no severe regression"
            if accepted
            else "did not produce robust majority-window EV/Gate 4 improvement"
        ),
    }


def main() -> None:
    run_at = datetime.now(timezone.utc).isoformat()
    universe = get_universe()

    baseline_results: dict[str, dict[str, Any]] = {}
    baseline_metrics: dict[str, dict[str, Any]] = {}
    for name, spec in WINDOWS.items():
        result = _run_engine(universe, spec)
        baseline_results[name] = result
        baseline_metrics[name] = _metric_slice(result)

    variants: dict[str, dict[str, Any]] = OrderedDict()
    for variant_name, variant in VARIANTS.items():
        variant_windows: dict[str, dict[str, Any]] = OrderedDict()
        touch_counts: dict[str, int] = {}
        for window_name, spec in WINDOWS.items():
            touches: list[dict[str, Any]] = []
            with _patched_enrich(variant, touches):
                result = _run_engine(universe, spec)
            metrics = _metric_slice(result)
            touch_counts[window_name] = len(touches)
            variant_windows[window_name] = {
                "metrics": metrics,
                "delta": _deltas(baseline_metrics[window_name], metrics),
                "candidate_retargets": len(touches),
                "retarget_state_sample": touches[:10],
                "slv_trade_summary": _slv_trade_summary(result),
            }
        decision = _variant_decision(baseline_metrics, variant_windows, touch_counts)
        variants[variant_name] = {
            "description": variant["description"],
            "parameters": {
                "target_tickers": list(variant["target_tickers"]),
                "base_target_mult": float(TREND_COMMODITIES_TARGET_ATR_MULT),
                "target_mult": float(variant["target_mult"]),
            },
            "windows": variant_windows,
            "touch_counts": touch_counts,
            "decision": decision,
        }

    accepted_variants = [
        name for name, payload in variants.items()
        if payload["decision"]["decision"] == "accepted_for_shared_implementation"
    ]
    best_variant = max(
        variants.items(),
        key=lambda item: sum(
            float((window_payload["delta"].get("expected_value_score") or 0.0))
            for window_payload in item[1]["windows"].values()
        ),
    )[0]
    final_decision = "accepted_for_implementation" if accepted_variants else "rejected"
    final_reason = (
        f"Accepted variants: {', '.join(accepted_variants)}"
        if accepted_variants
        else "All variants failed majority-window EV/Gate 4 robustness."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "stem": STEM,
        "run_at": run_at,
        "change_type": "exit_target_width_precious_metals_state_replay",
        "alpha_hypothesis": (
            "SLV trend winners should be allowed to run to the gold-like 8 ATR target only "
            "when silver is leading gold on 20-day momentum; otherwise the current 7 ATR "
            "target avoids repeating broad commodity target overextension."
        ),
        "alpha_category": "exit",
        "why_not_llm_soft_ranking": (
            "LLM soft-ranking still lacks enough replay coverage for trustworthy alpha "
            "evaluation, so this run tests an OHLCV-only exit alpha instead."
        ),
        "historical_no_repeat_check": {
            "nearby_failed_family": "broad commodity / SLV target widening",
            "why_this_is_not_simple_repeat": (
                "The replay adds an explicit precious-metals state discriminator using "
                "SLV-vs-GLD 20d momentum, which the playbook required before retrying "
                "non-gold commodity target extension."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "windows": {
            name: {
                "start": spec["start"],
                "end": spec["end"],
                "snapshot": _repo_rel(spec["snapshot"]),
                "state_note": spec["state_note"],
                "baseline_metrics": baseline_metrics[name],
                "baseline_slv_trade_summary": _slv_trade_summary(baseline_results[name]),
            }
            for name, spec in WINDOWS.items()
        },
        "variants": variants,
        "best_variant_by_sum_ev_delta": best_variant,
        "decision": final_decision,
        "decision_reason": final_reason,
        "next_step": (
            "Implement accepted variant in shared risk_engine and add parity coverage."
            if accepted_variants
            else "Do not promote precious-metals state target widening without new forward evidence."
        ),
    }

    log_payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": run_at,
        "hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "parameters": {
            name: variant["parameters"]
            for name, variant in variants.items()
        },
        "date_range": {
            name: {"start": spec["start"], "end": spec["end"]}
            for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"]
            for name, spec in WINDOWS.items()
        },
        "before_metrics": baseline_metrics,
        "after_metrics": {
            name: variant["windows"]
            for name, variant in variants.items()
        },
        "expected_value_score_delta": {
            name: {
                window: payload["delta"].get("expected_value_score")
                for window, payload in variant["windows"].items()
            }
            for name, variant in variants.items()
        },
        "decision": final_decision,
        "rejection_reason": None if accepted_variants else final_reason,
        "production_impact": payload["production_impact"],
        "artifacts": {
            "json": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "markdown": _repo_rel(ARTIFACT_MD),
        },
    }

    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Precious-metals state target replay",
        "status": final_decision,
        "summary": final_reason,
        "best_variant": best_variant,
        "artifact": _repo_rel(ARTIFACT_MD),
        "created_at": run_at,
    }

    lines = [
        f"# {EXPERIMENT_ID} precious-metals state target replay",
        "",
        f"Run at: `{run_at}`",
        "",
        "## Hypothesis",
        "",
        payload["alpha_hypothesis"],
        "",
        "## Decision",
        "",
        f"`{final_decision}` - {final_reason}",
        "",
        "## Baseline",
        "",
        "| window | EV | sharpe_daily | max_dd | pnl | win_rate | trades | survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, metrics in baseline_metrics.items():
        lines.append(
            "| {name} | {ev} | {sharpe} | {dd} | {pnl} | {win} | {trades} | {surv} |".format(
                name=name,
                ev=metrics.get("expected_value_score"),
                sharpe=metrics.get("sharpe_daily"),
                dd=metrics.get("max_drawdown_pct"),
                pnl=metrics.get("total_pnl"),
                win=metrics.get("win_rate"),
                trades=metrics.get("total_trades"),
                surv=metrics.get("survival_rate"),
            )
        )
    lines.extend(
        [
            "",
            "## Variants",
            "",
        ]
    )
    for variant_name, variant in variants.items():
        lines.extend(
            [
                f"### {variant_name}",
                "",
                variant["description"],
                "",
                "| window | retargets | EV delta | sharpe delta | max_dd delta | pnl delta | win delta | trades delta | Gate4 |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for window_name, window_payload in variant["windows"].items():
            delta = window_payload["delta"]
            gate4 = _gate4_window_pass(
                baseline_metrics[window_name],
                window_payload["metrics"],
            )
            lines.append(
                "| {window} | {touches} | {ev} | {sharpe} | {dd} | {pnl} | {win} | {trades} | {gate4} |".format(
                    window=window_name,
                    touches=window_payload["candidate_retargets"],
                    ev=delta.get("expected_value_score"),
                    sharpe=delta.get("sharpe_daily"),
                    dd=delta.get("max_drawdown_pct"),
                    pnl=delta.get("total_pnl"),
                    win=delta.get("win_rate"),
                    trades=delta.get("total_trades"),
                    gate4="PASS" if gate4 else "FAIL",
                )
            )
        lines.extend(
            [
                "",
                f"Decision: `{variant['decision']['decision']}` - {variant['decision']['reason']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Production parity",
            "",
            "Replay only. No production policy, backtester adapter, run adapter, candidate universe, ranking, sizing, stop, LLM, or news behavior changed.",
            "",
            "If a variant is later promoted, it must be implemented in shared `risk_engine.enrich_signals()` and covered by parity tests before enabling.",
            "",
        ]
    )
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_payload)
    _write_json(TICKET_JSON, ticket_payload)
    _append_jsonl_dedup(EXPERIMENT_LOG, log_payload)
    _write_text(ARTIFACT_MD, "\n".join(lines) + "\n")

    print(json.dumps(_safe({
        "experiment_id": EXPERIMENT_ID,
        "decision": final_decision,
        "decision_reason": final_reason,
        "best_variant": best_variant,
        "artifacts": log_payload["artifacts"],
    }), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
