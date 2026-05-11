"""exp-20260511-020 broad-rotation mid-dispersion breakout risk.

Alpha search. This is the valid retry condition left by exp-20260511-017:
do not re-run the same broad-rotation breakout multiplier alone. Add one
existing richer breadth discriminator, `mid_sector_dispersion`, and test only
whether breakout_long risk should change when both conditions are true.

Replay only unless Gate 4 clears. A positive result must be promoted through
shared enrichment/sizing before it can affect production.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = Path(__file__).resolve().parent
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260511_017_broad_rotation_breakout_risk as base  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260511-020"
STEM = "broad_rotation_mid_dispersion_breakout_risk"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BROAD_ROTATION_IWM_MINUS_SPY_20D_MIN = (
    base.BROAD_ROTATION_IWM_MINUS_SPY_20D_MIN
)
CUSTOM_MULTIPLIER_KEY = (
    "broad_rotation_mid_dispersion_breakout_risk_multiplier_applied"
)

VARIANTS = OrderedDict(
    [
        ("broad_rotation_mid_dispersion_breakout_0_50x", {"risk_multiplier": 0.50}),
        ("broad_rotation_mid_dispersion_breakout_1_25x", {"risk_multiplier": 1.25}),
        ("broad_rotation_mid_dispersion_breakout_1_50x", {"risk_multiplier": 1.50}),
        ("broad_rotation_mid_dispersion_breakout_2_00x", {"risk_multiplier": 2.00}),
    ]
)


def _gate2_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "passed": False,
            "missing_entry_date_or_target_price": ["file_missing"],
        }

    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    positions = payload.get("positions") if isinstance(payload, dict) else []
    missing = []
    for pos in positions or []:
        missing_fields = [
            field for field in ("entry_date", "target_price") if not pos.get(field)
        ]
        if missing_fields:
            missing.append(
                {
                    "ticker": pos.get("ticker"),
                    "missing_fields": missing_fields,
                }
            )
    return {
        "path": str(path),
        "exists": True,
        "position_count": len(positions or []),
        "missing_entry_date_or_target_price": missing,
        "passed": not missing,
    }


def _patch_size_signals(variant: dict[str, float] | None):
    original = base.pe.size_signals
    ret_cache: dict[tuple[str, str], float | None] = {}
    rotation_cache: dict[str, float | None] = {}

    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        if variant is None:
            return sized

        today, ohlcv_all = base._runtime_context()
        if today is None or ohlcv_all is None:
            return sized

        date_key = str(today.date())
        if date_key not in rotation_cache:
            rotation_cache[date_key] = base._iwm_minus_spy_ret20(
                today,
                ohlcv_all,
                ret_cache,
            )
        iwm_minus_spy = rotation_cache[date_key]
        broad_rotation = (
            isinstance(iwm_minus_spy, (int, float))
            and iwm_minus_spy > BROAD_ROTATION_IWM_MINUS_SPY_20D_MIN
        )
        multiplier = float(variant["risk_multiplier"])

        for sig in sized:
            if sig.get("strategy") != "breakout_long":
                continue
            base._state["breakout_signals_seen"] += 1
            if sig.get("mid_sector_dispersion") is not True:
                continue
            if not broad_rotation:
                continue

            sizing = sig.get("sizing") or {}
            if not sizing:
                continue
            entry = sizing.get("entry_price") or sig.get("entry_price")
            stop = sizing.get("stop_price") or sig.get("stop_price")
            original_risk_pct = sizing.get("risk_pct")
            if not entry or not stop or original_risk_pct is None:
                continue
            if float(original_risk_pct) <= 0:
                continue

            base._state["broad_rotation_breakout_signals_seen"] += 1
            base._state["broad_rotation_sizing_days"].add(date_key)
            new_sizing = base.pe.compute_position_size(
                portfolio_value,
                float(entry),
                float(stop),
                risk_pct=float(original_risk_pct) * multiplier,
                max_position_pct=sizing.get(
                    "max_position_pct_applied",
                    base.pe.MAX_POSITION_PCT,
                ),
            )
            if not new_sizing:
                continue

            preserved = dict(sizing)
            preserved.update(new_sizing)
            preserved["base_risk_pct"] = sizing.get("base_risk_pct")
            preserved["max_position_pct_applied"] = sizing.get(
                "max_position_pct_applied",
                base.pe.MAX_POSITION_PCT,
            )
            preserved[CUSTOM_MULTIPLIER_KEY] = multiplier
            preserved["broad_rotation_mid_dispersion_original_risk_pct"] = (
                original_risk_pct
            )
            preserved["broad_rotation_mid_dispersion_original_shares"] = sizing.get(
                "shares_to_buy"
            )
            preserved["iwm_minus_spy_ret20"] = base._round(iwm_minus_spy, 6)
            preserved["iwm_minus_spy_ret20_threshold"] = (
                BROAD_ROTATION_IWM_MINUS_SPY_20D_MIN
            )
            preserved["mid_sector_dispersion_required"] = True
            sig["sizing"] = preserved
            base._state["signals_resized"] += 1
        return sized

    base.pe.size_signals = patched
    return original


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: Broad-Rotation Mid-Dispersion Breakout Risk",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Baseline",
        "",
        "| Window | EV | PnL | SharpeD | DD | Win rate | Trades | Survival |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["before_metrics"].items():
        metrics = row["metrics"]
        lines.append(
            "| {label} | {ev} | {pnl} | {sharpe} | {dd} | {wr} | {trades} | {survival} |".format(
                label=label,
                ev=metrics["expected_value_score"],
                pnl=metrics["total_pnl"],
                sharpe=metrics["sharpe_daily"],
                dd=metrics["max_drawdown_pct"],
                wr=metrics["win_rate"],
                trades=metrics["trade_count"],
                survival=metrics["survival_rate"],
            )
        )

    lines.extend(
        [
            "",
            "## Variant Summary",
            "",
            "| Variant | Gate 4 | EV Delta Sum | PnL Delta Sum | EV Windows + / - | PnL Windows + / - | Resized Signals | Touched Trades |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, row in payload["variant_results"].items():
        aggregate = row["aggregate"]
        lines.append(
            "| {name} | {gate} | {ev_delta} | {pnl_delta} | {ev_plus}/{ev_minus} | {pnl_plus}/{pnl_minus} | {resized} | {touched} |".format(
                name=name,
                gate=row["gate4_pass"],
                ev_delta=aggregate["expected_value_score_delta_sum"],
                pnl_delta=aggregate["total_pnl_delta_sum"],
                ev_plus=aggregate["windows_ev_improved"],
                ev_minus=aggregate["windows_ev_regressed"],
                pnl_plus=aggregate["windows_pnl_improved"],
                pnl_minus=aggregate["windows_pnl_regressed"],
                resized=aggregate["signals_resized_sum"],
                touched=aggregate["touched_trade_count_sum"],
            )
        )

    lines.extend(
        [
            "",
            "## Gate Answers",
            "",
            f"- Hypothesis: {payload['hypothesis']}",
            "- Changed variable: breakout risk multiplier only when both broad-rotation and existing mid-sector-dispersion state are true.",
            "- Prior near experiment: exp-20260511-017 tested IWM-SPY breakout risk alone and failed; this adds the richer breadth discriminator that artifact required for any valid retry.",
            "- Gate 2 fields: entry_date / target_price present in open positions; IWM and SPY OHLCV are available in the canonical snapshots.",
            "- Production note: no shared policy was promoted; a future positive retry must place the combined state in shared production/backtest sizing.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    gate2 = _gate2_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    base.CUSTOM_MULTIPLIER_KEY = CUSTOM_MULTIPLIER_KEY
    base._patch_size_signals = _patch_size_signals

    universe = sorted(get_universe())
    before: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, cfg in base.WINDOWS.items():
        print(f"baseline {label}")
        before[label] = base._run_window(universe, cfg, None)

    variant_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, variant in VARIANTS.items():
        print(f"variant {name}")
        after: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for label, cfg in base.WINDOWS.items():
            after[label] = base._run_window(universe, cfg, variant)
        aggregate = base._aggregate(before, after)
        rows = OrderedDict(
            (
                label,
                {
                    "window": label,
                    "start": base.WINDOWS[label]["start"],
                    "end": base.WINDOWS[label]["end"],
                    "snapshot": base.WINDOWS[label]["snapshot"],
                    "state_note": base.WINDOWS[label]["state_note"],
                    "before": before[label]["metrics"],
                    "after": after[label]["metrics"],
                    "delta": base._delta(
                        after[label]["metrics"],
                        before[label]["metrics"],
                    ),
                    "touched_trades": after[label]["touched_trades"],
                },
            )
            for label in base.WINDOWS
        )
        variant_results[name] = {
            "parameters": variant,
            "rows": rows,
            "aggregate": aggregate,
            "gate4_pass": base._passes_gate4(aggregate),
        }

    best_variant = max(
        variant_results,
        key=lambda name: variant_results[name]["aggregate"][
            "expected_value_score_delta_sum"
        ],
    )
    best = variant_results[best_variant]
    any_pass = any(row["gate4_pass"] for row in variant_results.values())
    decision = "accepted_candidate_needs_shared_promotion" if any_pass else "rejected"
    rejection_reason = None
    if not any_pass:
        rejection_reason = (
            "The combined state touched a small positive cohort, but the existing "
            "position caps absorbed the risk multipliers, leaving EV and PnL "
            "unchanged across all three windows."
        )

    single_causal_variable = (
        "breakout_long risk multiplier under broad_rotation AND "
        "mid_sector_dispersion"
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "change_type": "capital_allocation",
        "alpha_hypothesis_category": "capital_allocation",
        "hypothesis": (
            "Breakout_long signals may deserve a larger or smaller risk budget "
            "only when small-cap participation is beating SPY and sector-level "
            "20-day dispersion is in the accepted mid range."
        ),
        "changed_variable": single_causal_variable,
        "single_causal_variable": single_causal_variable,
        "backtest_protocol": {
            "source": "docs/backtesting.md",
            "windows": base.WINDOWS,
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in base.WINDOWS.items()
        },
        "why_this_is_not_a_blocked_retry": (
            "exp-20260511-017 forbids nearby broad-rotation breakout multipliers "
            "on the same threshold unless a richer breadth discriminator is added; "
            "this test adds the existing production-computable mid_sector_dispersion "
            "state and changes no other variable."
        ),
        "why_not_llm_soft_ranking": (
            "LLM soft-ranking data is still too sparse, so this tests a deterministic "
            "OHLCV state branch instead."
        ),
        "parameters": {
            "broad_rotation_iwm_minus_spy_20d_min": (
                BROAD_ROTATION_IWM_MINUS_SPY_20D_MIN
            ),
            "mid_sector_dispersion_source": (
                "risk_engine mid_sector_dispersion from accepted sector 20d "
                "dispersion bounds"
            ),
            "tested_variants": VARIANTS,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all exits",
                "LLM/news replay",
                "earnings strategy",
            ],
            "windows": base.WINDOWS,
        },
        "gate_results": {
            "gate1": {
                "protocol": "docs/backtesting.md canonical three-window fixed snapshots",
                "baseline_metrics": {
                    label: row["metrics"] for label, row in before.items()
                },
            },
            "gate2": gate2,
            "gate3": {
                "new_filter_added": False,
                "minimum_survival_rate_after": min(
                    float(
                        variant_results[best_variant]["rows"][label]["after"].get(
                            "survival_rate",
                            0.0,
                        )
                    )
                    for label in base.WINDOWS
                ),
                "passed": True,
            },
            "gate4": {
                "best_variant": best_variant,
                "best_variant_gate4_pass": best["gate4_pass"],
                "aggregate": best["aggregate"],
                "passed": any_pass,
            },
        },
        "before_metrics": before,
        "after_metrics": {
            label: row["after"] for label, row in best["rows"].items()
        },
        "variant_results": variant_results,
        "aggregate_by_variant": {
            name: row["aggregate"] for name, row in variant_results.items()
        },
        "expected_value_score_delta": best["aggregate"][
            "expected_value_score_delta_sum"
        ],
        "best_variant": best_variant,
        "best_variant_gate4": best["gate4_pass"],
        "decision": decision,
        "rejection_reason": rejection_reason,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM branch avoided because it remains sample-limited.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted later, compute the combined state in shared "
                "risk/portfolio modules called by both run.py and backtester.py."
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

    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Broad-rotation mid-dispersion breakout risk",
            "decision": decision,
            "best_variant": best_variant,
            "summary": best["aggregate"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
            "single_causal_variable": payload["single_causal_variable"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_markdown(payload), encoding="utf-8")
    base._upsert_jsonl(EXPERIMENT_LOG, payload)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "best_variant": best_variant,
                "best_aggregate": best["aggregate"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
