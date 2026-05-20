"""exp-20260520-001: state-surface low-extension support notional.

Alpha search. Freezes the accepted state-surface default-off paper stack
through exp-20260519-033, then tests one production-visible allocation
variable: already-selected candidates whose 5-day return has not extended
above 2% receive a small paper-notional support scalar.

Core entries, exits, candidate eligibility, queue ranking, hold days, active
capacity, LLM/news, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260520-001"
EXPERIMENT_SLUG = "state_surface_low_extension_support_notional"
BASELINE_EXPERIMENT_ID = "exp-20260519-033"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_033_state_surface_rank_depth_score_volume_notional as e33  # noqa: E402
from state_surface_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    RANK_NOTIONAL_LOW_EXTENSION_SUPPORT_RULE_VERSION,
    _rank_notional_profile_payload,
)


prev = e33.prev
WINDOWS = e33.WINDOWS
BASELINE_VARIANT = "accepted_rank_depth_score_volume_notional"
LOW_EXTENSION_RULE_VERSION = RANK_NOTIONAL_LOW_EXTENSION_SUPPORT_RULE_VERSION
RET5_MAX = 0.02
MIN_SELECTED_TRADES = e33.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = 8
MIN_ADJUSTED_WINDOWS = 3
MIN_EV_IMPROVED_WINDOWS = 3
MAX_DRAWDOWN_WORSE = e33.MAX_DRAWDOWN_WORSE
MAX_SINGLE_TICKER_POSITIVE_SHARE = e33.MAX_SINGLE_TICKER_POSITIVE_SHARE

OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

LOW_EXTENSION_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [(BASELINE_VARIANT, {"scalar": None, "aggression_order": 0})]
)
for scalar in (0.95, 1.025, 1.05, 1.075, 1.10, 1.15):
    LOW_EXTENSION_VARIANTS[
        f"ret5_le_0p02_scalar_{str(scalar).replace('.', 'p')}"
    ] = {
        "scalar": scalar,
        "aggression_order": len(LOW_EXTENSION_VARIANTS),
        "description": (
            "selected state-surface paper candidates with ret5 <= 0.02 "
            f"receive {scalar:.3f}x notional support"
        ),
    }


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
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


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _round(value: Any, digits: int = 4) -> float | None:
    number = prev._float(value)
    if number is None:
        return None
    return round(number, digits)


def _ret5(trade: dict[str, Any]) -> float | None:
    top_level = prev._float(trade.get("ret5"))
    if top_level is not None:
        return top_level
    return prev._float((trade.get("features") or {}).get("ret5"))


def _profile_name(scalar: float | None) -> str | None:
    if scalar is None:
        return None
    scalar_text = str(round(float(scalar), 6)).rstrip("0").rstrip(".")
    return f"ret5_le_0p02_{scalar_text.replace('.', 'p')}x"


def _low_extension_qualified(trade: dict[str, Any]) -> bool:
    ret5 = _ret5(trade)
    return bool(ret5 is not None and ret5 <= RET5_MAX)


def _apply_low_extension_support(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    scalar = prev._float(variant.get("scalar"))
    adjusted: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade)
        row["features"] = dict(row.get("features") or {})
        qualifies = _low_extension_qualified(row)
        applies = variant_name != BASELINE_VARIANT and scalar is not None and qualifies
        row["low_extension_support_variant"] = variant_name
        row["low_extension_support_rule_version"] = LOW_EXTENSION_RULE_VERSION
        row["rank_notional_low_extension_support_rule_version"] = LOW_EXTENSION_RULE_VERSION
        row["low_extension_support_applied"] = bool(applies)
        row["low_extension_support_qualified"] = bool(qualifies)
        row["low_extension_support_ret5"] = _round(_ret5(row), 6)
        row["low_extension_support_max_ret5"] = RET5_MAX
        row["low_extension_support_configured_scalar"] = _round(scalar, 6)
        row["low_extension_support_scalar"] = scalar if applies else None
        row["low_extension_support_profile_name"] = _profile_name(scalar)
        row["low_extension_support_base_multiplier"] = prev._float(
            row.get("rank_notional_multiplier")
        )
        if applies:
            base_notional = float(row.get("notional") or 0.0)
            new_notional = round(base_notional * float(scalar), 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["low_extension_support_base_notional"] = base_notional
            row["notional"] = new_notional
            row["shares"] = new_notional / entry_open
            row["pnl"] = round(new_notional * net_return, 2)
            base_multiplier = prev._float(row.get("rank_notional_multiplier"))
            if base_multiplier is not None:
                row["rank_notional_multiplier"] = round(
                    base_multiplier * float(scalar),
                    6,
                )
        adjusted.append(row)
    return adjusted


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = e33._selected_trade_rows(trades)
    for row, trade in zip(rows, trades):
        row["low_extension_support_applied"] = trade.get(
            "low_extension_support_applied"
        )
        row["low_extension_support_qualified"] = trade.get(
            "low_extension_support_qualified"
        )
        row["low_extension_support_ret5"] = trade.get("low_extension_support_ret5")
        row["low_extension_support_max_ret5"] = trade.get(
            "low_extension_support_max_ret5"
        )
        row["low_extension_support_scalar"] = trade.get(
            "low_extension_support_scalar"
        )
        row["low_extension_support_base_multiplier"] = trade.get(
            "low_extension_support_base_multiplier"
        )
        row["low_extension_support_profile_name"] = trade.get(
            "low_extension_support_profile_name"
        )
    return rows


def _variant_payload(
    *,
    variant_name: str,
    variant: dict[str, Any],
    baseline_payload: dict[str, Any],
    baseline_trades_by_window: dict[str, list[dict[str, Any]]],
    core_curves: dict[str, list[tuple[str, float]]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    selected_all: list[dict[str, Any]] = []
    for label, window in WINDOWS.items():
        baseline_trades = baseline_trades_by_window[label]
        selected = _apply_low_extension_support(
            baseline_trades,
            variant_name=variant_name,
            variant=variant,
        )
        if variant_name == BASELINE_VARIANT:
            metrics[label] = baseline_payload["after_metrics"][label]
        else:
            event_curve = prev._event_equity_curve_variable_notional(
                selected,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            metrics[label] = prev._metrics_from_core_curve(
                baseline_metrics=baseline_payload["after_metrics"][label],
                core_curve=core_curves[label],
                event_curve=event_curve,
                event_trades=selected,
                baseline_event_trades=baseline_trades,
            )
        selected_all.extend(selected)
        qualified = [row for row in selected if row.get("low_extension_support_qualified")]
        applied = [row for row in selected if row.get("low_extension_support_applied")]
        surface_sleeve[label] = {
            "selected_trade_count": len(selected),
            "low_extension_support_qualified_trade_count": len(qualified),
            "low_extension_support_adjusted_trade_count": len(applied),
            "low_extension_support_adjusted_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in applied),
                2,
            ),
            "low_extension_support_qualified_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in qualified),
                2,
            ),
            "selected_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in selected),
                2,
            ),
            "selected_win_rate": round(
                sum(1 for row in selected if float(row.get("pnl") or 0.0) > 0)
                / len(selected),
                4,
            )
            if selected
            else None,
            "selected_trades": _selected_trade_rows(selected),
        }
    applied_all = [row for row in selected_all if row.get("low_extension_support_applied")]
    qualified_all = [
        row for row in selected_all if row.get("low_extension_support_qualified")
    ]
    applied_windows = {str(row.get("window")) for row in applied_all if row.get("window")}
    qualified_windows = {
        str(row.get("window")) for row in qualified_all if row.get("window")
    }
    return {
        "variant_name": variant_name,
        "variant_type": "low_extension_support_notional_scalar",
        "ret5_max": RET5_MAX,
        "scalar": variant.get("scalar"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected_all,
        "selected_trade_count": len(selected_all),
        "low_extension_support_qualified_trade_count": len(qualified_all),
        "low_extension_support_qualified_windows": sorted(qualified_windows),
        "low_extension_support_adjusted_trade_count": len(applied_all),
        "low_extension_support_adjusted_windows": sorted(applied_windows),
        "single_ticker_positive_share": prev._single_ticker_positive_share(
            selected_all
        ),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    baseline_share: float | None,
    variant: dict[str, Any],
) -> dict[str, Any]:
    delta = prev._aggregate_delta(baseline_metrics, variant["metrics"])
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["low_extension_support_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["low_extension_support_adjusted_windows"])
        >= MIN_ADJUSTED_WINDOWS
    )
    concentration_guard_passed = (
        variant["single_ticker_positive_share"] is None
        or variant["single_ticker_positive_share"]
        <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= MAX_DRAWDOWN_WORSE
    passed = (
        delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= MIN_EV_IMPROVED_WINDOWS
        and delta["windows_ev_regressed"] == 0
        and delta["windows_pnl_regressed"] == 0
        and sample_guard_passed
        and adjusted_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
    )
    share = variant["single_ticker_positive_share"]
    share_delta = (
        round(share - baseline_share, 6)
        if share is not None and baseline_share is not None
        else None
    )
    return {
        "passed": passed,
        "aggregate_ev_delta": delta["aggregate_ev_delta"],
        "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
        "windows_ev_improved": delta["windows_ev_improved"],
        "windows_ev_regressed": delta["windows_ev_regressed"],
        "windows_pnl_improved": delta["windows_pnl_improved"],
        "windows_pnl_regressed": delta["windows_pnl_regressed"],
        "low_extension_support_adjusted_trade_count": variant[
            "low_extension_support_adjusted_trade_count"
        ],
        "low_extension_support_adjusted_windows": variant[
            "low_extension_support_adjusted_windows"
        ],
        "low_extension_support_qualified_trade_count": variant[
            "low_extension_support_qualified_trade_count"
        ],
        "low_extension_support_qualified_windows": variant[
            "low_extension_support_qualified_windows"
        ],
        "selected_trade_count": variant["selected_trade_count"],
        "sample_guard_passed": sample_guard_passed,
        "adjusted_guard_passed": adjusted_guard_passed,
        "single_ticker_positive_share": share,
        "baseline_single_ticker_positive_share": baseline_share,
        "single_ticker_positive_share_delta": share_delta,
        "concentration_guard_passed": concentration_guard_passed,
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "drawdown_guard_passed": drawdown_guard_passed,
        "minimum_selected_trades": MIN_SELECTED_TRADES,
        "minimum_adjusted_trades": MIN_ADJUSTED_TRADES,
        "minimum_adjusted_windows": MIN_ADJUSTED_WINDOWS,
        "minimum_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
        "delta_metrics": delta,
    }


def _choose_best(rows: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [
        row
        for row in rows
        if row["variant_name"] != BASELINE_VARIANT and row["gate4"]["passed"]
    ]
    pool = passing or [row for row in rows if row["variant_name"] != BASELINE_VARIANT]
    return max(
        pool,
        key=lambda row: (
            bool(row["gate4"]["passed"]),
            row["gate4"]["aggregate_ev_delta"],
            row["gate4"]["aggregate_pnl_delta"],
            -row["gate4"]["max_drawdown_worse_max"],
            -row["aggression_order"],
        ),
    )


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {key: value for key, value in row.items() if key != "combined_equity_curve"}
        for label, row in metrics.items()
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} State-Surface Low-Extension Support Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `low_extension_support_notional_scalar` for already-selected default-off state-surface paper candidates with `ret5 <= 0.02`.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Scalar | dEV | dPnL | EV Improved | EV Regressed | PnL Regressed | Adjusted Trades | Max DD Worse | Single Share |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {gate} | {scalar} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {pr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                gate="PASS" if row["gate4"]["passed"] else "FAIL",
                scalar=row["scalar"] if row["scalar"] is not None else "n/a",
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                pr=row["gate4"]["windows_pnl_regressed"],
                adj=row["gate4"]["low_extension_support_adjusted_trade_count"],
                dd=row["gate4"]["max_drawdown_worse_max"],
                share=f"{share:.2%}" if share is not None else "n/a",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Best Variant",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted Trades |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {bdd:.2%} | {add:.2%} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                bdd=before["max_drawdown_pct"],
                add=after["max_drawdown_pct"],
                trades=sleeve["low_extension_support_adjusted_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    gate2 = prev._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baseline_payload = _json_load(e33.OUT_JSON)
    prices = prev._load_price_map()
    baseline_metrics = baseline_payload["after_metrics"]
    baseline_trades_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    core_curves: dict[str, list[tuple[str, float]]] = OrderedDict()
    for label, window in WINDOWS.items():
        rows = baseline_payload["surface_sleeve"][label]["selected_trades"]
        prepared = [prev._prepare_trade({**row, "window": label}, prices) for row in rows]
        baseline_trades_by_window[label] = prepared
        baseline_event_curve = prev._event_equity_curve_variable_notional(
            prepared,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        event_by_day = {row["date"]: float(row["event_pnl"]) for row in baseline_event_curve}
        combined_curve = [
            (str(day), float(equity))
            for day, equity in baseline_metrics[label]["combined_equity_curve"]
        ]
        core_curves[label] = [
            (day, round(equity - event_by_day.get(day, 0.0), 2))
            for day, equity in combined_curve
        ]

    baseline_trades_all = [
        row for rows in baseline_trades_by_window.values() for row in rows
    ]
    baseline_share = prev._single_ticker_positive_share(baseline_trades_all)
    variants = [
        _variant_payload(
            variant_name=name,
            variant=variant,
            baseline_payload=baseline_payload,
            baseline_trades_by_window=baseline_trades_by_window,
            core_curves=core_curves,
            prices=prices,
        )
        for name, variant in LOW_EXTENSION_VARIANTS.items()
    ]
    sweep_summary = []
    for variant in variants:
        gate4 = _gate4_for_variant(
            baseline_metrics=baseline_metrics,
            baseline_share=baseline_share,
            variant=variant,
        )
        sweep_summary.append(
            {
                "variant_name": variant["variant_name"],
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "ret5_max": variant["ret5_max"],
                "scalar": variant["scalar"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "low_extension_support_qualified_trade_count": variant[
                    "low_extension_support_qualified_trade_count"
                ],
                "low_extension_support_qualified_windows": variant[
                    "low_extension_support_qualified_windows"
                ],
                "low_extension_support_adjusted_trade_count": variant[
                    "low_extension_support_adjusted_trade_count"
                ],
                "low_extension_support_adjusted_windows": variant[
                    "low_extension_support_adjusted_windows"
                ],
                "single_ticker_positive_share": variant[
                    "single_ticker_positive_share"
                ],
                "gate4": gate4,
            }
        )

    best = _choose_best(sweep_summary)
    best_payload = next(row for row in variants if row["variant_name"] == best["variant_name"])
    delta = prev._aggregate_delta(baseline_metrics, best_payload["metrics"])
    passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_default_off_state_surface_low_extension_support_notional"
        if passed
        else "rejected_state_surface_low_extension_support_notional"
    )
    profile = _rank_notional_profile_payload(DEFAULT_CONFIG)
    shared_adapter_parity = {
        "passed": (
            bool(DEFAULT_CONFIG["rank_notional_low_extension_support_enabled"])
            and DEFAULT_CONFIG["rank_notional_low_extension_support_max_ret5"] == RET5_MAX
            and DEFAULT_CONFIG["rank_notional_low_extension_support_scalar"]
            == best["scalar"]
            and profile["low_extension_support_rule_version"]
            == LOW_EXTENSION_RULE_VERSION
            and profile["low_extension_support_max_ret5"] == RET5_MAX
            and profile["low_extension_support_scalar"] == best["scalar"]
        ),
        "shared_rule_version": LOW_EXTENSION_RULE_VERSION,
        "default_config_enabled": DEFAULT_CONFIG["rank_notional_low_extension_support_enabled"],
        "default_config_max_ret5": DEFAULT_CONFIG["rank_notional_low_extension_support_max_ret5"],
        "default_config_scalar": DEFAULT_CONFIG["rank_notional_low_extension_support_scalar"],
        "profile_payload_max_ret5": profile["low_extension_support_max_ret5"],
        "profile_payload_scalar": profile["low_extension_support_scalar"],
        "profile_payload_name": profile["low_extension_support_profile_name"],
    }
    if passed and not shared_adapter_parity["passed"]:
        raise RuntimeError(f"Shared adapter parity failed: {shared_adapter_parity}")

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "lane": "alpha_search",
        "status": "accepted" if passed else "rejected",
        "decision": decision,
        "hypothesis": (
            "Already-selected state-surface paper candidates with ret5 <= 2% "
            "are less short-term extended and may deserve a small support scalar "
            "after the accepted score/volume stack."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": (
                "Tests a new short-term extension/crowding field in the "
                "state-surface sleeve, avoiding LLM soft-ranking, broad-market "
                "threshold retunes, and core candidate-pool expansion."
            ),
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "low_extension_support_notional_scalar",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "best_variant": best["variant_name"],
            "ret5_max": RET5_MAX,
            "best_scalar": best["scalar"],
            "condition": "selected state-surface paper candidate features.ret5 <= 0.02",
            "profile_priority": "applies after accepted rank-depth score-volume support in the default-off paper notional stack",
            "locked_variables": [
                "core entries",
                "core exits",
                "core sizing",
                "state-surface candidate eligibility",
                "state-surface queue ranking",
                "state-surface hold days",
                "state-surface active capacity",
                "rank-depth score-volume support scalar",
                "candidate pool",
                "LLM/news",
                "live/default orders",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; accepted "
            "exp-20260519-033 baseline artifact plus default-off "
            "state-surface paper overlay replay."
        ),
        "before_metrics": baseline_metrics,
        "after_metrics": best_payload["metrics"],
        "delta_metrics": delta,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"]
            for label in WINDOWS
        }
        | {"aggregate": delta["aggregate_ev_delta"]},
        "total_pnl_delta": {
            label: delta["by_window"][label]["total_pnl"] for label in WINDOWS
        }
        | {"aggregate": delta["aggregate_pnl_delta"]},
        "gate1": {
            "passed": True,
            "baseline_artifact": _repo_rel(e33.OUT_JSON),
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "baseline_variant": BASELINE_VARIANT,
            "standard_protocol": "docs/backtesting.md canonical three fixed windows",
        },
        "gate2": {
            "open_position_fields": gate2,
            "runtime_fields": [
                "features.ret5",
                "rank_notional_multiplier",
                "event_notional_usd",
                "entry_open",
                "net_return_pct",
            ],
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_baseline_survival_rate": min(
                float(row.get("survival_rate") or 0.0)
                for row in baseline_metrics.values()
            ),
            "after_survival_rate": {
                label: best_payload["metrics"][label].get("survival_rate")
                for label in WINDOWS
            },
            "hard_rule": "No filter, ranking, or candidate gate changed; only paper notional changes for already-selected trades.",
        },
        "gate4": best["gate4"],
        "shared_adapter_parity": shared_adapter_parity,
        "surface_sleeve": best_payload["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "history_check": {
            "exp-20260519-023": "Accepted top-3 positive ret5 follow-through support; this experiment freezes it and tests low short-term extension after the accepted stack, not a ret5 threshold retune.",
            "exp-20260519-033": "Accepted rank-depth score-volume support; this experiment uses it as the Gate 1 baseline.",
            "anti_repeat": "Not a broad-market threshold/profile retune, LLM soft-ranking expansion, global capacity scalar, queue-lag scalar retry, or core universe expansion.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "LLM soft-ranking data remains sparse/PIT-limited; this tests a replayable deterministic feature.",
        },
        "production_impact": {
            "shared_policy_changed": passed,
            "backtester_adapter_changed": False,
            "run_adapter_changed": passed,
            "replay_only": False,
            "parity_test_added": passed,
            "live_default_orders_changed": False,
            "core_metrics_changed": False,
            "default_off_paper_only": True,
            "trade_enabled": False,
        },
        "interpretation": (
            "Low-extension support improved the default-off state-surface paper overlay without changing core trades, filters, ranking, or live/default orders."
            if passed
            else "Low-extension support did not clear Gate 4; keep the accepted rank-depth score-volume stack unchanged."
        ),
        "rejection_reason": None
        if passed
        else "Failed Gate 4 under the canonical three-window state-surface paper protocol.",
        "next_evidence_needed": (
            "Collect forward state-surface paper outcomes with the low-extension metadata and keep tail/concentration monitoring before live adapter work."
            if passed
            else "Do not retry nearby low-extension/ret5 support without a broader sample or a distinct crowding field."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: selected state-surface candidates with ret5 <= 2% may be less crowded and deserve a small paper-notional support scalar.",
            "2_history_check": "Related ret5 follow-through support was accepted earlier, but this freezes it and tests the opposite low-extension/crowding field after exp-20260519-033. Broad-market rank-notional and LLM soft-ranking are avoided per anti-repeat/data limits.",
            "3_single_causal_variable": "low_extension_support_notional_scalar",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; positive aggregate EV/PnL, all three EV-improved windows, zero EV/PnL-regressed windows, adjusted trades >=8 across all 3 windows, max DD drift <=0.5pp, single-ticker positive share <=50%.",
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "anti_js": "No JavaScript was used.",
        "related_files": {
            "script": _repo_rel(Path(__file__)),
            "shared_module": "quant/state_surface_sleeve.py",
            "shared_test": "quant/test_state_surface_sleeve.py",
            "output": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
            "experiment_log": _repo_rel(EXPERIMENT_LOG),
            "baseline": _repo_rel(e33.OUT_JSON),
        },
    }
    return _safe(payload)


def _experiment_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": _compact_metrics(payload["before_metrics"]),
        "after_metrics": _compact_metrics(payload["after_metrics"]),
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "shared_adapter_parity": payload["shared_adapter_parity"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "related_files": payload["related_files"],
    }


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": payload["lane"],
            "status": payload["status"],
            "decision": payload["decision"],
            "hypothesis": payload["hypothesis"],
            "gate4": payload["gate4"],
            "shared_adapter_parity": payload["shared_adapter_parity"],
            "production_impact": payload["production_impact"],
            "next_evidence_needed": payload["next_evidence_needed"],
            "related_files": payload["related_files"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_payload(payload))
    print(json.dumps(_safe(payload["sweep_summary"]), indent=2, sort_keys=True))
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "selected_variant": payload["parameters"]["best_variant"],
                    "gate4": payload["gate4"],
                    "shared_adapter_parity": payload["shared_adapter_parity"],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "output": payload["related_files"]["output"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
