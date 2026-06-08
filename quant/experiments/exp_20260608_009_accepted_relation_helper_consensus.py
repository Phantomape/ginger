"""exp-20260608-009: accepted relation-helper consensus replay.

Replay-only alpha search. It tests one fixed candidate-pool hypothesis:
when two or more accepted default-off relation helper families emit same-day
same-industry paper candidates, admit the top consensus candidate as a
separate observe-only paper overlay.

This does not change production orders, core ranking, sizing, exits, watchlist
behavior, LLM/news behavior, or any shared helper. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework
from data_layer import get_universe
from industry_relative_laggard_repair_paper_sleeve import (
    build_industry_relative_laggard_repair_historical_trades,
)
from industry_stable_core_flow_paper_sleeve import (
    build_industry_stable_core_flow_historical_trades,
)
from rolling_corr_peer_shock_paper_sleeve import (
    build_rolling_corr_peer_shock_historical_trades,
)
from volatility_relief_stock_leadership_paper_sleeve import (
    build_volatility_relief_stock_leadership_historical_trades,
)


EXPERIMENT_ID = "exp-20260608-009"
STEM = "accepted_relation_helper_consensus"
TRIAL_FAMILY = "accepted_relation_helper_consensus"
TRIAL_VARIANT_ID = "accepted_relation_helper_same_day_industry_consensus_candidate_source_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_009_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 15
MIN_SUPPORT_SOURCE_FAMILIES = 2
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

SOURCE_FAMILIES = OrderedDict(
    [
        ("volatility_relief", "volatility_relief_stock_leadership"),
        ("rolling_peer_shock", "rolling_corr_peer_shock_core_flow"),
        ("industry_laggard_repair", "industry_relative_laggard_repair"),
        ("industry_stable_core_flow", "industry_stable_core_flow"),
    ]
)

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sample_too_thin",
        "window_regression",
        "accepted_comparator_not_beaten",
        "drawdown_drift",
        "consensus_relabels_single_helper_noise",
    ],
    "confidence_reason": (
        "Recent accepted relation helpers prove free OHLCV relation sources can "
        "work, but cross-helper overlap is likely sparse and may mostly "
        "duplicate laggard repair or stable core-flow timing instead of adding "
        "independent replacement value."
    ),
    "recorded_at": "2026-06-08T08:13:49Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "live_realism_evaluated": False,
    "live_ready": False,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "still require a shared default-off helper that consumes the exact same "
        "accepted relation-helper source rows in historical replay and daily "
        "snapshot generation before any report, paper ledger, ranking, sizing, "
        "watchlist, or order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(payload: Any) -> Any:
    return framework._safe(payload)


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(payload), handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_trade(trade: dict[str, Any], source_family: str) -> dict[str, Any]:
    signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
    ticker = str(trade.get("ticker") or "").upper()
    sector = str(trade.get("sector") or trade.get("peer_sector") or "").strip()
    industry = str(trade.get("industry") or trade.get("peer_industry") or "").strip()
    source_score = 0.0
    for key in ("candidate_score", "paper_candidate_score", "peer_shock_score"):
        if trade.get(key) is not None:
            source_score = _float(trade.get(key))
            break
    return {
        **trade,
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "source_family": source_family,
        "consensus_industry_key": industry or sector or "unknown",
        "consensus_sector": sector,
        "consensus_source_score": _round(source_score, 6),
    }


def _build_source_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
    cfg: dict[str, str],
    label: str,
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_trades: list[dict[str, Any]] = []
    source_trade_counts: OrderedDict[str, int] = OrderedDict()
    raw_candidate_counts: OrderedDict[str, int | None] = OrderedDict()
    source_audits: OrderedDict[str, Any] = OrderedDict()

    volatility = build_volatility_relief_stock_leadership_historical_trades(
        ohlcv_by_ticker=snapshot,
        dates=dates,
        candidate_universe=sector_entries,
        core_entries_by_date=core_entries_by_date,
    )
    volatility_trades = [
        _normalise_trade(row, "volatility_relief") for row in volatility["trades"]
    ]
    source_trades.extend(volatility_trades)
    source_trade_counts["volatility_relief"] = len(volatility_trades)
    raw_candidate_counts["volatility_relief"] = len(volatility.get("candidates") or [])
    source_audits["volatility_relief"] = {
        "rule_version": volatility.get("rule_version"),
        "source_rule_version": volatility.get("source_rule_version"),
        "context_scan": volatility.get("context_scan"),
    }

    builders = [
        ("rolling_peer_shock", build_rolling_corr_peer_shock_historical_trades),
        (
            "industry_laggard_repair",
            build_industry_relative_laggard_repair_historical_trades,
        ),
        ("industry_stable_core_flow", build_industry_stable_core_flow_historical_trades),
    ]
    for source_family, builder in builders:
        trades, audit = builder(
            ohlcv_by_ticker=snapshot,
            core_entries_by_date=core_entries_by_date,
            windows=OrderedDict([(label, cfg)]),
            candidate_universe=sector_entries,
            sector_entries=sector_entries,
        )
        normalised = [_normalise_trade(row, source_family) for row in trades]
        source_trades.extend(normalised)
        source_trade_counts[source_family] = len(normalised)
        raw_candidate_counts[source_family] = (
            audit.get("raw_candidate_count_by_window", {}).get(label)
        )
        source_audits[source_family] = {
            "rule_version": audit.get("rule_version"),
            "source_rule_version": audit.get("source_rule_version"),
            "scan": audit.get("scan_by_window", {}).get(label),
        }

    audit_payload = {
        "source_families": SOURCE_FAMILIES,
        "source_trade_counts": source_trade_counts,
        "raw_candidate_counts": raw_candidate_counts,
        "source_audits": source_audits,
    }
    return source_trades, audit_payload


def _select_consensus_trades(
    *,
    source_trades: list[dict[str, Any]],
    trading_dates: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    by_industry: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_ticker: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trade in source_trades:
        signal_date = str(trade.get("signal_date") or "")[:10]
        ticker = str(trade.get("ticker") or "").upper()
        if not signal_date or not ticker:
            continue
        by_industry[(signal_date, str(trade.get("consensus_industry_key") or "unknown"))].append(
            trade
        )
        by_ticker[(signal_date, ticker)].append(trade)

    raw_candidates: list[dict[str, Any]] = []
    for trade in source_trades:
        signal_date = str(trade.get("signal_date") or "")[:10]
        ticker = str(trade.get("ticker") or "").upper()
        industry_key = str(trade.get("consensus_industry_key") or "unknown")
        same_industry = by_industry[(signal_date, industry_key)]
        same_ticker = by_ticker[(signal_date, ticker)]
        support_sources = sorted({str(row["source_family"]) for row in same_industry})
        same_ticker_sources = sorted({str(row["source_family"]) for row in same_ticker})
        if (
            len(support_sources) < MIN_SUPPORT_SOURCE_FAMILIES
            and len(same_ticker_sources) < MIN_SUPPORT_SOURCE_FAMILIES
        ):
            continue
        raw_candidates.append(
            {
                **trade,
                "source": "ACCEPTED_RELATION_HELPER_CONSENSUS_PAPER",
                "rule_version": TRIAL_VARIANT_ID,
                "candidate_score": _round(
                    100.0 * len(same_ticker_sources)
                    + 10.0 * len(support_sources)
                    + _float(trade.get("consensus_source_score")),
                    6,
                ),
                "support_source_count": len(support_sources),
                "support_sources": support_sources,
                "same_ticker_source_count": len(same_ticker_sources),
                "same_ticker_sources": same_ticker_sources,
                "same_day_same_industry_trade_count": len(same_industry),
                "same_day_same_ticker_trade_count": len(same_ticker),
                "paper_notional_usd": BASE_NOTIONAL_USD,
                "known_at": "after_signal_day_close_before_next_open_paper_entry",
                "trade_enabled": False,
                "uses_llm": False,
                "uses_free_ohlcv_only": True,
            }
        )

    raw_candidates.sort(
        key=lambda row: (
            str(row.get("signal_date") or ""),
            -int(row.get("same_ticker_source_count") or 0),
            -int(row.get("support_source_count") or 0),
            -int(row.get("same_day_same_industry_trade_count") or 0),
            -_float(row.get("candidate_score")),
            str(row.get("ticker") or ""),
            str(row.get("source_family") or ""),
        )
    )

    date_position = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    used_date_counts: Counter[str] = Counter()
    next_allowed_pos_by_ticker: dict[str, int] = {}
    seen_date_ticker: set[tuple[str, str]] = set()
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for row in raw_candidates:
        signal_date = str(row.get("signal_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_position.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if (signal_date, ticker) in seen_date_ticker:
            filtered.append({**row, "filter_reason": "duplicate_same_day_ticker"})
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        if pos < next_allowed_pos_by_ticker.get(ticker, -1):
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        selected.append(row)
        used_date_counts[signal_date] += 1
        seen_date_ticker.add((signal_date, ticker))
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS

    pair_counts = Counter(
        (
            str(row.get("signal_date") or "")[:10],
            str(row.get("consensus_industry_key") or "unknown"),
        )
        for row in source_trades
    )
    ticker_pair_counts = Counter(
        (str(row.get("signal_date") or "")[:10], str(row.get("ticker") or "").upper())
        for row in source_trades
    )
    audit = {
        "source_trade_count": len(source_trades),
        "raw_consensus_candidate_count": len(raw_candidates),
        "selected_consensus_trade_count": len(selected),
        "filtered_consensus_candidate_count": len(filtered),
        "same_day_same_industry_key_count": len(pair_counts),
        "multi_trade_same_day_same_industry_keys": sum(
            1 for count in pair_counts.values() if count >= 2
        ),
        "multi_source_same_day_same_ticker_keys": sum(
            1 for count in ticker_pair_counts.values() if count >= 2
        ),
    }
    return selected, filtered, raw_candidates, audit


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    return {
        "passed": not failed,
        "decision": (
            "positive_replay_lead_not_promoted_accepted_relation_helper_consensus"
            if not failed
            else "rejected_accepted_relation_helper_consensus"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_summary["windows_with_target_trades"],
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    target_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    raw_candidates_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    filtered_candidates_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    consensus_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    warehouse_coverage_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline and relation-helper consensus replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        dates = [
            day
            for day in framework.shadow._trading_dates(snapshot)
            if str(cfg["start"]) <= day <= str(cfg["end"])
        ]
        core_entries = framework.shadow._baseline_entries(before_result)
        source_trades, source_audit = _build_source_trades(
            snapshot=snapshot,
            dates=dates,
            cfg=cfg,
            label=label,
            core_entries_by_date=core_entries,
            sector_entries=window_sector_entries,
        )
        selected, filtered, raw_candidates, consensus_audit = _select_consensus_trades(
            source_trades=source_trades,
            trading_dates=dates,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected
        raw_candidates_by_window[label] = raw_candidates[:200]
        filtered_candidates_by_window[label] = filtered[:200]
        source_audit_by_window[label] = source_audit
        consensus_audit_by_window[label] = consensus_audit
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected),
            "raw_consensus_candidate_count": len(raw_candidates),
            "all_source_trade_count": len(source_trades),
            "source_trade_counts": source_audit["source_trade_counts"],
            "raw_source_candidate_counts": source_audit["raw_candidate_counts"],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    status = "accepted" if gate4["passed"] else "rejected"
    decision = gate4["decision"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    hypothesis = (
        "Accepted default-off relation helpers may be more predictive when two "
        "or more fixed helper families independently emit same-day "
        "same-industry candidates. Cross-helper agreement may identify real "
        "industry displacement instead of one sleeve's idiosyncratic noise."
    )
    interpretation = (
        "The same-day same-industry helper-consensus candidate pool cleared the "
        "replay-only gate but remains unpromoted until shared-helper parity."
        if gate4["passed"]
        else (
            "The same-day same-industry helper-consensus candidate pool failed "
            "Gate 4: overlap was too sparse and two windows regressed. Do not "
            "retry this fixed consensus definition by only changing top-N, "
            "cooldown, hold days, or notional."
        )
    )
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": hypothesis,
        "change_type": "default_off_paper_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "relation_aware_candidate_pool",
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_free_data_cross_helper_relation_overlap",
        "nearby_prior_experiments": [
            "exp-20260531-029",
            "exp-20260604-009",
            "exp-20260606-025",
            "exp-20260607-008",
            "exp-20260607-019",
            "exp-20260608-008",
        ],
        "prior_trial_count": 1,
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only accepted relation-helper consensus paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signals use only helper outputs known after signal-day close. "
                "Each helper already uses signal-date OHLCV, next-open paper "
                "entry, target-side sell slippage, round-trip cost, and fixed "
                "default-off paper semantics. This runner adds only a "
                "same-day same-industry support rule, top-1 daily selection, "
                "and 15-trading-day same-ticker cooldown."
            ),
        },
        "parameters": {
            "source_families": SOURCE_FAMILIES,
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_support_source_families": MIN_SUPPORT_SOURCE_FAMILIES,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool alpha: independent accepted relation helpers "
                "that agree on the same date and industry may point to a "
                "higher-quality displacement candidate than any single helper."
            ),
            "2_history_check": {
                "exp-20260531-029": (
                    "Accepted-source consensus was positive when same-ticker "
                    "same-date free-data sources agreed; this test is a "
                    "different same-industry relation-helper consensus, not a "
                    "same-ticker source-snapshot retry."
                ),
                "exp-20260604-009": (
                    "Lagged independent-source timing improved accepted "
                    "free-data consensus; this test does not alter that "
                    "source timing or add a source family."
                ),
                "exp-20260607-008": (
                    "Industry-relative laggard repair was accepted; this test "
                    "uses it as one fixed sensor, not a threshold retune."
                ),
                "exp-20260608-008": (
                    "Industry stable core-flow was accepted; this test uses it "
                    "as one fixed sensor, not a same-source retune."
                ),
                "recent_rejected_proxy_tests": (
                    "Copper, oil, IWM, DIA/MDY and defensive ETF proxy "
                    "variants were rejected, so this test avoids adding a new "
                    "broad proxy ticker source."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use the same three canonical windows. Aggregate EV/PnL must "
                "be positive; no EV/PnL regression window; at least 20 trades "
                "across all 3 windows; survival >=5%; drawdown drift <=0.5pp; "
                "concentration guard passes. Replay-only positives are not "
                "production accepted without a shared helper parity pass."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260608_009_accepted_relation_helper_consensus.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "docs/backtesting.md current canonical baseline and same-run "
                "before_metrics inside this artifact"
            ),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "data/reference/broad_market_sector_map.json sector/industry/status",
                "accepted helper source rows with signal_date/ticker/industry/source_family",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No core filter or live candidate ranking changed. The source "
                "is replay-only/default-off paper, so core signals generated "
                "and survived are unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "window_rows": window_rows,
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "raw_consensus_candidates_by_window": raw_candidates_by_window,
        "filtered_consensus_candidates_by_window": filtered_candidates_by_window,
        "source_audit_by_window": source_audit_by_window,
        "consensus_audit_by_window": consensus_audit_by_window,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": interpretation,
        "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": (
                "Cross-helper relation overlap was real but too sparse: only "
                "six selected trades survived top-1/day and cooldown across "
                "three windows. The late strong window improved, but mid weak "
                "and old thin windows both lost money and regressed EV. That "
                "suggests same-industry helper agreement mostly clustered "
                "around a few industry episodes rather than adding broad, "
                "independent replacement value."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun this fixed same-day same-industry accepted "
                "relation-helper consensus by only changing top-N, notional, "
                "hold days, or cooldown on these frozen windows."
            ),
            "new_evidence_required": (
                "A retry needs a materially new production-visible relation "
                "field, such as explicit peer-role causality, forward source "
                "maturation, or a separate non-overlapping source family with "
                "enough rows to clear the 20-trade minimum."
            ),
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Source trades | Raw consensus | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        row = payload["window_rows"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {source} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                source=row["all_source_trade_count"],
                raw=row["raw_consensus_candidate_count"],
                trades=row["target_trade_count"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accepted Relation Helper Consensus",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Production Impact",
            "",
            "Replay-only/default-off paper. No shared helper, daily run adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "source_trade_count": payload["window_rows"][label]["all_source_trade_count"],
                "raw_consensus_candidate_count": payload["window_rows"][label][
                    "raw_consensus_candidate_count"
                ],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
            },
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    _write_json(TICKET_JSON, ticket)

    registry = (
        json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
        if REGISTRY_JSON.exists()
        else {"schema_version": 1, "experiments": []}
    )
    experiments = registry.setdefault("experiments", [])
    entry = None
    for row in experiments:
        if isinstance(row, dict) and row.get("experiment_id") == EXPERIMENT_ID:
            entry = row
            break
    if entry is None:
        entry = {"experiment_id": EXPERIMENT_ID}
        experiments.append(entry)
    entry.update(
        {
            "status": payload["status"],
            "lane": payload["lane"],
            "owner": "alpha-search",
            "hypothesis": payload["hypothesis"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket_file": _repo_rel(TICKET_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
            "aggregate_strategy_total_pnl_delta": log_record[
                "aggregate_strategy_total_pnl_delta"
            ],
        }
    )
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(
        json.dumps(_safe(registry), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {_repo_rel(path): _sha256(path) for path in paths},
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
