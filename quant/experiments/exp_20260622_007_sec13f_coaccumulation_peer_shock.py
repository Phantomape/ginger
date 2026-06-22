"""exp-20260622-007: SEC 13F co-accumulation peer-shock scout.

Tests a materially different follow-up to exp-20260622-006.  The rejected
static 13F co-ownership graph said "these two names are held by many of the same
managers."  This run asks a sharper relation question: did the same managers
increase BOTH names across consecutive 13F filing windows, then did one name
shock up while the other lagged?

Replay-only default-off scout: no live orders, ranking, sizing, exits,
watchlists, LLM, news, or shared production helper are changed.  A positive
result would still require a shared helper/daily snapshot promotion.

Run:
    .\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260622_007_sec13f_coaccumulation_peer_shock.py
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402

shadow = framework.shadow
overlay_helper = framework.overlay_helper
sleeve_overlay = framework.sleeve
WINDOWS = framework.WINDOWS
REPO_ROOT = framework.REPO_ROOT
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import rolling_corr_peer_shock_paper_sleeve as rc  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from kova_data_sidecar import parse_sec13f_zip  # noqa: E402
from sec13f_coownership_edges import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    discover_window_labels,
    latest_label_for,
    window_end_date,
)
from sec13f_universe_map import load_company_name_index, normalize_issuer_name  # noqa: E402


EXPERIMENT_ID = "exp-20260622-007"
STEM = "sec13f_coaccumulation_peer_shock"
OWNER = "alpha-explore"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260622_007_sec13f_coaccumulation_peer_shock.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "candidate_pool: SEC 13F co-accumulation peer graph, where the same "
    "institutional managers increased both names across consecutive filing "
    "windows, may admit cleaner peer-shock laggards than static co-ownership "
    "and beat rolling-correlation peer-shock after costs."
)
CHANGED_VARIABLE = (
    "Use SEC 13F shared-manager co-accumulation edges as the peer-adjacency "
    "source for peer-shock laggard admission."
)
TRIAL_FAMILY = "sec13f_coaccumulation_peer_shock"
TRIAL_VARIANT_ID = "coaccumulation_peer_graph_top1_next_open_10d_v1"
RULE_VERSION = "sec13f_coaccumulation_peer_shock_replay_scout_v1"

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "stale_13f_signal",
        "index_overlap_noise",
        "not_incremental_vs_rolling_corr",
    ],
    "confidence_reason": (
        "exp-20260622-006 rejected static co-ownership but explicitly left "
        "holdings-change co-movement as a valid new evidence axis; "
        "co-accumulation should be less index-overlap-heavy than static "
        "co-hold, though quarterly filing lag and sample size are major risks."
    ),
    "recorded_at": "2026-06-22T07:05:32+00:00",
}

CONFIG = {
    **rc.DEFAULT_CONFIG,
    "min_accumulation_increase_pct": 0.10,
    "min_shared_accumulating_managers": 2,
    "min_coaccumulation_lift": 1.25,
    "lift_score_cap": 5.0,
    "manager_min_holdings": 5,
    "manager_max_holdings": 120,
    "manager_min_accumulations": 2,
    "manager_max_accumulations": 80,
    "min_current_value_usd_thousands": 5_000.0,
    "edge_top_k": 20,
}
CONFIG["enabled"] = False
CONFIG["trade_enabled"] = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, digits)


def _trade_economics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row.get("pnl") or 0.0) for row in trades]
    winners = [pnl for pnl in pnls if pnl > 0]
    by_ticker: dict[str, float] = {}
    for row in trades:
        ticker = str(row.get("ticker") or "").upper()
        by_ticker[ticker] = by_ticker.get(ticker, 0.0) + float(row.get("pnl") or 0.0)
    positive = {ticker: pnl for ticker, pnl in by_ticker.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_share = max(positive.values()) / positive_total if positive_total > 0 else None
    hhi = sum((pnl / positive_total) ** 2 for pnl in positive.values()) if positive_total > 0 else None
    return {
        "trade_count": len(trades),
        "net_pnl": _round(sum(pnls), 2),
        "win_rate": _round(len(winners) / len(trades), 4) if trades else None,
        "avg_pnl_per_trade": _round(sum(pnls) / len(trades), 2) if trades else None,
        "unique_tickers": len(by_ticker),
        "single_ticker_positive_share": _round(max_share, 4) if max_share is not None else None,
        "positive_pnl_hhi": _round(hhi, 4) if hhi is not None else None,
    }


class CoaccumulationEdgeProvider:
    """Point-in-time resolver for same-manager 13F co-accumulation edges."""

    def __init__(
        self,
        *,
        universe: set[str],
        cache_dir: Path | str = DEFAULT_CACHE_DIR,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._universe = {str(t).upper() for t in universe}
        self._cache_dir = Path(cache_dir)
        self._config = dict(CONFIG)
        if config:
            self._config.update(config)
        self._labels = discover_window_labels(self._cache_dir)
        self._name_index = load_company_name_index()
        self._holdings_cache: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
        self._edge_cache: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
        self._audit_cache: dict[str, dict[str, Any]] = {}

    @property
    def labels(self) -> list[str]:
        return list(self._labels)

    def label_for_date(self, signal_date: str) -> str | None:
        return latest_label_for(signal_date[:10], self._labels)

    def peers_for_date(self, signal_date: str) -> dict[str, dict[str, dict[str, Any]]]:
        label = self.label_for_date(signal_date)
        if label is None:
            return {}
        return self._edges_for_label(label)

    def audit_for_label(self, label: str) -> dict[str, Any]:
        self._edges_for_label(label)
        return dict(self._audit_cache.get(label, {}))

    def _holdings_for_label(self, label: str) -> dict[str, dict[str, dict[str, float]]]:
        if label in self._holdings_cache:
            return self._holdings_cache[label]
        zip_path = self._cache_dir / f"{label}_form13f.zip"
        rows = parse_sec13f_zip(zip_path, asof_date=window_end_date(label), cusip_ticker_map=None)
        holdings: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: {
            "shares": 0.0,
            "value_usd_thousands": 0.0,
        }))
        for row in rows:
            ticker = self._name_index.get(normalize_issuer_name(row.get("name_of_issuer")))
            if not ticker or ticker not in self._universe:
                continue
            manager = str(row.get("manager_cik") or row.get("manager_name") or "").strip()
            if not manager:
                continue
            shares = row.get("shares")
            value = row.get("value_usd_thousands")
            if isinstance(shares, (int, float)) and shares > 0:
                holdings[manager][ticker]["shares"] += float(shares)
            if isinstance(value, (int, float)) and value > 0:
                holdings[manager][ticker]["value_usd_thousands"] += float(value)
        self._holdings_cache[label] = holdings
        return holdings

    def _edges_for_label(self, label: str) -> dict[str, dict[str, dict[str, Any]]]:
        if label in self._edge_cache:
            return self._edge_cache[label]
        try:
            label_index = self._labels.index(label)
        except ValueError:
            self._edge_cache[label] = {}
            return {}
        if label_index == 0:
            self._audit_cache[label] = {"status": "missing_prior_13f_window", "edge_count": 0}
            self._edge_cache[label] = {}
            return {}

        prior_label = self._labels[label_index - 1]
        current = self._holdings_for_label(label)
        prior = self._holdings_for_label(prior_label)
        cfg = self._config
        min_increase = float(cfg["min_accumulation_increase_pct"])
        min_value = float(cfg["min_current_value_usd_thousands"])
        manager_min_holdings = int(cfg["manager_min_holdings"])
        manager_max_holdings = int(cfg["manager_max_holdings"])
        manager_min_accum = int(cfg["manager_min_accumulations"])
        manager_max_accum = int(cfg["manager_max_accumulations"])

        increased_by_manager: dict[str, set[str]] = {}
        for manager, current_holdings in current.items():
            n_current = len(current_holdings)
            if n_current < manager_min_holdings or n_current > manager_max_holdings:
                continue
            prior_holdings = prior.get(manager, {})
            increased: set[str] = set()
            for ticker, current_values in current_holdings.items():
                prior_values = prior_holdings.get(ticker)
                if not prior_values:
                    continue
                prior_shares = float(prior_values.get("shares") or 0.0)
                current_shares = float(current_values.get("shares") or 0.0)
                current_value = float(current_values.get("value_usd_thousands") or 0.0)
                if prior_shares <= 0 or current_shares <= 0 or current_value < min_value:
                    continue
                if (current_shares / prior_shares - 1.0) >= min_increase:
                    increased.add(ticker)
            if manager_min_accum <= len(increased) <= manager_max_accum:
                increased_by_manager[manager] = increased

        shared: dict[tuple[str, str], int] = defaultdict(int)
        accum_holders: Counter[str] = Counter()
        for tickers in increased_by_manager.values():
            for ticker in tickers:
                accum_holders[ticker] += 1
            for a, b in combinations(sorted(tickers), 2):
                shared[(a, b)] += 1

        total_managers = max(len(increased_by_manager), 1)
        min_shared = int(cfg["min_shared_accumulating_managers"])
        min_lift = float(cfg["min_coaccumulation_lift"])
        peer_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for (a, b), count in shared.items():
            if count < min_shared:
                continue
            expected = accum_holders[a] * accum_holders[b] / total_managers
            lift = count / expected if expected else 0.0
            if lift < min_lift:
                continue
            union = accum_holders[a] + accum_holders[b] - count
            jaccard = count / union if union else 0.0
            edge = {
                "shared_accumulating_managers": count,
                "coaccumulation_lift": _round(lift, 6),
                "coaccumulation_jaccard": _round(jaccard, 6),
                "current_window_label": label,
                "prior_window_label": prior_label,
            }
            peer_rows[a].append({**edge, "peer": b})
            peer_rows[b].append({**edge, "peer": a})

        top_k = int(cfg["edge_top_k"])
        edge_map: dict[str, dict[str, dict[str, Any]]] = {}
        edge_count = 0
        for ticker, rows in peer_rows.items():
            rows.sort(
                key=lambda row: (
                    -float(row.get("coaccumulation_lift") or 0.0),
                    -int(row.get("shared_accumulating_managers") or 0),
                    str(row.get("peer") or ""),
                )
            )
            kept = rows[:top_k]
            edge_count += len(kept)
            edge_map[ticker] = {str(row["peer"]).upper(): row for row in kept}

        self._audit_cache[label] = {
            "status": "ok",
            "current_window_label": label,
            "prior_window_label": prior_label,
            "managers_current": len(current),
            "managers_prior": len(prior),
            "managers_with_valid_accumulation_sets": len(increased_by_manager),
            "tickers_with_edges": len(edge_map),
            "directed_edge_count": edge_count,
            "params": {
                key: cfg[key]
                for key in [
                    "min_accumulation_increase_pct",
                    "min_shared_accumulating_managers",
                    "min_coaccumulation_lift",
                    "manager_min_holdings",
                    "manager_max_holdings",
                    "manager_min_accumulations",
                    "manager_max_accumulations",
                    "min_current_value_usd_thousands",
                    "edge_top_k",
                ]
            },
        }
        self._edge_cache[label] = edge_map
        return edge_map


def _config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(CONFIG)
    if overrides:
        cfg.update({key: value for key, value in overrides.items() if value is not None})
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _connection_strength(lift: float, cap: float) -> float:
    return min(max(lift, 0.0), cap) / cap


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(row.get("date") or ""),
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("coaccumulation_lift") or 0.0),
        -float(row.get("peer_relative_vs_spy") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("peer_ticker") or ""),
        str(row.get("ticker") or ""),
    )


def build_coaccumulation_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    sector_entries: dict[str, dict[str, Any]],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    config: dict[str, Any] | None = None,
    edge_provider: CoaccumulationEdgeProvider,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = rc._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    indices = {ticker: rc._row_index(rows) for ticker, rows in rows_by_ticker.items()}
    all_dates = rc._trading_dates(rows_by_ticker)
    date_pos = {day: pos for pos, day in enumerate(all_dates)}
    date_set = set(rc._date10(day) for day in dates)
    eligible_tickers = sorted(ticker for ticker in sector_entries if ticker in rows_by_ticker)
    candidates: list[dict[str, Any]] = []
    peer_contexts: list[dict[str, Any]] = []
    edge_labels_used: Counter[str] = Counter()
    scan = {
        "scanned_trading_days": len(date_set),
        "days_missing_edge_window": 0,
        "days_with_peer_shocks": 0,
        "days_with_laggard_candidates": 0,
        "days_with_coaccumulation_pairs": 0,
        "raw_peer_shocks": 0,
        "raw_laggard_candidates": 0,
        "raw_coaccumulation_pairs": 0,
        "raw_candidates_before_core_flow_filter": 0,
        "raw_candidates_after_core_flow_filter": 0,
        "edge_windows_available": edge_provider.labels,
        "core_flow_confirmation_required": True,
        "positive_candidate_signal_return_required": True,
        "rule_version": RULE_VERSION,
    }

    for signal_date in sorted(date_set):
        pos = date_pos.get(signal_date)
        if pos is None or pos < int(cfg["correlation_lookback_days"]):
            continue
        core_entries = core_entries_by_date.get(signal_date, [])
        if not core_entries:
            continue
        edge_map = edge_provider.peers_for_date(signal_date)
        edge_label = edge_provider.label_for_date(signal_date)
        if edge_label:
            edge_labels_used[edge_label] += 1
        if not edge_map:
            scan["days_missing_edge_window"] += 1
            continue

        peer_rows = [
            row
            for ticker in eligible_tickers
            if (
                row := rc._peer_shock_for_ticker(
                    rows_by_ticker=rows_by_ticker,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                    config=cfg,
                )
            )
            is not None
        ]
        if not peer_rows:
            continue
        scan["days_with_peer_shocks"] += 1
        scan["raw_peer_shocks"] += len(peer_rows)
        peer_rows.sort(
            key=lambda row: (
                -float(row["peer_score"]),
                -float(row["peer_signal_day_return"]),
                -float(row["peer_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        peer_rows = peer_rows[: int(cfg["max_shock_peers_per_day"])]

        laggard_rows = [
            row
            for ticker in eligible_tickers
            if (
                row := rc._laggard_candidate_for_ticker(
                    rows_by_ticker=rows_by_ticker,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                    config=cfg,
                )
            )
            is not None
        ]
        if not laggard_rows:
            continue
        scan["days_with_laggard_candidates"] += 1
        scan["raw_laggard_candidates"] += len(laggard_rows)
        laggard_rows.sort(
            key=lambda row: (
                -float(row["candidate_lag_quality_score"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        laggard_rows = laggard_rows[: int(cfg["max_laggard_candidates_per_day"])]

        day_rows: list[dict[str, Any]] = []
        cap = float(cfg["lift_score_cap"])
        for peer in peer_rows:
            peer_ticker = str(peer["ticker"]).upper()
            peer_edges = edge_map.get(peer_ticker)
            if not peer_edges:
                continue
            for laggard in laggard_rows:
                ticker = str(laggard["ticker"]).upper()
                if ticker == peer_ticker:
                    continue
                edge = peer_edges.get(ticker)
                if edge is None:
                    continue
                lift = float(edge.get("coaccumulation_lift") or 0.0)
                connection = _connection_strength(lift, cap)
                same_sector = peer.get("peer_sector") == laggard.get("sector")
                same_industry = peer.get("peer_industry") == laggard.get("industry")
                score = (
                    1.80 * connection
                    + 2.40 * float(peer["peer_relative_vs_spy"])
                    + 1.10 * float(peer["peer_signal_day_return"])
                    + 0.75 * float(laggard["candidate_lag_quality_score"])
                    - 1.20 * max(float(laggard["candidate_signal_day_return"]), 0.0)
                    + (0.08 if same_sector else 0.0)
                    + (0.05 if same_industry else 0.0)
                )
                day_rows.append(
                    {
                        "date": signal_date,
                        "ticker": ticker,
                        "source": "SEC13F_COACCUMULATION_PEER_SHOCK_PAPER",
                        "candidate_score": _round(score, 6),
                        "peer_ticker": peer_ticker,
                        "coaccumulation_lift": _round(lift, 6),
                        "shared_accumulating_managers": int(edge.get("shared_accumulating_managers") or 0),
                        "coaccumulation_jaccard": edge.get("coaccumulation_jaccard"),
                        "coaccumulation_connection_strength": _round(connection, 6),
                        "coaccumulation_current_window": edge.get("current_window_label"),
                        "coaccumulation_prior_window": edge.get("prior_window_label"),
                        "same_sector_as_peer": bool(same_sector),
                        "same_industry_as_peer": bool(same_industry),
                        "peer_signal_day_return": peer["peer_signal_day_return"],
                        "peer_relative_vs_spy": peer["peer_relative_vs_spy"],
                        "peer_volume_ratio_20d": peer["peer_volume_ratio_20d"],
                        "peer_ret20_excess_spy": peer["peer_ret20_excess_spy"],
                        "peer_avg_dollar_volume_20d": peer["peer_avg_dollar_volume_20d"],
                        "peer_sector": peer.get("peer_sector"),
                        "peer_industry": peer.get("peer_industry"),
                        **laggard,
                        "same_day_ab_entry_count": len(core_entries),
                        "same_day_ab_overlap": True,
                        "same_ticker_ab_overlap": any(
                            str(entry.get("ticker") or "").upper() == ticker
                            for entry in core_entries
                        ),
                        "rule_version": RULE_VERSION,
                        "source_rule_version": RULE_VERSION,
                        "uses_free_ohlcv": True,
                        "uses_free_sec13f": True,
                        "uses_llm": False,
                        "trade_enabled": False,
                        "known_at": "after_signal_day_close_before_next_open_paper_entry",
                    }
                )

        scan["raw_candidates_before_core_flow_filter"] += len(day_rows)
        if not day_rows:
            continue
        day_rows.sort(key=_candidate_sort_key)
        day_rows = day_rows[: int(cfg["max_raw_rows_per_day"])]
        candidates.extend(day_rows)
        scan["days_with_coaccumulation_pairs"] += 1
        scan["raw_coaccumulation_pairs"] += len(day_rows)
        scan["raw_candidates_after_core_flow_filter"] += len(day_rows)
        peer_contexts.append(
            {
                "date": signal_date,
                "edge_label": edge_label,
                "raw_peer_shock_count": len(peer_rows),
                "raw_laggard_candidate_count": len(laggard_rows),
                "coaccumulation_pair_count_kept": len(day_rows),
                "top_peer_ticker": day_rows[0]["peer_ticker"],
                "top_candidate": day_rows[0]["ticker"],
                "top_score": day_rows[0]["candidate_score"],
                "top_coaccumulation_lift": day_rows[0]["coaccumulation_lift"],
                "top_shared_accumulating_managers": day_rows[0]["shared_accumulating_managers"],
                "top_peer_relative_vs_spy": day_rows[0]["peer_relative_vs_spy"],
                "top_candidate_signal_day_return": day_rows[0]["candidate_signal_day_return"],
            }
        )

    candidates.sort(key=_candidate_sort_key)
    scan["edge_labels_used"] = dict(edge_labels_used)
    scan["edge_provider_audit"] = {
        label: edge_provider.audit_for_label(label)
        for label in sorted(edge_labels_used)
    }
    scan["params"] = {
        key: cfg[key]
        for key in [
            "min_accumulation_increase_pct",
            "min_shared_accumulating_managers",
            "min_coaccumulation_lift",
            "manager_min_holdings",
            "manager_max_holdings",
            "manager_min_accumulations",
            "manager_max_accumulations",
            "min_current_value_usd_thousands",
            "edge_top_k",
            "paper_notional_usd",
            "daily_entry_slots",
            "same_ticker_cooldown_days",
            "hold_days",
        ]
    }
    return candidates, peer_contexts, scan


def build_coaccumulation_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None,
    windows: dict[str, dict[str, str]],
    sector_entries: dict[str, dict[str, Any]],
    edge_provider: CoaccumulationEdgeProvider,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = rc._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    all_trades: list[dict[str, Any]] = []
    audit: dict[str, Any] = {
        "rule_version": RULE_VERSION,
        "selected_by_window": {},
        "raw_candidate_count_by_window": {},
        "rejected_count_by_window": {},
        "scan_by_window": {},
        "peer_contexts_by_window": {},
    }
    for label, window in windows.items():
        dates = [
            day
            for day in rc._trading_dates(rows_by_ticker)
            if str(window["start"]) <= day <= str(window["end"])
        ]
        candidates, peer_contexts, scan = build_coaccumulation_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            dates=dates,
            sector_entries=sector_entries,
            core_entries_by_date=core_entries_by_date or {},
            config=cfg,
            edge_provider=edge_provider,
        )
        selected, rejected = rc._select_candidates_for_paper(
            rows_by_ticker=rows_by_ticker,
            candidates=candidates,
            state=rc.empty_rolling_corr_peer_shock_paper_state(),
            config=cfg,
            create_trades=True,
        )
        window_trades = [{**row, "window": label} for row in selected]
        all_trades.extend(window_trades)
        audit["selected_by_window"][label] = len(window_trades)
        audit["raw_candidate_count_by_window"][label] = len(candidates)
        audit["rejected_count_by_window"][label] = len(rejected)
        audit["scan_by_window"][label] = scan
        audit["peer_contexts_by_window"][label] = peer_contexts[:100]
    return all_trades, framework._safe(audit)


def _run_window(
    *,
    label: str,
    cfg: dict[str, str],
    universe: list[str],
    sector_entries: dict[str, dict[str, Any]],
    edge_provider: CoaccumulationEdgeProvider,
) -> dict[str, Any]:
    print(f"[{label}] core baseline ...", flush=True)
    before_result = shadow._run_baseline(universe, cfg)
    before = overlay_helper._metrics(before_result)
    snapshot = framework._load_window_snapshot(cfg=cfg, eligible_tickers=set(sector_entries))
    core_entries_by_date = shadow._baseline_entries(before_result)
    sector_map = {ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot}
    window = {"start": cfg["start"], "end": cfg["end"]}

    print(f"[{label}] coaccumulation peer-shock replay ...", flush=True)
    co_trades, co_audit = build_coaccumulation_historical_trades(
        ohlcv_by_ticker=snapshot,
        core_entries_by_date=core_entries_by_date,
        windows={label: window},
        sector_entries=sector_map,
        edge_provider=edge_provider,
        config=CONFIG,
    )
    co_overlay = sleeve_overlay._overlay_from_paper_trades(before_result, co_trades)
    co_after = overlay_helper._metrics_with_overlay(before_result, co_overlay)
    co_delta = overlay_helper._delta(co_after, before)

    print(f"[{label}] rolling-corr comparator replay ...", flush=True)
    rc_trades, rc_audit = rc.build_rolling_corr_peer_shock_historical_trades(
        ohlcv_by_ticker=snapshot,
        core_entries_by_date=core_entries_by_date,
        windows={label: window},
        sector_entries=sector_map,
    )
    rc_overlay = sleeve_overlay._overlay_from_paper_trades(before_result, rc_trades)
    rc_after = overlay_helper._metrics_with_overlay(before_result, rc_overlay)
    rc_delta = overlay_helper._delta(rc_after, before)

    return {
        "label": label,
        "window": window,
        "before": before,
        "core_entry_days": len(core_entries_by_date),
        "loaded_ticker_count": len(snapshot),
        "coaccumulation": {
            "after": co_after,
            "delta": co_delta,
            "overlay_total_pnl": _round(co_overlay["overlay_total_pnl"], 2),
            "economics": _trade_economics(co_trades),
            "trades": co_trades,
            "audit": co_audit,
        },
        "rolling_corr": {
            "after": rc_after,
            "delta": rc_delta,
            "overlay_total_pnl": _round(rc_overlay["overlay_total_pnl"], 2),
            "economics": _trade_economics(rc_trades),
            "trades": rc_trades,
            "audit": rc_audit,
        },
    }


def _aggregate(window_records: dict[str, Any]) -> dict[str, Any]:
    base_ev = sum(float(row["before"].get("expected_value_score") or 0.0) for row in window_records.values())
    base_pnl = sum(float(row["before"].get("total_pnl") or 0.0) for row in window_records.values())
    base_max_dd = max(float(row["before"].get("max_drawdown_pct") or 0.0) for row in window_records.values())
    out = {
        "baseline": {
            "aggregate_expected_value_score": _round(base_ev, 4),
            "aggregate_total_pnl": _round(base_pnl, 2),
            "max_window_drawdown_pct": _round(base_max_dd, 4),
        }
    }
    for sleeve_name in ["coaccumulation", "rolling_corr"]:
        trades: list[dict[str, Any]] = []
        ev_delta = 0.0
        pnl_delta = 0.0
        max_dd_drift = 0.0
        windows_ev_improved = 0
        windows_ev_regressed = 0
        windows_pnl_improved = 0
        windows_pnl_regressed = 0
        for row in window_records.values():
            sleeve = row[sleeve_name]
            trades.extend(sleeve["trades"])
            delta = sleeve["delta"]
            delta_ev = float(delta.get("expected_value_score") or 0.0)
            delta_pnl = float(sleeve.get("overlay_total_pnl") or 0.0)
            ev_delta += delta_ev
            pnl_delta += delta_pnl
            if delta_ev > 0:
                windows_ev_improved += 1
            if delta_ev < 0:
                windows_ev_regressed += 1
            if delta_pnl > 0:
                windows_pnl_improved += 1
            if delta_pnl < 0:
                windows_pnl_regressed += 1
            before_dd = float(row["before"].get("max_drawdown_pct") or 0.0)
            after_dd = float(sleeve["after"].get("max_drawdown_pct") or 0.0)
            max_dd_drift = max(max_dd_drift, after_dd - before_dd)
        out[sleeve_name] = {
            "aggregate_expected_value_delta": _round(ev_delta, 6),
            "aggregate_total_pnl_delta": _round(pnl_delta, 2),
            "aggregate_expected_value_after": _round(base_ev + ev_delta, 4),
            "aggregate_total_pnl_after": _round(base_pnl + pnl_delta, 2),
            "max_drawdown_worse": _round(max_dd_drift, 6),
            "windows_ev_improved": windows_ev_improved,
            "windows_ev_regressed": windows_ev_regressed,
            "windows_pnl_improved": windows_pnl_improved,
            "windows_pnl_regressed": windows_pnl_regressed,
            "economics_all_windows": _trade_economics(trades),
        }
    co = out["coaccumulation"]
    roll = out["rolling_corr"]
    out["incremental_vs_rolling_corr"] = {
        "expected_value_delta": _round(
            float(co["aggregate_expected_value_delta"] or 0.0)
            - float(roll["aggregate_expected_value_delta"] or 0.0),
            6,
        ),
        "total_pnl_delta": _round(
            float(co["aggregate_total_pnl_delta"] or 0.0)
            - float(roll["aggregate_total_pnl_delta"] or 0.0),
            2,
        ),
    }
    return out


def _gate4(aggregate: dict[str, Any]) -> dict[str, Any]:
    co = aggregate["coaccumulation"]
    roll = aggregate["rolling_corr"]
    econ = co["economics_all_windows"]
    failures: list[str] = []
    if float(co["aggregate_expected_value_delta"] or 0.0) <= 0:
        failures.append("aggregate_ev_not_positive")
    if float(co["aggregate_total_pnl_delta"] or 0.0) <= 0:
        failures.append("aggregate_pnl_not_positive")
    if int(co["windows_ev_improved"] or 0) < 2:
        failures.append("fewer_than_two_ev_improved_windows")
    if int(co["windows_ev_regressed"] or 0) > 0:
        failures.append("window_ev_regression")
    if int(co["windows_pnl_regressed"] or 0) > 0:
        failures.append("window_pnl_regression")
    if int(econ["trade_count"] or 0) < 20:
        failures.append("target_sample_too_small")
    if float(co["max_drawdown_worse"] or 0.0) > 0.005:
        failures.append("drawdown_drift_too_high")
    single_share = econ.get("single_ticker_positive_share")
    hhi = econ.get("positive_pnl_hhi")
    if single_share is None or float(single_share) > 0.50 or hhi is None or float(hhi) > 0.35:
        failures.append("target_concentration_failed")
    if float(co["aggregate_expected_value_delta"] or 0.0) <= float(roll["aggregate_expected_value_delta"] or 0.0):
        failures.append("rolling_corr_peer_shock_ev_not_beaten")
    if float(co["aggregate_total_pnl_delta"] or 0.0) <= float(roll["aggregate_total_pnl_delta"] or 0.0):
        failures.append("rolling_corr_peer_shock_pnl_not_beaten")
    return {
        "passed": not failures,
        "failed_reasons": failures,
        "aggregate_ev_delta": co["aggregate_expected_value_delta"],
        "aggregate_pnl_delta": co["aggregate_total_pnl_delta"],
        "target_trade_count": econ["trade_count"],
        "target_trade_count_min": 20,
        "windows_ev_improved": co["windows_ev_improved"],
        "windows_ev_regressed": co["windows_ev_regressed"],
        "windows_pnl_improved": co["windows_pnl_improved"],
        "windows_pnl_regressed": co["windows_pnl_regressed"],
        "max_drawdown_worse": co["max_drawdown_worse"],
        "max_drawdown_worse_guardrail": 0.005,
        "target_concentration": {
            "single_ticker_positive_share": single_share,
            "single_ticker_positive_share_guardrail": 0.50,
            "positive_pnl_hhi": hhi,
            "positive_pnl_hhi_guardrail": 0.35,
            "passed": "target_concentration_failed" not in failures,
        },
        "accepted_comparator": {
            "name": "rolling_corr_peer_shock",
            "aggregate_ev_delta": roll["aggregate_expected_value_delta"],
            "aggregate_pnl_delta": roll["aggregate_total_pnl_delta"],
            "decision": "accepted_rolling_corr_peer_shock_shared_default_off_adapter",
            "experiment_id": "exp-20260606-025",
        },
    }


def _calibration(gate4: dict[str, Any]) -> dict[str, Any]:
    actual_success = 1 if gate4["passed"] else 0
    predicted = float(PREDICTION["success_probability"])
    actual_ev = float(gate4.get("aggregate_ev_delta") or 0.0)
    actual_pnl = float(gate4.get("aggregate_pnl_delta") or 0.0)
    failures = gate4.get("failed_reasons") or []
    realized = failures[0] if failures else "numeric_gate4_passed_but_replay_only"
    return {
        "actual_success": actual_success,
        "predicted_success_probability": predicted,
        "brier_score": _round((predicted - actual_success) ** 2, 4),
        "expected_ev_delta": PREDICTION.get("expected_ev_delta"),
        "actual_ev_delta": _round(actual_ev, 6),
        "ev_prediction_error": None,
        "expected_pnl_delta": PREDICTION.get("expected_pnl_delta"),
        "actual_pnl_delta": _round(actual_pnl, 2),
        "pnl_prediction_error": None,
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "realized_failure_mode": realized,
        "predicted_failure_mode_hit": any(
            failure in {
                "thin_sample",
                "stale_13f_signal",
                "index_overlap_noise",
                "not_incremental_vs_rolling_corr",
            }
            for failure in failures
        ) or "rolling_corr" in realized or "sample" in realized,
        "calibration_direction": "directionally_calibrated" if actual_success == 0 else "underconfident",
        "surprise_level": "low" if actual_success == 0 else "moderate",
        "surprise_note": (
            "Co-accumulation failed the predeclared Gate-4 screen; the main "
            "risk was stale/noisy 13F relation data not adding enough over "
            "rolling-correlation peer shock."
            if actual_success == 0
            else "Replay was positive, but it remains only a lead because no shared daily helper was promoted."
        ),
    }


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "trade_enabled": False,
        "daily_snapshot_exposed": False,
        "live_realism_evaluated": True,
        "live_ready": False,
        "parity_test_added": False,
        "adapter_status": "private_replay_scout_no_shared_adapter",
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "uses_free_ohlcv": True,
        "uses_free_sec13f": True,
        "uses_llm": False,
        "activation_envelope": {
            "target_notional_per_paper_trade": CONFIG["paper_notional_usd"],
            "daily_entry_slots": CONFIG["daily_entry_slots"],
            "same_ticker_cooldown_days": CONFIG["same_ticker_cooldown_days"],
            "hold_days": CONFIG["hold_days"],
            "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
            "order_semantics": "observe-only next-session-open paper entry; no broker order",
            "portfolio_displacement": "none unless a later shared helper and activation gate pass",
            "kill_switch": "trade_enabled remains false; no production adapter changes",
        },
        "parity_note": (
            "This experiment changes no production code. A positive result would be "
            "only a replay lead until a shared default-off helper builds the same "
            "13F co-accumulation edge map and daily snapshot path."
        ),
    }


def _build_payload() -> dict[str, Any]:
    universe = sorted(framework.get_universe())
    sector_entries = framework._load_sector_entries()
    edge_provider = CoaccumulationEdgeProvider(universe=set(universe), config=CONFIG)
    window_records = {
        label: _run_window(
            label=label,
            cfg=cfg,
            universe=universe,
            sector_entries=sector_entries,
            edge_provider=edge_provider,
        )
        for label, cfg in WINDOWS.items()
    }
    aggregate = _aggregate(window_records)
    gate4 = _gate4(aggregate)
    calibration = _calibration(gate4)
    numeric_decision = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    status = "observed_only" if gate4["passed"] else "rejected"
    timestamp = _utc_now()
    compact_windows: list[dict[str, Any]] = []
    for label, record in window_records.items():
        co = record["coaccumulation"]
        roll = record["rolling_corr"]
        compact_windows.append(
            {
                "label": label,
                "start": record["window"]["start"],
                "end": record["window"]["end"],
                "before_ev": record["before"].get("expected_value_score"),
                "before_pnl": record["before"].get("total_pnl"),
                "coaccumulation_ev_delta": co["delta"].get("expected_value_score"),
                "coaccumulation_pnl_delta": co["overlay_total_pnl"],
                "coaccumulation_trade_count": co["economics"]["trade_count"],
                "rolling_corr_ev_delta": roll["delta"].get("expected_value_score"),
                "rolling_corr_pnl_delta": roll["overlay_total_pnl"],
                "rolling_corr_trade_count": roll["economics"]["trade_count"],
                "coaccumulation_scan": co["audit"]["scan_by_window"].get(label, {}),
            }
        )
    return framework._safe(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": timestamp,
            "status": status,
            "decision": numeric_decision,
            "accepted": False,
            "accepted_alpha": False,
            "hypothesis": HYPOTHESIS,
            "change_type": "candidate_pool_full_stack",
            "implementation_mode": "private_replay_scout",
            "mechanism_family": "peer_shock",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": ["historical replay", "execution envelope", "full-stack verdict"],
            "prior_trial_count": 0,
            "nearby_prior_experiments": ["exp-20260622-006"],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "SEC 13F same-manager co-accumulation edge",
            "prediction": PREDICTION,
            "calibration": calibration,
            "backtest_protocol": {
                "source": "docs/backtesting.md canonical three-window core replay plus replay-only default-off 13F co-accumulation overlay",
                "windows": WINDOWS,
                "replay_llm": False,
                "replay_news": False,
            },
            "pre_run_questions": {
                "1_alpha_hypothesis": HYPOTHESIS,
                "2_history_check": {
                    "exp-20260622-006": "Rejected static 13F co-ownership peer graph; allowed holdings-change co-movement as a new evidence axis.",
                    "novelty_gate": "Reservation required novelty override because adjacent 13F families exist; override records same-manager co-accumulation across consecutive filing windows.",
                },
                "3_single_decision_hypothesis": CHANGED_VARIABLE,
                "4_acceptance_standard": "Gate 4 requires positive aggregate EV/PnL, no EV/PnL window regression, >=20 trades, drawdown drift <=0.5pp, concentration pass, and beating accepted rolling-corr peer-shock on EV and PnL. Positive replay-only evidence is only a lead.",
                "5_reproducibility": ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260622_007_sec13f_coaccumulation_peer_shock.py",
            },
            "parameters": {
                "coaccumulation": {
                    key: CONFIG[key]
                    for key in [
                        "min_accumulation_increase_pct",
                        "min_shared_accumulating_managers",
                        "min_coaccumulation_lift",
                        "manager_min_holdings",
                        "manager_max_holdings",
                        "manager_min_accumulations",
                        "manager_max_accumulations",
                        "min_current_value_usd_thousands",
                        "edge_top_k",
                        "paper_notional_usd",
                        "daily_entry_slots",
                        "hold_days",
                        "same_ticker_cooldown_days",
                    ]
                }
            },
            "aggregate": aggregate,
            "gate4": gate4,
            "windows": compact_windows,
            "production_impact": _production_impact(),
            "post_run_reflection": {
                "why_result_happened": (
                    "The same-manager co-accumulation graph did not clear the "
                    "predeclared Gate-4 screen; 13F relation staleness and "
                    "quarterly batch effects likely remain too noisy for "
                    "peer-shock admission versus the accepted rolling-corr "
                    "relation."
                    if not gate4["passed"]
                    else "The co-accumulation relation passed replay numerics, but no shared helper or daily snapshot was promoted."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping min_accumulation_increase_pct, "
                    "min_shared_accumulating_managers, min_coaccumulation_lift, "
                    "manager holding-count bounds, top-K, hold days, cooldown, "
                    "or notional on these frozen windows."
                ),
                "new_evidence_required": (
                    "A valid retry needs non-quarterly ownership/flow evidence, "
                    "active-manager conviction classification independent of "
                    "holding count, manager-level alpha attribution, or closed "
                    "forward replacement-value rows from a shared default-off helper."
                ),
            },
            "rejection_reason": "; ".join(gate4["failed_reasons"]) if gate4["failed_reasons"] else None,
            "next_retry_requires": [
                "non-quarterly ownership/flow evidence",
                "manager-level active conviction classification",
                "closed forward replacement-value rows",
            ],
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(TICKET_JSON),
            ],
        }
    )


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["aggregate"]
    co = aggregate["coaccumulation"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "change_summary": "Replay-only SEC 13F same-manager co-accumulation peer graph as peer-shock laggard admission source.",
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": payload["causal_components"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "component": _repo_rel(Path(__file__)),
        "parameters": payload["parameters"],
        "date_range": {"start": "2024-10-02", "end": "2026-04-21"},
        "secondary_windows": [],
        "before_metrics": {
            "expected_value_score": aggregate["baseline"]["aggregate_expected_value_score"],
            "total_pnl": aggregate["baseline"]["aggregate_total_pnl"],
            "max_drawdown_pct": aggregate["baseline"]["max_window_drawdown_pct"],
        },
        "after_metrics": {
            "expected_value_score": co["aggregate_expected_value_after"],
            "total_pnl": co["aggregate_total_pnl_after"],
            "max_drawdown_pct": None,
            "trade_count": co["economics_all_windows"]["trade_count"],
        },
        "delta_metrics": {
            "expected_value_score": co["aggregate_expected_value_delta"],
            "total_pnl": co["aggregate_total_pnl_delta"],
            "max_drawdown_pct": co["max_drawdown_worse"],
        },
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "gate4": payload["gate4"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    co = payload["aggregate"]["coaccumulation"]
    inc = payload["aggregate"]["incremental_vs_rolling_corr"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC 13F Co-Accumulation Peer Shock",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Aggregate EV delta: `{co['aggregate_expected_value_delta']}`",
            f"- Aggregate PnL delta: `${co['aggregate_total_pnl_delta']}`",
            f"- Incremental vs rolling-corr EV/PnL: `{inc['expected_value_delta']}` / `${inc['total_pnl_delta']}`",
            f"- Trade count: `{co['economics_all_windows']['trade_count']}`",
            f"- Failed reasons: `{', '.join(gate4['failed_reasons']) if gate4['failed_reasons'] else 'none'}`",
            "",
            "## Hypothesis",
            HYPOTHESIS,
            "",
            "## Fixed Policy Bundle",
            CHANGED_VARIABLE,
            "",
            "## Reflection",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduction",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260622_007_sec13f_coaccumulation_peer_shock.py",
            "```",
            "",
        ]
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    files = [Path(__file__), OUT_JSON, LOG_JSON, CARD_MD, TICKET_JSON]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["timestamp"],
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "files": [_repo_rel(path) for path in files],
        "file_hashes": {_repo_rel(path): framework._sha256(path) for path in files},
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["aggregate"]["coaccumulation"]["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": payload["aggregate"]["coaccumulation"]["aggregate_total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": payload["aggregate"]["coaccumulation"]["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": payload["aggregate"]["coaccumulation"]["aggregate_total_pnl_delta"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
