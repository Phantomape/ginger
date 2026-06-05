"""exp-20260605-031: inverse SEC business-win paper sleeve.

This alpha search reuses the frozen SEC customer-contract/business-win event
source from exp-20260603-012 and tests only the inverse direction. The source
phrases, PIT usable dates, candidate ordering, core strategy, sizing, exits,
and production paths stay unchanged.

The result is replay-only. Even a positive result cannot affect live orders
without a separate short/avoid adapter, borrow/cost review, and parity tests.
No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtester import BacktestEngine  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402

import exp_20260504_034_form4_satellite_overlay as overlay  # noqa: E402
import exp_20260603_012_sec_customer_contract_business_win as direct_source  # noqa: E402


EXP_ID = "exp-20260605-031"
STEM = "sec_business_win_inverse"
TRIAL_FAMILY = "sec_customer_contract_business_win_inverse_candidate_pool"
CHANGED_VARIABLE = "sec_customer_contract_business_win_inverse_paper_source_v1"
RULE_VERSION = CHANGED_VARIABLE
DIRECT_SOURCE_EXP_ID = "exp-20260603-012"
DIRECT_SOURCE_STEM = "sec_customer_contract_business_win"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

INITIAL_CAPITAL = direct_source.INITIAL_CAPITAL
EVENT_NOTIONAL = direct_source.EVENT_NOTIONAL
HOLD_DAYS = direct_source.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = direct_source.MAX_PAPER_TRADES_PER_DAY
MIN_TARGET_TRADES = direct_source.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = direct_source.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = direct_source.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = direct_source.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = direct_source.MAX_POSITIVE_HHI
WINDOWS: OrderedDict[str, dict[str, Any]] = direct_source.WINDOWS

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_inverse_short_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "short_borrow_cost_modeled": False,
    "round_trip_cost_modeled": True,
    "parity_note": (
        "This experiment changes no production code. It replays an inverse "
        "paper sleeve on the frozen exp-20260603-012 SEC text source. A "
        "positive result would still require a default-off short/avoid adapter, "
        "borrow/locate and cost review, and production/backtest parity before "
        "any live order, candidate queue, or daily report behavior could change."
    ),
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _configure_modules() -> None:
    direct_source._configure_overlay_module()
    overlay.WINDOWS = WINDOWS
    overlay.INITIAL_CAPITAL = INITIAL_CAPITAL
    overlay.EVENT_NOTIONAL = EVENT_NOTIONAL
    overlay.HOLD_DAYS = HOLD_DAYS


def _short_trade_from_long(long_trade: dict[str, Any]) -> dict[str, Any]:
    entry_open = float(long_trade["entry_open"])
    exit_close = float(long_trade["exit_close"])
    shares = EVENT_NOTIONAL / entry_open
    gross_return = (entry_open - exit_close) / entry_open
    net_return = gross_return - ROUND_TRIP_COST_PCT
    short_trade = dict(long_trade)
    short_trade.update(
        {
            "strategy": STEM,
            "rule_version": RULE_VERSION,
            "source_experiment_id": DIRECT_SOURCE_EXP_ID,
            "source_strategy": DIRECT_SOURCE_STEM,
            "position_direction": "inverse_short_paper",
            "trade_enabled": False,
            "alters_orders": False,
            "entry_open": round(entry_open, 6),
            "exit_close": round(exit_close, 6),
            "gross_return_pct": round(gross_return * 100.0, 6),
            "net_return_pct": round(net_return * 100.0, 6),
            "notional": EVENT_NOTIONAL,
            "shares": shares,
            "pnl": round(EVENT_NOTIONAL * net_return, 2),
            "long_gross_return_pct": long_trade.get("gross_return_pct"),
            "long_net_return_pct": long_trade.get("net_return_pct"),
            "long_pnl": long_trade.get("pnl"),
            "paper_short_cost_model": (
                "entry_open_to_exit_close_minus_round_trip_cost_no_borrow"
            ),
        }
    )
    return short_trade


def _short_event_equity_curve(
    trades: list[dict[str, Any]],
    *,
    prices: dict[str, list[dict[str, Any]]],
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    days = overlay._trading_days(prices, start, end)
    entries_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exits_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        entries_by_day[str(trade["entry_date"])].append(trade)
        exits_by_day[str(trade["exit_date"])].append(trade)

    realized_pnl = 0.0
    active: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []
    for day in days:
        for trade in entries_by_day.get(day, []):
            active.append(trade)

        exiting = exits_by_day.get(day, [])
        exit_keys = set()
        for trade in exiting:
            realized_pnl += float(trade.get("pnl") or 0.0)
            exit_keys.add((trade["ticker"], trade["entry_date"], trade["exit_date"]))
        if exit_keys:
            active = [
                trade
                for trade in active
                if (trade["ticker"], trade["entry_date"], trade["exit_date"])
                not in exit_keys
            ]

        active_unrealized = 0.0
        for trade in active:
            close = overlay._close_on_or_before(
                prices,
                str(trade["ticker"]),
                day,
            )
            if close is None:
                continue
            active_unrealized += EVENT_NOTIONAL - float(trade["shares"]) * float(close)

        event_pnl = round(realized_pnl + active_unrealized, 2)
        curve.append(
            {
                "date": day,
                "event_equity": round(INITIAL_CAPITAL + event_pnl, 2),
                "event_pnl": event_pnl,
                "active_event_positions": len(active),
            }
        )
    return curve


def _aggregate_metrics(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return direct_source._aggregate_metrics(rows)


def _comparison(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return direct_source._comparison(before, after)


def _target_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return direct_source._target_summary(target_trades_by_window)


def _daily_sharpe_from_combined_curve(metrics: dict[str, Any]) -> dict[str, Any]:
    curve = metrics.get("combined_equity_curve") or []
    returns = []
    for (_, prev), (_, curr) in zip(curve, curve[1:]):
        if float(prev) > 0:
            returns.append(float(curr) / float(prev) - 1.0)
    if len(returns) < 2:
        return {"daily_return_mean": None, "daily_return_stdev": None}
    stdev = statistics.stdev(returns)
    return {
        "daily_return_mean": round(sum(returns) / len(returns), 8),
        "daily_return_stdev": round(stdev, 8),
    }


def _gate4_decision(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    comparison = aggregate["comparison"]
    ev_delta = float(comparison.get("expected_value_score_delta") or 0.0)
    pnl_delta = float(comparison.get("strategy_total_pnl_delta") or 0.0)
    ev_windows_improved = [
        row["label"]
        for row in results
        if float(row["comparison"].get("expected_value_score_delta") or 0.0) > 0.0
    ]
    pnl_windows_improved = [
        row["label"]
        for row in results
        if float(row["comparison"].get("strategy_total_pnl_delta") or 0.0) > 0.0
    ]
    max_drawdown_delta = max(
        float(row["comparison"].get("max_drawdown_delta") or 0.0)
        for row in results
    )
    min_survival_rate = min(
        float(row["after"].get("survival_rate") or 0.0) for row in results
    )
    target_trade_count = int(target_summary["target_trade_count"])

    gates = {
        "aggregate_expected_value_positive": ev_delta > 0.0,
        "aggregate_pnl_positive": pnl_delta > 0.0,
        "all_windows_expected_value_improved": len(ev_windows_improved)
        == len(results),
        "all_windows_pnl_improved": len(pnl_windows_improved) == len(results),
        "target_trade_count_passed": target_trade_count >= MIN_TARGET_TRADES,
        "target_window_count_passed": sum(
            1 for row in results if int(row["target_trade_count"]) > 0
        )
        >= MIN_TARGET_WINDOWS,
        "drawdown_drift_passed": max_drawdown_delta <= MAX_DRAWDOWN_WORSE,
        "survival_floor_passed": min_survival_rate >= 0.05,
        "concentration_guard_passed": (
            float(target_summary["max_single_positive_share"])
            <= MAX_SINGLE_POSITIVE_SHARE
            and float(target_summary["positive_pnl_hhi"]) <= MAX_POSITIVE_HHI
        ),
        "production_impact_safe": not PRODUCTION_IMPACT["trade_enabled"]
        and not PRODUCTION_IMPACT["alters_orders"],
    }
    passed = all(gates.values())
    if passed:
        decision = "positive_inverse_replay_lead_not_promoted_requires_short_cost_parity"
        rationale = (
            "The inverse replay improved aggregate EV and PnL across all "
            "canonical windows while staying inside sample, drawdown, survival, "
            "and concentration guards. It is not retained for production: "
            "short/avoid semantics need a shared default-off adapter, borrow "
            "and cost checks, and parity tests."
        )
        status = "observed_only"
        reflection = (
            "The prior direct-long weakness inverted cleanly on the locked event "
            "source, suggesting the business-win language may be useful as avoid "
            "evidence rather than entry evidence."
        )
    else:
        decision = "rejected_sec_business_win_inverse_no_stable_alpha"
        rationale = (
            "One or more Gate 4 checks failed, so the inverse SEC business-win "
            "paper sleeve is not retained."
        )
        status = "rejected"
        reflection = (
            "A negative direct-long prior was not enough by itself. If this fails, "
            "the likely issue is that the phrase source is a noisy promotional "
            "bucket rather than a stable cross-sectional short/avoid signal."
        )
    return {
        "decision": decision,
        "status": status,
        "passed": passed,
        "rationale": rationale,
        "reflection": reflection,
        "gates": gates,
        "ev_windows_improved": ev_windows_improved,
        "pnl_windows_improved": pnl_windows_improved,
        "max_drawdown_delta": max_drawdown_delta,
        "min_survival_rate": min_survival_rate,
        "requires_parity_before_promotion": passed,
    }


def _window_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            "| {label} | {count} | ${target_pnl:,.2f} | {before_ev:.4f} | {after_ev:.4f} | {ev_delta:+.4f} | ${pnl_delta:+,.2f} | {dd_delta:+.4f} |".format(
                label=row["label"],
                count=row["target_trade_count"],
                target_pnl=float(row["target_trade_pnl_usd"]),
                before_ev=float(row["before"]["expected_value_score"]),
                after_ev=float(row["after"]["expected_value_score"]),
                ev_delta=float(row["comparison"]["expected_value_score_delta"]),
                pnl_delta=float(row["comparison"]["strategy_total_pnl_delta"]),
                dd_delta=float(row["comparison"]["max_drawdown_delta"]),
            )
        )
    return "\n".join(lines)


def _write_card(payload: dict[str, Any]) -> None:
    aggregate = payload["aggregate"]
    comparison = aggregate["comparison"]
    lines = [
        f"# {EXP_ID} SEC Business-Win Inverse Paper Sleeve",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Prior source: `{DIRECT_SOURCE_EXP_ID}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Preflight",
        "",
        payload["preflight"]["alpha_hypothesis"],
        "",
        "## Gate 1-4",
        "",
        _window_table(payload["results"]),
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in payload["gate4"]["gates"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Decision Rationale",
            "",
            payload["gate4"]["rationale"],
            "",
            "## Reflection",
            "",
            payload["gate4"]["reflection"],
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260605_031_sec_business_win_inverse.py"
            ),
        ]
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {"experiment_id": EXP_ID})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    prediction = ticket.get("prediction") or payload.get("prediction") or {}
    actual_success = 1 if payload["gate4"]["passed"] else 0
    if isinstance(prediction, dict):
        prediction.update(
            {
                "actual_success": actual_success,
                "actual_ev_delta": payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ],
                "actual_pnl_delta": payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ],
                "brier_score": round(
                    (
                        float(prediction.get("success_probability") or 0.0)
                        - actual_success
                    )
                    ** 2,
                    6,
                ),
            }
        )
    ticket.update(
        {
            "status": payload["gate4"]["status"],
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "prediction": prediction,
            "artifact": _repo_rel(OUT_JSON),
            "card": _repo_rel(CARD_MD),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "decision": payload["gate4"]["decision"],
                "aggregate_expected_value_delta": payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ],
                "aggregate_strategy_total_pnl_delta": payload["aggregate"][
                    "comparison"
                ]["strategy_total_pnl_delta"],
                "artifact": _repo_rel(OUT_JSON),
                "card": _repo_rel(CARD_MD),
                "log": _repo_rel(LOG_JSON),
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    if not isinstance(registry, dict):
        return
    experiments = registry.setdefault("experiments", [])
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXP_ID:
            item["status"] = payload["gate4"]["status"]
            item["decision"] = payload["gate4"]["decision"]
            item["updated_at"] = payload["completed_at"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["card"] = _repo_rel(CARD_MD)
            item["log"] = _repo_rel(LOG_JSON)
            item["aggregate_expected_value_delta"] = payload["aggregate"][
                "comparison"
            ]["expected_value_score_delta"]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"][
                "comparison"
            ]["strategy_total_pnl_delta"]
            break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    prediction = dict(payload.get("prediction") or {})
    prediction.update(
        {
            "actual_success": actual_success,
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "brier_score": round(
                (
                    float(prediction.get("success_probability") or 0.0)
                    - actual_success
                )
                ** 2,
                6,
            ),
        }
    )
    return {
        "experiment_id": EXP_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "trial_family": TRIAL_FAMILY,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(
            payload["gate4"]["requires_parity_before_promotion"]
        ),
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"][
                "expected_value_score"
            ],
            "aggregate_expected_value_after": payload["aggregate"]["after"][
                "expected_value_score"
            ],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"][
                "strategy_total_pnl"
            ],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"][
                "strategy_total_pnl"
            ],
            "aggregate_strategy_total_pnl_delta": comparison[
                "strategy_total_pnl_delta"
            ],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"][
                "target_trade_pnl_usd"
            ],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"][
                "max_single_positive_share"
            ],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"][
                    "expected_value_score_delta"
                ],
                "strategy_total_pnl_delta": row["comparison"][
                    "strategy_total_pnl_delta"
                ],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "prediction": prediction,
        "reflection": payload["gate4"]["reflection"],
        "next_action": payload["next_action"],
    }


def _append_experiment_log(record: dict[str, Any]) -> None:
    compact = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not EXPERIMENT_LOG.exists():
        EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")
        return
    lines = EXPERIMENT_LOG.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines()
    lines = [
        line
        for line in lines
        if f'"experiment_id":"{EXP_ID}"' not in line
        and f'"experiment_id": "{EXP_ID}"' not in line
    ]
    lines.append(compact)
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON, {"experiment_id": EXP_ID})
    if not isinstance(manifest, dict):
        manifest = {"experiment_id": EXP_ID}
    file_paths = {
        "runner": Path(__file__),
        "data": OUT_JSON,
        "before_aggregate": BEFORE_JSON,
        "after_aggregate": AFTER_JSON,
        "log": LOG_JSON,
        "ticket": TICKET_JSON,
        "card": CARD_MD,
    }
    files = manifest.setdefault("files", {})
    for key, path in file_paths.items():
        files[key] = {
            "path": _repo_rel(path),
            "exists": path.exists(),
            "sha256": _sha256(path),
        }
    manifest.update(
        {
            "completed_at": payload["completed_at"],
            "generated_at": payload["completed_at"],
            "result_decision": payload["gate4"]["decision"],
            "result_status": payload["gate4"]["status"],
            "aggregate_expected_value_delta": payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ],
            "aggregate_strategy_total_pnl_delta": payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ],
        }
    )
    _write_json(MANIFEST_JSON, manifest)


def build_payload() -> dict[str, Any]:
    _configure_modules()
    completed_at = _utc_now()
    universe = get_universe()
    prices = overlay._load_price_map()
    events, data_audit = direct_source._load_candidate_events()
    priced_candidates = direct_source._price_candidates(events, prices)

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    event_details: dict[str, dict[str, Any]] = {}
    target_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    core_run_audit: dict[str, dict[str, Any]] = {}

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        selected_long, skipped = direct_source._select_event_trades(
            priced_candidates,
            start=window["start"],
            end=window["end"],
        )
        selected = [_short_trade_from_long(trade) for trade in selected_long]
        target_trades_by_window[label] = selected
        event_curve = _short_event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before = overlay._core_metrics(result)
        after = overlay._combined_metrics(result, event_curve, selected)
        before_metrics[label] = before
        after_metrics[label] = after
        comp = {
            "expected_value_score_delta": round(
                float(after.get("expected_value_score") or 0.0)
                - float(before.get("expected_value_score") or 0.0),
                4,
            ),
            "strategy_total_pnl_delta": round(
                float(after.get("total_pnl") or 0.0)
                - float(before.get("total_pnl") or 0.0),
                2,
            ),
            "max_drawdown_delta": round(
                float(after.get("max_drawdown_pct") or 0.0)
                - float(before.get("max_drawdown_pct") or 0.0),
                6,
            ),
        }
        scoped_count = sum(
            1
            for row in priced_candidates
            if window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
        )
        price_ready_count = sum(
            1
            for row in priced_candidates
            if row.get("status") == "price_ready"
            and window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
        )
        results.append(
            {
                "label": label,
                "window": window,
                "before": before,
                "after": after,
                "comparison": comp,
                "target_trade_count": len(selected),
                "target_trade_pnl_usd": round(
                    sum(float(trade.get("pnl") or 0.0) for trade in selected),
                    2,
                ),
                "return_diagnostics": _daily_sharpe_from_combined_curve(after),
            }
        )
        event_details[label] = {
            "candidate_count": scoped_count,
            "price_ready_count": price_ready_count,
            "selected_trade_count": len(selected),
            "skipped_count": len(skipped),
            "skip_reasons": dict(
                sorted(Counter(row["reason"] for row in skipped).items())
            ),
            "selected_trades": selected,
            "skipped_candidates": skipped[:100],
            "event_equity_curve": event_curve,
        }
        core_run_audit[label] = {
            "converged": bool((result.get("convergence") or {}).get("converged")),
            "known_biases": result.get("known_biases"),
            "signals_generated": result.get("signals_generated"),
            "signals_survived": result.get("signals_survived"),
            "survival_rate": result.get("survival_rate"),
        }

    before_aggregate = _aggregate_metrics(before_metrics)
    after_aggregate = _aggregate_metrics(after_metrics)
    aggregate = {
        "before": before_aggregate,
        "after": after_aggregate,
        "comparison": _comparison(before_aggregate, after_aggregate),
    }
    target_summary = _target_summary(target_trades_by_window)
    gate4 = _gate4_decision(aggregate, results, target_summary)
    prediction = {
        "success_probability": 0.22,
        "expected_ev_delta": 0.12,
        "expected_pnl_delta": 900.0,
        "main_failure_modes": [
            "short_cost_unmodeled",
            "window_regression",
            "semantic_false_positive",
            "thin_sample",
            "concentration_failed",
        ],
        "confidence_reason": (
            "The prior direct long business-win replay was negative in all "
            "windows, but inverse short/avoid semantics may still be too small "
            "or too costly for production."
        ),
        "recorded_at": "2026-06-05T19:15:35Z",
    }

    return {
        "experiment_id": EXP_ID,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "trial_family": TRIAL_FAMILY,
        "changed_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "preflight": {
            "alpha_hypothesis": (
                "SEC customer-contract/business-win 8-K language may be a "
                "negative alpha/avoid signal. The prior direct-long replay was "
                "negative across all canonical windows, so this run tests the "
                "same PIT source as an inverse default-off paper sleeve."
            ),
            "category": "candidate_pool / risk_allocation / inverse_avoid",
            "playbook_alignment": (
                "Uses a free, production-visible SEC text context layer and "
                "tests candidate-pool direction rather than LLM soft-ranking, "
                "state-surface threshold retunes, or already-frozen ticker noise."
            ),
            "nearby_prior_experiments": {
                DIRECT_SOURCE_EXP_ID: (
                    "Direct-long SEC customer-contract/business-win candidate "
                    "pool; rejected with negative aggregate EV/PnL across the "
                    "same three windows."
                )
            },
            "single_causal_variable": CHANGED_VARIABLE,
            "acceptance_criteria": {
                "canonical_windows": list(WINDOWS.keys()),
                "aggregate_expected_value_delta": "> 0",
                "aggregate_pnl_delta": "> 0",
                "per_window_expected_value_delta": "3 of 3 windows > 0",
                "per_window_pnl_delta": "3 of 3 windows > 0",
                "minimum_target_trades": MIN_TARGET_TRADES,
                "minimum_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_drift": MAX_DRAWDOWN_WORSE,
                "survival_rate_floor": 0.05,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi_max": MAX_POSITIVE_HHI,
            },
        },
        "parameters": {
            "sec_text_path": _repo_rel(direct_source.SEC_TEXT_PATH),
            "source_experiment_id": DIRECT_SOURCE_EXP_ID,
            "source_business_win_patterns_locked": list(
                direct_source.BUSINESS_WIN_PATTERNS
            ),
            "source_exclusion_patterns_locked": list(
                direct_source.EXCLUSION_PATTERNS
            ),
            "source_excluded_language_bucket": direct_source.NEGATIVE_LANGUAGE_BUCKET,
            "event_notional": EVENT_NOTIONAL,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "borrow_or_locate_cost_pct": None,
            "initial_capital": INITIAL_CAPITAL,
            "selection_order": (
                "locked from exp-20260603-012: entry_date asc, "
                "candidate_selection_score desc, business_win_hits desc, ticker asc"
            ),
            "inverse_return_formula": (
                "(entry_open - exit_close) / entry_open - round_trip_cost_pct"
            ),
        },
        "data_availability": data_audit,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "results": results,
        "aggregate": aggregate,
        "target_summary": target_summary,
        "gate4": gate4,
        "event_candidate_details": event_details,
        "core_run_audit": core_run_audit,
        "prediction": prediction,
        "production_impact": PRODUCTION_IMPACT,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "note": (
                "LLM soft-ranking data remains sparse, so this run uses a "
                "deterministic free-data SEC text field."
            ),
        },
        "next_action": (
            "If treated as a lead, first build a default-off short/avoid adapter "
            "with borrow/cost modeling and production/backtest parity; otherwise "
            "move to a different free-data candidate-pool mechanism."
        )
        if gate4["passed"]
        else (
            "Do not retune nearby SEC business-win phrases on this sample; move "
            "to a different free-data candidate-pool mechanism."
        ),
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, payload["aggregate"]["before"])
    _write_json(AFTER_JSON, payload["aggregate"]["after"])
    _write_json(LOG_JSON, payload)
    _write_card(payload)
    _update_ticket(payload)
    _update_registry(payload)
    _append_experiment_log(_experiment_log_record(payload))
    _update_manifest(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": payload["target_summary"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
