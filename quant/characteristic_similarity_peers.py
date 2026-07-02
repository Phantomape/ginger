"""Read-only characteristic-similarity peer-shock candidate source.

This helper tests whether a peer with similar point-in-time business
characteristics can lead a laggard after a strong idiosyncratic move.  It is a
paper-only research surface: no live orders, sizing, exits, rankings, LLM
decisions, or production watchlists are changed here.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import fundamental_growth_rs_paper_sleeve as fgrs
    import rolling_corr_peer_shock_paper_sleeve as rc
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import fundamental_growth_rs_paper_sleeve as fgrs
    from quant import rolling_corr_peer_shock_paper_sleeve as rc
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage


SLEEVE_NAME = "CHARACTERISTIC_SIMILARITY_PEER_SHOCK_PAPER"
RULE_VERSION = "characteristic_similarity_peer_shock_observed_only_v1"
SOURCE_RULE_VERSION = "characteristic_similarity_peer_shock_candidate_source_v1"

DEFAULT_CONFIG = {
    **rc.DEFAULT_CONFIG,
    "min_characteristic_similarity": 0.64,
    "max_prior_return_correlation": 0.57,
    "min_non_price_pair_features": 2,
    "sector_similarity_weight": 0.10,
    "industry_similarity_weight": 0.08,
    "fundamental_similarity_weight": 0.42,
    "liquidity_similarity_weight": 0.14,
    "momentum_similarity_weight": 0.18,
    "analyst_similarity_weight": 0.08,
    "similarity_top_k_peer_pairs_per_day": 80,
    "feature_known_at": "OHLCV close plus SEC filed date <= signal_date",
}


def config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if overrides:
        cfg.update({key: value for key, value in overrides.items() if value is not None})
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def load_companyfacts_fundamental_index(
    *,
    max_filed: str,
    tickers: list[str] | set[str],
    non_ohlcv_dir: Path | str = fgrs.DEFAULT_NON_OHLCV_DIR,
) -> tuple[Any | None, dict[str, Any]]:
    audit = {
        "source": "sec_companyfacts_selected_jsonl",
        "max_filed": str(max_filed)[:10],
        "ticker_count": len(set(str(t).upper() for t in tickers)),
        "row_count": 0,
        "status": "not_loaded",
    }
    try:
        rows = fgrs.load_companyfacts_rows(
            max_filed=str(max_filed)[:10],
            tickers=sorted(str(t).upper() for t in tickers),
            non_ohlcv_dir=non_ohlcv_dir,
        )
    except Exception as exc:  # pragma: no cover - defensive for missing sidecars
        audit.update({"status": "load_failed", "error": str(exc)})
        return None, audit
    audit.update({"row_count": len(rows), "status": "ok" if rows else "empty"})
    if not rows:
        return None, audit
    return fgrs.CompanyfactsFundamentalIndex(rows, config=fgrs.DEFAULT_CONFIG), audit


class AnalystCoverageIndex:
    """Point-in-time analyst coverage breadth from existing revision ledgers."""

    def __init__(self, rows_by_ticker: dict[str, list[dict[str, Any]]]) -> None:
        self.rows_by_ticker = {
            ticker: sorted(rows, key=lambda row: str(row.get("asof_date") or ""))
            for ticker, rows in rows_by_ticker.items()
        }

    @classmethod
    def from_revision_ledgers(
        cls,
        *,
        root: Path | str,
        max_asof: str,
        tickers: list[str] | set[str],
    ) -> tuple["AnalystCoverageIndex", dict[str, Any]]:
        ticker_set = {str(t).upper() for t in tickers}
        rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
        # Scan both the per-experiment ledgers (data/experiments/exp-*/) and the
        # live daily ledger (data/non_ohlcv/), regardless of which one `root`
        # points at. The prior code only globbed exp-*/ under data/experiments,
        # so it silently missed the current data/non_ohlcv ledger entirely.
        root = Path(root)
        data_dir = root
        while data_dir.name and data_dir.name != "data" and data_dir.parent != data_dir:
            data_dir = data_dir.parent
        bases = [root]
        if data_dir.name == "data":
            bases = [data_dir / "experiments", data_dir / "non_ohlcv"]
        found: set[Path] = set()
        for base in bases:
            found.update(base.glob("exp-*/estimate_revision_ledger*.jsonl"))
            found.update(base.glob("estimate_revision_ledger*.jsonl"))
        paths = sorted(found)
        row_count = 0
        usable_count = 0
        for path in paths:
            try:
                handle = path.open("r", encoding="utf-8", errors="replace")
            except OSError:
                continue
            with handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ticker = str(raw.get("ticker") or "").upper()
                    asof = _date10(
                        raw.get("as_of_date")
                        or raw.get("asof_date")
                        or raw.get("date")
                        or raw.get("known_at")
                        or raw.get("generated_at")
                    )
                    if ticker not in ticker_set or not asof or asof > str(max_asof)[:10]:
                        continue
                    row_count += 1
                    count = _coverage_count(raw)
                    if count is None:
                        continue
                    usable_count += 1
                    rows_by_ticker.setdefault(ticker, []).append(
                        {"ticker": ticker, "asof_date": asof, "analyst_coverage_count": count}
                    )
        # Honest status: distinguish "no rows matched at all" (path/field bug or
        # no data) from "rows matched but the ledger schema carries no analyst
        # coverage field" (the current reality -- the revision ledger has
        # eps/revenue estimates but no analyst-count column).
        if usable_count:
            status = "ok"
        elif row_count:
            status = "no_coverage_field_in_source"
        else:
            status = "empty"
        audit = {
            "source": "estimate_revision_ledger_jsonl",
            "max_asof": str(max_asof)[:10],
            "ledger_file_count": len(paths),
            "row_count": row_count,
            "usable_coverage_rows": usable_count,
            "covered_ticker_count": len(rows_by_ticker),
            "status": status,
        }
        return cls(rows_by_ticker), audit

    def coverage_count(self, ticker: str, asof_date: str) -> float | None:
        rows = [
            row
            for row in self.rows_by_ticker.get(str(ticker).upper(), [])
            if str(row.get("asof_date") or "") <= str(asof_date)[:10]
        ]
        if not rows:
            return None
        return _float_or_none(rows[-1].get("analyst_coverage_count"))


class CharacteristicSimilarityProvider:
    def __init__(
        self,
        *,
        ohlcv_by_ticker: dict[str, Any],
        sector_entries: dict[str, dict[str, Any]],
        fundamental_index: Any | None = None,
        analyst_coverage_index: AnalystCoverageIndex | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.config = globals()["config"](config)
        self.rows_by_ticker = rc._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
        self.indices = {
            ticker: rc._row_index(rows) for ticker, rows in self.rows_by_ticker.items()
        }
        self.sector_entries = {
            str(ticker).upper(): meta for ticker, meta in sector_entries.items()
        }
        self.fundamental_index = fundamental_index
        self.analyst_coverage_index = analyst_coverage_index
        self._feature_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def features_for(self, ticker: str, signal_date: str) -> dict[str, Any]:
        ticker = str(ticker).upper()
        signal_date = _date10(signal_date)
        cache_key = (ticker, signal_date)
        if cache_key in self._feature_cache:
            return self._feature_cache[cache_key]

        rows = self.rows_by_ticker.get(ticker) or []
        spy_rows = self.rows_by_ticker.get("SPY") or []
        idx = self.indices.get(ticker, {}).get(signal_date)
        spy_idx = self.indices.get("SPY", {}).get(signal_date)
        meta = self.sector_entries.get(ticker, {})
        numeric: dict[str, float | None] = {}
        if idx is not None:
            adv20 = rc._avg_dollar_volume(rows, idx)
            numeric["log_avg_dollar_volume_20d"] = math.log1p(adv20) if adv20 else None
            numeric["realized_vol_20d"] = rc._realized_vol(rows, idx, 20)
            ret20 = rc._ret(rows, idx, 20)
            ret60 = rc._ret(rows, idx, 60)
            spy_ret20 = rc._ret(spy_rows, spy_idx, 20) if spy_idx is not None else None
            spy_ret60 = rc._ret(spy_rows, spy_idx, 60) if spy_idx is not None else None
            numeric["ret20_excess_spy"] = (
                ret20 - spy_ret20 if ret20 is not None and spy_ret20 is not None else None
            )
            numeric["ret60_excess_spy"] = (
                ret60 - spy_ret60 if ret60 is not None and spy_ret60 is not None else None
            )

        fundamental = self._fundamental_features(ticker, signal_date)
        analyst_count = (
            self.analyst_coverage_index.coverage_count(ticker, signal_date)
            if self.analyst_coverage_index is not None
            else None
        )
        if analyst_count is not None:
            numeric["log_analyst_coverage_count"] = math.log1p(analyst_count)
        else:
            numeric["log_analyst_coverage_count"] = None
        non_price_count = sum(1 for value in fundamental.values() if value is not None)
        if analyst_count is not None:
            non_price_count += 1
        out = {
            "ticker": ticker,
            "date": signal_date,
            "sector": meta.get("sector"),
            "industry": meta.get("industry"),
            "numeric": numeric,
            "fundamental": fundamental,
            "analyst_coverage_count": _round(analyst_count, 6),
            "non_price_feature_count": non_price_count,
        }
        self._feature_cache[cache_key] = out
        return out

    def similarity(self, left_ticker: str, right_ticker: str, signal_date: str) -> dict[str, Any]:
        left = self.features_for(left_ticker, signal_date)
        right = self.features_for(right_ticker, signal_date)
        components: dict[str, float | None] = {}
        component_counts: dict[str, int] = {}
        components["sector"] = (
            1.0
            if left.get("sector") and left.get("sector") == right.get("sector")
            else 0.0
        )
        components["industry"] = (
            1.0
            if left.get("industry") and left.get("industry") == right.get("industry")
            else 0.0
        )
        fundamental_pairs = [
            ("eps_yoy_growth", 1.50),
            ("revenue_yoy_growth", 1.00),
            ("operating_margin_current", 0.70),
            ("gross_margin", 0.60),
            ("liabilities_assets_ratio", 1.00),
        ]
        fundamental_score, fundamental_count = _mean_field_similarity(
            left["fundamental"], right["fundamental"], fundamental_pairs
        )
        components["fundamental"] = fundamental_score
        component_counts["fundamental"] = fundamental_count
        liquidity_score, liquidity_count = _mean_field_similarity(
            left["numeric"],
            right["numeric"],
            [("log_avg_dollar_volume_20d", 1.00)],
        )
        components["liquidity"] = liquidity_score
        component_counts["liquidity"] = liquidity_count
        momentum_score, momentum_count = _mean_field_similarity(
            left["numeric"],
            right["numeric"],
            [
                ("ret20_excess_spy", 0.35),
                ("ret60_excess_spy", 0.55),
                ("realized_vol_20d", 0.08),
            ],
        )
        components["momentum_rs"] = momentum_score
        component_counts["momentum_rs"] = momentum_count
        analyst_score, analyst_count = _mean_field_similarity(
            left["numeric"],
            right["numeric"],
            [("log_analyst_coverage_count", 1.00)],
        )
        components["analyst_coverage"] = analyst_score
        component_counts["analyst_coverage"] = analyst_count

        weights = {
            "sector": float(self.config["sector_similarity_weight"]),
            "industry": float(self.config["industry_similarity_weight"]),
            "fundamental": float(self.config["fundamental_similarity_weight"]),
            "liquidity": float(self.config["liquidity_similarity_weight"]),
            "momentum_rs": float(self.config["momentum_similarity_weight"]),
            "analyst_coverage": float(self.config["analyst_similarity_weight"]),
        }
        numerator = 0.0
        denominator = 0.0
        for name, score in components.items():
            if score is None:
                continue
            weight = weights.get(name, 0.0)
            numerator += weight * score
            denominator += weight
        score = numerator / denominator if denominator > 0 else 0.0
        non_price_pair_count = fundamental_count + analyst_count
        return {
            "score": _round(score, 6),
            "components": {key: _round(value, 6) for key, value in components.items()},
            "component_counts": component_counts,
            "non_price_pair_feature_count": non_price_pair_count,
            "fundamental_pair_feature_count": fundamental_count,
            "analyst_pair_feature_count": analyst_count,
            "left_non_price_feature_count": left["non_price_feature_count"],
            "right_non_price_feature_count": right["non_price_feature_count"],
            "left_sector": left.get("sector"),
            "right_sector": right.get("sector"),
            "left_industry": left.get("industry"),
            "right_industry": right.get("industry"),
        }


def build_characteristic_similarity_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None,
    windows: dict[str, dict[str, str]],
    sector_entries: dict[str, dict[str, Any]],
    fundamental_index: Any | None = None,
    analyst_coverage_index: AnalystCoverageIndex | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = globals()["config"](config)
    rows_by_ticker = rc._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
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
    provider = CharacteristicSimilarityProvider(
        ohlcv_by_ticker=rows_by_ticker,
        sector_entries=sector_entries,
        fundamental_index=fundamental_index,
        analyst_coverage_index=analyst_coverage_index,
        config=cfg,
    )
    for label, window in windows.items():
        dates = [
            day
            for day in rc._trading_dates(rows_by_ticker)
            if str(window["start"]) <= day <= str(window["end"])
        ]
        candidates, peer_contexts, scan = build_characteristic_similarity_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            dates=dates,
            sector_entries=sector_entries,
            core_entries_by_date=core_entries_by_date or {},
            similarity_provider=provider,
            config=cfg,
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
    return all_trades, rc._safe(audit)


def build_characteristic_similarity_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    sector_entries: dict[str, dict[str, Any]],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    similarity_provider: CharacteristicSimilarityProvider | None = None,
    fundamental_index: Any | None = None,
    analyst_coverage_index: AnalystCoverageIndex | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = globals()["config"](config)
    rows_by_ticker = rc._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    indices = {ticker: rc._row_index(rows) for ticker, rows in rows_by_ticker.items()}
    all_dates = rc._trading_dates(rows_by_ticker)
    date_pos = {day: pos for pos, day in enumerate(all_dates)}
    date_set = set(_date10(day) for day in dates)
    eligible_tickers = sorted(ticker for ticker in sector_entries if ticker in rows_by_ticker)
    provider = similarity_provider or CharacteristicSimilarityProvider(
        ohlcv_by_ticker=rows_by_ticker,
        sector_entries=sector_entries,
        fundamental_index=fundamental_index,
        analyst_coverage_index=analyst_coverage_index,
        config=cfg,
    )
    candidates: list[dict[str, Any]] = []
    peer_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(date_set),
        "days_with_peer_shocks": 0,
        "days_with_laggard_candidates": 0,
        "days_with_characteristic_pairs": 0,
        "raw_peer_shocks": 0,
        "raw_laggard_candidates": 0,
        "raw_characteristic_pairs": 0,
        "raw_candidates_before_core_flow_filter": 0,
        "raw_candidates_after_core_flow_filter": 0,
        "pairs_rejected_missing_prior_corr": 0,
        "pairs_rejected_high_prior_corr": 0,
        "pairs_rejected_low_characteristic_similarity": 0,
        "pairs_rejected_low_non_price_feature_count": 0,
        "core_flow_confirmation_required": True,
        "min_characteristic_similarity": cfg["min_characteristic_similarity"],
        "max_prior_return_correlation": cfg["max_prior_return_correlation"],
        "min_non_price_pair_features": cfg["min_non_price_pair_features"],
        "feature_known_at": cfg["feature_known_at"],
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
    }

    for signal_date in sorted(date_set):
        pos = date_pos.get(signal_date)
        if pos is None or pos < int(cfg["correlation_lookback_days"]):
            continue
        core_entries = core_entries_by_date.get(signal_date, [])
        if not core_entries:
            continue
        prior_dates = all_dates[pos - int(cfg["correlation_lookback_days"]) : pos]
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

        vector_by_ticker: dict[str, list[float]] = {}
        for row in [*peer_rows, *laggard_rows]:
            ticker = str(row["ticker"])
            if ticker not in vector_by_ticker:
                vector = rc._prior_return_vector_for_dates(
                    rows_by_ticker=rows_by_ticker,
                    indices=indices,
                    ticker=ticker,
                    prior_dates=prior_dates,
                )
                if vector is not None:
                    vector_by_ticker[ticker] = vector

        day_rows: list[dict[str, Any]] = []
        for peer in peer_rows:
            peer_ticker = str(peer["ticker"])
            peer_vector = vector_by_ticker.get(peer_ticker)
            if peer_vector is None:
                continue
            for laggard in laggard_rows:
                ticker = str(laggard["ticker"])
                if ticker == peer_ticker:
                    continue
                laggard_vector = vector_by_ticker.get(ticker)
                if laggard_vector is None:
                    continue
                prior_corr = rc._pearson_corr(peer_vector, laggard_vector)
                if prior_corr is None:
                    scan["pairs_rejected_missing_prior_corr"] += 1
                    continue
                if prior_corr > float(cfg["max_prior_return_correlation"]):
                    scan["pairs_rejected_high_prior_corr"] += 1
                    continue
                similarity = provider.similarity(peer_ticker, ticker, signal_date)
                sim_score = float(similarity["score"] or 0.0)
                if sim_score < float(cfg["min_characteristic_similarity"]):
                    scan["pairs_rejected_low_characteristic_similarity"] += 1
                    continue
                if int(similarity["non_price_pair_feature_count"] or 0) < int(
                    cfg["min_non_price_pair_features"]
                ):
                    scan["pairs_rejected_low_non_price_feature_count"] += 1
                    continue
                same_sector = peer.get("peer_sector") == laggard.get("sector")
                same_industry = peer.get("peer_industry") == laggard.get("industry")
                score = (
                    2.25 * sim_score
                    + 2.40 * float(peer["peer_relative_vs_spy"])
                    + 1.10 * float(peer["peer_signal_day_return"])
                    + 0.75 * float(laggard["candidate_lag_quality_score"])
                    - 1.20 * max(float(laggard["candidate_signal_day_return"]), 0.0)
                    + (0.05 if same_sector else 0.0)
                    + (0.03 if same_industry else 0.0)
                )
                day_rows.append(
                    {
                        "date": signal_date,
                        "ticker": ticker,
                        "source": SLEEVE_NAME,
                        "candidate_score": _round(score, 6),
                        "peer_ticker": peer_ticker,
                        "characteristic_similarity_score": similarity["score"],
                        "characteristic_similarity_components": similarity["components"],
                        "characteristic_component_counts": similarity["component_counts"],
                        "non_price_pair_feature_count": similarity[
                            "non_price_pair_feature_count"
                        ],
                        "fundamental_pair_feature_count": similarity[
                            "fundamental_pair_feature_count"
                        ],
                        "analyst_pair_feature_count": similarity[
                            "analyst_pair_feature_count"
                        ],
                        "rolling_corr_60d": _round(prior_corr, 6),
                        "same_sector_as_peer": bool(same_sector),
                        "same_industry_as_peer": bool(same_industry),
                        "peer_signal_day_return": peer["peer_signal_day_return"],
                        "peer_relative_vs_spy": peer["peer_relative_vs_spy"],
                        "peer_volume_ratio_20d": peer["peer_volume_ratio_20d"],
                        "peer_ret20_excess_spy": peer["peer_ret20_excess_spy"],
                        "peer_avg_dollar_volume_20d": peer[
                            "peer_avg_dollar_volume_20d"
                        ],
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
                        "uses_free_ohlcv": True,
                        "uses_sec_companyfacts": True,
                        "uses_estimate_revision_ledger": bool(
                            similarity["analyst_pair_feature_count"]
                        ),
                        "uses_llm": False,
                        "trade_enabled": False,
                        "known_at": "after_signal_day_close_before_next_open_paper_entry",
                    }
                )
        scan["raw_candidates_before_core_flow_filter"] += len(day_rows)
        if not day_rows:
            continue
        day_rows.sort(key=_candidate_sort_key)
        day_rows = day_rows[: int(cfg["similarity_top_k_peer_pairs_per_day"])]
        day_rows = day_rows[: int(cfg["max_raw_rows_per_day"])]
        candidates.extend(day_rows)
        scan["days_with_characteristic_pairs"] += 1
        scan["raw_characteristic_pairs"] += len(day_rows)
        scan["raw_candidates_after_core_flow_filter"] += len(day_rows)
        peer_contexts.append(
            {
                "date": signal_date,
                "raw_peer_shock_count": len(peer_rows),
                "raw_laggard_candidate_count": len(laggard_rows),
                "characteristic_pair_count_kept": len(day_rows),
                "top_peer_ticker": day_rows[0]["peer_ticker"],
                "top_candidate": day_rows[0]["ticker"],
                "top_score": day_rows[0]["candidate_score"],
                "top_characteristic_similarity_score": day_rows[0][
                    "characteristic_similarity_score"
                ],
                "top_rolling_corr_60d": day_rows[0]["rolling_corr_60d"],
                "top_non_price_pair_feature_count": day_rows[0][
                    "non_price_pair_feature_count"
                ],
                "top_peer_relative_vs_spy": day_rows[0]["peer_relative_vs_spy"],
                "top_candidate_signal_day_return": day_rows[0][
                    "candidate_signal_day_return"
                ],
            }
        )

    candidates.sort(key=_candidate_sort_key)
    scan.update(_threshold_audit(cfg))
    return candidates, peer_contexts, scan


def forward_horizon_summary(
    *,
    trades: list[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    horizons: tuple[int, ...] = (5, 10, 20),
    benchmarks: tuple[str, ...] = ("SPY", "QQQ"),
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = globals()["config"](config)
    rows_by_ticker = rc._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    indices = {ticker: rc._row_index(rows) for ticker, rows in rows_by_ticker.items()}
    by_horizon: dict[str, dict[str, Any]] = {}
    for horizon in horizons:
        rows_out: list[dict[str, Any]] = []
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            signal_date = _date10(trade.get("signal_date") or trade.get("date"))
            item = _forward_row(
                rows_by_ticker=rows_by_ticker,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
                horizon=horizon,
                benchmarks=benchmarks,
                config=cfg,
            )
            if item is not None:
                rows_out.append(item)
        by_horizon[str(horizon)] = _forward_stats(rows_out, benchmarks)
    return {
        "rule_version": RULE_VERSION,
        "known_at": "next_open_to_horizon_close_using_same OHLCV snapshot",
        "by_horizon": by_horizon,
    }


def write_candidate_rows_jsonl(path: Path | str, rows: list[dict[str, Any]]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(rc._safe(row), sort_keys=True) + "\n")


def _fundamental_features(self: CharacteristicSimilarityProvider, ticker: str, signal_date: str) -> dict[str, float | None]:
    if self.fundamental_index is None:
        return {
            "eps_yoy_growth": None,
            "revenue_yoy_growth": None,
            "operating_margin_current": None,
            "gross_margin": None,
            "liabilities_assets_ratio": None,
        }
    try:
        growth = self.fundamental_index.fundamental_context(ticker, signal_date)
    except Exception:
        growth = {}
    try:
        operating = self.fundamental_index.operating_quality(ticker, signal_date)
    except Exception:
        operating = {}
    try:
        gross = self.fundamental_index.gross_margin_quality(ticker, signal_date)
    except Exception:
        gross = {}
    try:
        balance = self.fundamental_index.balance_sheet_quality(ticker, signal_date)
    except Exception:
        balance = {}
    return {
        "eps_yoy_growth": _float_or_none(growth.get("eps_yoy_growth")),
        "revenue_yoy_growth": _float_or_none(growth.get("revenue_yoy_growth")),
        "operating_margin_current": _float_or_none(
            operating.get("operating_margin_current")
        ),
        "gross_margin": _float_or_none(gross.get("gross_margin")),
        "liabilities_assets_ratio": _float_or_none(
            balance.get("liabilities_assets_ratio")
        ),
    }


CharacteristicSimilarityProvider._fundamental_features = _fundamental_features


def _forward_row(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
    horizon: int,
    benchmarks: tuple[str, ...],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker) or []
    idx = indices.get(ticker, {}).get(signal_date)
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + int(horizon)
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = rc._value(rows[entry_idx], "open")
    exit_raw = rc._value(rows[exit_idx], "close")
    if entry_raw is None or exit_raw is None:
        return None
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct_net = (exit_price / entry_price) - 1.0 - float(config["round_trip_cost_pct"])
    notional = float(config["paper_notional_usd"])
    out = {
        "ticker": ticker,
        "signal_date": signal_date,
        "entry_date": rc._date(rows[entry_idx]),
        "exit_date": rc._date(rows[exit_idx]),
        "horizon": int(horizon),
        "pnl_pct_net": pnl_pct_net,
        "pnl": notional * pnl_pct_net,
    }
    for benchmark in benchmarks:
        bench_rows = rows_by_ticker.get(benchmark) or []
        bench_idx = indices.get(benchmark, {}).get(signal_date)
        if bench_idx is None:
            out[f"excess_vs_{benchmark.lower()}_pct"] = None
            out[f"excess_vs_{benchmark.lower()}_usd"] = None
            continue
        bench_entry = bench_idx + 1
        bench_exit = bench_idx + int(horizon)
        if bench_entry >= len(bench_rows) or bench_exit >= len(bench_rows):
            out[f"excess_vs_{benchmark.lower()}_pct"] = None
            out[f"excess_vs_{benchmark.lower()}_usd"] = None
            continue
        bench_open = rc._value(bench_rows[bench_entry], "open")
        bench_close = rc._value(bench_rows[bench_exit], "close")
        if bench_open is None or bench_close is None:
            out[f"excess_vs_{benchmark.lower()}_pct"] = None
            out[f"excess_vs_{benchmark.lower()}_usd"] = None
            continue
        bench_return = (bench_close / bench_open) - 1.0
        excess = pnl_pct_net - bench_return
        out[f"excess_vs_{benchmark.lower()}_pct"] = excess
        out[f"excess_vs_{benchmark.lower()}_usd"] = notional * excess
    return out


def _forward_stats(rows: list[dict[str, Any]], benchmarks: tuple[str, ...]) -> dict[str, Any]:
    count = len(rows)
    pnl = sum(float(row.get("pnl") or 0.0) for row in rows)
    winners = sum(1 for row in rows if float(row.get("pnl") or 0.0) > 0.0)
    out: dict[str, Any] = {
        "count": count,
        "net_pnl": _round(pnl, 2),
        "avg_pnl": _round(pnl / count, 2) if count else None,
        "avg_pnl_pct": _round(
            sum(float(row.get("pnl_pct_net") or 0.0) for row in rows) / count, 6
        )
        if count
        else None,
        "winner_count": winners,
        "win_rate": _round(winners / count, 6) if count else None,
    }
    for benchmark in benchmarks:
        key_pct = f"excess_vs_{benchmark.lower()}_pct"
        key_usd = f"excess_vs_{benchmark.lower()}_usd"
        values_pct = [
            float(row[key_pct]) for row in rows if row.get(key_pct) is not None
        ]
        values_usd = [
            float(row[key_usd]) for row in rows if row.get(key_usd) is not None
        ]
        out[f"count_vs_{benchmark.lower()}"] = len(values_pct)
        out[f"net_excess_vs_{benchmark.lower()}_usd"] = _round(sum(values_usd), 2)
        out[f"avg_excess_vs_{benchmark.lower()}_pct"] = (
            _round(sum(values_pct) / len(values_pct), 6) if values_pct else None
        )
        out[f"positive_excess_vs_{benchmark.lower()}_count"] = sum(
            1 for value in values_usd if value > 0
        )
    return out


def _mean_field_similarity(
    left: dict[str, Any],
    right: dict[str, Any],
    fields: list[tuple[str, float]],
) -> tuple[float | None, int]:
    scores = []
    for name, scale in fields:
        a = _float_or_none(left.get(name))
        b = _float_or_none(right.get(name))
        if a is None or b is None:
            continue
        scores.append(max(0.0, 1.0 - min(abs(a - b) / float(scale), 1.0)))
    if not scores:
        return None, 0
    return sum(scores) / len(scores), len(scores)


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    corr = _float_or_none(row.get("rolling_corr_60d"))
    return (
        str(row.get("date") or ""),
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("characteristic_similarity_score") or 0.0),
        abs(corr) if corr is not None else 999.0,
        -float(row.get("peer_relative_vs_spy") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("peer_ticker") or ""),
        str(row.get("ticker") or ""),
    )


def _threshold_audit(cfg: dict[str, Any]) -> dict[str, Any]:
    keys = [
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
        "min_characteristic_similarity",
        "max_prior_return_correlation",
        "min_non_price_pair_features",
    ]
    return {key: cfg[key] for key in keys}


def _coverage_count(row: dict[str, Any]) -> float | None:
    keys = [
        "analyst_coverage_count",
        "analyst_count",
        "analyst_count_current_qtr",
        "analyst_count_next_qtr",
        "current_analyst_count",
        "next_analyst_count",
        "estimate_count",
    ]
    values = [_float_or_none(row.get(key)) for key in keys]
    values = [value for value in values if value is not None]
    if values:
        return max(values)
    if row.get("estimate_revision_usable") is True:
        return 1.0
    return None


def _date10(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _round(value: Any, digits: int = 6) -> float | None:
    number = _float_or_none(value)
    if number is None:
        return None
    return round(number, digits)
