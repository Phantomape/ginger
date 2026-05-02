"""exp-20260502-003 event-guarded AI infra candidate pool.

Alpha search. Test one candidate-pool policy variable: AI infrastructure
research tickers may be tradeable only when the existing earnings-distance
context says event risk is not imminent. This is not a raw watchlist add, a
simple BULL gate, or an LLM ranking change.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
import risk_engine  # noqa: E402
import signal_engine  # noqa: E402
from filter import _BASE_WATCHLIST  # noqa: E402


EXPERIMENT_ID = "exp-20260502-003"
SOURCE_EXPERIMENT_ID = "exp-20260501-008"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "ai_infra_event_guarded_pool.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": (
            f"data/experiments/{SOURCE_EXPERIMENT_ID}/"
            "ohlcv_aug_20251023_20260421.json"
        ),
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": (
            f"data/experiments/{SOURCE_EXPERIMENT_ID}/"
            "ohlcv_aug_20250423_20251022.json"
        ),
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": (
            f"data/experiments/{SOURCE_EXPERIMENT_ID}/"
            "ohlcv_aug_20241002_20250422.json"
        ),
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("pilot_tradeable_event_guarded", {
        "added": ["BE", "INTC", "LITE"],
        "min_days_to_earnings": 20,
        "unknown_dte_allowed": False,
    }),
    ("optical_storage_event_guarded", {
        "added": ["INTC", "LITE", "COHR"],
        "min_days_to_earnings": 20,
        "unknown_dte_allowed": False,
    }),
    ("all_full_history_ai_event_guarded", {
        "added": ["BE", "INTC", "LITE", "COHR", "APLD"],
        "min_days_to_earnings": 20,
        "unknown_dte_allowed": False,
    }),
])

SECTOR_PATCH = {
    "APLD": "Technology",
    "BE": "Energy",
    "COHR": "Technology",
    "INTC": "Technology",
    "LITE": "Technology",
}


def _metrics(result: dict, added: set[str], guard_stats: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    added_trade_count = 0
    added_trade_pnl = 0.0
    added_tickers = set()
    for trade in result.get("trades", []):
        ticker = trade.get("ticker")
        if ticker in added:
            added_trade_count += 1
            added_trade_pnl += float(trade.get("pnl") or 0.0)
            added_tickers.add(ticker)
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "added_trade_count": added_trade_count,
        "added_trade_pnl": round(added_trade_pnl, 2),
        "added_tickers_traded": sorted(added_tickers),
        "guard_seen": guard_stats.get("seen", 0),
        "guard_dropped": guard_stats.get("dropped", 0),
        "guard_passed": guard_stats.get("passed", 0),
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _patch_generate_signals(added: set[str], min_dte: int, unknown_dte_allowed: bool):
    original = signal_engine.generate_signals
    stats = {"seen": 0, "dropped": 0, "passed": 0}

    def patched(features_dict, *args, **kwargs):
        signals = original(features_dict, *args, **kwargs)
        kept = []
        for sig in signals:
            ticker = sig.get("ticker")
            if ticker not in added:
                kept.append(sig)
                continue
            stats["seen"] += 1
            features = (features_dict or {}).get(ticker) or {}
            dte = features.get("days_to_earnings")
            eligible = (
                (dte is None and unknown_dte_allowed)
                or (isinstance(dte, (int, float)) and dte > min_dte)
            )
            if eligible:
                stats["passed"] += 1
                sig = dict(sig)
                sig["ai_infra_event_guard_passed"] = True
                sig["ai_infra_event_guard_min_dte"] = min_dte
                sig["days_to_earnings"] = dte
                kept.append(sig)
            else:
                stats["dropped"] += 1
        return kept

    signal_engine.generate_signals = patched
    return original, stats


def _run_window(universe: list[str], cfg: dict, variant: dict | None) -> dict:
    guard_stats = {"seen": 0, "dropped": 0, "passed": 0}
    added = set()
    original_generate = None
    if variant is not None:
        added = set(variant["added"])
        original_generate, guard_stats = _patch_generate_signals(
            added,
            int(variant["min_days_to_earnings"]),
            bool(variant["unknown_dte_allowed"]),
        )
    try:
        result = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
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


def _aggregate(before: OrderedDict, after: OrderedDict) -> dict:
    deltas = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_total_pnl = round(
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS), 2
    )
    total_pnl_delta = round(sum(d["total_pnl"] for d in deltas.values()), 2)
    baseline_ev = round(
        sum(before[label]["metrics"]["expected_value_score"] for label in WINDOWS),
        6,
    )
    ev_delta = round(sum(d["expected_value_score"] for d in deltas.values()), 6)
    return {
        "by_window": deltas,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / baseline_ev, 6) if baseline_ev else None,
        "baseline_expected_value_score_sum": baseline_ev,
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6) if baseline_total_pnl else None,
        "ev_windows_improved": sum(1 for d in deltas.values() if d["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for d in deltas.values() if d["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for d in deltas.values() if d["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for d in deltas.values() if d["total_pnl"] < 0),
        "max_drawdown_delta_max": max(d["max_drawdown_pct"] for d in deltas.values()),
        "trade_count_delta_sum": sum(d["trade_count"] for d in deltas.values()),
        "win_rate_delta_min": min(d["win_rate"] for d in deltas.values()),
        "sharpe_daily_delta_max": max(d["sharpe_daily"] for d in deltas.values()),
        "added_trade_count_delta_sum": sum(d["added_trade_count"] for d in deltas.values()),
        "added_trade_pnl_delta_sum": round(sum(d["added_trade_pnl"] for d in deltas.values()), 2),
        "guard_seen_delta_sum": sum(d["guard_seen"] for d in deltas.values()),
        "guard_dropped_delta_sum": sum(d["guard_dropped"] for d in deltas.values()),
        "guard_passed_delta_sum": sum(d["guard_passed"] for d in deltas.values()),
    }


def _passes_gate4(aggregate: dict) -> bool:
    if aggregate["ev_windows_improved"] < 2 or aggregate["ev_windows_regressed"] > 0:
        return False
    if aggregate["expected_value_score_delta_pct"] and aggregate["expected_value_score_delta_pct"] > 0.10:
        return True
    if aggregate["total_pnl_delta_pct"] and aggregate["total_pnl_delta_pct"] > 0.05:
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
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)


def build_payload() -> dict:
    # Use the canonical core watchlist only. data_layer.get_universe() also
    # pulls current open_positions.json, which would leak today's manual
    # holdings into historical fixed-window acceptance tests.
    base_universe = sorted(set(_BASE_WATCHLIST))
    original_sector_map = dict(risk_engine.SECTOR_MAP)
    risk_engine.SECTOR_MAP.update(SECTOR_PATCH)
    try:
        baseline = OrderedDict()
        for label, cfg in WINDOWS.items():
            baseline[label] = _run_window(base_universe, cfg, None)
            m = baseline[label]["metrics"]
            print(
                f"[{label} baseline] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"WR={m['win_rate']} trades={m['trade_count']}"
            )

        variants = OrderedDict()
        for name, variant in VARIANTS.items():
            universe = sorted(set(base_universe) | set(variant["added"]))
            rows = OrderedDict()
            for label, cfg in WINDOWS.items():
                rows[label] = _run_window(universe, cfg, variant)
                m = rows[label]["metrics"]
                print(
                    f"[{label} {name}] EV={m['expected_value_score']} "
                    f"PnL={m['total_pnl']} addedPnL={m['added_trade_pnl']} "
                    f"guard={m['guard_passed']}/{m['guard_seen']}"
                )
            aggregate = _aggregate(baseline, rows)
            variants[name] = {
                "variant": variant,
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
            item[1]["aggregate"]["ev_windows_improved"],
            -item[1]["aggregate"]["ev_windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    accepted = best["passes_gate4"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_candidate" if accepted else "rejected",
        "decision": "accepted_candidate" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "candidate_pool_ai_infra_event_guarded",
        "hypothesis": (
            "AI infrastructure candidates may have theme alpha, but raw promotion "
            "is fragile because event/earnings risk is unmanaged; requiring added "
            "AI infra tickers to be more than 20 trading days from earnings may "
            "preserve theme upside while avoiding event-risk drag."
        ),
        "alpha_hypothesis_category": "candidate_pool_entry_qualification",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain too thin; this tests "
            "an alternate deterministic candidate-pool policy using existing "
            "earnings-distance fields."
        ),
        "parameters": {
            "single_causal_variable": "event-guarded AI infrastructure candidate-pool policy",
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "baseline_universe_source": "filter._BASE_WATCHLIST only, excluding current open_positions",
            "tested_variants": dict(VARIANTS),
            "sector_map_patch": SECTOR_PATCH,
            "locked_variables": [
                "core production universe",
                "existing signal rules",
                "candidate ranking",
                "all sizing rules",
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
        "before_metrics": {label: baseline[label]["metrics"] for label in WINDOWS},
        "after_metrics": {
            name: {label: variant["rows"][label]["metrics"] for label in WINDOWS}
            for name, variant in variants.items()
        },
        "delta_metrics": {
            name: variant["aggregate"] for name, variant in variants.items()
        },
        "best_variant": best_variant,
        "best_variant_gate4": accepted,
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": accepted,
            "run_adapter_changed": accepted,
            "replay_only": False,
            "parity_test_added": accepted,
            "promotion_requirement": (
                "If accepted, implement the AI infra event guard in shared "
                "universe/pilot eligibility code and expose the same guard in run.py."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this avoids that data "
                "constraint rather than weakening LLM."
            ),
        },
        "history_guardrails": {
            "not_raw_ai_infra_watchlist_retry": True,
            "not_simple_bull_gate_retry": True,
            "not_proxy_etf_retry": True,
            "why_not_simple_repeat": (
                "Prior AI infra raw subsets and broad regime gates failed. This "
                "tests a point-in-time event-risk qualification policy tied to "
                "the existing registry requirement that these candidates need an event guard."
            ),
        },
        "rejection_reason": (
            None if accepted else
            "No event-guarded AI infra candidate-pool variant passed fixed-window Gate 4."
        ),
        "next_retry_requires": [
            "Do not retry raw AI infra core-pool promotion without forward evidence.",
            "A valid retry needs production-aligned event/news confirmation or pilot outcome evidence.",
            "If promoted, keep the policy shared between universe eligibility and backtest replay.",
        ],
        "related_files": [
            "quant/experiments/exp_20260502_003_ai_infra_event_guarded_pool.py",
            "data/experiments/exp-20260502-003/ai_infra_event_guarded_pool.json",
            "docs/experiments/logs/exp-20260502-003.json",
            "docs/experiments/tickets/exp-20260502-003.json",
        ],
    }


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    TICKET_JSON.write_text(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Event-guarded AI infra pool",
        "summary": (
            f"Best {payload['best_variant']} "
            f"Gate4={payload['best_variant_gate4']}"
        ),
        "best_variant": payload["best_variant"],
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "production_impact": payload["production_impact"],
    }, indent=2) + "\n", encoding="utf-8")
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")

    best = payload["delta_metrics"][payload["best_variant"]]
    playbook_note = f"""

### 2026-05-02 mechanism update: Event-guarded AI infra pool

Status: {payload["decision"]}.

Core conclusion: `{EXPERIMENT_ID}` tested whether AI infrastructure candidates
should be eligible only when the existing earnings-distance field shows more
than 20 trading days to earnings. This was an event-risk qualification policy,
not another raw AI infra promotion or broad BULL-state switch.

Evidence: best variant `{payload["best_variant"]}` produced aggregate EV delta
`{best["expected_value_score_delta_sum"]:+.4f}` and aggregate PnL delta
`${best["total_pnl_delta_sum"]:,.2f}` / `{best["total_pnl_delta_pct"]:.2%}`;
EV improved in `{best["ev_windows_improved"]}` windows and regressed in
`{best["ev_windows_regressed"]}`.

Mechanism insight: raw AI infra expansion still needs forward/event evidence.
The earnings-distance guard alone is not enough unless it clears the fixed-window
Gate 4 policy and can be shared by production and backtest.

Do not repeat: raw AI infra core-pool promotion, simple BULL-only activation, or
nearby event-distance guard thresholds without new forward or event/news evidence.
"""
    _append_once(PLAYBOOK, f"`{EXPERIMENT_ID}`", playbook_note)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["best_variant"],
        "best_gate4": payload["best_variant_gate4"],
        "best_delta": best,
        "artifact": str(OUT_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
