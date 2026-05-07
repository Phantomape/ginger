"""exp-20260506-012 crypto-beta regime-guarded candidate pool.

Alpha search. This tests a narrow candidate-pool policy instead of another
LLM-ranking, event-bundle, or broad-watchlist pass: crypto-beta candidates are
eligible only when the BTC ETF tape is itself in an uptrend.

No production policy is changed by this replay. A passing result must be moved
into shared universe eligibility / run.py reporting before promotion.
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
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from filter import _BASE_WATCHLIST  # noqa: E402
import risk_engine  # noqa: E402
import signal_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260506-012"
STEM = "crypto_beta_regime_guarded_pool"

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
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "base_snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "aug_snapshot": (
                    "data/experiments/exp-20260505-009/ohlcv/"
                    "exp-20260505-009_late_strong_fresh_ohlcv.json"
                ),
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "base_snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "aug_snapshot": (
                    "data/experiments/exp-20260505-009/ohlcv/"
                    "exp-20260505-009_mid_weak_fresh_ohlcv.json"
                ),
                "state_note": "rotation-heavy bull where strategy profits but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "base_snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "aug_snapshot": (
                    "data/experiments/exp-20260505-009/ohlcv/"
                    "exp-20260505-009_old_thin_fresh_ohlcv.json"
                ),
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

BTC_CONTEXT_TICKER = "IBIT"
CONTEXT_ONLY_TICKERS = {BTC_CONTEXT_TICKER}
SECTOR_PATCH = {
    "MSTR": "Financials",
    "IBIT": "ETF",
    "BITB": "ETF",
}

VARIANTS = OrderedDict(
    [
        ("mstr_guarded", ["MSTR"]),
        ("btc_etfs_guarded", ["IBIT", "BITB"]),
        ("mstr_plus_btc_etfs_guarded", ["MSTR", "IBIT", "BITB"]),
    ]
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _metrics(result: dict[str, Any], added: set[str], guard_stats: dict[str, int]) -> dict[str, Any]:
    added_trades = [
        trade for trade in result.get("trades", []) if trade.get("ticker") in added
    ]
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": round(float(result.get("total_pnl") or 0.0), 2),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "converged": (result.get("convergence") or {}).get("converged"),
        "entry_reason_counts": (
            result.get("entry_execution_attribution") or {}
        ).get("reason_counts"),
        "added_trade_count": len(added_trades),
        "added_trade_pnl": round(
            sum(float(trade.get("pnl") or 0.0) for trade in added_trades), 2
        ),
        "added_tickers_traded": sorted({trade.get("ticker") for trade in added_trades}),
        "guard_seen": guard_stats.get("seen", 0),
        "guard_passed": guard_stats.get("passed", 0),
        "guard_dropped_state": guard_stats.get("dropped_state", 0),
        "guard_dropped_context": guard_stats.get("dropped_context", 0),
        "context_only_dropped": guard_stats.get("context_only_dropped", 0),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
    return out


def _crypto_state_ok(features_dict: dict[str, dict[str, Any]]) -> bool:
    ibit = (features_dict or {}).get(BTC_CONTEXT_TICKER) or {}
    momentum_20d = ibit.get("momentum_20d_pct")
    return bool(
        ibit.get("above_200ma") is True
        and isinstance(momentum_20d, (int, float))
        and momentum_20d > 0.0
    )


def _patch_generate_signals(added: set[str], context_only: set[str]):
    original = signal_engine.generate_signals
    stats = {
        "seen": 0,
        "passed": 0,
        "dropped_state": 0,
        "dropped_context": 0,
        "context_only_dropped": 0,
    }

    def patched(features_dict, *args, **kwargs):
        signals = original(features_dict, *args, **kwargs)
        state_ok = _crypto_state_ok(features_dict)
        context_present = BTC_CONTEXT_TICKER in (features_dict or {})
        kept = []
        for sig in signals:
            ticker = str(sig.get("ticker") or "").upper()
            if ticker in context_only:
                stats["context_only_dropped"] += 1
                continue
            if ticker not in added:
                kept.append(sig)
                continue
            stats["seen"] += 1
            if not context_present:
                stats["dropped_context"] += 1
                continue
            if not state_ok:
                stats["dropped_state"] += 1
                continue
            stats["passed"] += 1
            sig = dict(sig)
            sig["crypto_beta_regime_guard_passed"] = True
            sig["crypto_beta_context_ticker"] = BTC_CONTEXT_TICKER
            kept.append(sig)
        return kept

    signal_engine.generate_signals = patched
    return original, stats


def _run_window(
    universe: list[str],
    cfg: dict[str, str],
    *,
    snapshot_key: str,
    added: set[str] | None = None,
    context_only: set[str] | None = None,
) -> dict[str, Any]:
    added = added or set()
    context_only = context_only or set()
    original_generate = None
    guard_stats = {
        "seen": 0,
        "passed": 0,
        "dropped_state": 0,
        "dropped_context": 0,
        "context_only_dropped": 0,
    }
    if added or context_only:
        original_generate, guard_stats = _patch_generate_signals(added, context_only)
    try:
        result = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg[snapshot_key]),
        ).run()
    finally:
        if original_generate is not None:
            signal_engine.generate_signals = original_generate
    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result, added, guard_stats),
        "trades": result.get("trades", []),
    }


def _aggregate(before: OrderedDict[str, dict[str, Any]], after: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    by_window = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_ev = round(
        sum(before[label]["metrics"]["expected_value_score"] for label in WINDOWS), 6
    )
    baseline_pnl = round(
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS), 2
    )
    ev_delta = round(sum(row["expected_value_score"] for row in by_window.values()), 6)
    pnl_delta = round(sum(row["total_pnl"] for row in by_window.values()), 2)
    return {
        "by_window": by_window,
        "baseline_expected_value_score_sum": baseline_ev,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / baseline_ev, 6) if baseline_ev else None,
        "baseline_total_pnl_sum": baseline_pnl,
        "total_pnl_delta_sum": pnl_delta,
        "total_pnl_delta_pct": round(pnl_delta / baseline_pnl, 6) if baseline_pnl else None,
        "ev_windows_improved": sum(1 for row in by_window.values() if row["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for row in by_window.values() if row["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for row in by_window.values() if row["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for row in by_window.values() if row["total_pnl"] < 0),
        "max_drawdown_delta_max": max(row["max_drawdown_pct"] for row in by_window.values()),
        "sharpe_daily_delta_max": max(row["sharpe_daily"] for row in by_window.values()),
        "trade_count_delta_sum": sum(row["trade_count"] for row in by_window.values()),
        "win_rate_delta_min": min(row["win_rate"] for row in by_window.values()),
        "added_trade_count_sum": sum(after[label]["metrics"]["added_trade_count"] for label in WINDOWS),
        "added_trade_pnl_sum": round(
            sum(after[label]["metrics"]["added_trade_pnl"] for label in WINDOWS),
            2,
        ),
        "guard_seen_sum": sum(after[label]["metrics"]["guard_seen"] for label in WINDOWS),
        "guard_passed_sum": sum(after[label]["metrics"]["guard_passed"] for label in WINDOWS),
        "guard_dropped_state_sum": sum(after[label]["metrics"]["guard_dropped_state"] for label in WINDOWS),
    }


def _passes_gate4(aggregate: dict[str, Any]) -> bool:
    if aggregate["ev_windows_improved"] < 2 or aggregate["ev_windows_regressed"] > 0:
        return False
    if aggregate["expected_value_score_delta_pct"] > 0.10:
        return True
    if aggregate["total_pnl_delta_pct"] > 0.05:
        return True
    if aggregate["sharpe_daily_delta_max"] > 0.10:
        return True
    if aggregate["max_drawdown_delta_max"] < -0.01:
        return True
    if aggregate["trade_count_delta_sum"] > 0 and aggregate["win_rate_delta_min"] >= 0:
        return True
    return False


def _append_once(path: Path, marker: str, text: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker not in existing:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)


def _write_artifact(payload: dict[str, Any]) -> None:
    best_name = payload["best_variant"]
    best = payload["delta_metrics"][best_name]
    lines = [
        f"# {EXPERIMENT_ID} crypto-beta regime-guarded pool",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{best_name}`",
        "",
        "| window | baseline EV | after EV | EV delta | PnL delta | added trades | guard passed/seen |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][best_name][label]
        delta = best["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${dpnl:,.2f} | {added} | {passed}/{seen} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                dpnl=delta["total_pnl"],
                added=after["added_trade_count"],
                passed=after["guard_passed"],
                seen=after["guard_seen"],
            )
        )
    lines.extend(
        [
            "",
            "Aggregate:",
            f"- EV delta sum: `{best['expected_value_score_delta_sum']:+.4f}`",
            f"- PnL delta sum: `${best['total_pnl_delta_sum']:,.2f}`",
            f"- Added trade PnL: `${best['added_trade_pnl_sum']:,.2f}`",
            f"- Gate 4: `{payload['best_variant_gate4']}`",
            "",
            "Production impact: replay-only. A positive future promotion must share the BTC-tape guard between backtest and run.py.",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    base_universe = sorted(set(_BASE_WATCHLIST))
    original_sector_map = dict(risk_engine.SECTOR_MAP)
    risk_engine.SECTOR_MAP.update(SECTOR_PATCH)
    try:
        baseline: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for label, cfg in WINDOWS.items():
            baseline[label] = _run_window(
                base_universe,
                cfg,
                snapshot_key="base_snapshot",
            )
            m = baseline[label]["metrics"]
            print(
                f"[{label} baseline] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"trades={m['trade_count']}"
            )

        variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for name, tickers in VARIANTS.items():
            added = set(tickers)
            context_only = CONTEXT_ONLY_TICKERS - added
            universe = sorted(set(base_universe) | added | context_only)
            rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
            for label, cfg in WINDOWS.items():
                rows[label] = _run_window(
                    universe,
                    cfg,
                    snapshot_key="aug_snapshot",
                    added=added,
                    context_only=context_only,
                )
                m = rows[label]["metrics"]
                print(
                    f"[{label} {name}] EV={m['expected_value_score']} "
                    f"PnL={m['total_pnl']} addedPnL={m['added_trade_pnl']} "
                    f"guard={m['guard_passed']}/{m['guard_seen']}"
                )
            aggregate = _aggregate(baseline, rows)
            variants[name] = {
                "added": tickers,
                "context_only": sorted(context_only),
                "rows": rows,
                "aggregate": aggregate,
                "passes_gate4": _passes_gate4(aggregate),
            }
    finally:
        risk_engine.SECTOR_MAP.clear()
        risk_engine.SECTOR_MAP.update(original_sector_map)

    best_variant, best = max(
        variants.items(),
        key=lambda item: (
            item[1]["passes_gate4"],
            item[1]["aggregate"]["ev_windows_improved"],
            -item[1]["aggregate"]["ev_windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    accepted = bool(best["passes_gate4"])
    decision = "accepted_candidate_needs_shared_policy" if accepted else "rejected"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "decision": decision,
        "status": decision,
        "change_type": "candidate_pool_crypto_beta_regime_guarded",
        "alpha_hypothesis_category": "candidate_pool_entry_qualification",
        "hypothesis": (
            "A narrow crypto-beta candidate pool may add external-asset momentum "
            "alpha only when the BTC ETF tape confirms the regime; this avoids "
            "both LLM soft-ranking data limits and broad noisy watchlist growth."
        ),
        "why_this_is_not_blocked": (
            "LLM soft-ranking and event-bundle promotion are data-limited. This "
            "uses existing OHLCV snapshots and a deterministic BTC ETF context "
            "source, not missing LLM archives or forward event outcomes."
        ),
        "history_check": {
            "recent_blocked_or_rejected": {
                "exp-20260505-009": "broad historical watchlist expansion failed badly",
                "exp-20260505-020": "simple HOOD/RBLX/SOFI gates were unstable",
                "exp-20260506-008": "free short-pressure overlays were weak",
                "exp-20260506-009": "simple options overlays were not decision-grade",
            },
            "why_not_simple_repeat": (
                "This is not broad ticker growth, not a raw crypto list, and not a "
                "short-squeeze proxy. It changes one policy variable: a fixed "
                "crypto-beta candidate pool gated by IBIT above its 200DMA with "
                "positive 20-day momentum."
            ),
            "mechanism_insight_guardrail": (
                "Avoids nearby SPY-leader, add-on, gap-cancel, slot-ranking, and "
                "external-event threshold families already rejected."
            ),
        },
        "parameters": {
            "single_causal_variable": "crypto_beta_candidate_pool_with_ibit_regime_guard",
            "btc_context_ticker": BTC_CONTEXT_TICKER,
            "guard": "IBIT above_200ma is true and IBIT momentum_20d_pct > 0",
            "tested_variants": dict(VARIANTS),
            "context_only_tickers": sorted(CONTEXT_ONLY_TICKERS),
            "sector_map_patch": SECTOR_PATCH,
            "source_augmented_snapshot": "exp-20260505-009 fresh OHLCV snapshots",
            "locked_variables": [
                "core production universe",
                "base signal rules",
                "candidate ranking",
                "position sizing rules",
                "entry/exit filters",
                "gap cancels",
                "add-ons",
                "MAX_POSITIONS",
                "MAX_PER_SECTOR",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": f"{WINDOWS['late_strong']['start']} -> {WINDOWS['late_strong']['end']}",
            "secondary": [
                f"{WINDOWS['mid_weak']['start']} -> {WINDOWS['mid_weak']['end']}",
                f"{WINDOWS['old_thin']['start']} -> {WINDOWS['old_thin']['end']}",
            ],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: baseline[label]["metrics"] for label in WINDOWS
        },
        "after_metrics": {
            name: {label: variant["rows"][label]["metrics"] for label in WINDOWS}
            for name, variant in variants.items()
        },
        "delta_metrics": {
            name: variant["aggregate"] for name, variant in variants.items()
        },
        "variant_details": {
            name: {
                "added": variant["added"],
                "context_only": variant["context_only"],
                "passes_gate4": variant["passes_gate4"],
            }
            for name, variant in variants.items()
        },
        "best_variant": best_variant,
        "best_variant_gate4": accepted,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If this later becomes production alpha, move the IBIT regime "
                "guard and crypto-beta universe eligibility into a shared policy "
                "called by both backtester.py and run.py."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_no_llm_change": (
                "LLM remains appropriate for event grading, but this experiment "
                "deliberately avoids the current LLM replay coverage bottleneck."
            ),
        },
        "rejection_reason": (
            None
            if accepted
            else "No crypto-beta guarded candidate-pool variant passed the three-window Gate 4 policy."
        ),
        "next_action": (
            "Do not promote the crypto-beta pool unless this replay clears Gate 4 "
            "and the guard is implemented in shared production/backtest policy."
        ),
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(TICKET_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
            "quant/experiments/exp_20260506_012_crypto_beta_regime_guarded_pool.py",
        ],
    }


def main() -> int:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "title": "Crypto-beta guarded pool",
            "summary": (
                f"Best {payload['best_variant']} "
                f"Gate4={payload['best_variant_gate4']}"
            ),
            "best_variant": payload["best_variant"],
            "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
            "production_impact": payload["production_impact"],
        },
    )
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG, payload)

    best = payload["delta_metrics"][payload["best_variant"]]
    playbook_note = f"""

### 2026-05-06 mechanism update: Crypto-beta regime-guarded pool

Status: {payload["decision"]}.

Core conclusion: `{EXPERIMENT_ID}` tested whether a narrow crypto-beta
candidate pool (`MSTR`, `IBIT`, `BITB`) should be eligible only when `IBIT`
is above its 200-day average and has positive 20-day momentum. This was a
state-gated candidate-pool alpha search, not broad watchlist growth, LLM
ranking, short-pressure tuning, or an external-event bundle sweep.

Evidence: best variant `{payload["best_variant"]}` produced aggregate EV delta
`{best["expected_value_score_delta_sum"]:+.4f}` and aggregate PnL delta
`${best["total_pnl_delta_sum"]:,.2f}` / `{best["total_pnl_delta_pct"]:.2%}`;
EV improved in `{best["ev_windows_improved"]}` windows and regressed in
`{best["ev_windows_regressed"]}`. Added crypto-beta trade PnL was
`${best["added_trade_pnl_sum"]:,.2f}` across `{best["added_trade_count_sum"]}`
trades.

Mechanism insight: BTC-tape confirmation is a valid way to avoid raw noisy
crypto ticker growth, but it still must clear the same three-window Gate 4 and
shared-policy parity rules before production promotion.

Do not repeat: raw crypto-beta watchlist promotion, nearby `IBIT` momentum
guard thresholds, or adding leveraged/inverse crypto proxies without forward
evidence or a materially different external-asset state source.
"""
    _append_once(PLAYBOOK, f"`{EXPERIMENT_ID}`", playbook_note)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "best_variant": payload["best_variant"],
                "best_gate4": payload["best_variant_gate4"],
                "best_delta": best,
                "artifact": str(OUT_JSON),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
