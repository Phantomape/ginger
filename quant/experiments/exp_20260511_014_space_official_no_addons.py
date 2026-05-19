"""Experiment exp-20260511-014: Space official-catalyst sleeve without add-ons.

This tests one lifecycle allocation variable on top of the accepted
exp-20260511-011 default-off forward hypothesis:

    space_official_catalyst_addon_eligibility = disabled

Everything else is locked to the accepted 0.75x official-catalyst Space sleeve:
pool, entry logic, ranking, exits, risk scalar, and core universe.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = ROOT / "quant" / "experiments"
QUANT_DIR = ROOT / "quant"
for path in (str(EXPERIMENTS_DIR), str(QUANT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from data_layer import get_universe  # noqa: E402
from exp_20260511_002_space_catalyst_static_pool_replay import (  # noqa: E402
    WINDOWS,
    _aggregate,
    _delta,
    _open_position_field_audit,
    _round,
    _snapshot_tickers,
)
from exp_20260511_009_space_static_pool_risk_scalar import (  # noqa: E402
    _run_window,
    _space_trade_attribution,
)
from exp_20260511_010_space_official_catalyst_subpool import (  # noqa: E402
    OFFICIAL_CATALYST_TICKERS,
    _aggregate_space_attr,
    _append_jsonl_once,
    _append_once,
    _write_json,
)


EXPERIMENT_ID = "exp-20260511-014"
STEM = "space_official_no_addons"
RISK_SCALAR = 0.75

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOC_PATH = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}_{STEM}.md"
LOG_PATH = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}_{STEM}.json"
EXPERIMENT_LOG_PATH = ROOT / "docs" / "experiment_log.jsonl"
CURRENT_STATE_PATH = ROOT / "docs" / "current_state.md"
PLAYBOOK_PATH = ROOT / "docs" / "alpha-optimization-playbook.md"


@contextmanager
def _patched_space_official_addon_block(official_tickers: set[str]):
    """Block follow-through add-ons only for the official Space sleeve."""

    import backtester
    import production_parity

    original_backtester_cap = backtester.cap_followthrough_addon_shares
    original_production_cap = production_parity.cap_followthrough_addon_shares
    official = {ticker.upper() for ticker in official_tickers}
    blocked: list[dict[str, Any]] = []

    def wrapped_cap_followthrough_addon_shares(
        ticker: str,
        requested_shares: int,
        current_shares: int,
        price: float,
        portfolio_value: float,
        addon_position_cap: float,
        portfolio_heat: float | None = None,
    ) -> tuple[int, dict[str, Any]]:
        ticker_upper = str(ticker).upper()
        if ticker_upper in official:
            try:
                portfolio_heat_snapshot = (
                    None
                    if portfolio_heat is None
                    else round(float(portfolio_heat), 6)
                )
            except (TypeError, ValueError):
                portfolio_heat_snapshot = portfolio_heat
            blocked.append(
                {
                    "ticker": ticker_upper,
                    "requested_shares": int(requested_shares),
                    "current_shares": int(current_shares),
                    "price": round(float(price), 4),
                    "portfolio_value": round(float(portfolio_value), 2),
                    "addon_position_cap": round(float(addon_position_cap), 6),
                    "portfolio_heat": portfolio_heat_snapshot,
                }
            )
            return 0, {
                "requested_shares": int(requested_shares),
                "cap_reason": "space_official_addon_disabled",
                "space_official_addon_disabled": True,
            }

        return original_backtester_cap(
            ticker,
            requested_shares,
            current_shares,
            price,
            portfolio_value,
            addon_position_cap,
            portfolio_heat=portfolio_heat,
        )

    backtester.cap_followthrough_addon_shares = wrapped_cap_followthrough_addon_shares
    production_parity.cap_followthrough_addon_shares = wrapped_cap_followthrough_addon_shares
    try:
        yield blocked
    finally:
        backtester.cap_followthrough_addon_shares = original_backtester_cap
        production_parity.cap_followthrough_addon_shares = original_production_cap


def _metric_line(metrics: dict[str, Any]) -> dict[str, float | int | None]:
    return {
        "expected_value_score": _round(metrics.get("expected_value_score")),
        "strategy_total_return_pct": _round(metrics.get("strategy_total_return_pct")),
        "sharpe_daily": _round(metrics.get("sharpe_daily")),
        "max_drawdown_pct": _round(metrics.get("max_drawdown_pct")),
        "total_pnl": _round(metrics.get("total_pnl")),
        "trades": metrics.get("total_trades"),
        "survival_rate": _round(metrics.get("survival_rate")),
        "worst_trade_pct": _round(metrics.get("worst_trade_pct")),
        "max_consecutive_losses": metrics.get("max_consecutive_losses"),
        "tail_loss_share": _round(metrics.get("tail_loss_share")),
    }


def _window_row(label: str, before: dict[str, Any], after: dict[str, Any], core: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": label,
        "core": _metric_line(core["metrics"]),
        "before_accepted_exp_011_075x": _metric_line(before["metrics"]),
        "after_no_space_addons": _metric_line(after["metrics"]),
        "delta_after_vs_before": _delta(after["metrics"], before["metrics"]),
        "delta_after_vs_core": _delta(after["metrics"], core["metrics"]),
    }


def _drawdown_delta(delta: dict[str, Any]) -> float:
    return float(
        delta.get("max_drawdown_pct_max")
        if delta.get("max_drawdown_pct_max") is not None
        else delta.get("max_drawdown_pct_worst") or 0.0
    )


def _make_artifact(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} {STEM}",
        "",
        "## Hypothesis",
        "",
        (
            "Disable follow-through add-ons only for the accepted 0.75x Space "
            "official-catalyst sleeve. If the sleeve's edge is mainly first-entry "
            "convexity, this should reduce concentration and drawdown without "
            "damaging aggregate EV."
        ),
        "",
        "## Gate Answers",
        "",
    ]
    for item in payload["gate_answers"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Three-Window Result",
            "",
            (
                "| window | before EV | after EV | dEV vs before | dEV vs core | "
                "before pnl | after pnl | blocked add-ons |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label, result in payload["windows"].items():
        before = result["before_accepted_exp_011_075x"]
        after = result["after_no_space_addons"]
        delta_before = result["delta_after_vs_before"]
        delta_core = result["delta_after_vs_core"]
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_before_ev:.4f} | "
            "{delta_core_ev:.4f} | {before_pnl:.2f} | {after_pnl:.2f} | {blocked} |".format(
                label=label,
                before_ev=float(before.get("expected_value_score") or 0.0),
                after_ev=float(after.get("expected_value_score") or 0.0),
                delta_before_ev=float(delta_before.get("expected_value_score") or 0.0),
                delta_core_ev=float(delta_core.get("expected_value_score") or 0.0),
                before_pnl=float(before.get("total_pnl") or 0.0),
                after_pnl=float(after.get("total_pnl") or 0.0),
                blocked=result["blocked_addon_count"],
            )
        )

    aggregate = payload["aggregate"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            (
                "- after vs accepted exp-011: EV delta {ev:.4f}, PnL delta {pnl:.2f}, "
                "max drawdown delta {dd:.4f} pp"
            ).format(
                ev=float(
                    aggregate["delta_after_vs_before_accepted_exp_011"][
                        "expected_value_score_sum"
                    ]
                ),
                pnl=float(
                    aggregate["delta_after_vs_before_accepted_exp_011"]["total_pnl_sum"]
                ),
                dd=_drawdown_delta(
                    aggregate["delta_after_vs_before_accepted_exp_011"]
                ),
            ),
            (
                "- after vs core baseline: EV delta {ev:.4f}, PnL delta {pnl:.2f}, "
                "max drawdown delta {dd:.4f} pp"
            ).format(
                ev=float(aggregate["delta_after_vs_core"]["expected_value_score_sum"]),
                pnl=float(aggregate["delta_after_vs_core"]["total_pnl_sum"]),
                dd=_drawdown_delta(aggregate["delta_after_vs_core"]),
            ),
            f"- decision: {payload['decision']}",
            f"- rejection_reason: {payload.get('rejection_reason')}",
            "",
            "## Production Impact",
            "",
            "```text",
            "production_impact:",
            "  shared_policy_changed: false",
            "  backtester_adapter_changed: false",
            "  run_adapter_changed: false",
            "  replay_only: true",
            "  parity_test_added: false",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    return (
        f"# {EXPERIMENT_ID} {STEM}\n\n"
        "Status: closed\n"
        f"Decision: {payload['decision']}\n\n"
        "## Summary\n\n"
        "Tested disabling follow-through add-ons only for the accepted 0.75x Space "
        "official-catalyst sleeve across the canonical three windows.\n\n"
        "## Outcome\n\n"
        "- EV delta vs accepted exp-011: "
        f"{aggregate['delta_after_vs_before_accepted_exp_011']['expected_value_score_sum']:.4f}\n"
        "- PnL delta vs accepted exp-011: "
        f"{aggregate['delta_after_vs_before_accepted_exp_011']['total_pnl_sum']:.2f}\n"
        "- EV delta vs core: "
        f"{aggregate['delta_after_vs_core']['expected_value_score_sum']:.4f}\n"
        f"- Decision: {payload['decision']}\n\n"
        "## Next Evidence Needed\n\n"
        f"{payload['next_evidence_needed']}\n"
    )


def _append_state_notes(payload: dict[str, Any]) -> None:
    marker = f"Latest Space add-on refinement: `{EXPERIMENT_ID}`"
    current = CURRENT_STATE_PATH.read_text(encoding="utf-8") if CURRENT_STATE_PATH.exists() else ""
    if marker not in current:
        note = (
            "\n\n## Latest Space Add-On Refinement\n\n"
            f"{marker} tested disabling follow-through add-ons for the accepted "
            "0.75x official-catalyst Space sleeve. The refinement was rejected "
            "versus `exp-20260511-011`; keep the accepted sleeve unchanged and "
            "do not disable all Space add-ons without a more selective ex-ante "
            "lifecycle signal.\n"
        )
        CURRENT_STATE_PATH.write_text(current.rstrip() + note, encoding="utf-8")

    playbook = PLAYBOOK_PATH.read_text(encoding="utf-8") if PLAYBOOK_PATH.exists() else ""
    if marker not in playbook:
        note = (
            "\n\n### Space Add-On Refinement Guardrail\n\n"
            f"{marker}: a blanket no-add-on lifecycle for the accepted 0.75x "
            "official-catalyst Space sleeve is not enough evidence to replace "
            "`exp-20260511-011`. Future Space lifecycle work needs a more precise "
            "ex-ante discriminator, not a global add-on ban.\n"
        )
        PLAYBOOK_PATH.write_text(playbook.rstrip() + note, encoding="utf-8")


def run_experiment() -> dict[str, Any]:
    run_at = datetime.now(timezone.utc).isoformat()
    core_universe = {str(ticker).upper() for ticker in get_universe()}
    field_audit = _open_position_field_audit()

    windows: dict[str, Any] = {}
    core_results: dict[str, Any] = {}
    before_results: dict[str, Any] = {}
    after_results: dict[str, Any] = {}
    before_space_attr: dict[str, Any] = {}
    after_space_attr: dict[str, Any] = {}

    for label, spec in WINDOWS.items():
        candidate_snapshot_tickers = _snapshot_tickers(ROOT / spec["candidate_snapshot"])
        included_space = {
            ticker
            for ticker in OFFICIAL_CATALYST_TICKERS
            if ticker in candidate_snapshot_tickers
        }
        candidate_universe = sorted(set(core_universe) | included_space)

        core = _run_window(label, spec, sorted(core_universe), spec["baseline_snapshot"])
        before = _run_window(
            label,
            spec,
            candidate_universe,
            spec["candidate_snapshot"],
            scalar=RISK_SCALAR,
        )
        with _patched_space_official_addon_block(included_space) as blocked_addons:
            after = _run_window(
                label,
                spec,
                candidate_universe,
                spec["candidate_snapshot"],
                scalar=RISK_SCALAR,
            )

        core_results[label] = core["metrics"]
        before_results[label] = before["metrics"]
        after_results[label] = after["metrics"]
        before_space_attr[label] = _space_trade_attribution(before["trades"], included_space)
        after_space_attr[label] = _space_trade_attribution(after["trades"], included_space)
        windows[label] = {
            **_window_row(label, before, after, core),
            "official_space_tickers_in_snapshot": sorted(included_space),
            "blocked_addon_count": len(blocked_addons),
            "blocked_addons": deepcopy(blocked_addons),
            "before_space_trade_attribution": before_space_attr[label],
            "after_space_trade_attribution": after_space_attr[label],
            "core_signals_survived": core["metrics"].get("signals_survived"),
            "before_signals_survived": before["metrics"].get("signals_survived"),
            "after_signals_survived": after["metrics"].get("signals_survived"),
            "core_reason_counts": core.get("entry_execution_reason_counts", {}),
            "before_reason_counts": before.get("entry_execution_reason_counts", {}),
            "after_reason_counts": after.get("entry_execution_reason_counts", {}),
        }

    core_agg = _aggregate(core_results)
    before_agg = _aggregate(before_results)
    after_agg = _aggregate(after_results)
    delta_after_vs_before = _delta(after_agg, before_agg)
    delta_after_vs_core = _delta(after_agg, core_agg)

    improved_windows_vs_before = sum(
        1
        for label in WINDOWS
        if windows[label]["delta_after_vs_before"]["expected_value_score"] > 0
    )
    regressed_windows_vs_before = sum(
        1
        for label in WINDOWS
        if windows[label]["delta_after_vs_before"]["expected_value_score"] < 0
    )
    improved_windows_vs_core = sum(
        1
        for label in WINDOWS
        if windows[label]["delta_after_vs_core"]["expected_value_score"] > 0
    )
    blocked_addon_total = sum(windows[label]["blocked_addon_count"] for label in WINDOWS)

    accept = (
        delta_after_vs_before["expected_value_score_sum"] > 0
        and delta_after_vs_before["total_pnl_sum"] >= 0
        and improved_windows_vs_before >= 2
        and regressed_windows_vs_before <= 1
        and delta_after_vs_core["expected_value_score_sum"] > 0
        and _drawdown_delta(delta_after_vs_core) <= 2.0
    )
    decision = (
        "accepted_default_off_no_addon_refinement"
        if accept
        else "rejected_no_addon_refinement_keep_exp_20260511_011"
    )
    rejection_reason = None
    if not accept:
        rejection_reason = (
            "Blanket Space official-catalyst add-on disablement did not beat the "
            "accepted exp-20260511-011 0.75x lifecycle with enough three-window "
            "EV/PnL evidence."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "run_at": run_at,
        "hypothesis": (
            "The accepted Space official-catalyst 0.75x sleeve may have better "
            "risk-adjusted EV if follow-through add-ons are disabled only for "
            "official Space entries."
        ),
        "change_type": "alpha_search",
        "alpha_category": "risk_allocation",
        "changed_variable": "space_official_catalyst_addon_eligibility",
        "parameters": {
            "official_catalyst_tickers": sorted(OFFICIAL_CATALYST_TICKERS),
            "risk_scalar": RISK_SCALAR,
            "before_addons": "enabled",
            "after_addons": "disabled_for_official_space_tickers_only",
            "core_universe": "unchanged_get_universe",
            "entry_exit_ranking": "unchanged",
        },
        "gate_answers": [
            (
                "Hypothesis category: risk allocation / lifecycle allocation on the "
                "Space official-catalyst sleeve; this follows the playbook because "
                "exp-20260511-011 is the strongest current non-LLM alpha lead."
            ),
            (
                "Prior related work: exp-20260511-010 full-risk official Space pool "
                "was rejected on drawdown; exp-20260511-011 accepted 0.75x default-off; "
                "exp-20260511-012 rejected blanket trend-only refinement; no prior "
                "Space-specific add-on eligibility test exists."
            ),
            (
                "Single variable: add-on eligibility for official Space tickers only; "
                "pool, 0.75x risk scalar, core universe, signal generation, ranking, "
                "exits, news/LLM, and live slots stay locked."
            ),
            (
                "Success criterion: beat accepted exp-20260511-011 on aggregate EV "
                "and PnL with at least two EV-improved windows, while keeping positive "
                "aggregate EV vs core and avoiding unacceptable drawdown damage."
            ),
            (
                "Reproducibility: this script writes JSON, ticket, artifact, and "
                "experiment_log JSONL with all parameters and three-window metrics."
            ),
        ],
        "gate_results": {
            "gate_1_baseline": {
                "protocol": "docs/backtesting.md canonical three-window protocol",
                "core_baseline_metrics": core_agg,
                "accepted_space_075x_before_metrics": before_agg,
            },
            "gate_2_field_check": field_audit,
            "gate_3_survival_rate": {
                label: {
                    "core_survival_rate": windows[label]["core"]["survival_rate"],
                    "before_survival_rate": windows[label]["before_accepted_exp_011_075x"][
                        "survival_rate"
                    ],
                    "after_survival_rate": windows[label]["after_no_space_addons"][
                        "survival_rate"
                    ],
                }
                for label in WINDOWS
            },
            "gate_4_after_measurement": {
                "improved_windows_vs_before": improved_windows_vs_before,
                "regressed_windows_vs_before": regressed_windows_vs_before,
                "improved_windows_vs_core": improved_windows_vs_core,
                "blocked_addon_total": blocked_addon_total,
            },
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md",
            "windows": {
                label: {
                    "start": spec["start"],
                    "end": spec["end"],
                    "baseline_snapshot": spec["baseline_snapshot"],
                    "candidate_snapshot": spec["candidate_snapshot"],
                }
                for label, spec in WINDOWS.items()
            },
        },
        "windows": windows,
        "aggregate": {
            "core_baseline": core_agg,
            "before_accepted_exp_011_075x": before_agg,
            "after_no_space_addons": after_agg,
            "delta_after_vs_before_accepted_exp_011": delta_after_vs_before,
            "delta_after_vs_core": delta_after_vs_core,
            "before_space_trade_attribution": _aggregate_space_attr(
                {
                    label: {"space_trade_attribution": attr}
                    for label, attr in before_space_attr.items()
                }
            ),
            "after_space_trade_attribution": _aggregate_space_attr(
                {
                    label: {"space_trade_attribution": attr}
                    for label, attr in after_space_attr.items()
                }
            ),
        },
        "expected_value_score_delta": delta_after_vs_before[
            "expected_value_score_sum"
        ],
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Keep exp-20260511-011 unchanged. Future Space lifecycle work needs a "
            "more selective ex-ante add-on discriminator, such as event freshness, "
            "contract quality, or post-entry confirmation, rather than a global ban."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains data-limited, broad Space pool expansion was "
            "already rejected, and this run isolates only Space add-on eligibility "
            "instead of changing tickers, thresholds, entry filters, or exits."
        ),
        "known_risks": [
            "Replay-only patch means an accepted result would still require shared production policy work before enablement.",
            "The experiment blocks all official Space add-ons, so it may miss a narrower profitable add-on subset.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_DIR / f"{STEM}.json", payload)
    _write_json(LOG_PATH, payload)
    _append_jsonl_once(EXPERIMENT_LOG_PATH, payload)
    _append_once(DOC_PATH, EXPERIMENT_ID, _make_artifact(payload))
    _append_once(TICKET_PATH, EXPERIMENT_ID, _ticket(payload))
    _append_state_notes(payload)
    return payload


if __name__ == "__main__":
    result = run_experiment()
    print(json.dumps(result["aggregate"], indent=2, sort_keys=True))
    print(result["decision"])
