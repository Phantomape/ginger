"""Deterministic all-surface capital allocator for exp-20260816-001.

The module is evaluation-only.  It reconstructs every strategy surface frozen
by exp-20260716-011, groups them by an outcome-blind source taxonomy, and
searches a capital-neutral allocation against the active cash-feasible core.
No production signal, ranking, sizing, exit, or order path imports this file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from quant import historical_current_contract_reassessment as reassess
from quant import portfolio_contribution_batch as pc
from scripts.experiment_fingerprint import infer_fingerprint


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ID = "exp-20260816-001"
WINDOWS = ("old_thin", "mid_weak", "late_strong")
BUCKETS = (
    "price_action",
    "fundamental_quality",
    "regulatory_event",
    "expectation_revision",
    "allocator_policy",
    "flow_positioning",
    "macro_derivatives",
    "other_cross_surface",
)
PORTFOLIO_CAPITAL_USD = 100_000.0
RECONSTRUCTION_CAPITAL_USD = 10_000.0
GLOBAL_STEP = 0.01
LOCAL_STEP = 0.0025
LOCAL_L1_RADIUS = 0.01
TOTAL_SATELLITE_CAP = 0.10
BUCKET_CAP = 0.05

MANIFEST_PATH = Path(
    "data/experiments/exp-20260716-011/historical_evidence_manifest.json"
)
MANIFEST_SHA256 = "ab1fceea636e1d3624c7ddbbd8ab40eb9b190760707ced313603932a80bf2007"
PANEL_PATH = Path("data/experiments/exp-20260716-011/historical_gate4p_panel.json")
PANEL_SHA256 = "4415600227868145f27e4f2769689bbe45d80fcf764425cf8adc6e410575ee94"
OHLCV_PATH = Path("data/experiments/exp-20260716-011/candidate_ohlcv_rowset.json.gz")
OHLCV_SHA256 = "b432672340b7dc2fdc05a08d561d6229c0c85827b05618cc9eeff3efb8ef4048"
FORWARD_PATH = Path("data/paper_sleeves/forward_replacement_value.jsonl")
FORWARD_SHA256 = "f577a0784bdb64664d1fb6e3504f8b9acc6cbe8053329d593214465f450d7f78"


SOURCE_BUCKETS = {
    "ohlcv_relation": "price_action",
    "ohlcv_momentum": "price_action",
    "kova_snapshot": "price_action",
    "regime_state": "price_action",
    "companyfacts_ratio": "fundamental_quality",
    "filing_timeliness": "fundamental_quality",
    "sec_text_event": "regulatory_event",
    "form4_insider": "regulatory_event",
    "sec13f_ownership": "regulatory_event",
    "sec13d_ownership": "regulatory_event",
    "sec_contract_relation": "regulatory_event",
    "dod_contract_award": "regulatory_event",
    "revision_expectation": "expectation_revision",
    "allocator": "allocator_policy",
    "finra_short_interest": "flow_positioning",
    "finra_ats_share": "flow_positioning",
    "finra_otc_internalization": "flow_positioning",
    "moomoo_short_volume": "flow_positioning",
    "moomoo_capital_flow": "flow_positioning",
    "microstructure_viability": "flow_positioning",
    "move_rate_volatility": "macro_derivatives",
    "credit_risk_etf": "macro_derivatives",
    "cboe_vvix": "macro_derivatives",
    "cboe_skew": "macro_derivatives",
    "cboe_ovx": "macro_derivatives",
    "chicago_fed_nfci": "macro_derivatives",
    "news_event_exposure": "other_cross_surface",
    "other": "other_cross_surface",
}


FORWARD_SLEEVE_BUCKETS = {
    "accepted_helper_source_priority_allocator": "allocator_policy",
    "accepted_source_consensus": "expectation_revision",
    "free_data_cross_source_consensus": "expectation_revision",
    "revision_surprise_low_extension": "expectation_revision",
    "alpha_score_market_regime": "price_action",
    "broad_market": "price_action",
    "distribution_day_absorption_leadership": "price_action",
    "industry_relative_laggard_repair": "price_action",
    "low_deployment_etf": "price_action",
    "state_surface": "price_action",
    "turn_of_month_liquid_leadership": "price_action",
    "volatility_contraction": "price_action",
    "volume_breadth_breakout": "price_action",
    "fundamental_growth_rs": "fundamental_quality",
    "sec_financial_report": "regulatory_event",
    "sec_governance": "regulatory_event",
    "sec_leadership": "regulatory_event",
    "sec_negative": "regulatory_event",
    "supplier_financing_debt_relief": "regulatory_event",
    "finra_otc_internalization": "flow_positioning",
    "moomoo_capital_flow": "flow_positioning",
}


def _repo_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with _repo_path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: str | Path) -> Any:
    return json.loads(_repo_path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, value: Any) -> None:
    target = _repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _serial(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _serial(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serial(item) for item in value]
    if isinstance(value, (np.floating, float)):
        return round(float(value), 12)
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def candidate_source(row: Mapping[str, Any]) -> str:
    fingerprint = infer_fingerprint(
        str(row.get("family") or ""),
        str(row.get("path") or ""),
        str(row.get("status") or ""),
        str(row.get("decision") or ""),
    )
    return str(fingerprint["data_source"])


def candidate_bucket(row: Mapping[str, Any]) -> str:
    source = candidate_source(row)
    if source not in SOURCE_BUCKETS:
        raise ValueError(f"unmapped candidate source: {source}")
    return SOURCE_BUCKETS[source]


def enumerate_global_vectors() -> Iterable[tuple[float, ...]]:
    """Enumerate the exact 1%-point grid, including the all-core null."""

    cap_units = round(BUCKET_CAP / GLOBAL_STEP)
    total_units = round(TOTAL_SATELLITE_CAP / GLOBAL_STEP)

    def visit(prefix: tuple[int, ...], remaining: int) -> Iterable[tuple[int, ...]]:
        if len(prefix) == len(BUCKETS):
            yield prefix
            return
        for units in range(min(cap_units, remaining) + 1):
            yield from visit((*prefix, units), remaining - units)

    for vector in visit((), total_units):
        yield tuple(round(units * GLOBAL_STEP, 10) for units in vector)


def enumerate_local_vectors(center: Sequence[float]) -> Iterable[tuple[float, ...]]:
    """Enumerate a fixed L1<=1%-point 0.25%-point neighborhood."""

    if len(center) != len(BUCKETS):
        raise ValueError("local center has wrong dimension")
    center_units = tuple(round(float(value) / LOCAL_STEP) for value in center)
    radius_units = round(LOCAL_L1_RADIUS / LOCAL_STEP)
    cap_units = round(BUCKET_CAP / LOCAL_STEP)
    total_units = round(TOTAL_SATELLITE_CAP / LOCAL_STEP)
    seen: set[tuple[int, ...]] = set()

    def visit(index: int, prefix: tuple[int, ...], l1_left: int) -> None:
        if index == len(BUCKETS):
            if sum(prefix) <= total_units:
                seen.add(prefix)
            return
        base = center_units[index]
        for delta in range(-l1_left, l1_left + 1):
            value = base + delta
            if 0 <= value <= cap_units:
                visit(index + 1, (*prefix, value), l1_left - abs(delta))

    visit(0, (), radius_units)
    for vector in sorted(seen):
        yield tuple(round(units * LOCAL_STEP, 10) for units in vector)


def _metric_delta(after: Mapping[str, Any], before: Mapping[str, Any]) -> dict[str, float]:
    keys = (
        "total_return_fraction",
        "total_pnl",
        "sharpe_daily",
        "expected_value_score",
        "max_drawdown_pct",
        "expected_shortfall_95",
    )
    return {key: float(after[key]) - float(before[key]) for key in keys}


def evaluate_weights(
    weights: Sequence[float],
    *,
    labels: Sequence[str],
    core_returns: Mapping[str, np.ndarray],
    bucket_returns: Mapping[str, Mapping[str, np.ndarray]],
) -> dict[str, Any]:
    values = np.asarray(weights, dtype=float)
    if len(values) != len(BUCKETS):
        raise ValueError("weight vector has wrong dimension")
    if np.any(values < -1e-12) or np.any(values > BUCKET_CAP + 1e-12):
        raise ValueError("weight vector violates bucket bounds")
    total_weight = float(values.sum())
    if total_weight > TOTAL_SATELLITE_CAP + 1e-12:
        raise ValueError("weight vector violates total bound")

    windows: dict[str, Any] = {}
    aggregate_ev_delta = 0.0
    aggregate_pnl_delta = 0.0
    material_regressions = 0
    max_drawdown_worsening = -math.inf
    max_es_worsening = -math.inf
    objective = 0.0
    for label in labels:
        core = np.asarray(core_returns[label], dtype=float)
        matrix = np.column_stack(
            [np.asarray(bucket_returns[bucket][label], dtype=float) for bucket in BUCKETS]
        )
        combined = (1.0 - total_weight) * core + matrix @ values
        core_metrics = reassess.current_return_metrics(core)
        combined_metrics = reassess.current_return_metrics(combined)
        delta = _metric_delta(combined_metrics, core_metrics)
        aggregate_ev_delta += delta["expected_value_score"]
        aggregate_pnl_delta += delta["total_pnl"]
        objective += float(combined_metrics["expected_value_score"])
        material = (
            delta["expected_value_score"]
            < -0.01 * abs(float(core_metrics["expected_value_score"]))
            and delta["total_pnl"] < 0.0
        )
        material_regressions += int(material)
        drawdown_worsening = delta["max_drawdown_pct"]
        core_es = float(core_metrics["expected_shortfall_95"])
        combined_es = float(combined_metrics["expected_shortfall_95"])
        es_worsening = (
            (combined_es - core_es) / core_es
            if core_es > 0.0
            else (0.0 if combined_es <= 0.0 else math.inf)
        )
        max_drawdown_worsening = max(max_drawdown_worsening, drawdown_worsening)
        max_es_worsening = max(max_es_worsening, es_worsening)
        windows[label] = {
            "core_metrics": core_metrics,
            "combined_metrics": combined_metrics,
            "delta_vs_core": delta,
            "material_regression": material,
            "es95_worsening_fraction": es_worsening,
        }

    checks = {
        "positive_aggregate_ev": aggregate_ev_delta > 0.0,
        "positive_aggregate_pnl": aggregate_pnl_delta > 0.0,
        "material_regressions_at_most_one": material_regressions <= 1,
        "drawdown_worsening_at_most_0p5pp": max_drawdown_worsening <= 0.005,
        "es95_worsening_at_most_5pct": max_es_worsening <= 0.05,
        "total_satellite_at_most_10pct": total_weight <= TOTAL_SATELLITE_CAP + 1e-12,
        "each_bucket_at_most_5pct": bool(np.all(values <= BUCKET_CAP + 1e-12)),
    }
    return {
        "weights": {bucket: float(value) for bucket, value in zip(BUCKETS, values)},
        "core_weight": 1.0 - total_weight,
        "satellite_weight": total_weight,
        "objective_ev_sum": objective,
        "aggregate_ev_delta": aggregate_ev_delta,
        "aggregate_pnl_delta": aggregate_pnl_delta,
        "material_regression_count": material_regressions,
        "max_drawdown_worsening": max_drawdown_worsening,
        "max_es95_worsening_fraction": max_es_worsening,
        "checks": checks,
        "feasible": all(checks.values()),
        "windows": windows,
    }


def _rank_key(result: Mapping[str, Any]) -> tuple[Any, ...]:
    weights = result["weights"]
    return (
        -float(result["objective_ev_sum"]),
        -float(result["aggregate_pnl_delta"]),
        float(result["max_drawdown_worsening"]),
        tuple(float(weights[bucket]) for bucket in BUCKETS),
    )


def optimize_vectors(
    vectors: Iterable[Sequence[float]],
    *,
    labels: Sequence[str],
    core_returns: Mapping[str, np.ndarray],
    bucket_returns: Mapping[str, Mapping[str, np.ndarray]],
) -> dict[str, Any]:
    scanned = 0
    feasible = 0
    best_feasible: dict[str, Any] | None = None
    best_unconstrained: dict[str, Any] | None = None
    best_nonzero: dict[str, Any] | None = None
    null_result: dict[str, Any] | None = None
    for vector in vectors:
        result = evaluate_weights(
            vector,
            labels=labels,
            core_returns=core_returns,
            bucket_returns=bucket_returns,
        )
        scanned += 1
        if all(abs(float(value)) <= 1e-12 for value in vector):
            null_result = result
        if best_unconstrained is None or _rank_key(result) < _rank_key(best_unconstrained):
            best_unconstrained = result
        if any(abs(float(value)) > 1e-12 for value in vector):
            if best_nonzero is None or _rank_key(result) < _rank_key(best_nonzero):
                best_nonzero = result
        if result["feasible"]:
            feasible += 1
            if best_feasible is None or _rank_key(result) < _rank_key(best_feasible):
                best_feasible = result
    if null_result is None:
        null_result = evaluate_weights(
            [0.0] * len(BUCKETS),
            labels=labels,
            core_returns=core_returns,
            bucket_returns=bucket_returns,
        )
    return {
        "scanned_vector_count": scanned,
        "feasible_vector_count": feasible,
        "best_feasible": best_feasible,
        "best_unconstrained": best_unconstrained,
        "best_nonzero": best_nonzero,
        "selected": best_feasible or null_result,
        "fallback_to_null_core": best_feasible is None,
    }


def reconstruct_all_surfaces() -> dict[str, Any]:
    expected_hashes = {
        MANIFEST_PATH.as_posix(): MANIFEST_SHA256,
        PANEL_PATH.as_posix(): PANEL_SHA256,
        OHLCV_PATH.as_posix(): OHLCV_SHA256,
        FORWARD_PATH.as_posix(): FORWARD_SHA256,
    }
    actual_hashes = {path: _sha256_file(path) for path in expected_hashes}
    mismatches = {
        path: {"expected": expected_hashes[path], "actual": actual_hashes[path]}
        for path in expected_hashes
        if expected_hashes[path] != actual_hashes[path]
    }
    if mismatches:
        raise ValueError(f"frozen input hash mismatch: {mismatches}")

    manifest = _read_json(MANIFEST_PATH)
    candidates = manifest.get("eligible_candidates") or []
    if len(candidates) != 480:
        raise ValueError(f"expected 480 eligible candidates, found {len(candidates)}")
    _, calendars, core_returns, core_identity = reassess.load_active_core()
    _, payload_by_id = reassess._load_candidate_payloads(candidates)
    ohlcv_rows, ohlcv_identity = reassess._load_ohlcv_snapshot(
        OHLCV_PATH,
        expected_experiment_id="exp-20260716-011",
        expected_gzip_sha256=OHLCV_SHA256,
    )
    price_map = pc._price_map_from_rows(ohlcv_rows)

    members: defaultdict[str, list[str]] = defaultdict(list)
    sources: Counter[str] = Counter()
    candidate_returns: dict[str, dict[str, np.ndarray]] = {}
    candidate_contributions: dict[str, list[tuple[str, float]]] = {}
    allocation_diagnostics: dict[str, Any] = {}
    candidate_metadata: dict[str, Any] = {}
    for row in sorted(candidates, key=lambda item: str(item["candidate_id"])):
        candidate_id = str(row["candidate_id"])
        source = candidate_source(row)
        bucket = candidate_bucket(row)
        sources[source] += 1
        members[bucket].append(candidate_id)
        candidate_metadata[candidate_id] = {
            "bucket": bucket,
            "source": source,
            "family": row.get("family"),
            "path": row.get("path"),
            "trade_surface_sha256": row.get("trade_surface_sha256"),
        }
        surface = payload_by_id[candidate_id]["target_trades_by_window"]
        by_window: dict[str, np.ndarray] = {}
        contributions: list[tuple[str, float]] = []
        window_diagnostics: dict[str, Any] = {}
        for window in WINDOWS:
            allocation = pc.allocate_sleeve_capital(
                surface[window],
                calendars[window],
                sleeve_capital=RECONSTRUCTION_CAPITAL_USD,
                price_map=price_map,
            )
            if not allocation.get("cash_nonnegative"):
                raise ValueError(f"negative candidate cash: {candidate_id}/{window}")
            if not allocation.get("ending_all_positions_settled"):
                raise ValueError(f"unsettled candidate position: {candidate_id}/{window}")
            pnl_by_day: defaultdict[date, float] = defaultdict(float)
            usable = 0
            for trade in allocation["allocated_rows"]:
                daily, diagnostic = pc.reconstruct_trade_daily_pnl(
                    trade, calendars[window], price_map
                )
                if not diagnostic.get("usable"):
                    continue
                usable += 1
                ticker = str(diagnostic["ticker"])
                contributions.append((ticker, float(diagnostic["net_pnl"])))
                for day, pnl in daily.items():
                    pnl_by_day[day] += float(pnl)
            by_window[window] = pc.pnl_to_returns(
                pnl_by_day,
                calendars[window],
                initial_capital=RECONSTRUCTION_CAPITAL_USD,
            )
            window_diagnostics[window] = {
                "source_trade_count": len(surface[window]),
                "allocated_trade_count": len(allocation["allocated_rows"]),
                "usable_trade_count": usable,
                "cash_nonnegative": True,
                "ending_all_positions_settled": True,
                "min_cash_usd": float(allocation["min_cash_usd"]),
            }
        candidate_returns[candidate_id] = by_window
        candidate_contributions[candidate_id] = contributions
        allocation_diagnostics[candidate_id] = window_diagnostics

    if set(members) != set(BUCKETS) or sum(map(len, members.values())) != 480:
        raise ValueError("bucket coverage is not complete and exclusive")
    bucket_returns: dict[str, dict[str, np.ndarray]] = {}
    for bucket in BUCKETS:
        bucket_returns[bucket] = {}
        for window in WINDOWS:
            bucket_returns[bucket][window] = np.mean(
                np.vstack(
                    [candidate_returns[candidate_id][window] for candidate_id in members[bucket]]
                ),
                axis=0,
            )

    return {
        "calendars": calendars,
        "core_returns": core_returns,
        "bucket_returns": bucket_returns,
        "members": dict(members),
        "source_counts": dict(sorted(sources.items())),
        "candidate_contributions": candidate_contributions,
        "candidate_metadata": candidate_metadata,
        "allocation_diagnostics": allocation_diagnostics,
        "input_identity": {
            "hashes": actual_hashes,
            "core": core_identity,
            "ohlcv": ohlcv_identity,
            "candidate_count": len(candidates),
        },
    }


def ticker_concentration(
    weights: Mapping[str, float],
    *,
    members: Mapping[str, Sequence[str]],
    candidate_contributions: Mapping[str, Sequence[tuple[str, float]]],
) -> dict[str, Any]:
    core_payloads, _, _, _ = reassess.load_active_core()
    satellite_weight = sum(float(value) for value in weights.values())
    rows: list[tuple[str, float]] = []
    for window in WINDOWS:
        for trade in core_payloads[window].get("trades") or []:
            ticker = str(trade.get("ticker") or "").strip().upper()
            pnl = reassess._finite(trade.get("pnl"))
            if ticker and pnl is not None:
                rows.append((ticker, (1.0 - satellite_weight) * pnl))
    for bucket in BUCKETS:
        bucket_weight = float(weights[bucket])
        if bucket_weight <= 0.0:
            continue
        member_ids = list(members[bucket])
        scale = (
            bucket_weight
            * PORTFOLIO_CAPITAL_USD
            / RECONSTRUCTION_CAPITAL_USD
            / len(member_ids)
        )
        for candidate_id in member_ids:
            rows.extend(
                (ticker, scale * pnl)
                for ticker, pnl in candidate_contributions[candidate_id]
            )
    result = pc._concentration(rows)
    result["checks"] = {
        "single_ticker_positive_share_at_most_50pct": (
            result["single_ticker_positive_share"] is not None
            and float(result["single_ticker_positive_share"]) <= 0.50
        ),
        "top_5_contribution_at_most_60pct": (
            result["top_5_contribution_pct"] is not None
            and float(result["top_5_contribution_pct"]) <= 0.60
        ),
        "hhi_at_most_0p35": (
            result["hhi_concentration"] is not None
            and float(result["hhi_concentration"]) <= 0.35
        ),
    }
    result["passed"] = all(result["checks"].values())
    return result


def recent_forward_diagnostic(weights: Mapping[str, float]) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in _repo_path(FORWARD_PATH).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 196 or len({row["decision_id"] for row in rows}) != len(rows):
        raise ValueError("forward replacement ledger identity changed")
    unknown = sorted({str(row["sleeve_key"]) for row in rows} - set(FORWARD_SLEEVE_BUCKETS))
    if unknown:
        raise ValueError(f"unmapped recent sleeves: {unknown}")

    sleeve_totals: defaultdict[str, dict[str, float]] = defaultdict(
        lambda: {"notional": 0.0, "pnl": 0.0, "spy": 0.0, "qqq": 0.0, "rows": 0.0}
    )
    dates: list[str] = []
    for row in rows:
        sleeve = str(row["sleeve_key"])
        item = sleeve_totals[sleeve]
        item["notional"] += float(row["notional_usd"])
        item["pnl"] += float(row["replacement_value_vs_cash_usd"])
        item["spy"] += float(row["replacement_value_vs_spy_usd"])
        item["qqq"] += float(row["replacement_value_vs_qqq_usd"])
        item["rows"] += 1.0
        dates.extend([str(row["entry_date"]), str(row["exit_date"])])

    by_bucket: defaultdict[str, list[dict[str, float]]] = defaultdict(list)
    sleeve_rows: dict[str, Any] = {}
    for sleeve, totals in sorted(sleeve_totals.items()):
        if totals["notional"] <= 0.0:
            raise ValueError(f"nonpositive recent notional: {sleeve}")
        values = {
            "row_count": int(totals["rows"]),
            "notional_usd": totals["notional"],
            "return_vs_cash": totals["pnl"] / totals["notional"],
            "return_vs_spy": totals["spy"] / totals["notional"],
            "return_vs_qqq": totals["qqq"] / totals["notional"],
        }
        bucket = FORWARD_SLEEVE_BUCKETS[sleeve]
        sleeve_rows[sleeve] = {"bucket": bucket, **values}
        by_bucket[bucket].append(values)

    bucket_rows: dict[str, Any] = {}
    for bucket in BUCKETS:
        values = by_bucket.get(bucket, [])
        bucket_rows[bucket] = {
            "sleeve_count": len(values),
            "row_count": sum(int(item["row_count"]) for item in values),
            "return_vs_cash": (
                float(np.mean([item["return_vs_cash"] for item in values]))
                if values else None
            ),
            "return_vs_spy": (
                float(np.mean([item["return_vs_spy"] for item in values]))
                if values else None
            ),
            "return_vs_qqq": (
                float(np.mean([item["return_vs_qqq"] for item in values]))
                if values else None
            ),
        }

    selected_buckets = [bucket for bucket in BUCKETS if float(weights[bucket]) > 0.0]
    missing = [bucket for bucket in selected_buckets if bucket_rows[bucket]["return_vs_cash"] is None]
    contributions = {
        comparator: PORTFOLIO_CAPITAL_USD * sum(
            float(weights[bucket]) * float(bucket_rows[bucket][f"return_vs_{comparator}"])
            for bucket in selected_buckets
            if bucket_rows[bucket][f"return_vs_{comparator}"] is not None
        )
        for comparator in ("cash", "spy", "qqq")
    }

    covered_returns = np.asarray(
        [
            float(bucket_rows[bucket]["return_vs_cash"])
            if bucket_rows[bucket]["return_vs_cash"] is not None
            else -math.inf
            for bucket in BUCKETS
        ]
    )
    recent_best_vector: tuple[float, ...] | None = None
    recent_best_value = -math.inf
    scanned = 0
    for vector in enumerate_global_vectors():
        values = np.asarray(vector, dtype=float)
        if np.any((values > 0.0) & ~np.isfinite(covered_returns)):
            continue
        value = float(values @ np.where(np.isfinite(covered_returns), covered_returns, 0.0))
        scanned += 1
        if value > recent_best_value + 1e-15 or (
            math.isclose(value, recent_best_value, abs_tol=1e-15)
            and (recent_best_vector is None or tuple(vector) < recent_best_vector)
        ):
            recent_best_value = value
            recent_best_vector = tuple(vector)

    return {
        "period": {"start": min(dates), "end": max(dates)},
        "row_count": len(rows),
        "sleeve_count": len(sleeve_totals),
        "bucket_diagnostics": bucket_rows,
        "sleeve_diagnostics": sleeve_rows,
        "selected_weights": dict(weights),
        "selected_bucket_coverage_complete": not missing,
        "selected_missing_buckets": missing,
        "selected_inferred_contribution_usd": contributions,
        "selected_nonnegative_vs_cash": contributions["cash"] >= 0.0,
        "recent_hindsight_best_1pct_grid": {
            "weights": {
                bucket: float(value)
                for bucket, value in zip(BUCKETS, recent_best_vector or ())
            },
            "inferred_contribution_vs_cash_usd": PORTFOLIO_CAPITAL_USD * recent_best_value,
            "scanned_covered_vector_count": scanned,
            "interpretation": "descriptive hindsight only; not used by the classic selector",
        },
    }


def _walk_forward(
    *,
    core_returns: Mapping[str, np.ndarray],
    bucket_returns: Mapping[str, Mapping[str, np.ndarray]],
) -> list[dict[str, Any]]:
    folds = [
        (("old_thin",), "mid_weak"),
        (("old_thin", "mid_weak"), "late_strong"),
    ]
    results: list[dict[str, Any]] = []
    for train, test in folds:
        global_search = optimize_vectors(
            enumerate_global_vectors(),
            labels=train,
            core_returns=core_returns,
            bucket_returns=bucket_returns,
        )
        center = tuple(
            float(global_search["selected"]["weights"][bucket]) for bucket in BUCKETS
        )
        local_search = optimize_vectors(
            enumerate_local_vectors(center),
            labels=train,
            core_returns=core_returns,
            bucket_returns=bucket_returns,
        )
        selected = local_search["selected"]
        selected_vector = tuple(float(selected["weights"][bucket]) for bucket in BUCKETS)
        oos = evaluate_weights(
            selected_vector,
            labels=(test,),
            core_returns=core_returns,
            bucket_returns=bucket_returns,
        )
        passed = (
            not global_search["fallback_to_null_core"]
            and not local_search["fallback_to_null_core"]
            and oos["aggregate_ev_delta"] >= 0.0
            and oos["aggregate_pnl_delta"] >= 0.0
        )
        results.append(
            {
                "train_windows": list(train),
                "test_window": test,
                "global_search": global_search,
                "local_search": local_search,
                "oos_result": oos,
                "passed": passed,
            }
        )
    return results


def run(output_dir: str | Path) -> dict[str, Any]:
    reconstructed = reconstruct_all_surfaces()
    core_returns = reconstructed["core_returns"]
    bucket_returns = reconstructed["bucket_returns"]

    global_search = optimize_vectors(
        enumerate_global_vectors(),
        labels=WINDOWS,
        core_returns=core_returns,
        bucket_returns=bucket_returns,
    )
    global_vector = tuple(
        float(global_search["selected"]["weights"][bucket]) for bucket in BUCKETS
    )
    local_search = optimize_vectors(
        enumerate_local_vectors(global_vector),
        labels=WINDOWS,
        core_returns=core_returns,
        bucket_returns=bucket_returns,
    )
    selected = local_search["selected"]
    selected_weights = {bucket: float(selected["weights"][bucket]) for bucket in BUCKETS}
    concentration = ticker_concentration(
        selected_weights,
        members=reconstructed["members"],
        candidate_contributions=reconstructed["candidate_contributions"],
    )
    walk_forward = _walk_forward(
        core_returns=core_returns,
        bucket_returns=bucket_returns,
    )
    recent = recent_forward_diagnostic(selected_weights)
    single_bucket_diagnostics = {
        bucket: evaluate_weights(
            tuple(0.05 if candidate == bucket else 0.0 for candidate in BUCKETS),
            labels=WINDOWS,
            core_returns=core_returns,
            bucket_returns=bucket_returns,
        )
        for bucket in BUCKETS
    }
    formal_checks = {
        "classic_gate_feasible": bool(selected["feasible"]),
        "global_positive_vector_exists": not global_search["fallback_to_null_core"],
        "local_positive_vector_exists": not local_search["fallback_to_null_core"],
        "ticker_concentration_caps_pass": bool(concentration["passed"]),
        "walk_forward_all_folds_pass": all(row["passed"] for row in walk_forward),
        "recent_selected_bucket_coverage_complete": bool(
            recent["selected_bucket_coverage_complete"]
        ),
        "recent_selected_nonnegative_vs_cash": bool(recent["selected_nonnegative_vs_cash"]),
    }
    passed = all(formal_checks.values())

    result = {
        "schema": "ginger.joint_strategy_allocator.v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "decision": "observed_only" if passed else "rejected",
        "result_ceiling": "observed_only",
        "trade_enabled": False,
        "selection_contract": {
            "candidate_count": 480,
            "buckets": list(BUCKETS),
            "within_bucket_weighting": "equal weight across unique frozen strategy paths",
            "global_grid_step": GLOBAL_STEP,
            "local_grid_step": LOCAL_STEP,
            "local_l1_radius": LOCAL_L1_RADIUS,
            "total_satellite_cap": TOTAL_SATELLITE_CAP,
            "bucket_cap": BUCKET_CAP,
            "formal_windows": list(WINDOWS),
            "recent_use": "post-selection observe-only contradiction diagnostic",
        },
        "input_identity": reconstructed["input_identity"],
        "source_counts": reconstructed["source_counts"],
        "bucket_members": reconstructed["members"],
        "global_search": global_search,
        "local_search": local_search,
        "selected_allocation": selected,
        "ticker_concentration": concentration,
        "walk_forward": walk_forward,
        "single_bucket_5pct_diagnostics": single_bucket_diagnostics,
        "recent_forward_diagnostic": recent,
        "formal_checks": formal_checks,
        "passed": passed,
        "limitations": [
            "The 480-surface history is research_pit because adaptive selection history is incomplete.",
            "Classic windows have been reused by earlier experiments and are not untouched holdouts.",
            "Bucket paths are daily constant-weight composites; arbitrary strategy-level weights were not searched.",
            "Recent forward rows are settled-trade returns, not a complete daily MTM covariance panel.",
            "A positive result cannot alter production allocation or orders.",
        ],
    }

    output = _repo_path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    full_path = output / "joint_strategy_allocator_result.json"
    _write_json(full_path, _serial(result))

    core_metrics = {
        window: reassess.current_return_metrics(core_returns[window]) for window in WINDOWS
    }
    core_ev = sum(float(row["expected_value_score"]) for row in core_metrics.values())
    core_pnl = sum(float(row["total_pnl"]) for row in core_metrics.values())
    core_return_pct = 100.0 * sum(
        float(row["total_return_fraction"]) for row in core_metrics.values()
    )
    before = {
        "schema": "ginger.joint_strategy_allocator.measurement.v1",
        "experiment_id": EXPERIMENT_ID,
        "role": "before_100pct_cash_feasible_core",
        "expected_value_score": core_ev,
        "sharpe_daily": None,
        "total_pnl": core_pnl,
        "max_drawdown_pct": max(float(row["max_drawdown_pct"]) for row in core_metrics.values()),
        "total_trades": 49,
        "survival_rate": 0.8116,
        "benchmarks": {"strategy_total_return_pct": core_return_pct},
        "windows": core_metrics,
    }
    after_windows = {
        window: selected["windows"][window]["combined_metrics"] for window in WINDOWS
    }
    after = {
        "schema": "ginger.joint_strategy_allocator.measurement.v1",
        "experiment_id": EXPERIMENT_ID,
        "role": "after_selected_joint_allocation",
        "expected_value_score": sum(
            float(row["expected_value_score"]) for row in after_windows.values()
        ),
        "sharpe_daily": None,
        "total_pnl": sum(float(row["total_pnl"]) for row in after_windows.values()),
        "max_drawdown_pct": max(
            float(row["max_drawdown_pct"]) for row in after_windows.values()
        ),
        "total_trades": 49,
        "survival_rate": 0.8116,
        "benchmarks": {
            "strategy_total_return_pct": 100.0
            * sum(float(row["total_return_fraction"]) for row in after_windows.values())
        },
        "windows": after_windows,
        "selected_weights": selected_weights,
        "formal_checks": formal_checks,
        "custom_gate_passed": passed,
        "result_artifact": str(full_path.relative_to(REPO_ROOT)).replace("\\", "/"),
    }
    _write_json(output / "before_measurement.json", _serial(before))
    _write_json(output / "after_measurement.json", _serial(after))

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "decision": result["decision"],
        "result_ceiling": "observed_only",
        "candidate_count": 480,
        "bucket_counts": {bucket: len(reconstructed["members"][bucket]) for bucket in BUCKETS},
        "selected_weights": selected_weights,
        "core_weight": selected["core_weight"],
        "aggregate_ev_delta": selected["aggregate_ev_delta"],
        "aggregate_pnl_delta": selected["aggregate_pnl_delta"],
        "global_vectors_scanned": global_search["scanned_vector_count"],
        "local_vectors_scanned": local_search["scanned_vector_count"],
        "formal_checks": formal_checks,
        "recent_selected_contribution": recent["selected_inferred_contribution_usd"],
        "recent_hindsight_best": recent["recent_hindsight_best_1pct_grid"],
        "best_nonzero_global": global_search["best_nonzero"],
        "best_nonzero_local": local_search["best_nonzero"],
        "result_artifact": str(full_path.relative_to(REPO_ROOT)).replace("\\", "/"),
    }
    _write_json(output / "summary.json", _serial(summary))
    return _serial(summary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", default=f"data/experiments/{EXPERIMENT_ID}"
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
