"""exp-20260510-019: mid-dispersion sector-leader top-up replay.

Alpha search. Test one allocation variable: whether non-Financials trend
signals inside the accepted mid-sector-dispersion sleeve deserve a small
cap-aware top-up when they lead their own sector on 20-day momentum, but do not
already qualify for the accepted RS20 entry-state top-up.

Replay only unless Gate 4 clears and the same policy is promoted into shared
risk/portfolio modules with run/backtester attribution parity.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
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
import risk_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260510-019"
STEM = "mid_dispersion_sector_leader_topup"
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

TOPUP_MULTIPLIER = 1.10
TOPUP_KEY = "mid_dispersion_sector_leader_topup_multiplier_applied"

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


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(payload_line)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(payload_line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _sector_ret20_context(
    features_dict: dict[str, dict[str, Any]] | None,
) -> tuple[dict[str, float], dict[str, int]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for ticker, features in (features_dict or {}).items():
        sector = risk_engine.SECTOR_MAP.get(str(ticker).upper(), "Unknown")
        if sector == "Unknown":
            continue
        ret20 = (features or {}).get("momentum_20d_pct")
        if isinstance(ret20, (int, float)):
            buckets[sector].append(float(ret20))
    averages = {
        sector: sum(values) / len(values)
        for sector, values in buckets.items()
        if len(values) >= 2
    }
    counts = {sector: len(values) for sector, values in buckets.items()}
    return averages, counts


def _patched_enrich_signals(original):
    def patched(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        sector_avgs, sector_counts = _sector_ret20_context(features_dict)
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            sector = sig.get("sector") or risk_engine.SECTOR_MAP.get(ticker, "Unknown")
            features = (features_dict or {}).get(ticker) or {}
            ticker_ret20 = features.get("momentum_20d_pct")
            sector_avg = sector_avgs.get(sector)
            if not isinstance(ticker_ret20, (int, float)):
                continue
            if not isinstance(sector_avg, (int, float)):
                continue
            rel = float(ticker_ret20) - float(sector_avg)
            sig["sector_avg_ret20_pct"] = round(float(sector_avg), 4)
            sig["ticker_ret20_minus_sector_avg_pct"] = round(rel, 4)
            sig["sector_relative_leader"] = rel > 0
            sig["sector_relative_peer_count"] = sector_counts.get(sector, 0)
        return enriched

    return patched


def _eligible_for_topup(sig: dict[str, Any]) -> bool:
    if sig.get("strategy") != "trend_long":
        return False
    if sig.get("mid_sector_dispersion") is not True:
        return False
    if sig.get("sector_relative_leader") is not True:
        return False
    if sig.get("rs20_entry_state_leader") is True:
        return False
    sector = sig.get("sector")
    if sector in {None, "Unknown", "Financials"}:
        return False
    return True


def _patched_size_signals(original):
    def patched(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            if not _eligible_for_topup(sig):
                continue
            sizing = sig.get("sizing") or {}
            old_shares = int(sizing.get("shares_to_buy") or 0)
            entry = sizing.get("entry_price") or sig.get("entry_price")
            if old_shares <= 0 or not isinstance(entry, (int, float)) or entry <= 0:
                continue
            max_position_pct = (
                sizing.get("max_position_pct_applied")
                or portfolio_engine.MAX_POSITION_PCT
            )
            cap_shares = int(math.floor(portfolio_value * max_position_pct / entry))
            desired_shares = max(
                old_shares,
                int(math.floor(old_shares * TOPUP_MULTIPLIER)),
            )
            new_shares = min(desired_shares, cap_shares)
            if new_shares <= old_shares:
                continue
            net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
            risk_amount = new_shares * net_risk_per_share
            position_value = new_shares * float(entry)
            sizing["shares_to_buy"] = new_shares
            sizing["position_value_usd"] = round(position_value, 2)
            sizing["position_pct_of_portfolio"] = round(
                position_value / portfolio_value,
                4,
            )
            sizing["risk_amount_usd"] = round(risk_amount, 2)
            sizing["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
            sizing[TOPUP_KEY] = TOPUP_MULTIPLIER
            sizing["mid_dispersion_sector_leader_baseline_shares"] = old_shares
            sizing["mid_dispersion_sector_leader_desired_shares"] = desired_shares
            sizing["mid_dispersion_sector_leader_cap_shares"] = cap_shares
            sizing["sector_avg_ret20_pct"] = sig.get("sector_avg_ret20_pct")
            sizing["ticker_ret20_minus_sector_avg_pct"] = sig.get(
                "ticker_ret20_minus_sector_avg_pct"
            )
            sizing["sector_relative_peer_count"] = sig.get(
                "sector_relative_peer_count"
            )
        return sized

    return patched


@contextmanager
def _variant_context(enabled: bool) -> Iterator[None]:
    original_enrich = risk_engine.enrich_signals
    original_size = portfolio_engine.size_signals
    original_keys = bt.SIZING_MULTIPLIER_KEYS
    try:
        if enabled:
            risk_engine.enrich_signals = _patched_enrich_signals(original_enrich)
            portfolio_engine.size_signals = _patched_size_signals(original_size)
            if TOPUP_KEY not in bt.SIZING_MULTIPLIER_KEYS:
                bt.SIZING_MULTIPLIER_KEYS = (*bt.SIZING_MULTIPLIER_KEYS, TOPUP_KEY)
        yield
    finally:
        risk_engine.enrich_signals = original_enrich
        portfolio_engine.size_signals = original_size
        bt.SIZING_MULTIPLIER_KEYS = original_keys


def _run_window(window: dict[str, str], enabled: bool = False) -> dict[str, Any]:
    with _variant_context(enabled):
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
    return result


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "strategy_total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct"),
            4,
        ),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 4),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key in {
                "trade_count",
                "signals_generated",
                "signals_survived",
                "max_consecutive_losses",
            }:
                out[key] = int(after_value - before_value)
            else:
                out[key] = _round(after_value - before_value, 6)
    return out


def _touched_trades(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for trade in result.get("trades") or []:
        multipliers = trade.get("sizing_multipliers") or {}
        if TOPUP_KEY not in multipliers:
            continue
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "sector": trade.get("sector"),
                "entry_date": str(trade.get("entry_date") or "")[:10],
                "exit_date": str(trade.get("exit_date") or "")[:10],
                "exit_reason": trade.get("exit_reason"),
                "pnl": _round(trade.get("pnl"), 2),
                "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
                "sizing_multipliers": multipliers,
            }
        )
    return rows


def _run_pairs() -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline")
        before_result = _run_window(window, enabled=False)
        print(f"[{label}] sector-leader top-up")
        after_result = _run_window(window, enabled=True)
        before = _metrics(before_result)
        after = _metrics(after_result)
        touched = _touched_trades(after_result)
        rows[label] = {
            "window": window,
            "before_metrics": before,
            "after_metrics": after,
            "delta_metrics": _delta(after, before),
            "touched_trade_count": len(touched),
            "touched_trade_pnl": _round(
                sum(float(row.get("pnl") or 0.0) for row in touched),
                2,
            ),
            "touched_trades": touched,
        }
        delta = rows[label]["delta_metrics"]
        print(
            f"[{label}] EV={delta['expected_value_score']:+.4f} "
            f"PnL={delta['total_pnl']:+.2f} touched={len(touched)}"
        )
    return rows


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(
        float(row["before_metrics"].get("expected_value_score") or 0.0)
        for row in rows.values()
    )
    after_ev = sum(
        float(row["after_metrics"].get("expected_value_score") or 0.0)
        for row in rows.values()
    )
    before_pnl = sum(
        float(row["before_metrics"].get("total_pnl") or 0.0)
        for row in rows.values()
    )
    after_pnl = sum(
        float(row["after_metrics"].get("total_pnl") or 0.0)
        for row in rows.values()
    )
    deltas = [row["delta_metrics"] for row in rows.values()]
    return {
        "baseline_expected_value_score_sum": _round(before_ev, 4),
        "after_expected_value_score_sum": _round(after_ev, 4),
        "expected_value_score_delta_sum": _round(after_ev - before_ev, 4),
        "expected_value_score_delta_pct": _round(
            (after_ev - before_ev) / abs(before_ev),
            6,
        ),
        "baseline_total_pnl_sum": _round(before_pnl, 2),
        "after_total_pnl_sum": _round(after_pnl, 2),
        "total_pnl_delta_sum": _round(after_pnl - before_pnl, 2),
        "total_pnl_delta_pct": _round((after_pnl - before_pnl) / abs(before_pnl), 6),
        "windows_ev_improved": sum(
            1 for delta in deltas if delta.get("expected_value_score", 0) > 0
        ),
        "windows_ev_regressed": sum(
            1 for delta in deltas if delta.get("expected_value_score", 0) < 0
        ),
        "windows_pnl_improved": sum(1 for delta in deltas if delta.get("total_pnl", 0) > 0),
        "windows_pnl_regressed": sum(1 for delta in deltas if delta.get("total_pnl", 0) < 0),
        "max_drawdown_worsening_max": _round(
            max(delta.get("max_drawdown_pct", 0) for delta in deltas),
            6,
        ),
        "max_drawdown_improvement_min": _round(
            min(delta.get("max_drawdown_pct", 0) for delta in deltas),
            6,
        ),
        "min_sharpe_daily_delta": _round(
            min(delta.get("sharpe_daily", 0) for delta in deltas),
            6,
        ),
        "best_sharpe_daily_delta": _round(
            max(delta.get("sharpe_daily", 0) for delta in deltas),
            6,
        ),
        "min_win_rate_delta": _round(min(delta.get("win_rate", 0) for delta in deltas), 6),
        "trade_count_delta_sum": sum(int(delta.get("trade_count", 0)) for delta in deltas),
        "signals_generated_delta_sum": sum(
            int(delta.get("signals_generated", 0)) for delta in deltas
        ),
        "signals_survived_delta_sum": sum(
            int(delta.get("signals_survived", 0)) for delta in deltas
        ),
        "touched_trade_count_sum": sum(row["touched_trade_count"] for row in rows.values()),
        "touched_trade_pnl_sum": _round(
            sum(float(row["touched_trade_pnl"] or 0.0) for row in rows.values()),
            2,
        ),
    }


def _gate4_pass(aggregate: dict[str, Any]) -> bool:
    material = (
        (aggregate.get("expected_value_score_delta_pct") or 0.0) > 0.02
        or (aggregate.get("total_pnl_delta_pct") or 0.0) > 0.02
        or (aggregate.get("max_drawdown_improvement_min") or 0.0) < -0.005
    )
    stable = (
        aggregate.get("windows_ev_improved", 0) >= 2
        and aggregate.get("windows_ev_regressed", 0) == 0
        and aggregate.get("windows_pnl_regressed", 0) == 0
        and (aggregate.get("max_drawdown_worsening_max") or 0.0) <= 0.005
        and aggregate.get("touched_trade_count_sum", 0) >= 3
    )
    return bool(material and stable)


def _payload(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    aggregate = _aggregate(rows)
    accepted = _gate4_pass(aggregate)
    timestamp = datetime.now(timezone.utc).isoformat()
    rejection = None
    if not accepted:
        rejection = (
            "The sector-relative leader top-up did not clear the stability/materiality "
            "gate across the canonical windows, so no production rule is promoted."
        )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "change_type": "capital_allocation_mid_dispersion_sector_relative_leader_topup",
        "mechanism_family": "sector_relative_strength_allocation",
        "hypothesis": (
            "Within the accepted mid-sector-dispersion trend sleeve, known-sector "
            "non-Financials names that lead their own sector on 20-day momentum but "
            "do not already qualify for the RS20 top-up may deserve a small "
            "cap-aware allocation increase."
        ),
        "alpha_hypothesis": {
            "category": "capital_allocation",
            "entry_exit_ranking_or_allocation": "allocation",
            "playbook_alignment": (
                "Avoids blocked LLM/event data paths, avoids noisy universe expansion, "
                "does not retune accepted RS20 or mid-dispersion multipliers, and tests "
                "the playbook-requested state/sleeve-specific sector leadership signal."
            ),
        },
        "historical_experiment_check": {
            "broad_sector_persistence_entry": (
                "Previously rejected as too broad; this experiment does not alter entry "
                "or filtering and only sizes already-accepted trend trades."
            ),
            "financials_sector_leader": (
                "Previously accepted; Financials are excluded here to avoid retuning "
                "that accepted policy."
            ),
            "rs20_entry_state": (
                "Accepted at 1.10x; rs20_entry_state_leader trades are excluded to avoid "
                "a nearby RS20 scalar retry."
            ),
            "mid_dispersion_trend_risk": (
                "Accepted base sleeve; this tests an orthogonal sector-relative qualifier "
                "rather than another raw mid-dispersion multiplier."
            ),
        },
        "parameters": {
            "single_causal_variable": "non-Financials mid-dispersion trend sector-relative leader 1.10x cap-aware top-up",
            "topup_multiplier": TOPUP_MULTIPLIER,
            "topup_key": TOPUP_KEY,
            "eligibility": [
                "strategy == trend_long",
                "mid_sector_dispersion == True",
                "sector_relative_leader == True",
                "sector not in {Unknown, Financials}",
                "rs20_entry_state_leader != True",
            ],
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all existing sizing multipliers",
                "position caps",
                "portfolio heat",
                "add-ons",
                "exits",
                "LLM/news replay",
            ],
        },
        "date_range": {
            label: {"start": window["start"], "end": window["end"]}
            for label, window in WINDOWS.items()
        },
        "snapshots": {label: window["snapshot"] for label, window in WINDOWS.items()},
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": {
            label: row["before_metrics"] for label, row in rows.items()
        },
        "after_metrics": {label: row["after_metrics"] for label, row in rows.items()},
        "delta_metrics": {
            "aggregate": aggregate,
            "by_window": {label: row["delta_metrics"] for label, row in rows.items()},
        },
        "touched_trades": {
            label: row["touched_trades"] for label, row in rows.items()
        },
        "gate2_field_audit": {
            "operator_position_fields_required": ["entry_date", "target_price"],
            "new_runtime_fields": [
                "features_dict[*].momentum_20d_pct",
                "risk_engine.SECTOR_MAP",
                "sector_ret20 average from same-day features",
            ],
            "ghost_rule_check": (
                "Top-up requires explicit same-day feature momentum and known sector; "
                "missing fields make the signal ineligible rather than inferred."
            ),
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta_sum": aggregate["signals_generated_delta_sum"],
            "signals_survived_delta_sum": aggregate["signals_survived_delta_sum"],
            "survival_rates_after": {
                label: row["after_metrics"].get("survival_rate")
                for label, row in rows.items()
            },
        },
        "gate4": {
            "passed_replay": accepted,
            "basis": "Three canonical backtesting.md windows using the same snapshots.",
            "rule": (
                "Require >=2 EV-improved windows, zero EV/PnL-regressed windows, "
                "max DD worsening <= 0.5pp, >=3 touched trades, and at least a "
                "2% aggregate EV/PnL lift or 0.5pp DD improvement."
            ),
        },
        "decision": "accepted_replay_candidate" if accepted else "rejected",
        "status": "accepted_replay_candidate" if accepted else "rejected",
        "rejection_reason": rejection,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains data-limited, so this run uses deterministic "
                "features already available to backtest and production."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "A positive replay candidate still needs shared risk_engine/portfolio_engine "
                "implementation and run/backtester attribution parity before production."
            ),
        },
        "why_not_other_changes": {
            "LLM_soft_ranking": "Production-aligned closed attribution is still too sparse.",
            "Form4_SEC_options": "Latest refreshes produced no mature production alpha candidates.",
            "universe_expansion": "Recent broad/static expansion tests added noise or unstable one-window gains.",
            "mid_dispersion_multiplier_retune": "Blocked by playbook without a new discriminator.",
        },
        "known_risks": [
            "Sector-relative leadership can overweight a weak sector's best member.",
            "The non-RS20 exclusion may leave small sample size.",
            "If accepted, production implementation must share exactly the same feature/sector field logic.",
        ],
        "next_evidence_needed": (
            "If rejected, do not retry nearby sector-leader top-up multipliers on the "
            "same snapshots. A valid retry needs a different sleeve, forward evidence, "
            "or a candidate-pool classification gap."
        ),
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260510_019_mid_dispersion_sector_leader_topup.py",
        ],
    }


def _artifact(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Mid-Dispersion Sector-Leader Top-Up",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Aggregate",
        "",
        f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']:+.4f}` ({aggregate['expected_value_score_delta_pct']:+.2%})",
        f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']:+,.2f}` ({aggregate['total_pnl_delta_pct']:+.2%})",
        f"- EV windows improved/regressed: `{aggregate['windows_ev_improved']}` / `{aggregate['windows_ev_regressed']}`",
        f"- PnL windows improved/regressed: `{aggregate['windows_pnl_improved']}` / `{aggregate['windows_pnl_regressed']}`",
        f"- max DD worsening: `{aggregate['max_drawdown_worsening_max']:+.4f}`",
        f"- touched trades: `{aggregate['touched_trade_count_sum']}`",
        "",
        "## Three-Window Deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Touched |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["delta_metrics"]["by_window"].items():
        touched = len(payload["touched_trades"].get(label) or [])
        lines.append(
            f"| `{label}` | {row['expected_value_score']:+.4f} | "
            f"{row['total_pnl']:+.2f} | {row['sharpe_daily']:+.2f} | "
            f"{row['max_drawdown_pct']:+.4f} | {row['win_rate']:+.4f} | "
            f"{row['trade_count']:+d} | {touched} |"
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "No production/shared policy was changed by this replay. A positive replay candidate must still be promoted into shared `risk_engine` / `portfolio_engine` logic and exposed through both `run.py` and `backtester.py` attribution before live orders change.",
            "",
            "```text",
            "production_impact:",
            "  shared_policy_changed: false",
            "  backtester_adapter_changed: true",
            "  run_adapter_changed: false",
            "  replay_only: true",
            "  parity_test_added: false",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "Mid-dispersion sector leader top-up replay",
        "decision": payload["decision"],
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4_passed_replay": payload["gate4"]["passed_replay"],
        "next_action": (
            "Promote to shared policy only if follow-up implementation preserves run/backtester parity."
            if payload["gate4"]["passed_replay"]
            else payload["next_evidence_needed"]
        ),
    }


def run() -> dict[str, Any]:
    rows = _run_pairs()
    payload = _payload(rows)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, _ticket(payload))
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    return payload


if __name__ == "__main__":
    result = run()
    aggregate = result["delta_metrics"]["aggregate"]
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": result["decision"],
        "expected_value_score_delta_sum": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta_sum": aggregate["total_pnl_delta_sum"],
        "touched_trade_count_sum": aggregate["touched_trade_count_sum"],
    }, ensure_ascii=False, sort_keys=True))
