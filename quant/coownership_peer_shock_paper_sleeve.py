"""Default-off institutional co-ownership peer-shock paper sleeve.

Shared helper for exp-20260622-006. This is the Anton-Polk "Connected Stocks"
(JF 2014) variant of the accepted ``rolling_corr_peer_shock`` sleeve: the ONLY
difference is the peer-adjacency source. Where the rolling-corr sleeve admits a
(peer-shock, laggard) pair when their 60d return vectors are highly correlated,
this sleeve admits the pair when the two names are **institutional co-ownership
network peers** -- held by many of the SAME 13F managers beyond chance (lift over
independence). The shock detection, laggard quality screen, core-flow gate,
paper-trade simulation, state machine, snapshot schema, and forward gate are
reused verbatim from the rolling-corr helper so the two sleeves are an
apples-to-apples comparison of peer DEFINITIONS.

The co-ownership edges are the persisted ``coownership_edges_<window>.json``
artifacts built by ``sec13f_coownership_edges.py`` (manager_cik -> set(ticker)
bipartite projection). They are resolved point-in-time: for a signal day, the
newest quarterly window whose 13F filing window ended on or before that day.

Default-off: emits paper candidates/snapshots and historical paper trades, but
never alters live orders, core ranking, sizing, exits, watchlists, LLM, or news.
"""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from data_paths import DATA_ROOT
    from sec13f_coownership_edges import latest_label_for, window_end_date
    import rolling_corr_peer_shock_paper_sleeve as rc
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.data_paths import DATA_ROOT
    from quant.sec13f_coownership_edges import latest_label_for, window_end_date
    from quant import rolling_corr_peer_shock_paper_sleeve as rc

# Reused generic internals (peer-shock detection, laggard screen, paper-trade
# simulation, state machine, snapshot plumbing). These are independent of the
# peer-adjacency source, so importing keeps the two sleeves byte-for-byte aligned
# on everything except the relation.
from_rc = rc
utc_now_iso = rc.utc_now_iso
_normalise_ohlcv_by_ticker = rc._normalise_ohlcv_by_ticker
_row_index = rc._row_index
_trading_dates = rc._trading_dates
_date10 = rc._date10
_round = rc._round
_safe = rc._safe
_peer_shock_for_ticker = rc._peer_shock_for_ticker
_laggard_candidate_for_ticker = rc._laggard_candidate_for_ticker
_select_candidates_for_paper = rc._select_candidates_for_paper
_advance_paper_state = rc._advance_paper_state
_unrealized_pnl = rc._unrealized_pnl
_forward_paper_gate = rc._forward_paper_gate
_resolve_sector_entries = rc._resolve_sector_entries
_normalise_state = rc._normalise_state
_production_impact = rc._production_impact


SLEEVE_NAME = "COOWNERSHIP_PEER_SHOCK_CORE_FLOW_PAPER"
RULE_VERSION = "coownership_peer_shock_core_flow_shared_adapter_v1"
SOURCE_RULE_VERSION = "coownership_peer_shock_core_flow_positive_candidate_source_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = DATA_ROOT / "paper_sleeves" / "coownership_peer_shock" / "state.json"
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT / "paper_sleeves" / "coownership_peer_shock" / "snapshots.jsonl"
)
DEFAULT_EDGES_DIR = DATA_ROOT / "non_ohlcv" / "sec13f_institutional"
_EDGE_PREFIX = "coownership_edges_"
_EDGE_SUFFIX = ".json"

# Co-ownership admission defaults. The persisted edges already require
# >= 30 shared managers (edge builder min_shared_managers), so the LIFT floor is
# the meaningful gate: it keeps genuinely connected pairs (co-held beyond each
# name's marginal popularity) and drops "both just widely held" pairs whose lift
# sits near 1. Everything else mirrors the rolling-corr config exactly.
_COOWNERSHIP_OVERRIDES = {
    "min_shared_managers": 30,
    "min_coownership_lift": 1.5,
    "lift_score_cap": 5.0,
}
DEFAULT_CONFIG = {**rc.DEFAULT_CONFIG, **_COOWNERSHIP_OVERRIDES}


def _config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        cfg.update({key: value for key, value in overrides.items() if value is not None})
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


# ---------------------------------------------------------------------------
# Point-in-time co-ownership edge provider
# ---------------------------------------------------------------------------
class CoownershipEdgeProvider:
    """PIT resolver over persisted ``coownership_edges_<window>.json`` artifacts.

    For a signal day, returns the symmetric peer map of the newest quarterly
    window whose 13F filing window ended on or before that day. Edge payloads are
    public once their filing window closes, so ``window_end <= signal_date`` is
    point-in-time safe.
    """

    def __init__(self, edges_dir: Path | str = DEFAULT_EDGES_DIR) -> None:
        self._dir = Path(edges_dir)
        self._labels = self._discover_labels()
        self._cache: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}

    def _discover_labels(self) -> list[str]:
        labels = [
            p.name[len(_EDGE_PREFIX) : -len(_EDGE_SUFFIX)]
            for p in self._dir.glob(f"{_EDGE_PREFIX}*{_EDGE_SUFFIX}")
        ]
        return sorted(labels, key=window_end_date)

    @property
    def labels(self) -> list[str]:
        return list(self._labels)

    def label_for_date(self, signal_date: str) -> str | None:
        return latest_label_for(_date10(signal_date), self._labels)

    def peers_for_date(self, signal_date: str) -> dict[str, dict[str, dict[str, Any]]]:
        label = self.label_for_date(signal_date)
        if label is None:
            return {}
        return self._load(label)

    def _load(self, label: str) -> dict[str, dict[str, dict[str, Any]]]:
        if label not in self._cache:
            path = self._dir / f"{_EDGE_PREFIX}{label}{_EDGE_SUFFIX}"
            payload = json.loads(path.read_text(encoding="utf-8"))
            peers_by_ticker = payload.get("peers_by_ticker", {})
            edge_map: dict[str, dict[str, dict[str, Any]]] = {}
            for ticker, peer_list in peers_by_ticker.items():
                edge_map[str(ticker).upper()] = {
                    str(p.get("peer")).upper(): p for p in peer_list if p.get("peer")
                }
            self._cache[label] = edge_map
        return self._cache[label]


def _coownership_connection_strength(lift: float, cap: float) -> float:
    """Bounded [0, 1] connection strength from co-ownership lift.

    Lift is open-ended (>1 = connected beyond chance). Cap+normalise it so it
    occupies the same role and scale the rolling-corr sleeve gives Pearson corr
    in its candidate score, keeping the two scoring formulas comparable.
    """
    return min(max(lift, 0.0), cap) / cap


# ---------------------------------------------------------------------------
# Candidate construction -- the ONE function that differs from rolling-corr:
# the peer relation is a co-ownership edge, not a rolling correlation.
# ---------------------------------------------------------------------------
def build_coownership_peer_shock_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    sector_entries: dict[str, dict[str, Any]],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    config: dict[str, Any] | None = None,
    edge_provider: CoownershipEdgeProvider | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    provider = edge_provider if edge_provider is not None else CoownershipEdgeProvider()
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    indices = {ticker: _row_index(rows) for ticker, rows in rows_by_ticker.items()}
    all_dates = _trading_dates(rows_by_ticker)
    date_pos = {day: pos for pos, day in enumerate(all_dates)}
    date_set = set(_date10(day) for day in dates)
    eligible_tickers = sorted(ticker for ticker in sector_entries if ticker in rows_by_ticker)
    candidates: list[dict[str, Any]] = []
    peer_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(date_set),
        "days_with_peer_shocks": 0,
        "days_with_laggard_candidates": 0,
        "days_with_coownership_pairs": 0,
        "raw_peer_shocks": 0,
        "raw_laggard_candidates": 0,
        "raw_coownership_pairs": 0,
        "raw_candidates_before_core_flow_filter": 0,
        "raw_candidates_after_core_flow_filter": 0,
        "days_missing_edge_window": 0,
        "core_flow_confirmation_required": True,
        "positive_candidate_signal_return_required": True,
        "min_shared_managers": cfg["min_shared_managers"],
        "min_coownership_lift": cfg["min_coownership_lift"],
        "correlation_lookback_days": cfg["correlation_lookback_days"],
        "max_shock_peers_per_day": cfg["max_shock_peers_per_day"],
        "max_laggard_candidates_per_day": cfg["max_laggard_candidates_per_day"],
        "edge_windows_available": provider.labels,
    }

    for signal_date in sorted(date_set):
        pos = date_pos.get(signal_date)
        if pos is None or pos < int(cfg["correlation_lookback_days"]):
            continue
        core_entries = core_entries_by_date.get(signal_date, [])
        if not core_entries:
            continue
        edge_map = provider.peers_for_date(signal_date)
        if not edge_map:
            scan["days_missing_edge_window"] += 1
            continue

        peer_rows = [
            row
            for ticker in eligible_tickers
            if (
                row := _peer_shock_for_ticker(
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
                row := _laggard_candidate_for_ticker(
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

        min_shared = int(cfg["min_shared_managers"])
        min_lift = float(cfg["min_coownership_lift"])
        cap = float(cfg["lift_score_cap"])
        day_rows: list[dict[str, Any]] = []
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
                shared_managers = int(edge.get("shared_managers") or 0)
                lift = float(edge.get("lift") or 0.0)
                jaccard = float(edge.get("jaccard") or 0.0)
                if shared_managers < min_shared or lift < min_lift:
                    continue
                connection = _coownership_connection_strength(lift, cap)
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
                        "source": SLEEVE_NAME,
                        "candidate_score": _round(score, 6),
                        "peer_ticker": peer_ticker,
                        "coownership_lift": _round(lift, 6),
                        "coownership_shared_managers": shared_managers,
                        "coownership_jaccard": _round(jaccard, 6),
                        "coownership_connection_strength": _round(connection, 6),
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
                        "source_rule_version": SOURCE_RULE_VERSION,
                        "uses_free_ohlcv_only": True,
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
        scan["days_with_coownership_pairs"] += 1
        scan["raw_coownership_pairs"] += len(day_rows)
        scan["raw_candidates_after_core_flow_filter"] += len(day_rows)
        peer_contexts.append(
            {
                "date": signal_date,
                "raw_peer_shock_count": len(peer_rows),
                "raw_laggard_candidate_count": len(laggard_rows),
                "coownership_pair_count_kept": len(day_rows),
                "top_peer_ticker": day_rows[0]["peer_ticker"],
                "top_candidate": day_rows[0]["ticker"],
                "top_score": day_rows[0]["candidate_score"],
                "top_coownership_lift": day_rows[0]["coownership_lift"],
                "top_coownership_shared_managers": day_rows[0]["coownership_shared_managers"],
                "top_peer_relative_vs_spy": day_rows[0]["peer_relative_vs_spy"],
                "top_candidate_signal_day_return": day_rows[0]["candidate_signal_day_return"],
            }
        )

    candidates.sort(key=_candidate_sort_key)
    scan.update(_threshold_audit(cfg))
    return candidates, peer_contexts, scan


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(row.get("date") or ""),
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("coownership_lift") or 0.0),
        -float(row.get("peer_relative_vs_spy") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("peer_ticker") or ""),
        str(row.get("ticker") or ""),
    )


def _threshold_audit(config: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "min_shared_managers",
        "min_coownership_lift",
        "min_peer_signal_return",
        "min_peer_relative_vs_spy",
        "min_peer_volume_ratio_20d",
        "min_peer_ret20_excess_spy",
        "min_candidate_signal_return",
        "max_candidate_signal_return",
        "min_candidate_close_location",
        "min_candidate_ret5",
        "max_candidate_ret5",
        "min_candidate_ret20_excess_spy",
        "min_candidate_ret60_excess_spy",
        "max_candidate_realized_vol_20d",
    ]
    return {key: config[key] for key in keys}


def _pending_entry_from_candidate(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": str(row.get("ticker") or "").upper(),
        "signal_date": row.get("date"),
        "source": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "intended_notional": float(config["paper_notional_usd"]),
        "paper_notional_usd": float(config["paper_notional_usd"]),
        "candidate_score": row.get("candidate_score"),
        "peer_ticker": row.get("peer_ticker"),
        "coownership_lift": row.get("coownership_lift"),
        "coownership_shared_managers": row.get("coownership_shared_managers"),
        "trade_enabled": False,
        "created_at": utc_now_iso(),
    }


# ---------------------------------------------------------------------------
# State / snapshot plumbing (thin wrappers; schema mirrors rolling-corr)
# ---------------------------------------------------------------------------
def empty_coownership_peer_shock_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_coownership_peer_shock_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_coownership_peer_shock_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_coownership_peer_shock_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state_local(state)
    return state


def save_coownership_peer_shock_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_coownership_peer_shock_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def _normalise_state_local(state: dict[str, Any]) -> None:
    for key in ["pending_entries", "open_positions", "closed_positions", "skipped_entries"]:
        if not isinstance(state.get(key), list):
            state[key] = []
    state["schema_version"] = STATE_SCHEMA_VERSION
    state["sleeve"] = SLEEVE_NAME


def empty_coownership_peer_shock_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": _date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "rejected_candidate_count": 0,
        "new_pending_count": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "closed_count_today": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "peer_shock_context": {
            "status": reason,
            "rule_version": SOURCE_RULE_VERSION,
            "read_only": True,
            "trade_enabled": False,
            "candidate_count": 0,
        },
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_coownership_peer_shock_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    core_entries: list[dict[str, Any]] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    edge_provider: CoownershipEdgeProvider | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker or {})
    if not rows_by_ticker:
        return empty_coownership_peer_shock_paper_sleeve_snapshot(as_of_date, "missing_ohlcv")
    if "SPY" not in rows_by_ticker:
        return empty_coownership_peer_shock_paper_sleeve_snapshot(as_of_date, "missing_spy_ohlcv")

    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    if not sector_map:
        return empty_coownership_peer_shock_paper_sleeve_snapshot(
            as_of_date,
            "missing_sector_entries",
        )

    working_state = deepcopy(
        state if state is not None else load_coownership_peer_shock_paper_state(state_path)
    )
    _normalise_state_local(working_state)
    lifecycle = _advance_paper_state(
        rows_by_ticker=rows_by_ticker,
        state=working_state,
        as_of_date=as_of_date,
        config=cfg,
    )

    candidates, peer_contexts, scan = build_coownership_peer_shock_candidate_rows(
        ohlcv_by_ticker=rows_by_ticker,
        dates=[as_of_date],
        sector_entries=sector_map,
        core_entries_by_date={as_of_date: list(core_entries or [])},
        config=cfg,
        edge_provider=edge_provider,
    )
    selected, rejected = _select_candidates_for_paper(
        rows_by_ticker=rows_by_ticker,
        candidates=candidates,
        state=working_state,
        config=cfg,
        create_trades=False,
    )
    pending = [_pending_entry_from_candidate(row, cfg) for row in selected]
    working_state["pending_entries"].extend(pending)

    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": bool(cfg["enabled"]),
        "paper_enabled": bool(cfg["paper_enabled"]),
        "trade_enabled": False,
        "candidate_count": len(selected),
        "raw_candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "new_pending_count": len(pending),
        "pending_count": len(working_state["pending_entries"]),
        "open_position_count": len(working_state["open_positions"]),
        "closed_position_count": len(working_state["closed_positions"]),
        "closed_count_today": len(lifecycle["closed_this_run"]),
        "realized_pnl_to_date": _round(
            sum(float(row.get("pnl") or 0.0) for row in working_state["closed_positions"]),
            2,
        ),
        "unrealized_pnl": _unrealized_pnl(
            rows_by_ticker=rows_by_ticker,
            open_positions=working_state["open_positions"],
            as_of_date=as_of_date,
            config=cfg,
        ),
        "candidates": selected,
        "rejected_candidates": rejected[:50],
        "opened_positions_this_run": lifecycle["opened_this_run"],
        "closed_positions_this_run": lifecycle["closed_this_run"],
        "skipped_entries_this_run": lifecycle["skipped_this_run"],
        "peer_shock_context": {
            **scan,
            "rule_version": SOURCE_RULE_VERSION,
            "read_only": True,
            "trade_enabled": False,
            "candidate_count": len(selected),
            "raw_candidate_count": len(candidates),
            "context_samples": peer_contexts[:10],
        },
        "forward_paper_gate": _forward_paper_gate(working_state, cfg),
        "production_impact": _production_impact(),
    }
    if persist:
        save_coownership_peer_shock_paper_state(working_state, state_path)
        append_coownership_peer_shock_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def build_coownership_peer_shock_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None,
    windows: dict[str, dict[str, str]],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
    edge_provider: CoownershipEdgeProvider | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    sector_map = _resolve_sector_entries(
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
    )
    provider = edge_provider if edge_provider is not None else CoownershipEdgeProvider()
    all_trades: list[dict[str, Any]] = []
    audit = {
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "selected_by_window": {},
        "raw_candidate_count_by_window": {},
        "rejected_count_by_window": {},
        "scan_by_window": {},
        "peer_contexts_by_window": {},
    }
    for label, window in windows.items():
        dates = [
            day
            for day in _trading_dates(rows_by_ticker)
            if str(window["start"]) <= day <= str(window["end"])
        ]
        candidates, peer_contexts, scan = build_coownership_peer_shock_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            dates=dates,
            sector_entries=sector_map,
            core_entries_by_date=core_entries_by_date or {},
            config=cfg,
            edge_provider=provider,
        )
        selected, rejected = _select_candidates_for_paper(
            rows_by_ticker=rows_by_ticker,
            candidates=candidates,
            state=empty_coownership_peer_shock_paper_state(),
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
    return all_trades, _safe(audit)


def prep_and_build_coownership_peer_shock_paper_sleeve_snapshot(
    *,
    as_of: str,
    broad_market_ohlcv: dict,
    broad_market_candidate_universe: dict,
    spy_ohlcv=None,
    core_entries=None,
):
    if not broad_market_candidate_universe.get("tickers"):
        return empty_coownership_peer_shock_paper_sleeve_snapshot(
            as_of, "broad_market_candidate_universe_unavailable")
    ohlcv = dict(broad_market_ohlcv)
    if "SPY" not in ohlcv and spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    return build_coownership_peer_shock_paper_sleeve_snapshot(
        as_of=as_of, ohlcv_by_ticker=ohlcv, core_entries=core_entries,
        candidate_universe=broad_market_candidate_universe,
    )
