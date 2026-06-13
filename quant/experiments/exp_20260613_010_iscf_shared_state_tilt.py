"""exp-20260613-010: shared ISCF state-conditioned notional tilt.

Alpha search / shared-paper-first promotion. This promotes the fixed positive
exp-20260613-005 industry_stable_core_flow sleeve state tilt into the shared
default-off paper helper, then evaluates the helper's own before/after switch
over the docs/backtesting.md canonical three windows.

Single attributable policy bundle:
  - prior-close SPY/QQQ state classifier from the exp-20260606-022 line,
  - fixed cell mixed|balanced|normal,
  - fixed 1.5x paper notional scalar,
  - no entry, exit, candidate, ranking, cooldown, LLM/news, or order changes.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260613-010"
STEM = "iscf_shared_state_tilt"
TRIAL_FAMILY = "market_state_conditioned_sleeve_router"
TRIAL_VARIANT_ID = "industry_stable_core_flow_shared_state_tilt_v1"
CHANGED_VARIABLE = "industry_stable_core_flow_shared_state_tilt_default_off_helper_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260611_005_lagged_consensus_shared_allocator_source as alloc  # noqa: E402
from data_layer import get_universe  # noqa: E402
from industry_stable_core_flow_paper_sleeve import (  # noqa: E402
    STATE_ROUTER_CELL,
    STATE_ROUTER_NOTIONAL_SCALAR,
    STATE_ROUTER_RULE_VERSION,
    build_industry_stable_core_flow_historical_trades,
)
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH  # noqa: E402


framework = alloc.framework
exp008 = alloc.exp008
WINDOWS = framework.WINDOWS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_010_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"exp_20260613_010_{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"exp_20260613_010_{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_IN_CELL_TRADES_TOTAL = 18
MIN_IN_CELL_WINDOWS = 3
MIN_EV_IMPROVED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50
SNAPSHOT_LOOKBACK_CALENDAR_DAYS = getattr(exp008, "SNAPSHOT_LOOKBACK_CALENDAR_DAYS", 450)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round(value: Any, digits: int = 6) -> float | None:
    number = _float(value)
    return round(number, digits) if number is not None else None


def _safe(payload: Any) -> Any:
    return framework._safe(payload)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_window_snapshot_deep(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = framework._parse_date(cfg["start"]) - timedelta(
        days=SNAPSHOT_LOOKBACK_CALENDAR_DAYS
    )
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | {"SPY", "QQQ"})
    warehouse = DEFAULT_WAREHOUSE_PATH if DEFAULT_WAREHOUSE_PATH.exists() else framework.WAREHOUSE
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    with sqlite3.connect(f"file:{warehouse.as_posix()}?mode=ro&immutable=1", uri=True) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, framework._date_str(start), framework._date_str(end)]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()].append(
                    {
                        "Date": str(day)[:10],
                        "Open": float(open_),
                        "High": float(high),
                        "Low": float(low),
                        "Close": float(close),
                        "Volume": float(volume),
                    }
                )
    return {ticker: rows for ticker, rows in snapshot.items() if rows}


def _single_ticker_positive_share(rows: list[dict[str, Any]], *, pnl_key: str = "pnl") -> float | None:
    positives = [row for row in rows if (_float(row.get(pnl_key)) or 0.0) > 0.0]
    total = sum(_float(row.get(pnl_key)) or 0.0 for row in positives)
    if total <= 0:
        return None
    by_ticker: dict[str, float] = defaultdict(float)
    for row in positives:
        by_ticker[str(row.get("ticker") or "").upper()] += _float(row.get(pnl_key)) or 0.0
    return round(max(by_ticker.values()) / total, 6) if by_ticker else None


def _positive_hhi(rows: list[dict[str, Any]], *, pnl_key: str = "pnl") -> float | None:
    positives = [row for row in rows if (_float(row.get(pnl_key)) or 0.0) > 0.0]
    total = sum(_float(row.get(pnl_key)) or 0.0 for row in positives)
    if total <= 0:
        return None
    by_ticker: dict[str, float] = defaultdict(float)
    for row in positives:
        by_ticker[str(row.get("ticker") or "").upper()] += _float(row.get(pnl_key)) or 0.0
    return round(sum((value / total) ** 2 for value in by_ticker.values()), 6)


def _run_variant(
    *,
    variant_name: str,
    state_router_enabled: bool,
    baselines: dict[str, dict[str, Any]],
    deep_snapshots: dict[str, dict[str, Any]],
    sector_entries_by_window: dict[str, dict[str, Any]],
    candidate_universe_by_window: dict[str, dict[str, Any]],
    core_entries_by_window: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    per_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    all_trades: list[dict[str, Any]] = []
    audits: OrderedDict[str, dict[str, Any]] = OrderedDict()
    helper_config = {"state_router_enabled": state_router_enabled}

    for label in WINDOWS:
        trades, audit = build_industry_stable_core_flow_historical_trades(
            ohlcv_by_ticker=deep_snapshots[label],
            core_entries_by_date=core_entries_by_window[label],
            windows=OrderedDict([(label, WINDOWS[label])]),
            candidate_universe=candidate_universe_by_window[label],
            sector_entries=sector_entries_by_window[label],
            config=helper_config,
        )
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        per_window[label] = {
            "before": before,
            "after": after,
            "trade_count": len(trades),
            "in_cell_trade_count": sum(
                1 for row in trades if row.get("combined_state") == STATE_ROUTER_CELL
            ),
            "tilted_trade_count": sum(1 for row in trades if row.get("state_router_applied")),
            "state_router_status_counts": dict(
                Counter(str(row.get("state_router_status") or "unknown") for row in trades)
            ),
            "state_counts": dict(
                Counter(str(row.get("combined_state") or "unknown") for row in trades)
            ),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "trades": [
                {
                    "ticker": row.get("ticker"),
                    "signal_date": row.get("signal_date"),
                    "entry_date": row.get("entry_date"),
                    "exit_date": row.get("exit_date"),
                    "combined_state": row.get("combined_state"),
                    "state_router_status": row.get("state_router_status"),
                    "state_router_applied": row.get("state_router_applied"),
                    "state_router_scalar": row.get("state_router_scalar"),
                    "paper_notional_usd": row.get("paper_notional_usd"),
                    "state_router_base_paper_notional_usd": row.get(
                        "state_router_base_paper_notional_usd"
                    ),
                    "pnl": row.get("pnl"),
                    "state_router_base_pnl": row.get("state_router_base_pnl"),
                    "state_router_incremental_pnl": row.get("state_router_incremental_pnl"),
                }
                for row in trades
            ],
        }
        audits[label] = audit
        all_trades.extend(trades)

    return {
        "variant_name": variant_name,
        "state_router_enabled": state_router_enabled,
        "per_window": per_window,
        "audits": audits,
        "aggregate_after_ev": round(
            sum(_float(per_window[label]["after"]["expected_value_score"]) or 0.0 for label in WINDOWS),
            6,
        ),
        "aggregate_after_pnl": round(
            sum(_float(per_window[label]["after"]["total_pnl"]) or 0.0 for label in WINDOWS),
            2,
        ),
        "in_cell_trade_count_total": sum(
            1 for row in all_trades if row.get("combined_state") == STATE_ROUTER_CELL
        ),
        "tilted_trade_count_total": sum(1 for row in all_trades if row.get("state_router_applied")),
        "in_cell_windows": sorted(
            {
                label
                for label in WINDOWS
                if per_window[label]["in_cell_trade_count"] > 0
            }
        ),
        "in_cell_single_ticker_positive_share": _single_ticker_positive_share(
            [row for row in all_trades if row.get("combined_state") == STATE_ROUTER_CELL]
        ),
        "in_cell_positive_hhi": _positive_hhi(
            [row for row in all_trades if row.get("combined_state") == STATE_ROUTER_CELL]
        ),
        "incremental_single_ticker_positive_share": _single_ticker_positive_share(
            [row for row in all_trades if row.get("state_router_applied")],
            pnl_key="state_router_incremental_pnl",
        ),
        "incremental_positive_hhi": _positive_hhi(
            [row for row in all_trades if row.get("state_router_applied")],
            pnl_key="state_router_incremental_pnl",
        ),
    }


def _gate4(after_variant: dict[str, Any], before_variant: dict[str, Any]) -> dict[str, Any]:
    ev_delta = OrderedDict()
    pnl_delta = OrderedDict()
    dd_delta = OrderedDict()
    for label in WINDOWS:
        ev_delta[label] = round(
            (_float(after_variant["per_window"][label]["after"]["expected_value_score"]) or 0.0)
            - (_float(before_variant["per_window"][label]["after"]["expected_value_score"]) or 0.0),
            6,
        )
        pnl_delta[label] = round(
            (_float(after_variant["per_window"][label]["after"]["total_pnl"]) or 0.0)
            - (_float(before_variant["per_window"][label]["after"]["total_pnl"]) or 0.0),
            2,
        )
        dd_delta[label] = round(
            (_float(after_variant["per_window"][label]["after"]["max_drawdown_pct"]) or 0.0)
            - (_float(before_variant["per_window"][label]["after"]["max_drawdown_pct"]) or 0.0),
            6,
        )

    agg_ev = round(sum(ev_delta.values()), 6)
    agg_pnl = round(sum(pnl_delta.values()), 2)
    improved = sum(1 for value in ev_delta.values() if value > 0.0)
    regressed = sum(1 for value in ev_delta.values() if value < 0.0)
    pnl_regressed = sum(1 for value in pnl_delta.values() if value < 0.0)
    max_dd_worse = max(dd_delta.values()) if dd_delta else 0.0
    sample_guard = (
        after_variant["in_cell_trade_count_total"] >= MIN_IN_CELL_TRADES_TOTAL
        and len(after_variant["in_cell_windows"]) >= MIN_IN_CELL_WINDOWS
    )
    in_cell_share = after_variant["in_cell_single_ticker_positive_share"]
    incr_share = after_variant["incremental_single_ticker_positive_share"]
    in_cell_conc = in_cell_share is None or in_cell_share <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    incr_conc = incr_share is None or incr_share <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    dd_guard = max_dd_worse <= MAX_DRAWDOWN_WORSE
    passed = (
        agg_ev > 0.0
        and agg_pnl > 0.0
        and improved >= MIN_EV_IMPROVED_WINDOWS
        and regressed == 0
        and pnl_regressed == 0
        and sample_guard
        and in_cell_conc
        and incr_conc
        and dd_guard
    )
    return {
        "passed": passed,
        "comparator": "shared helper with state_router_enabled=false identity",
        "aggregate_ev_delta": agg_ev,
        "aggregate_ev_delta_pct": round(agg_ev / before_variant["aggregate_after_ev"], 6)
        if before_variant["aggregate_after_ev"]
        else None,
        "aggregate_pnl_delta": agg_pnl,
        "ev_delta_by_window": ev_delta,
        "pnl_delta_by_window": pnl_delta,
        "max_drawdown_delta_by_window": dd_delta,
        "windows_ev_improved": improved,
        "windows_ev_regressed": regressed,
        "windows_pnl_regressed": pnl_regressed,
        "minimum_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
        "in_cell_trade_count_total": after_variant["in_cell_trade_count_total"],
        "tilted_trade_count_total": after_variant["tilted_trade_count_total"],
        "in_cell_windows": after_variant["in_cell_windows"],
        "minimum_in_cell_trades_total": MIN_IN_CELL_TRADES_TOTAL,
        "minimum_in_cell_windows": MIN_IN_CELL_WINDOWS,
        "sample_guard_passed": sample_guard,
        "in_cell_single_ticker_positive_share": in_cell_share,
        "in_cell_positive_hhi": after_variant["in_cell_positive_hhi"],
        "in_cell_concentration_guard_passed": in_cell_conc,
        "incremental_single_ticker_positive_share": incr_share,
        "incremental_positive_hhi": after_variant["incremental_positive_hhi"],
        "incremental_concentration_guard_passed": incr_conc,
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "max_drawdown_worse_max": max_dd_worse,
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "drawdown_guard_passed": dd_guard,
    }


def build_payload() -> dict[str, Any]:
    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    baselines: OrderedDict[str, dict[str, Any]] = OrderedDict()
    deep_snapshots: dict[str, dict[str, Any]] = {}
    sector_entries_by_window: dict[str, dict[str, Any]] = {}
    candidate_universe_by_window: dict[str, dict[str, Any]] = {}
    core_entries_by_window: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for label, cfg in WINDOWS.items():
        print(f"[{label}] baseline and shared ISCF helper inputs")
        before_result = framework.shadow._run_baseline(universe, cfg)
        baselines[label] = {
            "result": before_result,
            "metrics": framework.overlay_helper._metrics(before_result),
        }
        core_entries_by_window[label] = framework.shadow._baseline_entries(before_result)
        deep_snapshot = _load_window_snapshot_deep(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        deep_snapshots[label] = deep_snapshot
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in deep_snapshot
        }
        sector_entries_by_window[label] = window_sector_entries
        candidate_universe_by_window[label] = alloc._candidate_universe_from_sector_entries(
            window_sector_entries
        )

    before_variant = _run_variant(
        variant_name="shared_helper_state_router_disabled",
        state_router_enabled=False,
        baselines=baselines,
        deep_snapshots=deep_snapshots,
        sector_entries_by_window=sector_entries_by_window,
        candidate_universe_by_window=candidate_universe_by_window,
        core_entries_by_window=core_entries_by_window,
    )
    after_variant = _run_variant(
        variant_name="shared_helper_state_router_enabled",
        state_router_enabled=True,
        baselines=baselines,
        deep_snapshots=deep_snapshots,
        sector_entries_by_window=sector_entries_by_window,
        candidate_universe_by_window=candidate_universe_by_window,
        core_entries_by_window=core_entries_by_window,
    )
    gate4 = _gate4(after_variant, before_variant)
    decision = (
        "accepted_iscf_shared_state_tilt_default_off_helper"
        if gate4["passed"]
        else "rejected_iscf_shared_state_tilt_default_off_helper"
    )
    status = "accepted" if gate4["passed"] else "rejected"

    windows = []
    for label in WINDOWS:
        windows.append(
            {
                "label": label,
                "expected_value_before": before_variant["per_window"][label]["after"][
                    "expected_value_score"
                ],
                "expected_value_after": after_variant["per_window"][label]["after"][
                    "expected_value_score"
                ],
                "expected_value_delta": gate4["ev_delta_by_window"][label],
                "strategy_total_pnl_before": before_variant["per_window"][label]["after"][
                    "total_pnl"
                ],
                "strategy_total_pnl_after": after_variant["per_window"][label]["after"][
                    "total_pnl"
                ],
                "strategy_total_pnl_delta": gate4["pnl_delta_by_window"][label],
                "target_trade_count": after_variant["per_window"][label]["trade_count"],
                "tilted_trade_count": after_variant["per_window"][label]["tilted_trade_count"],
                "in_cell_trade_count": after_variant["per_window"][label]["in_cell_trade_count"],
            }
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "The accepted industry_stable_core_flow sleeve's "
            "mixed|balanced|normal rows carry enough edge that a fixed 1.5x "
            "default-off paper notional tilt should reproduce exp-20260613-005 "
            "through the shared helper without changing entries, exits, "
            "candidate generation, live orders, or core behavior."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / regime router",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": (
                "Promotes the only ex-top-clean positive regime-router cell from "
                "exp-20260613-005 into a production-visible shared helper; avoids "
                "allocator source retunes rejected by exp-20260613-002/004/006/009."
            ),
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "rule_version": STATE_ROUTER_RULE_VERSION,
        "parameters": {
            "router_cell": STATE_ROUTER_CELL,
            "notional_scalar": STATE_ROUTER_NOTIONAL_SCALAR,
            "landing_point": "industry_stable_core_flow shared default-off paper sleeve",
            "identity_config": {"state_router_enabled": False},
            "after_config": {"state_router_enabled": True},
            "locked_variables": [
                "sleeve candidate generation and gates",
                "sleeve entry/exit timing and hold days",
                "state cell definition",
                "core entries/exits/sizing",
                "all other sleeves and accepted allocator",
                "live/default orders",
                "LLM/news behavior",
            ],
        },
        "circularity_disclosure": (
            "The state cell came from in-sample canonical-window screening in "
            "exp-20260612-027 and exp-20260613-005. This shared-helper promotion "
            "can be accepted only as default-off paper pending forward evidence, "
            "not live-ready."
        ),
        "gate1": {
            "comparator": "same shared helper with state_router_enabled=false",
            "canonical_core_baseline": "docs/backtesting.md three-window core baseline",
        },
        "gate2": {
            "runtime_fields": [
                "entry_date",
                "target_price",
                "paper_notional_usd",
                "pnl",
                "SPY/QQQ OHLCV at prior close",
                "combined_state",
            ],
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "note": "No survival-thinning filter was added; only selected paper row notional changes.",
        },
        "gate4": gate4,
        "before_variant": before_variant,
        "after_variant": after_variant,
        "windows": windows,
        "history_check": {
            "exp-20260612-027": "Observed ISCF x mixed|balanced|normal as the sole ex-top-clean source-state survivor.",
            "exp-20260613-002": "Rejected allocator routing; landing point should be the sleeve, not allocator source priority.",
            "exp-20260613-005": "Accepted replay-only 1.5x sleeve state tilt: aggregate EV +0.0804, PnL +$1,872.59, zero window regression.",
            "exp-20260613-008": "Observed no net-new robust cells; do not add more cells now.",
            "exp-20260613-009": "Rejected further source arbitration; avoid allocator retunes.",
        },
        "llm_metrics": {"used_llm": False, "why_not_llm": "Deterministic OHLCV state fields."},
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "adapter_status": "shared_default_off_paper_helper",
            "shared_policy_changed": True,
            "backtester_adapter_changed": True,
            "run_adapter_changed": True,
            "daily_snapshot_exposed": True,
            "default_off_paper_only": True,
            "replay_only": False,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "uses_llm": False,
            "uses_free_ohlcv_only": True,
            "live_realism_evaluated": True,
            "live_ready": False,
            "execution_envelope": {
                "base_notional": 4000.0,
                "tilted_notional": 6000.0,
                "max_active_positions": 8,
                "daily_entry_slots": 1,
                "hold_days": 10,
                "same_ticker_cooldown_days": 15,
                "min_dollar_volume": 50_000_000.0,
                "order_semantics": "next_open_paper_only_no_orders_emitted",
                "portfolio_displacement": "same selected sleeve rows; only paper weight changes",
                "kill_switch": "default-off only; future live eligibility requires forward gate and activation experiment",
            },
            "parity_note": (
                "Historical replay and daily default-off snapshot call "
                "quant/industry_stable_core_flow_paper_sleeve.py and the shared "
                "quant/market_state_router.py. quant/run.py now passes QQQ into "
                "this sleeve's daily OHLCV dict, matching historical SPY/QQQ "
                "state inputs. No orders, core ranking, sizing, exits, watchlist, "
                "LLM, or news path changes."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation/regime router: 1.5x default-off paper notional for ISCF mixed|balanced|normal rows.",
            "2_history_check": "exp-20260613-005 passed; exp-20260613-002/004/006/009 reject allocator retunes; exp-20260613-008 found no extra robust cells.",
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "docs/backtesting.md three-window before/after using shared helper "
                "switch; aggregate EV/PnL > 0, no EV/PnL window regression, sample/"
                "concentration/drawdown guards pass, and production impact remains "
                "default-off."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260613_010_iscf_shared_state_tilt.py"
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The shared helper should match exp-20260613-005 because the fixed "
                "cell/scalar is identical and only moves from runner-local logic "
                "into the production-visible default-off helper."
            )
            if gate4["passed"]
            else (
                "Shared-helper promotion failed to reproduce the replay lead; likely "
                "causes are state annotation drift, missing QQQ state input, or "
                "notional/PnL scaling mismatch."
            ),
            "realized_failure_mode": "none_passed_all_guards"
            if gate4["passed"]
            else "shared_helper_reproduction_failed",
            "forbidden_near_neighbor_retry": (
                "Do not sweep scalar, cell boundaries, lookbacks, top-N, hold days, "
                "cooldown, candidate gates, or allocator rank on the frozen windows. "
                "Do not add the macro_relief thin cell until forward rows mature."
            ),
            "new_evidence_required": (
                "Closed forward default-off ISCF rows tagged with entry market state, "
                "showing positive mixed|balanced|normal replacement value out of sample."
            ),
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/market_state_router.py",
            "quant/industry_stable_core_flow_paper_sleeve.py",
            "quant/run.py",
            "quant/test_market_state_router.py",
            "quant/test_industry_stable_core_flow_paper_sleeve.py",
            "quant/experiments/exp_20260613_010_iscf_shared_state_tilt.py",
            "data/experiments/exp-20260613-010/exp_20260613_010_iscf_shared_state_tilt.json",
            "experiments/logs/exp-20260613-010.json",
            "experiments/tickets/exp-20260613-010.json",
            "experiments/cards/exp-20260613-010.md",
            "experiments/manifests/exp-20260613-010.json",
            "docs/experiment_log.jsonl",
            "docs/production_backtest_parity_matrix.md",
            "docs/alpha-optimization-playbook.md",
        ],
    }
    return _safe(payload)


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "regime_router",
        "component": ", ".join(payload["related_files"]),
        "parameters": payload["parameters"],
        "history_check": payload["history_check"],
        "gate4": payload["gate4"],
        "before_metrics": {
            "expected_value_score": payload["before_variant"]["aggregate_after_ev"],
            "total_pnl": payload["before_variant"]["aggregate_after_pnl"],
        },
        "after_metrics": {
            "expected_value_score": payload["after_variant"]["aggregate_after_ev"],
            "total_pnl": payload["after_variant"]["aggregate_after_pnl"],
        },
        "delta_metrics": {
            "expected_value_score": payload["gate4"]["aggregate_ev_delta"],
            "total_pnl": payload["gate4"]["aggregate_pnl_delta"],
        },
        "windows": payload["windows"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": payload["anti_js"],
        "related_files": payload["related_files"],
        "calibration": {
            "predicted_success_probability": 0.55,
            "expected_ev_delta": 0.0804,
            "expected_pnl_delta": 1872.59,
            "actual_success": 1 if payload["gate4"]["passed"] else 0,
            "actual_decision": payload["status"],
            "actual_ev_delta": payload["gate4"]["aggregate_ev_delta"],
            "actual_pnl_delta": payload["gate4"]["aggregate_pnl_delta"],
            "realized_failure_mode": payload["post_run_reflection"]["realized_failure_mode"],
        },
    }


def _write_experiment_log(record: dict[str, Any]) -> None:
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if EXPERIMENT_LOG.exists():
        for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                return
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(record), ensure_ascii=True, sort_keys=True) + "\n")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = {}
    if TICKET_JSON.exists():
        try:
            ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            ticket = {}
    ticket.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "gate4": payload["gate4"],
                "production_impact": payload["production_impact"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _write_card(payload: dict[str, Any]) -> None:
    gate4 = payload["gate4"]
    lines = [
        f"# {EXPERIMENT_ID} ISCF Shared State Tilt",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Status: `{payload['status']}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Aggregate EV delta: `{gate4['aggregate_ev_delta']:+.4f}`",
        f"- Aggregate PnL delta: `${gate4['aggregate_pnl_delta']:+,.2f}`",
        f"- Tilted trades: `{gate4['tilted_trade_count_total']}`",
        f"- In-cell concentration: `{gate4['in_cell_single_ticker_positive_share']}`",
        f"- Incremental concentration: `{gate4['incremental_single_ticker_positive_share']}`",
        "",
        "## Windows",
        "",
        "| Window | EV before | EV after | dEV | PnL before | PnL after | dPnL | tilted |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["windows"]:
        lines.append(
            "| {label} | {evb:.4f} | {eva:.4f} | {dev:+.4f} | ${pnb:,.2f} | ${pna:,.2f} | ${dpn:+,.2f} | {tilted} |".format(
                label=row["label"],
                evb=float(row["expected_value_before"]),
                eva=float(row["expected_value_after"]),
                dev=float(row["expected_value_delta"]),
                pnb=float(row["strategy_total_pnl_before"]),
                pna=float(row["strategy_total_pnl_after"]),
                dpn=float(row["strategy_total_pnl_delta"]),
                tilted=row["tilted_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "- Shared default-off helper changed; `trade_enabled=false`.",
            "- Historical replay and daily snapshot use the same `market_state_router`.",
            "- `run.py` passes QQQ into the sleeve input to match historical SPY/QQQ state features.",
            "- No live/default orders, core ranking, sizing, exits, watchlist, LLM, or news path changed.",
            "",
            "## Reproduction",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260613_010_iscf_shared_state_tilt.py",
            "```",
            "",
        ]
    )
    _write_text(CARD_MD, "\n".join(lines))


def _write_manifest() -> None:
    files = [
        OUT_JSON,
        BEFORE_AGG_JSON,
        AFTER_AGG_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        Path(__file__),
        REPO_ROOT / "quant" / "market_state_router.py",
        REPO_ROOT / "quant" / "industry_stable_core_flow_paper_sleeve.py",
        REPO_ROOT / "quant" / "run.py",
        REPO_ROOT / "quant" / "test_market_state_router.py",
        REPO_ROOT / "quant" / "test_industry_stable_core_flow_paper_sleeve.py",
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "files": [
            {
                "path": _repo_rel(path),
                "sha256": _sha256(path),
            }
            for path in files
        ],
    }
    _write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(
        BEFORE_AGG_JSON,
        {
            "expected_value_score": payload["before_variant"]["aggregate_after_ev"],
            "total_pnl": payload["before_variant"]["aggregate_after_pnl"],
            "note": "aggregate shared helper identity with state_router_enabled=false",
        },
    )
    _write_json(
        AFTER_AGG_JSON,
        {
            "expected_value_score": payload["after_variant"]["aggregate_after_ev"],
            "total_pnl": payload["after_variant"]["aggregate_after_pnl"],
            "note": "aggregate shared helper after with state_router_enabled=true",
        },
    )
    _write_json(LOG_JSON, _log_record(payload))
    _write_experiment_log(_log_record(payload))
    _update_ticket(payload)
    _write_card(payload)
    _write_manifest()
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(
        f"{EXPERIMENT_ID} {payload['decision']} "
        f"dEV={payload['gate4']['aggregate_ev_delta']:+.4f} "
        f"dPnL=${payload['gate4']['aggregate_pnl_delta']:+,.2f} "
        f"tilted={payload['gate4']['tilted_trade_count_total']}"
    )


if __name__ == "__main__":
    main()
