"""Gate 1-4 replay for the fixed SEC Form N-PORT entry-notional scalar.

The experiment changes one allocation variable after the accepted stack has
selected, enriched, filtered, and sized a core signal.  A PIT-safe N-PORT
annotation scales only the requested opening shares by 1.10 (accumulation),
0.90 (distribution), or 1.00 (missing/neutral).  Existing position caps remain
binding.  Candidate admission/ranking, exits, add-on policy, and the execution
cost model are not patched.

The runner deliberately reuses exp-20260712-015's frozen behavior inputs,
warehouse snapshots, earnings calendar, and active three-window raw baseline.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import inspect
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for path in (QUANT, EXPERIMENTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import backtester as bt  # noqa: E402
import portfolio_engine as pe  # noqa: E402
import sec_nport_share_accumulation as nport  # noqa: E402
import exp_20260712_015_post_mtm_gate1_baseline as baseline  # noqa: E402


EXPERIMENT_ID = "exp-20260715-009"
PROTOCOL_ID = "post_mtm_gate4_sec_nport_entry_notional_scalar_v1"
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
COMPACT_DIR = EXP_DIR / "nport_compact"
ARTIFACT = EXP_DIR / "sec_nport_entry_notional_scalar.json"
BASELINE_SUMMARY = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)

SCALAR_KEY = "sec_nport_entry_notional_scalar_applied"
POSITIVE_SCALAR = 1.10
NEGATIVE_SCALAR = 0.90
NEUTRAL_SCALAR = 1.00
MIN_MATCHED_SERIES = 20
REPORT_GAP_DAYS = (70, 110)
SPLIT_FACTOR_TOLERANCE = 0.05
PRICE_UNION_REL_TOLERANCE = 1e-6
EV_ACCEPTANCE_FLOOR = 13.4968
PNL_ACCEPTANCE_FLOOR = 237852.27
MAX_DRAWDOWN_DRIFT = 0.01

METRIC_KEYS = (
    "expected_value_score",
    "sharpe_daily",
    "total_pnl",
    "max_drawdown_pct",
    "worst_trade_pct",
    "tail_loss_share",
    "win_rate",
    "total_trades",
    "signals_generated",
    "signals_survived",
    "survival_rate",
)


class _FrozenPriceUnion:
    def __init__(
        self,
        rows_by_ticker: dict[str, tuple[tuple[str, float], ...]],
        identity: dict[str, Any],
    ) -> None:
        self.rows_by_ticker = rows_by_ticker
        self.identity = identity

    def lookup(self, ticker: str, report_date: str) -> float | None:
        rows = self.rows_by_ticker.get(str(ticker).upper()) or ()
        if not rows:
            return None
        dates = [row[0] for row in rows]
        index = bisect.bisect_right(dates, str(report_date)[:10]) - 1
        return rows[index][1] if index >= 0 else None


def _round(value: Any, digits: int = 6) -> Any:
    if value is None or isinstance(value, bool):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _runtime_dates(
    ticker: str,
) -> tuple[str | None, str | None]:
    """Mirror backtester's signal-to-opening-date lookup, without using price."""

    for frame_info in inspect.stack():
        local_vars = frame_info.frame.f_locals
        today = local_vars.get("today")
        all_dates = local_vars.get("all_dates")
        ohlcv_all = local_vars.get("ohlcv_all")
        if (
            today is None
            or not hasattr(today, "date")
            or not isinstance(all_dates, list)
            or not isinstance(ohlcv_all, dict)
        ):
            continue
        signal_date = str(today.date())
        ticker_frame = ohlcv_all.get(ticker)
        if ticker_frame is None:
            return signal_date, None
        future_dates = [day for day in all_dates if day > today]
        for opening_date in future_dates[:3]:
            if opening_date in ticker_frame.index:
                return signal_date, str(opening_date.date())
        return signal_date, None
    return None, None


def _annotation_value(annotation: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if annotation.get(key) is not None:
            return annotation[key]
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalize_annotation(annotation: dict[str, Any] | None) -> dict[str, Any]:
    """Bind the ticket's sign policy and verify the helper agrees exactly."""

    raw = dict(annotation or {})
    matched = _as_int(
        _annotation_value(
            raw,
            "matched_series_count",
            "continuous_series_count",
            "match_count",
        )
    )
    change = _as_float(
        _annotation_value(
            raw,
            "split_adjusted_share_change_pct",
            "aggregate_share_change_pct",
            "share_change_pct",
            "qoq_share_change_pct",
            "qoq_change",
        )
    )
    direction = str(
        _annotation_value(raw, "direction", "bucket", "status") or "missing"
    ).strip().lower()
    helper_scalar = _as_float(
        _annotation_value(raw, "notional_scalar", "entry_notional_scalar", "scalar")
    )

    if matched is None or matched < MIN_MATCHED_SERIES or change is None:
        expected_scalar = NEUTRAL_SCALAR
    elif change > 0:
        expected_scalar = POSITIVE_SCALAR
    elif change < 0:
        expected_scalar = NEGATIVE_SCALAR
    else:
        expected_scalar = NEUTRAL_SCALAR

    # Real helper annotations must carry the fixed scalar and match the sign
    # derived above.  Locally generated no-fill annotations have no rule_version.
    if raw.get("rule_version"):
        if helper_scalar not in {NEGATIVE_SCALAR, NEUTRAL_SCALAR, POSITIVE_SCALAR}:
            raise RuntimeError(f"helper emitted invalid N-PORT scalar: {helper_scalar}")
        if not math.isclose(float(helper_scalar), expected_scalar):
            raise RuntimeError(
                "helper N-PORT scalar disagrees with matched-series/change sign: "
                f"helper={helper_scalar}, expected={expected_scalar}, "
                f"matched={matched}, change={change}, direction={direction}"
            )
    scalar = expected_scalar

    if math.isclose(scalar, POSITIVE_SCALAR):
        bucket = "positive"
    elif math.isclose(scalar, NEGATIVE_SCALAR):
        bucket = "negative"
    else:
        bucket = "neutral_or_missing"

    return {
        **raw,
        "matched_series_count": matched,
        "split_adjusted_share_change_pct": change,
        "helper_notional_scalar": helper_scalar,
        "nport_bucket": bucket,
        "notional_scalar": scalar,
    }


def _compute_annotation(
    dataset: Any,
    action_date: str,
    ticker: str,
    raw_prices: Callable[[str, str], float | None],
) -> dict[str, Any]:
    annotation = nport.compute_share_accumulation(
        dataset,
        action_date=action_date,
        ticker=ticker,
        raw_prices=raw_prices,
        min_matched_series=MIN_MATCHED_SERIES,
    )
    if not isinstance(annotation, dict):
        raise TypeError("compute_share_accumulation must return a dict annotation")
    return _normalize_annotation(annotation)


def _assert_helper_policy() -> None:
    expected = {
        "MIN_MATCHED_SERIES": MIN_MATCHED_SERIES,
        "MIN_REPORT_GAP_DAYS": REPORT_GAP_DAYS[0],
        "MAX_REPORT_GAP_DAYS": REPORT_GAP_DAYS[1],
        "POSITIVE_SCALAR": POSITIVE_SCALAR,
        "NEGATIVE_SCALAR": NEGATIVE_SCALAR,
        "NEUTRAL_SCALAR": NEUTRAL_SCALAR,
        "SPLIT_FACTOR_TOLERANCE": SPLIT_FACTOR_TOLERANCE,
    }
    mismatches = {}
    for name, wanted in expected.items():
        actual = getattr(nport, name, None)
        if actual is None or not math.isclose(float(actual), float(wanted)):
            mismatches[name] = {"expected": wanted, "actual": actual}
    if mismatches:
        raise RuntimeError(f"shared N-PORT helper policy drift: {mismatches}")


def _scaled_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
) -> tuple[dict[str, Any], bool]:
    """Scale requested opening shares and recompute its notional/risk fields."""

    original_shares = _as_int(sizing.get("shares_to_buy")) or 0
    entry = _as_float(sizing.get("entry_price")) or 0.0
    if original_shares <= 0 or entry <= 0 or math.isclose(scalar, NEUTRAL_SCALAR):
        return sizing, False

    if scalar < 1.0:
        new_shares = max(1, int(math.floor(original_shares * scalar)))
    else:
        max_position_pct = _as_float(sizing.get("max_position_pct_applied"))
        if max_position_pct is None:
            max_position_pct = float(pe.MAX_POSITION_PCT)
        cap_shares = max(1, int(math.floor(portfolio_value * max_position_pct / entry)))
        new_shares = min(
            cap_shares,
            max(original_shares, int(math.floor(original_shares * scalar))),
        )

    out = dict(sizing)
    out[SCALAR_KEY] = scalar
    out["sec_nport_baseline_shares"] = original_shares
    out["sec_nport_requested_shares"] = new_shares
    if new_shares == original_shares:
        return out, False

    net_risk_per_share = _as_float(sizing.get("net_risk_per_share")) or 0.0
    position_value = entry * new_shares
    risk_amount = net_risk_per_share * new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(position_value, 2)
    out["position_pct_of_portfolio"] = (
        round(position_value / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(risk_amount, 2)
    out["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    return out, True


def _make_size_wrapper(
    original: Callable[..., list[dict[str, Any]]],
    dataset: Any,
    price_union: _FrozenPriceUnion,
    state: dict[str, Any],
) -> Callable[..., list[dict[str, Any]]]:
    cache: dict[tuple[str, str], dict[str, Any]] = {}

    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            if not ticker:
                continue
            signal_date, opening_date = _runtime_dates(ticker)
            if signal_date is None:
                raise RuntimeError("Could not resolve the backtest signal date")
            if opening_date is None:
                annotation = _normalize_annotation(
                    {"status": "missing", "reason": "no_future_fill_date"}
                )
            else:
                key = (opening_date, ticker)
                if key not in cache:
                    cache[key] = _compute_annotation(
                        dataset,
                        opening_date,
                        ticker,
                        price_union.lookup,
                    )
                annotation = cache[key]
            scalar = float(annotation["notional_scalar"])
            if annotation["nport_bucket"] in {"positive", "negative"}:
                coverage = annotation.get("raw_price_coverage_status")
                factor_sources = {
                    details.get("source")
                    for details in (annotation.get("split_factors") or {}).values()
                    if isinstance(details, dict)
                }
                if coverage not in {
                    "complete",
                    "insufficient_samples",
                    "provided_split_factors",
                } or (
                    "not_supplied" in factor_sources
                ):
                    raise RuntimeError(
                        "non-neutral N-PORT annotation lacks policy-valid frozen-price "
                        f"coverage: ticker={ticker}, opening={opening_date}, "
                        f"coverage={coverage}, factor_sources={sorted(factor_sources)}"
                    )
            sizing = signal.get("sizing") or {}
            baseline_shares = _as_int(sizing.get("shares_to_buy")) or 0
            adjusted, material = _scaled_sizing(sizing, scalar, portfolio_value)

            # Attribution fields are retained on the signal even when rounding or
            # an existing position cap makes a non-neutral scalar share-neutral.
            adjusted = dict(adjusted)
            adjusted[SCALAR_KEY] = scalar
            adjusted["sec_nport_bucket"] = annotation["nport_bucket"]
            adjusted["sec_nport_matched_series_count"] = annotation.get(
                "matched_series_count"
            )
            adjusted["sec_nport_split_adjusted_share_change_pct"] = annotation.get(
                "split_adjusted_share_change_pct"
            )
            signal["sizing"] = adjusted

            state["candidate_annotations"].append(
                {
                    "signal_date": signal_date,
                    "opening_execution_date": opening_date,
                    "ticker": ticker,
                    "strategy": signal.get("strategy"),
                    "bucket": annotation["nport_bucket"],
                    "notional_scalar": scalar,
                    "matched_series_count": annotation.get("matched_series_count"),
                    "split_adjusted_share_change_pct": annotation.get(
                        "split_adjusted_share_change_pct"
                    ),
                    "previous_report_date": _annotation_value(
                        annotation, "previous_report_date", "prior_report_date"
                    ),
                    "current_report_date": annotation.get("current_report_date"),
                    "split_factors": annotation.get("split_factors") or {},
                    "raw_price_coverage_status": annotation.get(
                        "raw_price_coverage_status"
                    ),
                    "baseline_shares": baseline_shares,
                    "requested_shares": adjusted.get("shares_to_buy"),
                    "material_share_change": material,
                }
            )
        return sized

    return wrapped


def _load_frozen_inputs() -> dict[str, Any]:
    payload = json.loads(baseline.FROZEN_INPUTS.read_text(encoding="utf-8"))
    if payload.get("behavior_sha256") != baseline._stable_hash(payload.get("behavior")):
        raise RuntimeError("exp-20260712-015 frozen behavior inputs failed identity check")
    return payload


def _run_after_window(
    spec: dict[str, str],
    frozen: dict[str, Any],
    dataset: Any,
    price_union: _FrozenPriceUnion,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    behavior = frozen["behavior"]
    calendar = baseline._calendar_dates(frozen)
    state: dict[str, Any] = {"candidate_annotations": []}
    engine = baseline.BacktestEngine(
        list(behavior["universe"]),
        start=spec["start"],
        end=spec["end"],
        config=baseline.RUN_CONFIG,
        ohlcv_warehouse_path=str(baseline.WAREHOUSE),
        ohlcv_warehouse_snapshot_source=spec["snapshot"],
        replay_llm=False,
        replay_news=False,
        include_pilot_sleeve=False,
        require_non_ohlcv=False,
        include_oracle_diagnostics=False,
    )
    engine._earnings_snapshots = behavior["earnings_snapshots"]
    engine._download_earnings_calendar = lambda: {
        ticker: list(values) for ticker, values in calendar.items()
    }

    original_size = pe.size_signals
    original_multiplier_keys = bt.SIZING_MULTIPLIER_KEYS
    pe.size_signals = _make_size_wrapper(original_size, dataset, price_union, state)
    if SCALAR_KEY not in original_multiplier_keys:
        bt.SIZING_MULTIPLIER_KEYS = (*original_multiplier_keys, SCALAR_KEY)
    try:
        result = engine.run()
    finally:
        pe.size_signals = original_size
        bt.SIZING_MULTIPLIER_KEYS = original_multiplier_keys

    if result.get("error"):
        raise RuntimeError(f"{spec['label']}: {result['error']}")
    identity = baseline._result_identity(result)
    identity["resolved_config_sha256"] = baseline._stable_hash(engine.config)
    identity["window"] = dict(spec)
    return result, identity, state


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    return {key: result.get(key) for key in METRIC_KEYS}


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in METRIC_KEYS:
        left = before.get(key)
        right = after.get(key)
        if (
            isinstance(left, (int, float))
            and not isinstance(left, bool)
            and isinstance(right, (int, float))
            and not isinstance(right, bool)
        ):
            out[key] = _round(float(right) - float(left))
        else:
            out[key] = None
    return out


def _bucket_counts(result: dict[str, Any]) -> dict[str, int]:
    counts = {"positive": 0, "negative": 0, "non_neutral": 0}
    for trade in result.get("trades") or []:
        scalar = _as_float((trade.get("sizing_multipliers") or {}).get(SCALAR_KEY))
        if scalar is None:
            continue
        counts["non_neutral"] += 1
        if math.isclose(scalar, POSITIVE_SCALAR):
            counts["positive"] += 1
        elif math.isclose(scalar, NEGATIVE_SCALAR):
            counts["negative"] += 1
    return counts


def _candidate_bucket_counts(state: dict[str, Any]) -> dict[str, int]:
    counts = {"positive": 0, "negative": 0, "neutral_or_missing": 0, "material": 0}
    for row in state["candidate_annotations"]:
        counts[row["bucket"]] += 1
        counts["material"] += int(bool(row["material_share_change"]))
    return counts


def _candidate_split_coverage_counts(state: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in state["candidate_annotations"]:
        status = str(row.get("raw_price_coverage_status") or "not_applicable")
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _executed_annotations(
    result: dict[str, Any], state: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Join planned opening-share attribution to positions that actually entered."""

    executed_keys = {
        (str(trade.get("ticker") or "").upper(), str(trade.get("entry_date") or "")[:10])
        for trade in result.get("trades") or []
    }
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in state["candidate_annotations"]:
        key = (row["ticker"], str(row.get("opening_execution_date") or "")[:10])
        if key in executed_keys:
            by_key.setdefault(key, row)
    rows = list(by_key.values())
    counts = {
        "positive": 0,
        "negative": 0,
        "neutral_or_missing": 0,
        "material_positive": 0,
        "material_negative": 0,
        "non_neutral_with_invalid_split_price_coverage": 0,
    }
    for row in rows:
        bucket = row["bucket"]
        counts[bucket] += 1
        if row["material_share_change"] and bucket == "positive":
            counts["material_positive"] += 1
        if row["material_share_change"] and bucket == "negative":
            counts["material_negative"] += 1
        if bucket in {"positive", "negative"}:
            factors = row.get("split_factors") or {}
            has_missing = any(
                details.get("source") == "not_supplied"
                for details in factors.values()
                if isinstance(details, dict)
            )
            coverage = row.get("raw_price_coverage_status")
            if has_missing or coverage not in {
                "complete",
                "insufficient_samples",
                "provided_split_factors",
            }:
                counts["non_neutral_with_invalid_split_price_coverage"] += 1
    return rows, counts


def _load_dataset() -> Any:
    if not COMPACT_DIR.exists():
        raise FileNotFoundError(f"Missing compact N-PORT directory: {COMPACT_DIR}")
    return nport.load_nport_rows(COMPACT_DIR)


def _compact_identity() -> dict[str, Any]:
    files = []
    for path in sorted(COMPACT_DIR.glob("*.json.gz")):
        files.append(
            {
                "path": _repo_rel(path),
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    return {
        "schema": "sec_nport_compact_identity_v1",
        "file_count": len(files),
        "files": files,
        "bundle_sha256": baseline._stable_hash(files),
    }


def _load_frozen_price_union() -> _FrozenPriceUnion:
    """Merge the three exp-015 snapshot JSON price histories without preference."""

    observations: dict[tuple[str, str], list[tuple[str, float]]] = {}
    sources = []
    for spec in baseline.WINDOWS:
        path = ROOT / spec["snapshot"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        sources.append(
            {
                "label": spec["label"],
                "path": _repo_rel(path),
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
        for ticker, rows in (payload.get("ohlcv") or {}).items():
            symbol = str(ticker).upper()
            for row in rows:
                date_text = str(row.get("Date") or "")[:10]
                close = _as_float(row.get("Close"))
                if date_text and close is not None:
                    observations.setdefault((symbol, date_text), []).append(
                        (_repo_rel(path), close)
                    )

    rows_by_ticker: dict[str, list[tuple[str, float]]] = {}
    hash_rows = []
    max_relative_difference = 0.0
    for (ticker, date_text), values in sorted(observations.items()):
        closes = [value for _, value in values]
        reference = closes[0]
        for source, value in values[1:]:
            difference = abs(value - reference) / max(abs(value), abs(reference), 1e-12)
            max_relative_difference = max(max_relative_difference, difference)
            if not math.isclose(
                value,
                reference,
                rel_tol=PRICE_UNION_REL_TOLERANCE,
                abs_tol=1e-6,
            ):
                raise RuntimeError(
                    "frozen snapshot Close disagreement: "
                    f"ticker={ticker}, date={date_text}, reference={reference}, "
                    f"value={value}, source={source}"
                )
        # Mean numerically equivalent observations so no source is preferred.
        consensus = math.fsum(closes) / len(closes)
        rows_by_ticker.setdefault(ticker, []).append((date_text, consensus))
        hash_rows.append([ticker, date_text, consensus, len(closes)])

    frozen_rows = {
        ticker: tuple(sorted(rows)) for ticker, rows in rows_by_ticker.items()
    }
    identity = {
        "schema": "exp_20260712_015_three_snapshot_adjusted_close_union_v1",
        "sources": sources,
        "source_count": len(sources),
        "ticker_count": len(frozen_rows),
        "row_count": len(hash_rows),
        "date_min": min((row[1] for row in hash_rows), default=None),
        "date_max": max((row[1] for row in hash_rows), default=None),
        "same_date_consensus_rule": (
            "Require all source Closes equal within rel_tol=1e-6/abs_tol=1e-6, "
            "then use their arithmetic mean; never prefer a source."
        ),
        "maximum_observed_relative_difference": max_relative_difference,
        "merged_surface_sha256": baseline._stable_hash(hash_rows),
        "lookup": "last consensus frozen Close on or before N-PORT report_date",
    }
    return _FrozenPriceUnion(frozen_rows, identity)


def build_artifact(selected_windows: set[str] | None = None) -> dict[str, Any]:
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    _assert_helper_policy()
    frozen = _load_frozen_inputs()
    dataset = _load_dataset()
    price_union = _load_frozen_price_union()
    baseline_summary = json.loads(BASELINE_SUMMARY.read_text(encoding="utf-8"))
    before_rows = {row["label"]: row for row in baseline_summary["windows"]}
    specs = [
        spec
        for spec in baseline.WINDOWS
        if selected_windows is None or spec["label"] in selected_windows
    ]
    if not specs:
        raise ValueError("No canonical windows selected")

    windows: dict[str, Any] = {}
    for spec in specs:
        label = spec["label"]
        before_row = before_rows[label]
        before_path = ROOT / before_row["path"]
        before_manifest = ROOT / before_row["manifest_path"]
        if _file_sha256(before_path) != before_row["artifact_sha256"]:
            raise RuntimeError(f"{label}: active Gate-1 raw baseline hash drifted")
        if _file_sha256(before_manifest) != before_row["manifest_sha256"]:
            raise RuntimeError(f"{label}: active Gate-1 manifest hash drifted")
        before_result = json.loads(before_path.read_text(encoding="utf-8"))
        after_result, after_identity, state = _run_after_window(
            spec, frozen, dataset, price_union
        )
        after_path = EXP_DIR / f"after_raw_{label}.json"
        baseline._atomic_write_json(
            after_path,
            baseline._persistable_backtest_result(after_result),
        )
        before_metrics = _metrics(before_result)
        after_metrics = _metrics(after_result)
        executed_rows, executed_material_counts = _executed_annotations(
            after_result, state
        )
        windows[label] = {
            "window": dict(spec),
            "split_price_surface": {
                **price_union.identity,
            },
            "before": before_metrics,
            "after": after_metrics,
            "delta": _delta(after_metrics, before_metrics),
            "before_raw": {
                "path": before_row["path"],
                "sha256": _file_sha256(before_path),
                "baseline_manifest_sha256": before_row["baseline_manifest_sha256"],
            },
            "after_raw": {
                "path": _repo_rel(after_path),
                "sha256": _file_sha256(after_path),
                "result_identity": after_identity,
            },
            "executed_bucket_counts": _bucket_counts(after_result),
            "executed_material_bucket_counts": executed_material_counts,
            "executed_annotations": executed_rows,
            "candidate_bucket_counts": _candidate_bucket_counts(state),
            "candidate_split_coverage_counts": _candidate_split_coverage_counts(
                state
            ),
            "candidate_annotations": state["candidate_annotations"],
        }

    complete = len(windows) == len(baseline.WINDOWS)
    aggregate = {
        "before_expected_value_score_sum": _round(
            sum(row["before"]["expected_value_score"] for row in windows.values())
        ),
        "after_expected_value_score_sum": _round(
            sum(row["after"]["expected_value_score"] for row in windows.values())
        ),
        "expected_value_score_sum_delta": _round(
            sum(row["delta"]["expected_value_score"] for row in windows.values())
        ),
        "before_total_pnl_sum": _round(
            sum(row["before"]["total_pnl"] for row in windows.values()), 2
        ),
        "after_total_pnl_sum": _round(
            sum(row["after"]["total_pnl"] for row in windows.values()), 2
        ),
        "total_pnl_sum_delta": _round(
            sum(row["delta"]["total_pnl"] for row in windows.values()), 2
        ),
        "before_trade_count_sum": sum(
            row["before"]["total_trades"] for row in windows.values()
        ),
        "after_trade_count_sum": sum(
            row["after"]["total_trades"] for row in windows.values()
        ),
    }

    checks = {
        "all_three_canonical_windows": complete,
        "aggregate_ev_above_fixed_10pct_floor": complete
        and aggregate["after_expected_value_score_sum"] > EV_ACCEPTANCE_FLOOR,
        "aggregate_pnl_above_baseline": complete
        and aggregate["after_total_pnl_sum"] > PNL_ACCEPTANCE_FLOOR,
        "no_window_ev_regression": all(
            row["delta"]["expected_value_score"] >= 0 for row in windows.values()
        ),
        "no_window_pnl_regression": all(
            row["delta"]["total_pnl"] >= 0 for row in windows.values()
        ),
        "max_drawdown_drift_lte_one_percentage_point": all(
            row["after"]["max_drawdown_pct"]
            <= row["before"]["max_drawdown_pct"] + MAX_DRAWDOWN_DRIFT
            for row in windows.values()
        ),
        "trade_counts_unchanged": all(
            row["delta"]["total_trades"] == 0 for row in windows.values()
        ),
        "signal_and_survival_counts_unchanged": all(
            row["delta"]["signals_generated"] == 0
            and row["delta"]["signals_survived"] == 0
            for row in windows.values()
        ),
        "positive_and_negative_material_executed_buckets_each_window": all(
            row["executed_material_bucket_counts"]["material_positive"] > 0
            and row["executed_material_bucket_counts"]["material_negative"] > 0
            for row in windows.values()
        ),
        "non_neutral_executions_have_policy_valid_split_price_coverage": all(
            row["executed_material_bucket_counts"][
                "non_neutral_with_invalid_split_price_coverage"
            ]
            == 0
            for row in windows.values()
        ),
    }
    gate4_passed = all(checks.values())
    artifact = {
        "schema": "sec_nport_entry_notional_scalar_gate4_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol_id": PROTOCOL_ID,
        "hypothesis": (
            "For an executed core company position with at least 20 continuously "
            "reporting N-PORT fund series, split-adjusted aggregate shares increasing "
            "quarter over quarter merit 1.10x opening notional, decreasing shares "
            "0.90x, and missing coverage 1.00x."
        ),
        "single_causal_variable": (
            "SEC N-PORT split-adjusted continuous-fund QoQ aggregate-share sign "
            "controls a fixed 1.10/0.90/1.00 opening-notional scalar."
        ),
        "parameters": {
            "positive_scalar": POSITIVE_SCALAR,
            "negative_scalar": NEGATIVE_SCALAR,
            "missing_or_neutral_scalar": NEUTRAL_SCALAR,
            "minimum_matched_series": MIN_MATCHED_SERIES,
            "report_gap_days_inclusive": list(REPORT_GAP_DAYS),
            "filing_date_rule": "strictly_before_opening_execution_date",
            "integer_split_factor_tolerance": SPLIT_FACTOR_TOLERANCE,
            "split_low_sample_fallback": (
                "When a report-date cross-section has fewer than 20 implied-price "
                "observations, the locked split factor is 1.0 and the signal remains eligible."
            ),
            "eligible_instruments": "UNIT=NS, ASSET_CAT=EC, PAYOFF_PROFILE=Long, company tickers",
        },
        "locked_behavior": {
            "candidate_admission": "unchanged",
            "candidate_ranking": "unchanged",
            "exits": "unchanged",
            "addon_policy": "unchanged",
            "execution_and_cost_model": "unchanged",
            "patched_surface": "post-sizing requested opening shares only",
            "existing_position_cap": "remains binding",
        },
        "baseline": {
            "summary_path": _repo_rel(BASELINE_SUMMARY),
            "summary_sha256": _file_sha256(BASELINE_SUMMARY),
            "experiment_id": baseline_summary["experiment_id"],
            "protocol_id": baseline_summary["protocol_id"],
            "frozen_behavior_input_path": _repo_rel(baseline.FROZEN_INPUTS),
            "frozen_behavior_input_sha256": _file_sha256(baseline.FROZEN_INPUTS),
            "frozen_behavior_sha256": frozen["behavior_sha256"],
        },
        "nport_compact_identity": _compact_identity(),
        "frozen_split_price_union": price_union.identity,
        "shared_helper": {
            "path": _repo_rel(ROOT / "quant" / "sec_nport_share_accumulation.py"),
            "sha256": _file_sha256(ROOT / "quant" / "sec_nport_share_accumulation.py"),
            "loader": "load_nport_rows",
            "annotation": "compute_share_accumulation",
        },
        "windows": windows,
        "aggregate": aggregate,
        "gate4": {
            "acceptance_floors": {
                "expected_value_score_sum_strictly_above": EV_ACCEPTANCE_FLOOR,
                "total_pnl_sum_strictly_above": PNL_ACCEPTANCE_FLOOR,
                "max_drawdown_drift_lte": MAX_DRAWDOWN_DRIFT,
            },
            "checks": checks,
            "passed": gate4_passed,
        },
        "decision": (
            "gate4_passed_pending_shared_daily_parity"
            if gate4_passed
            else "rejected_by_gate4"
            if complete
            else "partial_window_diagnostic_only"
        ),
        "production_impact": (
            "Experiment runner only. The shared helper is default-off and this runner "
            "does not alter live/default orders."
        ),
    }
    baseline._atomic_write_json(ARTIFACT, artifact)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--window",
        action="append",
        choices=[spec["label"] for spec in baseline.WINDOWS],
        help="Run one or more canonical windows; default runs all three.",
    )
    args = parser.parse_args()
    artifact = build_artifact(set(args.window) if args.window else None)
    print(json.dumps(
        {
            "experiment_id": EXPERIMENT_ID,
            "artifact": _repo_rel(ARTIFACT),
            "decision": artifact["decision"],
            "aggregate": artifact["aggregate"],
            "gate4": artifact["gate4"],
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
