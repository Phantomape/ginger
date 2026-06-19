"""exp-20260619-004: inventory component-mix sell-through scout.

Replay-only alpha search. The single decision hypothesis is that raw SEC
Companyfacts inventory component mix can separate true sell-through from the
rejected total-inventory and DIO signals: finished-goods share should fall
year over year while raw-material/work-in-process support remains, then liquid
SPY-relative price confirmation tests whether demand is visible before the
next-open paper entry.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily helper reproduces it. No JavaScript
is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260616_003_raw_sec_rd_intensity_candidate_pool as rd
import exp_20260616_022_quarterly_inventory_dio_turnover_improvement as q


base = q.base

EXPERIMENT_ID = "exp-20260619-004"
STEM = "inventory_component_mix_sellthrough"
TRIAL_FAMILY = "inventory_component_mix_sellthrough_candidate_pool"
TRIAL_VARIANT_ID = "inventory_component_mix_sellthrough_top1_next_open_10d_v1"
CHANGED_VARIABLE = "inventory_component_mix_sellthrough_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260619_004_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

TOTAL_INVENTORY_TAGS = ("InventoryNet",)
FINISHED_GOODS_TAGS = (
    "InventoryFinishedGoodsNetOfReserves",
    "InventoryFinishedGoods",
)
RAW_MATERIAL_TAGS = (
    "InventoryRawMaterialsNetOfReserves",
    "InventoryRawMaterials",
    "InventoryRawMaterialsAndSuppliesNetOfReserves",
    "InventoryRawMaterialsAndSupplies",
    "InventoryRawMaterialsAndPurchasedPartsNetOfReserves",
)
WORK_IN_PROCESS_TAGS = (
    "InventoryWorkInProcessNetOfReserves",
    "InventoryWorkInProcess",
)
COMPONENT_TAG_GROUPS = {
    "total": TOTAL_INVENTORY_TAGS,
    "finished_goods": FINISHED_GOODS_TAGS,
    "raw_materials": RAW_MATERIAL_TAGS,
    "work_in_process": WORK_IN_PROCESS_TAGS,
}

MAX_COMPONENT_FACT_AGE_DAYS = 430
COMPARABLE_PERIOD_MIN_GAP_DAYS = 250
COMPARABLE_PERIOD_MAX_GAP_DAYS = 450
MIN_TOTAL_INVENTORY_USD = 50_000_000.0
MIN_FINISHED_GOODS_USD = 10_000_000.0
MIN_SUPPORT_INVENTORY_USD = 10_000_000.0
MIN_FINISHED_GOODS_SHARE_IMPROVEMENT = 0.03
MIN_SUPPORT_VALUE_GROWTH = -0.10
MAX_TOTAL_INVENTORY_GROWTH = 0.30
MIN_TOTAL_INVENTORY_GROWTH = -0.50

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "component_coverage_too_thin",
        "old_thin_regression",
        "drawdown_drift",
        "sector_concentration",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Prior inventory total-ratio and DIO surfaces were aggregate-positive "
        "but failed old_thin and drawdown. Component mix is the explicitly "
        "allowed new PIT decomposition axis; risk remains high because "
        "component reporters are sparse and may still relabel 2025 momentum."
    ),
    "recorded_at": "2026-06-19T02:09:47+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_free_sec_companyfacts": True,
    "uses_raw_companyfacts_cache": True,
    "uses_free_ohlcv": True,
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until one shared default-off helper computes the same "
        "raw SEC finished-goods/raw-material/WIP component mix, filed-date PIT "
        "availability, price confirmation, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical "
        "replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC Companyfacts inventory component mix may "
        "separate true sell-through from rejected total-inventory and DIO "
        "signals. Finished-goods share falling year over year while raw-"
        "material/work-in-process support remains, combined with liquid "
        "SPY-relative price confirmation, may add next-open 10d replacement "
        "value without noisy ticker expansion."
    ),
    "2_history_check": {
        "exp-20260616-018": (
            "Rejected inventory/revenue leanness despite aggregate-positive "
            "EV/PnL because old_thin regressed and drawdown drift was too high."
        ),
        "exp-20260616-019": (
            "Rejected annual DIO/turnover improvement; component mix is not a "
            "DIO threshold, COGS-growth, fact-age, hold, or cooldown retune."
        ),
        "exp-20260616-022": (
            "Rejected quarterly DIO/turnover improvement and named finished-"
            "goods vs raw-material decomposition as the next valid PIT axis."
        ),
        "exp-20260603-013": (
            "Rejected earlier inventory discipline. This run uses raw component "
            "composition, not total inventory/revenue discipline."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260619_004_inventory_component_mix_sellthrough.py"
    ),
}

_COMPONENT_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _raw_instant_facts(usgaap: dict[str, Any], tags: tuple[str, ...]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    priority = {tag: idx for idx, tag in enumerate(tags)}
    for tag in tags:
        tag_payload = usgaap.get(tag) or {}
        for raw in tag_payload.get("units", {}).get("USD", []):
            end = str(raw.get("end") or "")[:10]
            filed = str(raw.get("filed") or "")[:10]
            start = str(raw.get("start") or "")[:10]
            value = rd._float_or_none(raw.get("val"))
            if not end or not filed or value is None:
                continue
            if start and start != end:
                continue
            facts.append(
                {
                    "filed": filed,
                    "start": end,
                    "end": end,
                    "value": value,
                    "tag": tag,
                    "tag_priority": priority[tag],
                    "form": str(raw.get("form") or ""),
                    "fy": raw.get("fy"),
                    "fp": str(raw.get("fp") or ""),
                }
            )
    facts.sort(key=lambda row: (row["end"], row["filed"], -int(row["tag_priority"]), row["tag"], row["value"]))
    return facts


def _latest_component_fact(
    facts: list[dict[str, Any]], *, asof: str, end: str | None = None, before_end: str | None = None
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for fact in facts:
        if fact["filed"] > asof:
            continue
        if end is not None and fact["end"] != end:
            continue
        if before_end is not None and fact["end"] >= before_end:
            continue
        candidates.append(fact)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda fact: (
            str(fact["end"]),
            str(fact["filed"]),
            -int(fact.get("tag_priority") or 0),
            abs(float(fact.get("value") or 0.0)),
        ),
    )


def _prior_comparable_fact(facts: list[dict[str, Any]], *, asof: str, current_end: str) -> dict[str, Any] | None:
    current_end_date = base.framework._parse_date(current_end)
    candidates: list[dict[str, Any]] = []
    for fact in facts:
        if fact["filed"] > asof or fact["end"] >= current_end:
            continue
        gap_days = (current_end_date - base.framework._parse_date(fact["end"])).days
        if COMPARABLE_PERIOD_MIN_GAP_DAYS <= gap_days <= COMPARABLE_PERIOD_MAX_GAP_DAYS:
            candidates.append({**fact, "_gap_days": gap_days})
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda fact: (
            abs(int(fact["_gap_days"]) - 365),
            -int(fact["_gap_days"]),
            str(fact["filed"]),
            abs(float(fact.get("value") or 0.0)),
        ),
    )


def _load_component_index() -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    global _COMPONENT_INDEX_CACHE
    if _COMPONENT_INDEX_CACHE is not None:
        return _COMPONENT_INDEX_CACHE

    stats: Counter[str] = Counter()
    ticker_ciks: dict[str, int] = {}
    uri = f"file:{Path(base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as con:
        rows = con.execute(
            """
            select u.ticker, u.cik
            from ticker_universe u
            join coverage_summary c on c.ticker = u.ticker
            where u.hygiene_pass = 1
              and c.all_windows_full_liquid = 1
              and u.cik is not null
            order by u.ticker
            """
        ).fetchall()
    for ticker, cik in rows:
        try:
            ticker_ciks[str(ticker).upper()] = int(cik)
        except (TypeError, ValueError):
            stats["invalid_cik_rows"] += 1

    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for ticker, cik in ticker_ciks.items():
        stats["warehouse_tickers_with_cik"] += 1
        path = RAW_COMPANYFACTS_CACHE / f"CIK{cik:010d}.json"
        if not path.exists():
            stats["missing_companyfacts_cache_file"] += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stats["unreadable_companyfacts_cache_file"] += 1
            continue
        usgaap = payload.get("facts", {}).get("us-gaap", {})
        grouped = {
            name: _raw_instant_facts(usgaap, tags)
            for name, tags in COMPONENT_TAG_GROUPS.items()
        }
        if not grouped["total"]:
            stats["tickers_missing_total_inventory"] += 1
            continue
        if not grouped["finished_goods"]:
            stats["tickers_missing_finished_goods"] += 1
            continue
        if not (grouped["raw_materials"] or grouped["work_in_process"]):
            stats["tickers_missing_raw_or_wip"] += 1
            continue
        index[ticker] = grouped
        stats["tickers_with_component_mix"] += 1
        for name, facts in grouped.items():
            stats[f"{name}_fact_count"] += len(facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "component_tag_groups": {key: list(value) for key, value in COMPONENT_TAG_GROUPS.items()},
        "warehouse_source": _repo_rel(base.framework.WAREHOUSE),
        **dict(stats),
    }
    _COMPONENT_INDEX_CACHE = (index, summary)
    return _COMPONENT_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    index, summary = _load_component_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "raw_sec_companyfacts_component_mix_not_selected_sidecar",
    }


def _support_value(facts: dict[str, list[dict[str, Any]]], *, asof: str, end: str) -> tuple[float, list[str]]:
    value = 0.0
    tags: list[str] = []
    for key in ("raw_materials", "work_in_process"):
        fact = _latest_component_fact(facts[key], asof=asof, end=end)
        if fact is None:
            continue
        amount = abs(float(fact["value"]))
        if amount <= 0.0:
            continue
        value += amount
        tags.append(str(fact["tag"]))
    return value, tags


def _component_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_total = _latest_component_fact(facts["total"], asof=asof)
    if current_total is None:
        return None
    if base._days_between(asof, current_total["filed"]) > MAX_COMPONENT_FACT_AGE_DAYS:
        return None
    current_finished = _latest_component_fact(
        facts["finished_goods"], asof=asof, end=current_total["end"]
    )
    if current_finished is None:
        return None
    current_support_value, current_support_tags = _support_value(
        facts, asof=asof, end=current_total["end"]
    )
    if current_support_value <= 0.0:
        return None

    prior_total = _prior_comparable_fact(facts["total"], asof=asof, current_end=current_total["end"])
    if prior_total is None:
        return None
    prior_finished = _latest_component_fact(
        facts["finished_goods"], asof=asof, end=prior_total["end"]
    )
    if prior_finished is None:
        return None
    prior_support_value, prior_support_tags = _support_value(
        facts, asof=asof, end=prior_total["end"]
    )
    if prior_support_value <= 0.0:
        return None

    current_total_value = abs(float(current_total["value"]))
    prior_total_value = abs(float(prior_total["value"]))
    current_finished_value = abs(float(current_finished["value"]))
    prior_finished_value = abs(float(prior_finished["value"]))
    if (
        current_total_value < MIN_TOTAL_INVENTORY_USD
        or prior_total_value <= 0.0
        or current_finished_value < MIN_FINISHED_GOODS_USD
        or current_support_value < MIN_SUPPORT_INVENTORY_USD
    ):
        return None

    current_fg_share = current_finished_value / current_total_value
    prior_fg_share = prior_finished_value / prior_total_value
    current_support_share = current_support_value / current_total_value
    prior_support_share = prior_support_value / prior_total_value
    fg_share_improvement = prior_fg_share - current_fg_share
    support_value_growth = (current_support_value - prior_support_value) / abs(prior_support_value)
    support_share_change = current_support_share - prior_support_share
    total_inventory_growth = (current_total_value - prior_total_value) / abs(prior_total_value)

    if fg_share_improvement < MIN_FINISHED_GOODS_SHARE_IMPROVEMENT:
        return None
    if support_value_growth < MIN_SUPPORT_VALUE_GROWTH:
        return None
    if total_inventory_growth > MAX_TOTAL_INVENTORY_GROWTH:
        return None
    if total_inventory_growth < MIN_TOTAL_INVENTORY_GROWTH:
        return None

    return {
        "ticker": ticker,
        "current_period_end": current_total["end"],
        "prior_period_end": prior_total["end"],
        "current_total_inventory_filed": current_total["filed"],
        "current_finished_goods_filed": current_finished["filed"],
        "prior_total_inventory_filed": prior_total["filed"],
        "prior_finished_goods_filed": prior_finished["filed"],
        "current_total_inventory": _round(current_total_value, 2),
        "prior_total_inventory": _round(prior_total_value, 2),
        "current_finished_goods": _round(current_finished_value, 2),
        "prior_finished_goods": _round(prior_finished_value, 2),
        "current_support_inventory": _round(current_support_value, 2),
        "prior_support_inventory": _round(prior_support_value, 2),
        "current_finished_goods_share": _round(current_fg_share, 6),
        "prior_finished_goods_share": _round(prior_fg_share, 6),
        "finished_goods_share_improvement": _round(fg_share_improvement, 6),
        "current_support_share": _round(current_support_share, 6),
        "prior_support_share": _round(prior_support_share, 6),
        "support_share_change": _round(support_share_change, 6),
        "support_value_growth": _round(support_value_growth, 6),
        "total_inventory_growth": _round(total_inventory_growth, 6),
        "current_total_inventory_tag": current_total["tag"],
        "current_finished_goods_tag": current_finished["tag"],
        "current_support_tags": current_support_tags,
        "prior_total_inventory_tag": prior_total["tag"],
        "prior_finished_goods_tag": prior_finished["tag"],
        "prior_support_tags": prior_support_tags,
        "comparable_period_gap_days": (
            base.framework._parse_date(current_total["end"])
            - base.framework._parse_date(prior_total["end"])
        ).days,
        "fact_age_days": base._days_between(asof, current_total["filed"]),
        "known_at": "raw_companyfacts_component_filed_and_signal_close_before_next_open_paper_entry",
        "rule_version": RULE_VERSION,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = base.framework.shadow._trading_dates(snapshot)
    window_dates = [day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])]
    eligible = sorted(set(quality_index) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["eligible_quality_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []

    for signal_date in window_dates:
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            observation = _component_observation(ticker, signal_date, quality_index[ticker])
            if observation is None:
                scan["failed_component_mix_gate"] += 1
                continue
            confirm = base._price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            fg_improvement = float(observation["finished_goods_share_improvement"] or 0.0)
            support_growth = float(observation["support_value_growth"] or 0.0)
            support_share_change = float(observation["support_share_change"] or 0.0)
            inventory_growth = float(observation["total_inventory_growth"] or 0.0)
            score = (
                2.20 * min(fg_improvement, 0.30)
                + 0.35 * max(min(support_growth, 0.60), -0.10)
                + 0.25 * max(min(support_share_change, 0.25), -0.10)
                - 0.20 * max(inventory_growth, 0.0)
                + 0.55 * float(confirm["candidate_ret20_excess_spy"])
                + 0.14 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.035
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "INVENTORY_COMPONENT_MIX_SELLTHROUGH_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"component_{k}": v for k, v in observation.items()},
                    **confirm,
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(existing["candidate_score"]):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["component_finished_goods_share_improvement"] or 0.0),
            -float(row["component_support_value_growth"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "max_component_fact_age_days": MAX_COMPONENT_FACT_AGE_DAYS,
        "comparable_period_min_gap_days": COMPARABLE_PERIOD_MIN_GAP_DAYS,
        "comparable_period_max_gap_days": COMPARABLE_PERIOD_MAX_GAP_DAYS,
        "min_total_inventory_usd": MIN_TOTAL_INVENTORY_USD,
        "min_finished_goods_usd": MIN_FINISHED_GOODS_USD,
        "min_support_inventory_usd": MIN_SUPPORT_INVENTORY_USD,
        "min_finished_goods_share_improvement": MIN_FINISHED_GOODS_SHARE_IMPROVEMENT,
        "min_support_value_growth": MIN_SUPPORT_VALUE_GROWTH,
        "max_total_inventory_growth": MAX_TOTAL_INVENTORY_GROWTH,
        "min_total_inventory_growth": MIN_TOTAL_INVENTORY_GROWTH,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_inventory_component_mix_sellthrough"
        if gate["passed"]
        else "rejected_inventory_component_mix_sellthrough_candidate_pool"
    )
    return gate


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The inventory component-mix sell-through source cleared the "
            "numeric three-window replay screen, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The inventory component-mix sell-through source did not clear "
            f"Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "Do not promote or tune this component-mix bundle on the same "
            "frozen windows."
        )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "lane": "alpha_search",
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_sec_companyfacts_inventory_quality_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_inventory_component_mix_pit_field",
            "nearby_prior_experiments": [
                "exp-20260616-018",
                "exp-20260616-019",
                "exp-20260616-022",
                "exp-20260603-013",
            ],
            "prior_trial_count": 3,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["parameters"] = {
        "base_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "max_component_fact_age_days": MAX_COMPONENT_FACT_AGE_DAYS,
        "comparable_period_min_gap_days": COMPARABLE_PERIOD_MIN_GAP_DAYS,
        "comparable_period_max_gap_days": COMPARABLE_PERIOD_MAX_GAP_DAYS,
        "min_total_inventory_usd": MIN_TOTAL_INVENTORY_USD,
        "min_finished_goods_usd": MIN_FINISHED_GOODS_USD,
        "min_support_inventory_usd": MIN_SUPPORT_INVENTORY_USD,
        "min_finished_goods_share_improvement": MIN_FINISHED_GOODS_SHARE_IMPROVEMENT,
        "min_support_value_growth": MIN_SUPPORT_VALUE_GROWTH,
        "max_total_inventory_growth": MAX_TOTAL_INVENTORY_GROWTH,
        "min_total_inventory_growth": MIN_TOTAL_INVENTORY_GROWTH,
        "component_tag_groups": {key: list(value) for key, value in COMPONENT_TAG_GROUPS.items()},
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "max_signal_return": base.MAX_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Raw SEC Companyfacts inventory component facts are read as balance-"
        "sheet INSTANT facts and known only by filed date <= signal date. The "
        "rule compares latest total inventory, finished goods, and raw-material/"
        "work-in-process support against a comparable prior period roughly one "
        "year earlier. Finished-goods share must fall by at least 3pp, support "
        "inventory value must not contract more than 10%, and total inventory "
        "must not build more than 30%. Price confirmation uses only signal-date "
        "OHLCV. Paper entry is next available open; exit is 10 trading days "
        "after the signal close with existing costs and slippage."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts InventoryNet instant facts",
        "raw SEC companyfacts finished-goods inventory component facts",
        "raw SEC companyfacts raw-material or work-in-process component facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT inventory-quality evidence such "
        "as finished-goods/raw-material decomposition with segment context, "
        "closed forward replacement-value rows, or customer/supplier demand "
        "provenance. Do not sweep component tag lists, share thresholds, fact "
        "freshness, price guards, top-N, hold, cooldown, or notional on these "
        "frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; max "
            "drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping component tag lists, finished-goods share "
            "thresholds, support-retention thresholds, total-inventory growth "
            "caps, fact freshness, RS/close/volume/vol guards, top-N, hold "
            "days, cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(q.REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {elig} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                elig=scan.get("eligible_quality_tickers", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Inventory Component-Mix Sell-Through",
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
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _configure_modules() -> None:
    q.__file__ = __file__
    q.EXPERIMENT_ID = EXPERIMENT_ID
    q.STEM = STEM
    q.TRIAL_FAMILY = TRIAL_FAMILY
    q.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    q.CHANGED_VARIABLE = CHANGED_VARIABLE
    q.RULE_VERSION = RULE_VERSION
    q.OWNER = OWNER
    q.OUT_DIR = OUT_DIR
    q.OUT_JSON = OUT_JSON
    q.LOG_JSON = LOG_JSON
    q.TICKET_JSON = TICKET_JSON
    q.CARD_MD = CARD_MD
    q.MANIFEST_JSON = MANIFEST_JSON
    q.EXPERIMENT_LOG = EXPERIMENT_LOG
    q.PREDICTION = PREDICTION
    q.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    q.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    q.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    q.HOLD_DAYS = HOLD_DAYS
    q.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    q.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    q._build_quality_index = _build_quality_index
    q._candidate_rows_for_window = _candidate_rows_for_window
    q._gate4 = _gate4
    q._build_card = _build_card
    q._configure_base()


def main() -> None:
    _configure_modules()
    payload = _postprocess_payload(base._build_payload())
    q._persist(payload)
    print(json.dumps(base.framework._safe(q._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
