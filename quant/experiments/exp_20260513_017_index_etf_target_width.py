"""exp-20260513-017: index ETF target-width replay.

Tests one lifecycle variable: whether broad index ETFs (QQQ/SPY/IWM) should
use their own wider ATR target path before being treated as a separate strategy
pool. The current live QQQ concern is a SIGNAL_TARGET trigger, so this scout
isolates target/exit width and leaves entries, ranking, sizing, universe, LLM,
news, and overlay behavior unchanged.

This script is replay-only. A positive result must be promoted through shared
risk_engine/constants policy and re-run before it can affect live orders.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260513-017"
EXPERIMENT_SLUG = "index_etf_target_width"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import risk_engine  # noqa: E402
from backtester import BacktestEngine, DEFAULT_CONFIG  # noqa: E402
from data_layer import get_universe  # noqa: E402


OUTPUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUTPUT_JSON = OUTPUT_DIR / f"{EXPERIMENT_SLUG}.json"
DOC_LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK_MD = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
LIVE_TREND_SIGNALS_JSON = REPO_ROOT / "data" / "trend_signals_20260512.json"

INDEX_ETFS = ("QQQ", "SPY", "IWM")
TARGET_STRATEGIES = ("trend_long", "breakout_long")
TARGET_KEY = "index_etf_target_width_applied"

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
                "state_note": "rotation-heavy bull where strategy profits but lags indexes",
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

VARIANTS = OrderedDict(
    [
        ("index_etf_target_5_0atr", {"target_atr_mult": 5.0}),
        ("index_etf_target_6_0atr", {"target_atr_mult": 6.0}),
        ("index_etf_target_7_0atr", {"target_atr_mult": 7.0}),
    ]
)


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


RESULT_KEYS = (
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
)


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    convergence = result.get("convergence") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score")),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct", result.get("total_return_pct"))
        ),
        "sharpe_daily": _round(result.get("sharpe_daily"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct")),
        "win_rate": _round(result.get("win_rate")),
        "trade_count": _round(result.get("total_trades", result.get("trade_count"))),
        "signals_generated": _round(result.get("signals_generated")),
        "signals_survived": _round(result.get("signals_survived")),
        "survival_rate": _round(result.get("survival_rate")),
        "worst_trade_pct": _round(result.get("worst_trade_pct")),
        "max_consecutive_losses": _round(result.get("max_consecutive_losses")),
        "tail_loss_share": _round(result.get("tail_loss_share")),
        "spy_buy_hold_return_pct": _round(benchmarks.get("spy_buy_hold_return_pct")),
        "qqq_buy_hold_return_pct": _round(benchmarks.get("qqq_buy_hold_return_pct")),
        "converged": bool(convergence.get("converged", False)) if convergence else None,
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in RESULT_KEYS:
        a_value = after.get(key)
        b_value = before.get(key)
        if isinstance(a_value, (int, float)) and isinstance(b_value, (int, float)):
            if key in {"trade_count", "signals_generated", "signals_survived", "max_consecutive_losses"}:
                out[key] = int(a_value - b_value)
            else:
                out[key] = _round(a_value - b_value)
    return out


def _aggregate(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values())
        ),
        "total_pnl_sum": _round(
            sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()),
            2,
        ),
        "trade_count_sum": int(sum(int(row.get("trade_count") or 0) for row in metrics.values())),
        "signals_generated_sum": int(
            sum(int(row.get("signals_generated") or 0) for row in metrics.values())
        ),
        "signals_survived_sum": int(
            sum(int(row.get("signals_survived") or 0) for row in metrics.values())
        ),
        "max_drawdown_pct_max": _round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values())
        ),
        "survival_rate_min": _round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics.values())
        ),
        "tail_loss_share_max": _round(
            max(float(row.get("tail_loss_share") or 0.0) for row in metrics.values())
        ),
        "worst_trade_pct_min": _round(
            min(float(row.get("worst_trade_pct") or 0.0) for row in metrics.values())
        ),
        "max_consecutive_losses_max": int(
            max(int(row.get("max_consecutive_losses") or 0) for row in metrics.values())
        ),
    }


def _aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in after.items():
        before_value = before.get(key)
        if isinstance(value, (int, float)) and isinstance(before_value, (int, float)):
            out[key] = _round(value - before_value)
    return out


def _audit_open_positions() -> dict[str, Any]:
    payload = json.loads(OPEN_POSITIONS_JSON.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for section in ("positions", "observations"):
        for row in payload.get(section) or []:
            if isinstance(row, dict):
                rows.append(row)

    missing = []
    for row in rows:
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"ticker": row.get("ticker"), "field": field})

    qqq_row = next((row for row in rows if row.get("ticker") == "QQQ"), None)
    return {
        "path": str(OPEN_POSITIONS_JSON.relative_to(REPO_ROOT)),
        "checked_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_required_fields": missing,
        "passed": not missing,
        "qqq_position": {
            "entry_date": (qqq_row or {}).get("entry_date"),
            "avg_cost": (qqq_row or {}).get("avg_cost"),
            "target_price": (qqq_row or {}).get("target_price"),
            "stop_price": (qqq_row or {}).get("stop_price"),
            "opened_by_strategy": (qqq_row or {}).get("opened_by_strategy"),
        },
    }


def _live_qqq_trigger_audit() -> dict[str, Any]:
    if not LIVE_TREND_SIGNALS_JSON.exists():
        return {"available": False}
    payload = json.loads(LIVE_TREND_SIGNALS_JSON.read_text(encoding="utf-8"))
    signals = payload.get("signals") or {}
    qqq = signals.get("QQQ") if isinstance(signals, dict) else None
    if not isinstance(qqq, dict):
        return {"available": False}
    position = qqq.get("position") or {}
    exit_levels = position.get("exit_levels") or {}
    exit_signals = position.get("exit_signals") or {}
    return {
        "available": True,
        "source": str(LIVE_TREND_SIGNALS_JSON.relative_to(REPO_ROOT)),
        "close": _round(qqq.get("close")),
        "daily_high": _round(qqq.get("daily_high")),
        "atr": _round(qqq.get("atr")),
        "unrealized_pnl_pct": _round(position.get("unrealized_pnl_pct")),
        "signal_target_price": _round(exit_levels.get("signal_target_price")),
        "signal_target_pct": _round(exit_levels.get("signal_target_pct")),
        "triggered_rules": [
            {
                "rule": rule.get("rule"),
                "message": rule.get("message"),
                "trigger_price": _round(rule.get("trigger_price")),
                "target_price": _round(rule.get("target_price")),
            }
            for rule in exit_signals.get("triggered_rules") or []
            if isinstance(rule, dict)
        ],
    }


def _matches_index_etf_signal(signal: dict[str, Any]) -> bool:
    return (
        signal.get("ticker") in INDEX_ETFS
        and signal.get("strategy") in TARGET_STRATEGIES
    )


def _make_enrich_signals(original_enrich, target_mult: float):
    touched: list[dict[str, Any]] = []

    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(signals, features_dict, atr_target_mult=atr_target_mult)
        out = []
        for signal in enriched:
            if not _matches_index_etf_signal(signal):
                out.append(signal)
                continue
            ticker = signal.get("ticker")
            features = (features_dict or {}).get(ticker) or {}
            atr = features.get("atr")
            if not isinstance(atr, (int, float)) or atr <= 0:
                out.append(signal)
                continue
            before_target = signal.get("target_price")
            before_mult = signal.get("target_mult_used")
            retargeted = risk_engine._retarget_signal_with_atr_mult(
                signal,
                atr,
                target_mult,
            )
            retargeted[TARGET_KEY] = target_mult
            out.append(retargeted)
            touched.append(
                {
                    "ticker": ticker,
                    "strategy": signal.get("strategy"),
                    "sector": signal.get("sector"),
                    "signal_date": signal.get("signal_date") or signal.get("date"),
                    "entry_price": _round(signal.get("entry_price"), 4),
                    "stop_price": _round(signal.get("stop_price"), 4),
                    "target_before": _round(before_target, 4),
                    "target_after": _round(retargeted.get("target_price"), 4),
                    "target_mult_before": before_mult,
                    "target_mult_after": target_mult,
                    "atr": _round(atr, 4),
                    "trade_quality_score": signal.get("trade_quality_score"),
                    "regime_exit_bucket": signal.get("regime_exit_bucket"),
                    "regime_exit_score": signal.get("regime_exit_score"),
                }
            )
        return out

    wrapped.touched = touched  # type: ignore[attr-defined]
    return wrapped


def _run_window(window: dict[str, str], variant: dict[str, Any] | None = None) -> dict[str, Any]:
    original_enrich = risk_engine.enrich_signals
    if variant is not None:
        risk_engine.enrich_signals = _make_enrich_signals(
            original_enrich,
            float(variant["target_atr_mult"]),
        )
    try:
        engine = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config=deepcopy(DEFAULT_CONFIG),
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        )
        result = engine.run()
        touched = (
            list(getattr(risk_engine.enrich_signals, "touched", []))
            if variant is not None
            else []
        )
    finally:
        risk_engine.enrich_signals = original_enrich

    if result.get("error"):
        raise RuntimeError(result["error"])
    return {
        "result": result,
        "metrics": _metrics(result),
        "trades": result.get("trades") or [],
        "touched_candidates": touched,
    }


def _trade_key(trade: dict[str, Any]) -> str:
    return "|".join(
        [
            str(trade.get("ticker") or ""),
            str(trade.get("entry_date") or ""),
            str(trade.get("strategy") or ""),
            str(round(float(trade.get("entry_price") or 0.0), 4)),
        ]
    )


def _index_etf_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        if trade.get("ticker") not in INDEX_ETFS:
            continue
        rows.append(
            {
                "trade_key": _trade_key(trade),
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "shares": trade.get("shares"),
                "entry_price": _round(trade.get("entry_price"), 4),
                "exit_price": _round(trade.get("exit_price"), 4),
                "target_mult_used": trade.get("target_mult_used"),
                "pnl": _round(trade.get("pnl"), 2),
                "pnl_pct_net": _round(trade.get("pnl_pct_net")),
                "addon_count": trade.get("addon_count"),
                "sizing_multipliers": trade.get("sizing_multipliers") or {},
            }
        )
    return rows


def _changed_index_trades(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    before_by_key = {_trade_key(row): row for row in before if row.get("ticker") in INDEX_ETFS}
    after_by_key = {_trade_key(row): row for row in after if row.get("ticker") in INDEX_ETFS}
    changed = []
    for key in sorted(set(before_by_key) & set(after_by_key)):
        b = before_by_key[key]
        a = after_by_key[key]
        if (
            round(float(b.get("pnl") or 0.0), 2) == round(float(a.get("pnl") or 0.0), 2)
            and b.get("exit_date") == a.get("exit_date")
            and b.get("exit_reason") == a.get("exit_reason")
        ):
            continue
        changed.append(
            {
                "key": key,
                "before": {
                    "ticker": b.get("ticker"),
                    "entry_date": b.get("entry_date"),
                    "exit_date": b.get("exit_date"),
                    "exit_reason": b.get("exit_reason"),
                    "target_mult_used": b.get("target_mult_used"),
                    "pnl": _round(b.get("pnl"), 2),
                    "pnl_pct_net": _round(b.get("pnl_pct_net")),
                },
                "after": {
                    "ticker": a.get("ticker"),
                    "entry_date": a.get("entry_date"),
                    "exit_date": a.get("exit_date"),
                    "exit_reason": a.get("exit_reason"),
                    "target_mult_used": a.get("target_mult_used"),
                    "pnl": _round(a.get("pnl"), 2),
                    "pnl_pct_net": _round(a.get("pnl_pct_net")),
                },
            }
        )
    return {
        "added_count": len(set(after_by_key) - set(before_by_key)),
        "removed_count": len(set(before_by_key) - set(after_by_key)),
        "changed_count": len(changed),
        "changed": changed,
    }


def _summarize_variant(
    name: str,
    variant: dict[str, Any],
    baselines: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] {name}")
        after = _run_window(window, variant)
        before_metrics = baselines[label]["metrics"]
        after_metrics = after["metrics"]
        rows[label] = {
            "window": window,
            "before": before_metrics,
            "after": after_metrics,
            "delta": _delta(after_metrics, before_metrics),
            "index_etf_candidate_count": len(after["touched_candidates"]),
            "index_etf_candidates": after["touched_candidates"],
            "index_etf_trades_before": _index_etf_trades(baselines[label]["trades"]),
            "index_etf_trades_after": _index_etf_trades(after["trades"]),
            "changed_index_etf_trades": _changed_index_trades(
                baselines[label]["trades"],
                after["trades"],
            ),
        }
        delta = rows[label]["delta"]
        print(
            "[{label}] {name} dEV={dev:+.4f} dPnL={dpnl:+.2f} candidates={candidates} changed_trades={changed}".format(
                label=label,
                name=name,
                dev=float(delta.get("expected_value_score") or 0.0),
                dpnl=float(delta.get("total_pnl") or 0.0),
                candidates=rows[label]["index_etf_candidate_count"],
                changed=rows[label]["changed_index_etf_trades"]["changed_count"],
            )
        )
    return {
        "variant": variant,
        "rows": rows,
        "aggregate": _variant_aggregate(rows),
    }


def _variant_aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_metrics = {label: row["before"] for label, row in rows.items()}
    after_metrics = {label: row["after"] for label, row in rows.items()}
    before = _aggregate(before_metrics)
    after = _aggregate(after_metrics)
    delta = _aggregate_delta(after, before)
    ev_delta_sum = float(delta.get("expected_value_score_sum") or 0.0)
    pnl_delta_sum = float(delta.get("total_pnl_sum") or 0.0)
    ev_before_sum = float(before.get("expected_value_score_sum") or 0.0)
    pnl_before_sum = float(before.get("total_pnl_sum") or 0.0)
    return {
        "expected_value_score_before_sum": _round(ev_before_sum),
        "expected_value_score_after_sum": _round(after.get("expected_value_score_sum")),
        "expected_value_score_delta_sum": _round(ev_delta_sum),
        "expected_value_score_delta_pct": _round(ev_delta_sum / ev_before_sum)
        if ev_before_sum
        else None,
        "total_pnl_before_sum": _round(pnl_before_sum, 2),
        "total_pnl_after_sum": _round(after.get("total_pnl_sum"), 2),
        "total_pnl_delta_sum": _round(pnl_delta_sum, 2),
        "total_pnl_delta_pct": _round(pnl_delta_sum / pnl_before_sum)
        if pnl_before_sum
        else None,
        "ev_windows_improved": sum(
            1 for row in rows.values() if row["delta"].get("expected_value_score", 0) > 0
        ),
        "ev_windows_regressed": sum(
            1 for row in rows.values() if row["delta"].get("expected_value_score", 0) < 0
        ),
        "pnl_windows_improved": sum(
            1 for row in rows.values() if row["delta"].get("total_pnl", 0) > 0
        ),
        "pnl_windows_regressed": sum(
            1 for row in rows.values() if row["delta"].get("total_pnl", 0) < 0
        ),
        "drawdown_delta_max": _round(
            max(float(row["delta"].get("max_drawdown_pct") or 0.0) for row in rows.values())
        ),
        "survival_rate_min_after": _round(after.get("survival_rate_min")),
        "tail_loss_share_delta_max": _round(
            max(float(row["delta"].get("tail_loss_share") or 0.0) for row in rows.values())
        ),
        "worst_trade_delta_min": _round(
            min(float(row["delta"].get("worst_trade_pct") or 0.0) for row in rows.values())
        ),
        "max_consecutive_losses_delta_max": int(
            max(int(row["delta"].get("max_consecutive_losses") or 0) for row in rows.values())
        ),
        "index_etf_candidate_count_sum": int(
            sum(row["index_etf_candidate_count"] for row in rows.values())
        ),
        "changed_index_etf_trade_count_sum": int(
            sum(row["changed_index_etf_trades"]["changed_count"] for row in rows.values())
        ),
        "added_index_etf_trade_count_sum": int(
            sum(row["changed_index_etf_trades"]["added_count"] for row in rows.values())
        ),
        "removed_index_etf_trade_count_sum": int(
            sum(row["changed_index_etf_trades"]["removed_count"] for row in rows.values())
        ),
    }


def _gate4_passed(aggregate: dict[str, Any]) -> bool:
    return bool(
        aggregate["index_etf_candidate_count_sum"] > 0
        and aggregate["changed_index_etf_trade_count_sum"] > 0
        and aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] == 0
        and aggregate["pnl_windows_regressed"] <= 1
        and aggregate["survival_rate_min_after"] >= 0.05
        and aggregate["drawdown_delta_max"] <= 0.01
        and aggregate["tail_loss_share_delta_max"] <= 0.05
    )


def _best_variant(variants: OrderedDict[str, dict[str, Any]]) -> str:
    return max(
        variants,
        key=lambda name: (
            variants[name]["aggregate"]["expected_value_score_delta_sum"],
            variants[name]["aggregate"]["total_pnl_delta_sum"],
            -variants[name]["aggregate"]["drawdown_delta_max"],
        ),
    )


def _make_payload(
    gate2: dict[str, Any],
    live_trigger: dict[str, Any],
    baselines: OrderedDict[str, dict[str, Any]],
    variants: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    best_name = _best_variant(variants)
    best = variants[best_name]
    accepted = _gate4_passed(best["aggregate"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "accepted" if accepted else "rejected",
        "decision": (
            "accepted_for_shared_policy_implementation"
            if accepted
            else "rejected_index_etf_target_width"
        ),
        "hypothesis": (
            "Broad index ETFs may be target-clipped by the generic target path. "
            "If QQQ/SPY/IWM behave more like slow index trend sleeves than single-name "
            "breakouts, a separate target-width pool should improve three-window EV "
            "without worsening drawdown or tail loss."
        ),
        "alpha_hypothesis": {
            "category": "exit / lifecycle",
            "statement": (
                "QQQ-like index ETFs should only become their own strategy pool if a "
                "single deterministic lifecycle variable, wider ATR targets, improves "
                "accepted-stack outcomes across the canonical fixed windows."
            ),
            "why_now": (
                "The live QQQ position triggered SIGNAL_TARGET at a relatively small "
                "index gain. LLM soft-ranking remains sample-limited, and prior broad "
                "ETF pool expansion was rejected, so this tests lifecycle width rather "
                "than adding or reshuffling tickers."
            ),
        },
        "gate2": gate2,
        "live_qqq_trigger_audit": live_trigger,
        "change_type": "alpha_search_exit_lifecycle_sweep",
        "changed_variable": (
            "target ATR multiple for index ETF signals with ticker in QQQ/SPY/IWM"
        ),
        "parameters": {
            "single_causal_variable": "index_etf_target_atr_multiple",
            "index_etfs": INDEX_ETFS,
            "target_strategies": TARGET_STRATEGIES,
            "variants": VARIANTS,
            "best_variant": best_name,
            "locked_variables": [
                "core universe",
                "ETF overlay candidate pool",
                "signal generation",
                "entry ranking",
                "entry open cancels",
                "position sizing",
                "risk multipliers",
                "add-ons",
                "portfolio slot limits",
                "LLM/news behavior",
                "hard stops",
                "sector map",
            ],
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260512-777": (
                    "Adjacent low-deployment ETF candidate-pool variants were rejected; "
                    "this run does not add or replace ETF tickers."
                ),
                "exp-20260506-006": (
                    "SPY-relative leader target widening was rejected; this run narrows "
                    "scope to actual broad index ETFs only, excluding single-name leaders."
                ),
                "exp-20260428-035 / exp-20260430-008": (
                    "Broad ETF universe expansion as direct core alpha was rejected; "
                    "this tests exit lifecycle, not universe expansion."
                ),
                "exp-20260513-008": (
                    "Legacy target full exits were not promoted; this run tests future "
                    "simulated index ETF target width through the canonical target path."
                ),
            },
            "mechanism_guard": (
                "Avoids no-repeat zones: no broad/static ETF expansion, no adjacent "
                "low-deployment overlay pool retry, no LLM soft-ranking, and no blunt "
                "production-only target trim."
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window protocol",
            "windows": {
                label: {
                    "date_range": f"{window['start']} -> {window['end']}",
                    "snapshot": window["snapshot"],
                    "state_note": window["state_note"],
                }
                for label, window in WINDOWS.items()
            },
        },
        "before_metrics": {label: row["metrics"] for label, row in baselines.items()},
        "after_metrics": {
            label: row["after"] for label, row in best["rows"].items()
        },
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in best["rows"].items()},
            "aggregate": best["aggregate"],
        },
        "variants": variants,
        "best_variant": best_name,
        "gate3": {
            "new_filter_added": False,
            "survival_rate_min_after": best["aggregate"]["survival_rate_min_after"],
            "passed": best["aggregate"]["survival_rate_min_after"] >= 0.05,
        },
        "gate4": {
            "passed": accepted,
            "basis": (
                "Requires at least one behavior-changing index ETF trade, positive "
                "aggregate EV and PnL, EV improvement in at least two windows, no EV "
                "regression, survival >= 5%, and no material drawdown/tail loss drift."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add shared constants/risk_engine target policy used by both "
                "backtester.py and run.py, then rerun the same three-window comparison."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking data remains insufficient, so this deterministic "
                "lifecycle scout avoids depending on LLM historical replay."
            ),
        },
        "rejection_reason": None
        if accepted
        else (
            "Index ETF target widening did not clear the canonical three-window "
            "behavioral Gate 4; do not split QQQ/SPY/IWM into a promoted target "
            "pool on this evidence."
        ),
        "next_evidence_needed": [
            "Forward shadow tracking of index ETF target touches versus holding/ratcheting.",
            "A narrower state discriminator, such as index trend strength or breadth, before retrying target width.",
            "If a future variant is positive, implement it in shared risk_engine/constants before production use.",
        ],
        "decision_notes": (
            "A separate index ETF strategy pool is only justified if this or a narrower "
            "state-conditioned lifecycle rule creates real behavior-changing PnL/EV in "
            "the fixed windows. Otherwise, treat the recent QQQ trigger as a forward "
            "watch item rather than a production policy change."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_017_index_etf_target_width.py",
            str(OUTPUT_JSON.relative_to(REPO_ROOT)),
            str(DOC_LOG_JSON.relative_to(REPO_ROOT)),
            str(DOC_TICKET_JSON.relative_to(REPO_ROOT)),
            str(DOC_ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }


def _write_markdown(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Index ETF Target Width",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Live QQQ Trigger",
        "",
        f"- source: `{payload['live_qqq_trigger_audit'].get('source')}`",
        f"- close/high: `{payload['live_qqq_trigger_audit'].get('close')}` / `{payload['live_qqq_trigger_audit'].get('daily_high')}`",
        f"- signal target: `{payload['live_qqq_trigger_audit'].get('signal_target_price')}` "
        f"({payload['live_qqq_trigger_audit'].get('signal_target_pct')})",
        f"- triggered rules: `{payload['live_qqq_trigger_audit'].get('triggered_rules')}`",
        "",
        "## Gate 4",
        "",
        f"- passed: `{payload['gate4']['passed']}`",
        f"- best variant: `{payload['best_variant']}`",
        f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']:+.4f}` "
        f"({aggregate['expected_value_score_delta_pct']:+.2%})",
        f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']:+,.2f}` "
        f"({aggregate['total_pnl_delta_pct']:+.2%})",
        f"- EV windows improved/regressed: `{aggregate['ev_windows_improved']}` / `{aggregate['ev_windows_regressed']}`",
        f"- index ETF candidates / changed trades: `{aggregate['index_etf_candidate_count_sum']}` / `{aggregate['changed_index_etf_trade_count_sum']}`",
        f"- survival min after: `{aggregate['survival_rate_min_after']}`",
        "",
        "## Three-Window Deltas",
        "",
        "| Window | EV delta | PnL delta | Sharpe delta | DD delta | Tail delta | Trades delta | Candidates | Changed index trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    best_rows = payload["variants"][payload["best_variant"]]["rows"]
    for label, row in best_rows.items():
        delta = row["delta"]
        lines.append(
            "| `{label}` | {dev:+.4f} | {dpnl:+.2f} | {dsharpe:+.4f} | {ddd:+.4f} | {dtail:+.4f} | {dtrades:+d} | {candidates} | {changed} |".format(
                label=label,
                dev=float(delta.get("expected_value_score") or 0.0),
                dpnl=float(delta.get("total_pnl") or 0.0),
                dsharpe=float(delta.get("sharpe_daily") or 0.0),
                ddd=float(delta.get("max_drawdown_pct") or 0.0),
                dtail=float(delta.get("tail_loss_share") or 0.0),
                dtrades=int(delta.get("trade_count") or 0),
                candidates=row["index_etf_candidate_count"],
                changed=row["changed_index_etf_trades"]["changed_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Production Parity",
            "",
            "No production order path changed. A positive promotion requires moving the target policy into shared `constants.py` / `risk_engine.py`, which is imported by both `run.py` and `backtester.py`, then rerunning this same three-window protocol.",
            "",
        ]
    )
    DOC_ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_playbook(payload: dict[str, Any]) -> None:
    if not PLAYBOOK_MD.exists():
        return
    text = PLAYBOOK_MD.read_text(encoding="utf-8", errors="replace")
    if f"`{EXPERIMENT_ID}`" in text:
        return
    aggregate = payload["delta_metrics"]["aggregate"]
    marker = "## Recent mechanism insights"
    entry = (
        "\n"
        f"- `{EXPERIMENT_ID}` ({payload['decision']}): Index ETF lifecycle scout "
        "tested wider target widths for `QQQ`/`SPY`/`IWM` only. Best "
        f"`{payload['best_variant']}` produced aggregate EV delta "
        f"{aggregate['expected_value_score_delta_sum']} "
        f"({aggregate['expected_value_score_delta_pct']:.2%}), PnL delta "
        f"${aggregate['total_pnl_delta_sum']}, with "
        f"{aggregate['changed_index_etf_trade_count_sum']} changed index ETF trades. "
        "Do not split broad index ETFs into a promoted target pool without a "
        "positive shared-policy retest or a narrower state-conditioned discriminator.\n"
    )
    if marker in text:
        text = text.replace(marker, marker + entry, 1)
    else:
        text = text + "\n" + marker + "\n" + entry
    PLAYBOOK_MD.write_text(text, encoding="utf-8")


def run() -> dict[str, Any]:
    gate2 = _audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    live_trigger = _live_qqq_trigger_audit()

    baselines: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline")
        baselines[label] = _run_window(window)

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, variant in VARIANTS.items():
        variants[name] = _summarize_variant(name, variant, baselines)

    payload = _make_payload(gate2, live_trigger, baselines, variants)
    _write_json(OUTPUT_JSON, payload)
    _write_json(DOC_LOG_JSON, payload)
    _write_json(
        DOC_TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "generated_at": payload["generated_at"],
            "decision": payload["decision"],
            "title": "Index ETF target width",
            "summary": f"Best {payload['best_variant']}; Gate4={payload['gate4']['passed']}",
            "best_variant": payload["best_variant"],
            "delta_metrics": payload["delta_metrics"]["aggregate"],
            "production_impact": payload["production_impact"],
            "log_file": str(DOC_LOG_JSON.relative_to(REPO_ROOT)),
        },
    )
    _write_markdown(payload)
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _update_playbook(payload)
    return payload


def main() -> int:
    payload = run()
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "best_variant": payload["best_variant"],
                "aggregate": payload["delta_metrics"]["aggregate"],
                "output": str(OUTPUT_JSON.relative_to(REPO_ROOT)),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
