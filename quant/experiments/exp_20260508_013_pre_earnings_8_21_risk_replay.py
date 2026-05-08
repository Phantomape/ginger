"""exp-20260508-013: pre-earnings 8-21 day risk replay.

Alpha search, replay-only. Recent work rejected nearby 22-45 day and 46+ day
pre-earnings allocation variants, while LLM/state-surface/10-K directions remain
forward-sample limited. This experiment isolates a different entry-state bucket:
already-entered A/B trades whose signal date is 8-21 calendar days before the
next earnings date.

Only the risk multiplier for already-entered tagged trades is replayed. Signal
generation, ranking, entries, exits, event sleeves, LLM/news, universe, and
production orders are locked. Any positive result would still require a shared
run.py/backtester.py risk policy plus parity tests before promotion.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_DIR = Path(__file__).resolve().parent
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

import exp_20260507_033_far_earnings_entry_state_risk as base  # noqa: E402


EXPERIMENT_ID = "exp-20260508-013"
STEM = "pre_earnings_8_21_risk_replay"
SOURCE_EXPERIMENTS = (
    "exp-20260507-032",
    "exp-20260507-033",
    "exp-20260508-001",
)
TREATMENT_TAG = "pre_earnings_8_21"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = (
    REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
)
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)

VARIANTS = OrderedDict(
    [
        ("pre_earnings_8_21_0_50x_replay", {"risk_multiplier": 0.50}),
        ("pre_earnings_8_21_0_75x_replay", {"risk_multiplier": 0.75}),
        ("pre_earnings_8_21_1_25x_cap_aware", {"risk_multiplier": 1.25}),
    ]
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _official_baseline_sum(by_window: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": base._round(
            sum(
                (window.get("official_baseline_metrics") or {}).get(
                    "expected_value_score"
                )
                or 0.0
                for window in by_window.values()
            ),
            4,
        ),
        "total_pnl_sum": base._round(
            sum(
                (window.get("official_baseline_metrics") or {}).get("total_pnl")
                or 0.0
                for window in by_window.values()
            ),
            2,
        ),
        "trade_count_sum": sum(
            int((window.get("official_baseline_metrics") or {}).get("trade_count") or 0)
            for window in by_window.values()
        ),
    }


def _risk_variant_trades(
    trades: list[dict[str, Any]],
    baseline_equity: OrderedDict[str, float],
    tag_by_trade: dict[tuple[str, str, str], dict[str, Any]],
    *,
    risk_multiplier: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
    touched = 0
    changed = 0
    tagged_entered = 0

    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        entry_date = str(trade.get("entry_date") or "")[:10]
        strategy = str(trade.get("strategy") or "")
        tag_row = tag_by_trade.get((entry_date, ticker, strategy))
        tags = list((tag_row or {}).get("tags") or [])
        if tag_row is not None:
            tagged_entered += 1
        if TREATMENT_TAG not in tags:
            out.append(trade)
            continue

        touched += 1
        old_shares = int(trade.get("shares") or 0)
        entry_price = base._float(trade.get("entry_price"))
        entry_equity = baseline_equity.get(entry_date)
        cap_pct, cap_source = base._position_cap_pct(trade)

        if old_shares <= 0 or entry_price is None or entry_equity is None:
            status = "missing_resize_inputs"
            status_counts[status] += 1
            out.append(trade)
            continue

        if risk_multiplier < 1.0:
            desired_shares = max(1, int(math.floor(old_shares * risk_multiplier)))
            replay_shares = min(old_shares, desired_shares)
            if replay_shares >= old_shares:
                status = "rounding_no_risk_reduction"
        else:
            desired_shares = max(old_shares, int(math.floor(old_shares * risk_multiplier)))
            cap_shares = int(math.floor((entry_equity * cap_pct) / entry_price))
            replay_shares = min(desired_shares, cap_shares)
            if replay_shares <= old_shares:
                status = "cap_bound_no_headroom"

        if replay_shares == old_shares:
            status_counts[status] += 1
            out.append(trade)
            details.append(
                {
                    "ticker": ticker,
                    "strategy": strategy,
                    "entry_date": entry_date,
                    "baseline_shares": old_shares,
                    "desired_shares": desired_shares,
                    "replay_shares": old_shares,
                    "status": status,
                    "baseline_pnl": base._round(trade.get("pnl"), 2),
                    "pnl_delta": 0.0,
                    "tags": tags,
                    "cap_pct": cap_pct,
                    "cap_source": cap_source,
                    "entry_proxy_equity": base._round(entry_equity, 2),
                }
            )
            continue

        reason = "pre_earnings_8_21_entry_state_risk_multiplier_replay"
        replacement = base._resize_trade(
            trade,
            new_shares=replay_shares,
            reason=reason,
            cap_pct=cap_pct,
            cap_source=cap_source,
            entry_equity=entry_equity,
            tags=tags,
        )
        old_pnl = base._float(trade.get("pnl")) or 0.0
        new_pnl = base._float(replacement.get("pnl")) or 0.0
        pnl_delta = new_pnl - old_pnl
        changed += 1
        status = "risk_reduced" if risk_multiplier < 1.0 else "risk_increased"
        status_counts[status] += 1
        pnl_delta_by_ticker[ticker] += pnl_delta
        out.append(replacement)
        details.append(
            {
                "ticker": ticker,
                "strategy": strategy,
                "entry_date": entry_date,
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "baseline_shares": old_shares,
                "desired_shares": desired_shares,
                "replay_shares": replay_shares,
                "status": status,
                "baseline_pnl": base._round(old_pnl, 2),
                "variant_pnl": base._round(new_pnl, 2),
                "pnl_delta": base._round(pnl_delta, 2),
                "tags": tags,
                "cap_pct": cap_pct,
                "cap_source": cap_source,
                "entry_proxy_equity": base._round(entry_equity, 2),
            }
        )

    return out, {
        "entered_trades_with_entry_state_tags": tagged_entered,
        "touched_treatment_trades": touched,
        "changed_treatment_trades": changed,
        "status_counts": dict(sorted(status_counts.items())),
        "pnl_delta_by_ticker": {
            ticker: base._round(value, 2)
            for ticker, value in sorted(pnl_delta_by_ticker.items())
        },
        "details": details,
    }


def _choose_best(aggregate: dict[str, Any]) -> str:
    return max(
        aggregate,
        key=lambda name: (
            aggregate[name].get("expected_value_score_delta_sum") or -10**9,
            aggregate[name].get("total_pnl_delta_sum") or -10**9,
        ),
    )


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Pre-Earnings 8-21 Risk Replay",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{payload['best_variant']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Baseline",
        "",
        "| EV sum | PnL sum | Trades |",
        "|---:|---:|---:|",
        "| {ev} | {pnl} | {trades} |".format(
            ev=payload["official_baseline_metrics"]["expected_value_score_sum"],
            pnl=payload["official_baseline_metrics"]["total_pnl_sum"],
            trades=payload["official_baseline_metrics"]["trade_count_sum"],
        ),
        "",
        "## Aggregate Replay",
        "",
        "| Variant | EV delta | EV delta % | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, metrics in payload["aggregate"].items():
        lines.append(
            "| {name} | {ev} | {ev_pct} | {pnl} | {pnl_pct} | {up}/{down} | {touched} | {changed} | {dd} | {share} | {gate} |".format(
                name=name,
                ev=metrics["expected_value_score_delta_sum"],
                ev_pct=metrics["expected_value_score_delta_pct"],
                pnl=metrics["total_pnl_delta_sum"],
                pnl_pct=metrics["total_pnl_delta_pct"],
                up=metrics["windows_ev_improved"],
                down=metrics["windows_ev_regressed"],
                touched=metrics["touched_treatment_trades"],
                changed=metrics["changed_treatment_trades"],
                dd=metrics["max_drawdown_worsening_max"],
                share=metrics["max_single_ticker_positive_share"],
                gate="PASS" if metrics["proxy_gate4_passed"] else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "## Window Deltas",
            "",
            "| Variant | Window | EV delta | PnL delta | Sharpe delta | DD delta |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for name, metrics in payload["aggregate"].items():
        for window, delta in metrics["by_window_delta"].items():
            lines.append(
                "| {name} | {window} | {ev} | {pnl} | {sharpe} | {dd} |".format(
                    name=name,
                    window=window,
                    ev=delta["expected_value_score"],
                    pnl=delta["total_pnl"],
                    sharpe=delta["sharpe_daily"],
                    dd=delta["max_drawdown_pct"],
                )
            )
    lines.extend(
        [
            "",
            "## Rejection Reason",
            "",
            payload["rejection_reason"] or "None",
            "",
            "## Production Impact",
            "",
            "Replay-only diagnostic. No shared policy, default backtest strategy, production orders, LLM/news boundary, or universe changed.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    original_tag = base.TREATMENT_TAG
    original_variants = base.VARIANTS
    original_variant_trades = base._variant_trades
    base.TREATMENT_TAG = TREATMENT_TAG
    base.VARIANTS = VARIANTS
    base._variant_trades = _risk_variant_trades
    try:
        by_window = OrderedDict(
            (name, base._replay_window(name, spec))
            for name, spec in base.WINDOWS.items()
        )
        aggregate = base._aggregate(by_window)
    finally:
        base.TREATMENT_TAG = original_tag
        base.VARIANTS = original_variants
        base._variant_trades = original_variant_trades

    best_variant = _choose_best(aggregate)
    best = aggregate[best_variant]
    decision = "accepted_replay_only" if best["proxy_gate4_passed"] else "rejected"
    rejection_reason = None
    if decision == "rejected":
        rejection_reason = (
            f"Best variant `{best_variant}` failed Gate 4: EV delta "
            f"{best['expected_value_score_delta_sum']} "
            f"({best['expected_value_score_delta_pct']}), PnL delta "
            f"{best['total_pnl_delta_sum']} ({best['total_pnl_delta_pct']}), "
            f"windows improved/regressed {best['windows_ev_improved']}/"
            f"{best['windows_ev_regressed']}, changed trades "
            f"{best['changed_treatment_trades']} of {best['touched_treatment_trades']} "
            f"touched, max DD worsening {best['max_drawdown_worsening_max']}, "
            f"single ticker positive share {best['max_single_ticker_positive_share']}."
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "source_experiments": SOURCE_EXPERIMENTS,
        "hypothesis": (
            "Accepted A/B trades 8-21 calendar days before the next earnings "
            "date may represent a distinct pre-event risk bucket. If the bucket "
            "is a noisy overhang, 0.50x/0.75x should improve weak-window EV; if "
            "it is anticipation momentum, 1.25x should improve EV without hurting "
            "old_thin drawdown."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "change_type": "entry_state_risk_multiplier_replay",
        "mechanism_family": "pre_earnings_entry_state_lifecycle_allocation",
        "single_causal_variable": "pre_earnings_8_21_entry_state_risk_multiplier",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}"
            for name, spec in base.WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in base.WINDOWS.items()
        },
        "historical_experiment_check": {
            "nearby_rejected": {
                "exp-20260508-001": (
                    "pre_earnings_22_45 risk boost failed Gate 4; this tests a "
                    "different 8-21 day bucket and includes de-risk variants."
                ),
                "exp-20260507-033": (
                    "pre_earnings_46_plus far-from-earnings add-on failed Gate 4; "
                    "this is closer to the earnings event and not a far-DTE retry."
                ),
                "exp-20260505-016": (
                    "Sector-specific breakout DTE zero-risk failed; this is not "
                    "sector-specific and does not zero out trades."
                ),
            },
            "mechanism_insight_conflict": (
                "No conflict with current do-not-repeat zones: it is not LLM "
                "soft-ranking, event source pruning, state-surface paper tuning, "
                "SMA20 reclaim, platform RS20, C-sleeve enablement, or 10-K "
                "candidate expansion."
            ),
            "why_not_simple_repeat": (
                "The 8-21 day bucket has a different event lifecycle than the "
                "already rejected 22-45 and 46+ buckets, and this replay evaluates "
                "both de-risk and modest cap-aware boost before any promotion."
            ),
        },
        "parameters": {
            "treatment_tag": TREATMENT_TAG,
            "variants": VARIANTS,
            "risk_multiplier_semantics": {
                "below_1": "reduce already-entered tagged trade shares only",
                "above_1": "increase shares only when existing cap policy has headroom",
            },
            "position_cap_policy": {
                "default_initial_cap": base.MAX_POSITION_PCT,
                "spy_relative_leader_cap": base.RISK_ON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT,
                "entry_equity_source": "baseline proxy daily equity at entry date",
                "if_cap_has_no_headroom": "leave baseline shares unchanged",
            },
            "locked_variables": [
                "core universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "exits",
                "add-ons",
                "event sleeves",
                "LLM/news replay",
                "earnings_event_long enablement",
            ],
            "gate4": {
                "expected_value_score_delta_pct": "> 10%",
                "total_pnl_delta_pct": "> 5%",
                "windows_ev_improved": ">= 2 of 3",
                "windows_ev_regressed": "0",
                "max_drawdown_worsening": "<= 1pp",
                "touched_treatment_trades": ">= 8",
                "changed_treatment_trades": ">= 3",
                "single_ticker_positive_contribution": "<= 50%",
            },
        },
        "official_baseline_metrics": _official_baseline_sum(by_window),
        "before_metrics": {
            name: window["official_baseline_metrics"]
            for name, window in by_window.items()
        },
        "proxy_before_metrics": {
            name: window["proxy_before_metrics"] for name, window in by_window.items()
        },
        "after_metrics": {
            variant: {
                name: by_window[name]["variant_results"][variant]["metrics"]
                for name in by_window
            }
            for variant in VARIANTS
        },
        "by_window": by_window,
        "aggregate": aggregate,
        "delta_metrics": aggregate,
        "best_variant": best_variant,
        "expected_value_score_delta": best["expected_value_score_delta_sum"],
        "gate4": {
            "passed": bool(best["proxy_gate4_passed"]),
            "basis": (
                "Replay-only cap-aware resize of baseline entered trades across "
                "the three fixed windows from docs/backtesting.md."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM/news replay is locked out of this deterministic entry-state replay."
            ),
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "Do not retry nearby pre_earnings_8_21 risk multipliers on the same sample.",
            "A valid retry needs forward entry-state outcomes or an orthogonal event/news quality discriminator.",
            "Any promotion must move the rule into a shared risk policy consumed by run.py and backtester.py with parity tests.",
        ],
        "risk_of_change": (
            "A DTE-shaped risk layer can add brittle event-timing complexity and "
            "mis-size good continuation winners in late/mid tapes or losers in old_thin."
        ),
        "why_not_other_attractive_points": {
            "llm_soft_ranking": "Replay/outcome join coverage remains too sparse.",
            "sec_10k_candidate_pool": "Forward watch found no outside-universe eligible 10-K candidates yet.",
            "state_surface_pilot": "Only pending paper rows exist; no closed forward outcomes.",
            "sma20_reclaim": "Read-only precheck showed negative EV and only seven touched entered trades.",
            "platform_rs20": "Recent missed-feature audit is forward-watch only and not promotable same-sample.",
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(Path(__file__).relative_to(REPO_ROOT)),
        ],
    }
    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis_category": payload["alpha_hypothesis_category"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "single_causal_variable": payload["single_causal_variable"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "historical_experiment_check": payload["historical_experiment_check"],
        "parameters": payload["parameters"],
        "before_metrics": payload["before_metrics"],
        "proxy_before_metrics": payload["proxy_before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": aggregate,
        "best_variant": best_variant,
        "expected_value_score_delta": best["expected_value_score_delta_sum"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "rejection_reason": rejection_reason,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "risk_of_change": payload["risk_of_change"],
        "why_not_other_attractive_points": payload["why_not_other_attractive_points"],
    }
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Pre-earnings 8-21 risk replay",
        "decision": decision,
        "best_variant": best_variant,
        "expected_value_score_delta_sum": best["expected_value_score_delta_sum"],
        "expected_value_score_delta_pct": best["expected_value_score_delta_pct"],
        "total_pnl_delta_sum": best["total_pnl_delta_sum"],
        "total_pnl_delta_pct": best["total_pnl_delta_pct"],
        "windows_ev_improved": best["windows_ev_improved"],
        "windows_ev_regressed": best["windows_ev_regressed"],
        "next_action": (
            "Do not promote; avoid nearby 8-21 day earnings-distance risk multipliers without new evidence."
            if decision == "rejected"
            else "Promote only after shared policy and parity tests."
        ),
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    print(json.dumps(ticket, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
