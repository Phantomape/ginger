"""exp-20260507-907: platform RS20 leader risk replay.

Alpha search, replay-only. This tests whether already-entered core-platform
A/B trades deserve extra cap-aware risk only when the signal-date entry-state
oracle tags them as `rs20_leader`.

This is deliberately narrower than the rejected broad platform risk replay in
exp-20260507-027: ticker identity alone is not enough. It also avoids LLM,
earnings C-sleeve, event-source retuning, entry timing, and universe expansion.
No live orders, default backtest behavior, shared policy, or production report
surface changes here.
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
EXPERIMENT_DIR = Path(__file__).resolve().parent
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

import exp_20260507_033_far_earnings_entry_state_risk as base  # noqa: E402


EXPERIMENT_ID = "exp-20260507-907"
STEM = "platform_rs20_leader_risk"
SOURCE_EXPERIMENTS = ("exp-20260507-027", "exp-20260507-032")
TREATMENT_TAG = "rs20_leader"
PLATFORM_TICKERS = {"NFLX", "APP", "META", "GOOG", "AMZN", "SPOT", "DIS"}

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

VARIANTS = OrderedDict(
    [
        ("platform_rs20_1_25x_cap_aware", {"risk_multiplier": 1.25}),
        ("platform_rs20_1_50x_cap_aware", {"risk_multiplier": 1.50}),
        ("platform_rs20_2_00x_cap_aware", {"risk_multiplier": 2.00}),
    ]
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _replay_window(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    snapshot = base._load_json(REPO_ROOT / spec["snapshot"])
    ohlcv = base._load_ohlcv(REPO_ROOT / spec["snapshot"])
    result = base._run_backtest(spec)
    candidate_events = result.get("entry_candidate_events") or []
    entry_rows = base._entry_state_rows(result, snapshot, candidate_events)
    platform_entry_rows = [
        row
        for row in entry_rows
        if str(row.get("ticker") or "").upper() in PLATFORM_TICKERS
    ]
    tag_by_trade = base._tag_lookup(platform_entry_rows)
    trades = [
        dict(trade)
        for trade in result.get("trades") or []
        if trade.get("entry_date") and trade.get("exit_date")
    ]
    spy_rows = ohlcv["SPY"]
    baseline_equity = base._daily_equity_series(
        trades,
        ohlcv,
        spy_rows,
        spec["start"],
        spec["end"],
    )
    proxy_before = base._daily_equity_metrics(
        trades,
        ohlcv,
        spy_rows,
        spec["start"],
        spec["end"],
    )
    tag_counts: dict[str, int] = {}
    entered_tag_counts: dict[str, int] = {}
    for row in platform_entry_rows:
        for tag in row.get("tags") or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
            if row.get("decision") == "entered":
                entered_tag_counts[tag] = entered_tag_counts.get(tag, 0) + 1

    variant_results: dict[str, Any] = {}
    for variant_name, params in VARIANTS.items():
        variant_trades, meta = base._variant_trades(
            trades,
            baseline_equity,
            tag_by_trade,
            risk_multiplier=params["risk_multiplier"],
        )
        proxy_after = base._daily_equity_metrics(
            variant_trades,
            ohlcv,
            spy_rows,
            spec["start"],
            spec["end"],
        )
        ev_delta = None
        if (
            proxy_after.get("expected_value_score") is not None
            and proxy_before.get("expected_value_score") is not None
        ):
            ev_delta = (
                proxy_after["expected_value_score"]
                - proxy_before["expected_value_score"]
            )
        variant_results[variant_name] = {
            "metrics": proxy_after,
            "delta_vs_proxy_before": {
                "expected_value_score": base._round(ev_delta, 4),
                "total_pnl": base._round(
                    proxy_after["total_pnl"] - proxy_before["total_pnl"],
                    2,
                ),
                "sharpe_daily": base._round(
                    proxy_after["sharpe_daily"] - proxy_before["sharpe_daily"],
                    2,
                ),
                "max_drawdown_pct": base._round(
                    proxy_after["max_drawdown_pct"]
                    - proxy_before["max_drawdown_pct"],
                    4,
                ),
                "trade_count": proxy_after["trade_count"] - proxy_before["trade_count"],
            },
            **meta,
        }

    return {
        "window": name,
        "window_spec": spec,
        "official_baseline_metrics": base._window_metrics(result),
        "proxy_before_metrics": proxy_before,
        "baseline_trade_count": len(trades),
        "platform_entry_state_candidate_count": len(platform_entry_rows),
        "platform_entry_state_tag_counts": dict(sorted(tag_counts.items())),
        "platform_entered_entry_state_tag_counts": dict(sorted(entered_tag_counts.items())),
        "treatment_entered_trade_count": entered_tag_counts.get(TREATMENT_TAG, 0),
        "variant_results": variant_results,
    }


def _positive_share(pnl_delta_by_ticker: dict[str, float]) -> float | None:
    positives = [value for value in pnl_delta_by_ticker.values() if value > 0]
    total = sum(positives)
    if total <= 0:
        return None
    return max(positives) / total


def _aggregate(by_window: dict[str, Any]) -> dict[str, Any]:
    baseline_ev_sum = sum(
        (window.get("proxy_before_metrics") or {}).get("expected_value_score") or 0.0
        for window in by_window.values()
    )
    baseline_pnl_sum = sum(
        (window.get("proxy_before_metrics") or {}).get("total_pnl") or 0.0
        for window in by_window.values()
    )
    out: dict[str, Any] = {}
    for variant_name in VARIANTS:
        after_ev_sum = 0.0
        after_pnl_sum = 0.0
        touched_sum = 0
        changed_sum = 0
        improved = 0
        regressed = 0
        max_dd_worsening = 0.0
        by_window_delta: dict[str, Any] = {}
        status_counts: dict[str, int] = {}
        pnl_delta_by_ticker: dict[str, float] = {}
        for window_name, window in by_window.items():
            variant = window["variant_results"][variant_name]
            metrics = variant["metrics"]
            delta = variant["delta_vs_proxy_before"]
            after_ev_sum += metrics.get("expected_value_score") or 0.0
            after_pnl_sum += metrics.get("total_pnl") or 0.0
            touched_sum += variant.get("touched_treatment_trades") or 0
            changed_sum += variant.get("changed_treatment_trades") or 0
            ev_delta = delta.get("expected_value_score") or 0.0
            if ev_delta > 0:
                improved += 1
            elif ev_delta < 0:
                regressed += 1
            max_dd_worsening = max(
                max_dd_worsening,
                delta.get("max_drawdown_pct") or 0.0,
            )
            by_window_delta[window_name] = delta
            for status, count in (variant.get("status_counts") or {}).items():
                status_counts[status] = status_counts.get(status, 0) + int(count or 0)
            for ticker, value in (variant.get("pnl_delta_by_ticker") or {}).items():
                pnl_delta_by_ticker[ticker] = pnl_delta_by_ticker.get(ticker, 0.0) + float(value or 0.0)

        ev_delta_sum = after_ev_sum - baseline_ev_sum
        pnl_delta_sum = after_pnl_sum - baseline_pnl_sum
        ev_delta_pct = ev_delta_sum / abs(baseline_ev_sum) if baseline_ev_sum else None
        pnl_delta_pct = pnl_delta_sum / baseline_pnl_sum if baseline_pnl_sum else None
        max_single_share = _positive_share(pnl_delta_by_ticker)
        gate_passed = (
            ev_delta_pct is not None
            and ev_delta_pct > 0.10
            and pnl_delta_pct is not None
            and pnl_delta_pct > 0.05
            and improved >= 2
            and regressed == 0
            and max_dd_worsening <= 0.01
            and touched_sum >= 8
            and changed_sum >= 3
            and (max_single_share is None or max_single_share <= 0.50)
        )
        out[variant_name] = {
            "baseline_proxy_expected_value_score_sum": base._round(baseline_ev_sum, 4),
            "after_proxy_expected_value_score_sum": base._round(after_ev_sum, 4),
            "expected_value_score_delta_sum": base._round(ev_delta_sum, 4),
            "expected_value_score_delta_pct": base._round(ev_delta_pct, 6),
            "baseline_proxy_total_pnl_sum": base._round(baseline_pnl_sum, 2),
            "after_proxy_total_pnl_sum": base._round(after_pnl_sum, 2),
            "total_pnl_delta_sum": base._round(pnl_delta_sum, 2),
            "total_pnl_delta_pct": base._round(pnl_delta_pct, 6),
            "windows_ev_improved": improved,
            "windows_ev_regressed": regressed,
            "max_drawdown_worsening_max": base._round(max_dd_worsening, 4),
            "touched_treatment_trades": touched_sum,
            "changed_treatment_trades": changed_sum,
            "status_counts": dict(sorted(status_counts.items())),
            "max_single_ticker_positive_share": base._round(max_single_share, 4),
            "pnl_delta_by_ticker": {
                ticker: base._round(value, 2)
                for ticker, value in sorted(pnl_delta_by_ticker.items())
            },
            "by_window_delta": by_window_delta,
            "proxy_gate4_passed": gate_passed,
        }
    return out


def _choose_best(aggregate: dict[str, Any]) -> str:
    return max(
        aggregate,
        key=lambda name: (
            aggregate[name].get("expected_value_score_delta_sum") or -10**9,
            aggregate[name].get("total_pnl_delta_sum") or -10**9,
        ),
    )


def _official_baseline_sum(by_window: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": base._round(
            sum(
                (window.get("official_baseline_metrics") or {}).get("expected_value_score")
                or 0.0
                for window in by_window.values()
            ),
            4,
        ),
        "total_pnl_sum": base._round(
            sum(
                (window.get("official_baseline_metrics") or {}).get("total_pnl") or 0.0
                for window in by_window.values()
            ),
            2,
        ),
        "trade_count_sum": sum(
            int((window.get("official_baseline_metrics") or {}).get("trade_count") or 0)
            for window in by_window.values()
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    best_variant = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Platform RS20 Leader Risk Replay",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{best_variant}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Aggregate Replay",
        "",
        "| Variant | EV delta | EV delta % | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, metrics in aggregate.items():
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
    for name, metrics in aggregate.items():
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
            "Replay-only diagnostic. No production orders, shared policy, default backtest strategy, LLM/news boundary, or universe changed.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    base.TREATMENT_TAG = TREATMENT_TAG
    base.VARIANTS = VARIANTS
    timestamp = datetime.now(timezone.utc).isoformat()
    by_window = OrderedDict(
        (name, _replay_window(name, spec)) for name, spec in base.WINDOWS.items()
    )
    aggregate = _aggregate(by_window)
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

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "source_experiments": SOURCE_EXPERIMENTS,
        "hypothesis": (
            "Already-entered core-platform A/B trades with signal-date "
            "`rs20_leader` entry-state tags may deserve cap-aware add-on risk, "
            "while platform names without the leadership tag should keep baseline size."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "change_type": "cap_aware_entry_state_risk_replay",
        "mechanism_family": "platform_rs20_leader_lifecycle_allocation",
        "single_causal_variable": "platform_rs20_leader_entry_state_risk_multiplier",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}"
            for name, spec in base.WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in base.WINDOWS.items()
        },
        "historical_experiment_check": {
            "nearby_rejected": {
                "exp-20260507-027": (
                    "Broad core-platform cap-aware risk was positive but immaterial "
                    "and APP-concentrated; this run requires the oracle `rs20_leader` "
                    "entry-state tag instead of ticker identity alone."
                ),
                "exp-20260507-030": (
                    "META/NFLX-specific timing overlap was underpowered; this run "
                    "uses the broader platform cohort while still requiring a "
                    "pre-entry state tag."
                ),
                "exp-20260507-033": (
                    "Far-from-earnings risk add-on failed on mid_weak regression; "
                    "this test uses RS leadership rather than earnings distance."
                ),
            },
            "mechanism_insight_conflict": (
                "No conflict with LLM soft-ranking, C-sleeve, event-source pruning, "
                "runner exit, post-news continuation, or raw universe expansion do-not-repeat zones."
            ),
            "why_not_simple_repeat": (
                "The causal variable is a specific oracle entry-state leadership tag "
                "inside the platform cohort, not another broad platform multiplier."
            ),
        },
        "parameters": {
            "platform_tickers": sorted(PLATFORM_TICKERS),
            "treatment_tag": TREATMENT_TAG,
            "variants": VARIANTS,
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
                "Replay-only cap-aware resize of baseline entered trades. "
                "Promotion would require shared run.py/backtester.py risk policy."
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
            "blocker_relation": "LLM/news replay is locked out of this deterministic replay.",
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "Do not retry nearby platform RS20 risk scalars on this same sample.",
            "A valid retry needs forward platform-RS outcomes or an orthogonal event/news discriminator that reduces APP concentration.",
            "Any promotion must move the rule into a shared risk policy consumed by run.py and backtester.py with parity tests.",
        ],
        "risk_of_change": (
            "Could overweight APP-like platform winners and create hidden single-name "
            "concentration while adding little late_strong headroom."
        ),
        "why_not_other_attractive_points": {
            "llm_soft_ranking": "Replay/outcome join coverage remains too sparse.",
            "earnings_c_sleeve": "Revalidated after snapshot repair and regressed all three windows.",
            "event_bundle_tuning": "Full event/state add-on surface is already default-off for forward evidence; more same-sample tuning risks overfit.",
            "universe_expansion": "Recent event-sensitive liquidity refresh did not prove scarce-slot replacement value.",
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(Path(__file__).relative_to(REPO_ROOT)),
        ],
    }
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Platform RS20 leader risk replay",
        "decision": decision,
        "best_variant": best_variant,
        "expected_value_score_delta_sum": best["expected_value_score_delta_sum"],
        "total_pnl_delta_sum": best["total_pnl_delta_sum"],
        "next_action": (
            "Do not promote; avoid nearby platform RS20 risk scalars without new evidence."
            if decision == "rejected"
            else "Promote only after shared policy and parity tests."
        ),
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    print(json.dumps(ticket, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
