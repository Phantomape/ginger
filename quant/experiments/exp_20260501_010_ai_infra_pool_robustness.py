"""exp-20260501-010 AI infrastructure pool robustness audit.

Alpha search. Audit the user-supplied AI infrastructure candidate-pool
expansion with leave-one-out, leave-theme-out, and refined sub-pool tests.
This intentionally stays shadow-only: it changes only test universe membership
and does not promote a production watchlist, ranking, sizing, or exit rule.
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
from data_layer import get_universe  # noqa: E402
import risk_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260501-010"
SOURCE_EXPERIMENT_ID = "exp-20260501-008"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "ai_infra_pool_robustness.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

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

ALL_ADDED = [
    "APLD",
    "BE",
    "CIFR",
    "COHR",
    "CORZ",
    "DBRG",
    "INTC",
    "IREN",
    "LITE",
    "MARA",
    "RIOT",
    "TLN",
    "VST",
    "WULF",
]

THEMES = {
    "power_energy": ["BE", "TLN", "VST"],
    "datacenter_infra": ["APLD", "DBRG"],
    "optical": ["LITE", "COHR"],
    "bitcoin_miners": ["CORZ", "IREN", "CIFR", "WULF", "RIOT", "MARA"],
    "storage_semis": ["INTC"],
}

VARIANTS = OrderedDict([
    ("add_all_user_tradeable", ALL_ADDED),
    ("all_minus_intc", [t for t in ALL_ADDED if t != "INTC"]),
    ("all_minus_lite", [t for t in ALL_ADDED if t != "LITE"]),
    ("all_minus_be", [t for t in ALL_ADDED if t != "BE"]),
    ("all_minus_top3_intc_lite_be", [
        t for t in ALL_ADDED if t not in {"INTC", "LITE", "BE"}
    ]),
    ("all_minus_optical", [
        t for t in ALL_ADDED if t not in set(THEMES["optical"])
    ]),
    ("all_minus_power_energy", [
        t for t in ALL_ADDED if t not in set(THEMES["power_energy"])
    ]),
    ("all_minus_datacenter_infra", [
        t for t in ALL_ADDED if t not in set(THEMES["datacenter_infra"])
    ]),
    ("all_minus_bitcoin_miners", [
        t for t in ALL_ADDED if t not in set(THEMES["bitcoin_miners"])
    ]),
    ("all_minus_storage_semis", [
        t for t in ALL_ADDED if t not in set(THEMES["storage_semis"])
    ]),
    ("focused_top3_intc_lite_be", ["INTC", "LITE", "BE"]),
    ("optical_plus_intc", ["LITE", "COHR", "INTC"]),
    ("clean_no_dbrg_tln_vst", [
        t for t in ALL_ADDED if t not in {"DBRG", "TLN", "VST"}
    ]),
])

SECTOR_PATCH = {
    "BE": "Energy",
    "TLN": "Energy",
    "VST": "Energy",
    "APLD": "Technology",
    "DBRG": "Real Estate",
    "LITE": "Technology",
    "COHR": "Technology",
    "CORZ": "Financials",
    "IREN": "Financials",
    "CIFR": "Financials",
    "WULF": "Financials",
    "RIOT": "Financials",
    "MARA": "Financials",
    "SNDK": "Technology",
    "INTC": "Technology",
    "CRDO": "Technology",
}

BASELINE = {
    "late_strong": {
        "expected_value_score": 2.7000,
        "sharpe_daily": 4.30,
        "total_pnl": 62788.03,
        "total_return_pct": 0.6279,
        "max_drawdown_pct": 0.0439,
        "win_rate": 0.7895,
        "trade_count": 19,
        "survival_rate": 0.8039,
        "tail_loss_share": 0.5045,
    },
    "mid_weak": {
        "expected_value_score": 1.2036,
        "sharpe_daily": 2.58,
        "total_pnl": 46654.10,
        "total_return_pct": 0.4665,
        "max_drawdown_pct": 0.0799,
        "win_rate": 0.5238,
        "trade_count": 21,
        "survival_rate": 0.7925,
        "tail_loss_share": 0.4839,
    },
    "old_thin": {
        "expected_value_score": 0.2563,
        "sharpe_daily": 1.27,
        "total_pnl": 20181.65,
        "total_return_pct": 0.2018,
        "max_drawdown_pct": 0.0688,
        "win_rate": 0.4091,
        "trade_count": 22,
        "survival_rate": 0.9167,
        "tail_loss_share": 0.4234,
    },
}


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_val in before.items():
        after_val = after.get(key)
        out[key] = (
            round(after_val - before_val, 6)
            if isinstance(after_val, (int, float))
            and isinstance(before_val, (int, float))
            else None
        )
    return out


def _pnl_quality(trades: list[dict]) -> dict:
    pnls = [float(t.get("pnl") or 0.0) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    avg_win = sum(wins) / len(wins) if wins else None
    avg_loss = sum(losses) / len(losses) if losses else None
    payoff_ratio = (
        avg_win / abs(avg_loss)
        if avg_win is not None and avg_loss not in (None, 0)
        else None
    )
    return {
        "trade_count": len(trades),
        "win_count": len(wins),
        "loss_count": len(losses),
        "avg_win_pnl": round(avg_win, 2) if avg_win is not None else None,
        "avg_loss_pnl": round(avg_loss, 2) if avg_loss is not None else None,
        "payoff_ratio": round(payoff_ratio, 4) if payoff_ratio is not None else None,
    }


def _candidate_trade_summary(result: dict, added: set[str]) -> dict:
    trades = [t for t in result.get("trades", []) if t.get("ticker") in added]
    by_ticker = {}
    for trade in trades:
        ticker = trade.get("ticker")
        rec = by_ticker.setdefault(ticker, {"trades": 0, "pnl": 0.0, "wins": 0})
        rec["trades"] += 1
        rec["pnl"] += float(trade.get("pnl") or 0.0)
        if (trade.get("pnl") or 0) > 0:
            rec["wins"] += 1
    for rec in by_ticker.values():
        rec["pnl"] = round(rec["pnl"], 2)
        rec["win_rate"] = (
            round(rec["wins"] / rec["trades"], 4) if rec["trades"] else None
        )
    return {
        "candidate_trade_count": len(trades),
        "candidate_pnl": round(sum(float(t.get("pnl") or 0.0) for t in trades), 2),
        "candidate_payoff": _pnl_quality(trades),
        "by_ticker": by_ticker,
    }


def _run_window(universe: list[str], window: dict) -> dict:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    )
    return engine.run()


def _aggregate_rows(variant_rows: list[dict]) -> dict:
    pnl_delta_sum = round(sum(r["delta"]["total_pnl"] for r in variant_rows), 2)
    baseline_pnl_sum = round(
        sum(BASELINE[r["window"]]["total_pnl"] for r in variant_rows), 2
    )
    candidate_pnl_sum = round(
        sum(r["candidate_trades"]["candidate_pnl"] for r in variant_rows), 2
    )
    interaction_pnl_sum = round(pnl_delta_sum - candidate_pnl_sum, 2)
    return {
        "expected_value_score_delta_sum": round(
            sum(r["delta"]["expected_value_score"] for r in variant_rows), 4
        ),
        "total_pnl_delta_sum": pnl_delta_sum,
        "baseline_total_pnl_sum": baseline_pnl_sum,
        "total_pnl_delta_pct": (
            round(pnl_delta_sum / baseline_pnl_sum, 6) if baseline_pnl_sum else None
        ),
        "ev_windows_improved": sum(
            1 for r in variant_rows if r["delta"]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for r in variant_rows if r["delta"]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for r in variant_rows if r["delta"]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for r in variant_rows if r["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": round(
            max(r["delta"]["max_drawdown_pct"] for r in variant_rows), 6
        ),
        "trade_count_delta_sum": sum(r["delta"]["trade_count"] for r in variant_rows),
        "win_rate_delta_min": round(
            min(r["delta"]["win_rate"] for r in variant_rows), 6
        ),
        "candidate_trade_count_sum": sum(
            r["candidate_trades"]["candidate_trade_count"] for r in variant_rows
        ),
        "candidate_pnl_sum": candidate_pnl_sum,
        "interaction_pnl_sum": interaction_pnl_sum,
    }


def _ranked(summary: dict) -> list[dict]:
    ranked = []
    for name, rec in summary.items():
        agg = rec["aggregate"]
        ranked.append({
            "variant": name,
            "added": rec["added"],
            "ev_delta_sum": agg["expected_value_score_delta_sum"],
            "pnl_delta_sum": agg["total_pnl_delta_sum"],
            "candidate_pnl_sum": agg["candidate_pnl_sum"],
            "interaction_pnl_sum": agg["interaction_pnl_sum"],
            "ev_windows_improved": agg["ev_windows_improved"],
            "ev_windows_regressed": agg["ev_windows_regressed"],
            "pnl_windows_improved": agg["pnl_windows_improved"],
            "max_drawdown_delta_max": agg["max_drawdown_delta_max"],
            "win_rate_delta_min": agg["win_rate_delta_min"],
            "candidate_trade_count_sum": agg["candidate_trade_count_sum"],
        })
    return sorted(
        ranked,
        key=lambda r: (
            r["ev_windows_improved"] - r["ev_windows_regressed"],
            r["ev_delta_sum"],
            r["pnl_delta_sum"],
        ),
        reverse=True,
    )


def _append_once(path: Path, marker: str, text: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker not in existing:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)

    baseline_universe = sorted(get_universe())
    original_sector_map = dict(risk_engine.SECTOR_MAP)
    risk_engine.SECTOR_MAP.update(SECTOR_PATCH)

    rows = []
    summary = {}
    try:
        for variant, added in VARIANTS.items():
            universe = sorted(set(baseline_universe) | set(added))
            variant_rows = []
            for label, window in WINDOWS.items():
                result = _run_window(universe, window)
                if "error" in result:
                    raise RuntimeError(
                        f"{variant} {label} failed: {result['error']}"
                    )
                metrics = _metrics(result)
                delta = _delta(metrics, BASELINE[label])
                candidate_trades = _candidate_trade_summary(result, set(added))
                row = {
                    "window": label,
                    "variant": variant,
                    "added": added,
                    "metrics": metrics,
                    "delta": delta,
                    "candidate_trades": candidate_trades,
                    "all_trade_payoff": _pnl_quality(result.get("trades", [])),
                    "interaction_pnl": round(
                        delta["total_pnl"] - candidate_trades["candidate_pnl"], 2
                    ),
                }
                rows.append(row)
                variant_rows.append(row)

            summary[variant] = {
                "added": added,
                "by_window": {
                    r["window"]: {
                        "before": BASELINE[r["window"]],
                        "after": r["metrics"],
                        "delta": r["delta"],
                        "candidate_trades": r["candidate_trades"],
                        "interaction_pnl": r["interaction_pnl"],
                        "all_trade_payoff": r["all_trade_payoff"],
                    }
                    for r in variant_rows
                },
                "aggregate": _aggregate_rows(variant_rows),
            }
    finally:
        risk_engine.SECTOR_MAP.clear()
        risk_engine.SECTOR_MAP.update(original_sector_map)

    ranked = _ranked(summary)
    best_variant = ranked[0]["variant"]
    best = summary[best_variant]["aggregate"]
    all_bundle = summary["add_all_user_tradeable"]["aggregate"]

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "rejected",
        "decision": "rejected",
        "lane": "alpha_search",
        "change_type": "ai_infra_universe_robustness_audit",
        "hypothesis": (
            "The AI infrastructure expansion should be retained only if "
            "leave-one-out and theme-level tests show stable cross-window EV "
            "rather than dependence on a few AI/power/crypto beta winners."
        ),
        "alpha_hypothesis_category": "candidate_universe",
        "parameters": {
            "single_causal_variable": "tradeable universe membership",
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "all_added": ALL_ADDED,
            "themes": THEMES,
            "tested_variants": VARIANTS,
            "sector_map_patch": SECTOR_PATCH,
            "short_history_observation": {
                "CRDO": "already in accepted universe",
                "SNDK": (
                    "has partial cached rows but remains short-history for the "
                    "three fixed-window acceptance frame"
                ),
                "CRWV": (
                    "treat as short-history listed watch candidate if data is "
                    "added later; not included in this fixed-window audit"
                ),
            },
            "locked_variables": [
                "signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "position caps",
                "portfolio heat",
                "add-ons",
                "exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": BASELINE,
        "after_metrics": summary,
        "ranking": ranked,
        "best_variant": best_variant,
        "best_variant_gate4_passed": False,
        "gate4_basis": (
            "Rejected for production promotion: the best variants are still "
            "too concentrated in a few names/windows, while old_thin or "
            "late drawdown/low trade-count fragility remains."
        ),
        "robustness_findings": {
            "all_bundle_total_pnl_delta": all_bundle["total_pnl_delta_sum"],
            "all_bundle_candidate_pnl": all_bundle["candidate_pnl_sum"],
            "all_bundle_interaction_pnl": all_bundle["interaction_pnl_sum"],
            "best_variant_total_pnl_delta": best["total_pnl_delta_sum"],
            "best_variant_candidate_pnl": best["candidate_pnl_sum"],
            "best_variant_interaction_pnl": best["interaction_pnl_sum"],
            "top_contributor_concentration_tested": [
                "all_minus_intc",
                "all_minus_lite",
                "all_minus_be",
                "all_minus_top3_intc_lite_be",
            ],
            "theme_leave_out_tested": [
                "all_minus_optical",
                "all_minus_power_energy",
                "all_minus_datacenter_infra",
                "all_minus_bitcoin_miners",
                "all_minus_storage_semis",
            ],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If a future refined pool is accepted, add tickers and sector "
                "tags to production watchlist/sector map and rerun canonical "
                "three-window backtests."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this avoids that "
                "constraint by auditing deterministic universe membership."
            ),
        },
        "history_guardrails": {
            "builds_on_exp_20260501_008": True,
            "builds_on_exp_20260501_009": True,
            "not_minimal_be_intc_repeat": True,
            "why_not_simple_repeat": (
                "This does not test another direct promotion subset. It audits "
                "concentration, theme beta dependence, and interaction PnL."
            ),
        },
        "rejection_reason": (
            "The audit supports AI infrastructure as a research pool, but not "
            "as a production watchlist promotion. Evidence remains sparse and "
            "concentrated, with beta/theme dependence and interaction effects."
        ),
        "next_retry_requires": [
            "Forward evidence or an event/news discriminator for BE old-tape risk.",
            "A separate short-history scout for CRWV and SNDK.",
            "A theme-level rule that preserves optical/semi upside without "
            "blindly adding negative power/infra names.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260501_010_ai_infra_pool_robustness.py",
        ],
    }

    for path in (OUT_JSON, LOG_JSON, TICKET_JSON):
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    jsonl_record = {
        key: payload[key]
        for key in [
            "experiment_id",
            "timestamp",
            "status",
            "decision",
            "lane",
            "change_type",
            "hypothesis",
            "alpha_hypothesis_category",
            "parameters",
            "date_range",
            "market_regime_summary",
            "before_metrics",
            "best_variant",
            "gate4_basis",
            "production_impact",
            "llm_metrics",
            "history_guardrails",
            "rejection_reason",
            "next_retry_requires",
            "related_files",
        ]
    }
    jsonl_record["after_metrics"] = {
        name: rec["aggregate"] for name, rec in summary.items()
    }
    jsonl_record["robustness_findings"] = payload["robustness_findings"]
    _append_once(
        EXPERIMENT_LOG,
        f'"experiment_id": "{EXPERIMENT_ID}"',
        json.dumps(jsonl_record, ensure_ascii=False) + "\n",
    )

    playbook_text = f"""

### 2026-05-01 mechanism update: AI infra pool robustness audit

Status: rejected for production promotion; retained as research pool.

Core conclusion: `{EXPERIMENT_ID}` audited the user-supplied AI infrastructure
candidate expansion with leave-one-out, leave-theme-out, and refined-pool
variants. The prior all-name result is real enough to keep researching, but it
does not justify a raw production watchlist addition.

Evidence: best ranked variant `{best_variant}` produced aggregate PnL delta
`${best['total_pnl_delta_sum']:,.2f}` and aggregate EV delta
`{best['expected_value_score_delta_sum']:+.4f}`, but the evidence remains
concentrated and sparse. The original all-name bundle's aggregate PnL delta
was `${all_bundle['total_pnl_delta_sum']:,.2f}`, split into direct candidate
PnL `${all_bundle['candidate_pnl_sum']:,.2f}` and interaction PnL
`${all_bundle['interaction_pnl_sum']:,.2f}`. That confirms the expansion
changed incumbent ranking/capital competition, not only added clean standalone
new-name alpha.

Mechanism insight: AI infrastructure individual names are a valuable research
source, especially optical/semi/power winners, but current evidence is still
too close to theme beta plus a few winner paths. Bitcoin miners remain inert
under the current A/B rules, and short-history names such as CRWV/SNDK need a
separate scout rather than being mixed into the fixed-window acceptance test.

Do not repeat: promoting the full AI infra list, promoting `BE + INTC`, or
using aggregate PnL alone to override old-window EV fragility, low trade count,
or concentration.

Next valid retry requires: forward evidence, an event/news discriminator, or a
theme-level production rule that explains when the fragile power/infra names
should be inactive while preserving optical/semi upside.
"""
    _append_once(PLAYBOOK, f"`{EXPERIMENT_ID}`", playbook_text)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "best_variant": best_variant,
        "best_aggregate": best,
        "all_bundle_aggregate": all_bundle,
        "decision": payload["decision"],
        "top_5_ranked": ranked[:5],
    }, indent=2))


if __name__ == "__main__":
    main()
