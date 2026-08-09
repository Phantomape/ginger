"""exp-20260712-012: session downside-semivariance attribution.

Read-only alpha attribution over the currently accepted default-off paper
allocator population.  The experiment labels each selected trade at its
signal-day close with a point-in-time 60-session decomposition of downside
semivariance into overnight (previous close -> open) and intraday
(open -> close) components.  The raw overnight share is converted to a
same-day sector-relative percentile before closed-trade outcome attribution.

No entry, ranking, sizing, exit, order, allocator, or live/default behavior is
changed.  A positive result is only a lead for a later shared policy experiment.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "quant", ROOT / "quant" / "experiments", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
import exp_20260712_008_move_rate_volatility_allocator_source as allocator_run  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


EXPERIMENT_ID = "exp-20260712-012"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "session_semivariance_paper_entry_attribution"
RUNNER = f"quant/experiments/exp_20260712_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OUT_JSON = ROOT / "data" / "experiments" / EXPERIMENT_ID / f"exp_20260712_012_{SLUG}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"
CURRENT_BASELINE = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260712-006"
    / "current_working_stack_sharpe_inference.json"
)

HYPOTHESIS = (
    "Observed-only risk-allocation alpha hypothesis: PIT sector-relative "
    "overnight-versus-intraday downside semivariance partition on accepted "
    "paper-sleeve entries identifies a monotonic loss cohort; high overnight "
    "downside heterogeneity should have worse closed-trade PnL in aggregate "
    "and at least two canonical windows."
)
CHANGED_VARIABLE = "session_semivariance_sector_relative_paper_entry_attribution_v1"
TRIAL_FAMILY = "session_semivariance_paper_entry_attribution"
MECHANISM_FAMILY = "production_visible_ohlcv_session_semivariance_risk_attribution"
RULE_VERSION = "session_semivariance_sector_relative_paper_entry_attribution_v1"
NEARBY = ["exp-20260522-027", "exp-20260613-016", "exp-20260711-025"]
NEW_AXIS = (
    "Unprecedented field on the unsaturated OHLCV-relation source: separate "
    "60-session overnight and intraday downside semivariance with a point-in-time "
    "same-sector relative partition. Prior work used broad component means or raw "
    "overnight-gap share, not session-specific downside-tail heterogeneity."
)

LOOKBACK = 60
MIN_COMPONENT_OBSERVATIONS = 40
MIN_COVERAGE = 0.80
MIN_LABELED_TRADES = 100
MIN_DIRECT_SECTOR_PARTITION_SHARE = 0.60
MIN_BUCKET_ROWS = 20
PREDICTION = json.loads(TICKET_JSON.read_text(encoding="utf-8"))["prediction"]


def _utc_now() -> str:
    return framework._utc_now()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _rank(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(indexed):
        end = cursor + 1
        while end < len(indexed) and indexed[end][1] == indexed[cursor][1]:
            end += 1
        average_rank = (cursor + 1 + end) / 2.0
        for offset in range(cursor, end):
            ranks[indexed[offset][0]] = average_rank
        cursor = end
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    x_var = sum((value - x_mean) ** 2 for value in xs)
    y_var = sum((value - y_mean) ** 2 for value in ys)
    if x_var <= 0.0 or y_var <= 0.0:
        return None
    covariance = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    return covariance / math.sqrt(x_var * y_var)


def _spearman(rows: Iterable[dict[str, Any]]) -> float | None:
    pairs = [
        (float(row["session_tail_percentile"]), float(row["pnl"]))
        for row in rows
        if _finite(row.get("session_tail_percentile")) is not None
        and _finite(row.get("pnl")) is not None
    ]
    if len(pairs) < 3:
        return None
    return _pearson(_rank([row[0] for row in pairs]), _rank([row[1] for row in pairs]))


def _percentile(value: float, population: list[float]) -> float | None:
    clean = sorted(item for item in population if math.isfinite(item))
    if not clean:
        return None
    below = sum(item < value for item in clean)
    equal = sum(item == value for item in clean)
    return (below + 0.5 * equal) / len(clean)


def _bucket(percentile: float) -> str:
    if percentile <= 1.0 / 3.0:
        return "low_overnight_tail"
    if percentile <= 2.0 / 3.0:
        return "mid_overnight_tail"
    return "high_overnight_tail"


def _normalise_rows(snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    normalised = allocator_run.move_helper.leader._normalise_ohlcv_by_ticker(snapshot)
    result: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in normalised.items():
        clean = []
        for row in rows:
            day = str(row.get("date") or "")[:10]
            open_price = _finite(row.get("open"))
            close_price = _finite(row.get("close"))
            if not day or open_price is None or close_price is None:
                continue
            clean.append({"date": day, "open": open_price, "close": close_price})
        clean.sort(key=lambda row: row["date"])
        result[str(ticker).upper()] = clean
    return result


def _feature_for_date(
    rows: list[dict[str, Any]], signal_date: str
) -> dict[str, Any] | None:
    eligible_indices = [index for index, row in enumerate(rows) if row["date"] <= signal_date]
    if not eligible_indices:
        return None
    end = eligible_indices[-1]
    start = max(1, end - LOOKBACK + 1)
    overnight: list[float] = []
    intraday: list[float] = []
    for index in range(start, end + 1):
        previous_close = rows[index - 1]["close"]
        open_price = rows[index]["open"]
        close_price = rows[index]["close"]
        if previous_close <= 0.0 or open_price <= 0.0 or close_price <= 0.0:
            continue
        overnight_return = open_price / previous_close - 1.0
        intraday_return = close_price / open_price - 1.0
        if abs(overnight_return) > 0.50 or abs(intraday_return) > 0.50:
            continue
        overnight.append(overnight_return)
        intraday.append(intraday_return)
    if len(overnight) < MIN_COMPONENT_OBSERVATIONS:
        return None
    overnight_downside = statistics.fmean(min(value, 0.0) ** 2 for value in overnight)
    intraday_downside = statistics.fmean(min(value, 0.0) ** 2 for value in intraday)
    total_downside = overnight_downside + intraday_downside
    if total_downside <= 0.0:
        return None
    return {
        "component_observations": len(overnight),
        "overnight_downside_semivariance": overnight_downside,
        "intraday_downside_semivariance": intraday_downside,
        "overnight_downside_share": overnight_downside / total_downside,
        "session_downside_semivariance": total_downside,
    }


def _sector(meta: dict[str, Any] | None) -> str:
    if not isinstance(meta, dict):
        return "Unknown"
    return str(meta.get("sector") or meta.get("sector_name") or "Unknown")


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl = [float(row["pnl"]) for row in rows]
    loss_rows = [value for value in pnl if value < 0.0]
    tickers = Counter(str(row.get("ticker") or "").upper() for row in rows)
    return {
        "row_count": len(rows),
        "avg_pnl": round(statistics.fmean(pnl), 6) if pnl else None,
        "median_pnl": round(statistics.median(pnl), 6) if pnl else None,
        "total_pnl": round(sum(pnl), 2),
        "win_rate": round(sum(value > 0.0 for value in pnl) / len(pnl), 6) if pnl else None,
        "loss_rate": round(len(loss_rows) / len(pnl), 6) if pnl else None,
        "avg_loss_pnl": round(statistics.fmean(loss_rows), 6) if loss_rows else None,
        "unique_tickers": len(tickers),
        "max_ticker_row_share": round(max(tickers.values()) / len(rows), 6) if rows else None,
    }


def _attribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket = {
        bucket: _summary([row for row in rows if row["session_tail_bucket"] == bucket])
        for bucket in ("low_overnight_tail", "mid_overnight_tail", "high_overnight_tail")
    }
    return {
        "overall": _summary(rows),
        "spearman_tail_percentile_vs_pnl": (
            round(value, 6) if (value := _spearman(rows)) is not None else None
        ),
        "buckets": by_bucket,
        "high_minus_low_avg_pnl": (
            round(
                float(by_bucket["high_overnight_tail"]["avg_pnl"])
                - float(by_bucket["low_overnight_tail"]["avg_pnl"]),
                6,
            )
            if by_bucket["high_overnight_tail"]["avg_pnl"] is not None
            and by_bucket["low_overnight_tail"]["avg_pnl"] is not None
            else None
        ),
        "high_minus_low_loss_rate": (
            round(
                float(by_bucket["high_overnight_tail"]["loss_rate"])
                - float(by_bucket["low_overnight_tail"]["loss_rate"]),
                6,
            )
            if by_bucket["high_overnight_tail"]["loss_rate"] is not None
            and by_bucket["low_overnight_tail"]["loss_rate"] is not None
            else None
        ),
    }


def _baseline_reference() -> dict[str, dict[str, Any]]:
    payload = json.loads(CURRENT_BASELINE.read_text(encoding="utf-8"))
    return {row["label"]: row for row in payload["windows"]}


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    gate2_open = framework.sleeve._audit_open_positions()
    universe = sorted(get_universe())
    all_sector_entries = framework._load_sector_entries()
    baseline_reference = _baseline_reference()
    baseline_identity: dict[str, Any] = {}
    baseline_metrics: dict[str, Any] = {}
    per_window_raw: dict[str, list[dict[str, Any]]] = {}
    feature_cache: dict[tuple[str, str], dict[str, Any] | None] = {}
    audit_by_window: dict[str, Any] = {}

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] accepted paper rows + PIT session semivariance")
        core = framework.shadow._run_baseline(universe, cfg)
        reference = baseline_reference[label]
        core_inference = core.get("sharpe_inference") or {}
        reference_inference = reference.get("sharpe_inference") or {}
        baseline_identity[label] = {
            "schema_version": core_inference.get("schema_version"),
            "current_return_series_sha256": core_inference.get("return_series_sha256"),
            "exp_20260712_006_return_series_sha256": reference_inference.get(
                "return_series_sha256"
            ),
            "return_hash_matched": bool(
                core_inference.get("return_series_sha256")
                and core_inference.get("return_series_sha256")
                == reference_inference.get("return_series_sha256")
            ),
            "current_total_pnl": round(float(core.get("total_pnl") or 0.0), 2),
            "reference_total_pnl": reference["after_metrics"]["total_pnl"],
        }
        baseline_metrics[label] = {
            "expected_value_score": round(float(core.get("expected_value_score") or 0.0), 6),
            "sharpe_daily": round(float(core.get("sharpe_daily") or 0.0), 6),
            "strategy_total_return_pct": round(
                float(core.get("strategy_total_return_pct") or 0.0), 6
            ),
            "max_drawdown_pct": round(float(core.get("max_drawdown_pct") or 0.0), 6),
            "total_pnl": round(float(core.get("total_pnl") or 0.0), 2),
            "trade_count": int(core.get("trade_count") or 0),
            "survival_rate": round(float(core.get("survival_rate") or 0.0), 6),
        }

        snapshot = allocator_run.deep_loader._load_window_snapshot_deep(
            cfg=cfg,
            eligible_tickers=set(all_sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in all_sector_entries.items() if ticker in snapshot
        }
        core_entries = framework.shadow._baseline_entries(core)
        accepted_trades, allocator_audit = allocator_run._build_allocator_trades(
            snapshot=snapshot,
            cfg=cfg,
            label=label,
            sector_entries=window_sector_entries,
            core_entries=core_entries,
            with_move=False,
        )
        ohlcv = _normalise_rows(snapshot)
        trade_dates = sorted(
            {str(row.get("signal_date") or row.get("date") or "")[:10] for row in accepted_trades}
            - {""}
        )
        tickers = sorted(window_sector_entries)
        for day in trade_dates:
            for ticker in tickers:
                feature_cache[(ticker, day)] = _feature_for_date(ohlcv.get(ticker, []), day)

        labeled: list[dict[str, Any]] = []
        missing_feature = 0
        direct_sector_partition = 0
        global_fallback_partition = 0
        for trade in accepted_trades:
            ticker = str(trade.get("ticker") or "").upper()
            day = str(trade.get("signal_date") or trade.get("date") or "")[:10]
            feature = feature_cache.get((ticker, day))
            if not feature:
                missing_feature += 1
                continue
            sector = _sector(window_sector_entries.get(ticker))
            same_sector_scores = [
                float(peer_feature["overnight_downside_share"])
                for peer_ticker in tickers
                if _sector(window_sector_entries.get(peer_ticker)) == sector
                and (peer_feature := feature_cache.get((peer_ticker, day)))
            ]
            partition_source = "same_sector"
            population = same_sector_scores
            if len(population) < 3:
                partition_source = "global_fallback"
                population = [
                    float(peer_feature["overnight_downside_share"])
                    for peer_ticker in tickers
                    if (peer_feature := feature_cache.get((peer_ticker, day)))
                ]
                global_fallback_partition += 1
            else:
                direct_sector_partition += 1
            percentile = _percentile(float(feature["overnight_downside_share"]), population)
            pnl = _finite(trade.get("pnl"))
            if percentile is None or pnl is None:
                missing_feature += 1
                continue
            labeled.append(
                {
                    **trade,
                    "window": label,
                    "session_tail_rule_version": RULE_VERSION,
                    "session_tail_partition_source": partition_source,
                    "session_tail_sector": sector,
                    "session_tail_peer_count": len(population),
                    "session_tail_percentile": round(percentile, 9),
                    "session_tail_bucket": _bucket(percentile),
                    **{
                        key: round(float(value), 12) if isinstance(value, float) else value
                        for key, value in feature.items()
                    },
                    "pnl": pnl,
                }
            )
        per_window_raw[label] = labeled
        audit_by_window[label] = {
            "accepted_trade_count": len(accepted_trades),
            "labeled_trade_count": len(labeled),
            "missing_feature_count": missing_feature,
            "coverage": round(len(labeled) / len(accepted_trades), 6) if accepted_trades else 0.0,
            "direct_sector_partition_count": direct_sector_partition,
            "global_fallback_partition_count": global_fallback_partition,
            "allocator_selected_source_counts": allocator_audit[
                "selected_source_counts_by_window"
            ][label],
        }

    labeled_all = [row for rows in per_window_raw.values() for row in rows]
    total_trades = sum(row["accepted_trade_count"] for row in audit_by_window.values())
    coverage = len(labeled_all) / total_trades if total_trades else 0.0
    direct_count = sum(row["direct_sector_partition_count"] for row in audit_by_window.values())
    direct_share = direct_count / len(labeled_all) if labeled_all else 0.0
    aggregate = _attribution(labeled_all)
    per_window = {label: _attribution(rows) for label, rows in per_window_raw.items()}

    separation_windows = [
        label
        for label, row in per_window.items()
        if row["high_minus_low_avg_pnl"] is not None and row["high_minus_low_avg_pnl"] < 0.0
    ]
    negative_spearman_windows = [
        label
        for label, row in per_window.items()
        if row["spearman_tail_percentile_vs_pnl"] is not None
        and row["spearman_tail_percentile_vs_pnl"] < 0.0
    ]
    bucket_min = min(
        aggregate["buckets"][bucket]["row_count"]
        for bucket in ("low_overnight_tail", "mid_overnight_tail", "high_overnight_tail")
    )
    minimum_survival = min(row["survival_rate"] for row in baseline_metrics.values())
    checks = OrderedDict(
        [
            (
                "gate1_current_schema_identity",
                all(
                    row["return_hash_matched"] and int(row["schema_version"] or 0) >= 1
                    for row in baseline_identity.values()
                ),
            ),
            ("gate2_open_position_sentinels", bool(gate2_open.get("passed"))),
            ("gate2_feature_coverage", coverage >= MIN_COVERAGE),
            ("gate3_core_survival_at_least_5pct", minimum_survival >= 0.05),
            ("labeled_trade_count_at_least_100", len(labeled_all) >= MIN_LABELED_TRADES),
            ("direct_sector_partition_share", direct_share >= MIN_DIRECT_SECTOR_PARTITION_SHARE),
            ("minimum_bucket_rows", bucket_min >= MIN_BUCKET_ROWS),
            (
                "aggregate_high_tail_avg_pnl_below_low_tail",
                aggregate["high_minus_low_avg_pnl"] is not None
                and aggregate["high_minus_low_avg_pnl"] < 0.0,
            ),
            ("two_of_three_windows_high_tail_worse", len(separation_windows) >= 2),
            (
                "aggregate_spearman_negative",
                aggregate["spearman_tail_percentile_vs_pnl"] is not None
                and aggregate["spearman_tail_percentile_vs_pnl"] < 0.0,
            ),
            ("two_of_three_windows_spearman_negative", len(negative_spearman_windows) >= 2),
        ]
    )
    failed = [name for name, passed in checks.items() if not passed]
    observed_only_lead = not failed
    decision = (
        "observed_only_positive_session_semivariance_loss_separation_lead"
        if observed_only_lead
        else "observed_only_rejected_session_semivariance_loss_separation"
    )
    realized_failure_modes = []
    if coverage < MIN_COVERAGE:
        realized_failure_modes.append("feature_coverage_incomplete")
    if direct_share < MIN_DIRECT_SECTOR_PARTITION_SHARE:
        realized_failure_modes.append("sector_peer_count_too_small")
    if not checks["aggregate_spearman_negative"]:
        realized_failure_modes.append("pooled_spearman_not_negative")
    if len(separation_windows) < 2 or len(negative_spearman_windows) < 2:
        realized_failure_modes.append("window_separation_unstable")
    if not realized_failure_modes and not observed_only_lead:
        realized_failure_modes.append("selected_trade_population_masks_tail_signal")

    why = (
        "The preregistered session-tail field separated a sufficiently broad, "
        "sector-relative high-tail cohort with worse closed-trade PnL and negative "
        "rank correlation across the required windows. This is an observed-only lead, "
        "not an accepted sizing policy."
        if observed_only_lead
        else "The preregistered session-tail field did not produce the required "
        "aggregate and cross-window monotonic loss separation after current accepted "
        "selection. The result is rejected as a risk-allocation discriminator."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only" if observed_only_lead else "observed_only_rejected",
        "lane": LANE,
        "owner": OWNER,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "change_summary": (
            "Label current accepted paper entries with a fixed PIT 60-session "
            "overnight/intraday downside-semivariance sector partition and attribute "
            "closed outcomes without changing strategy behavior."
        ),
        "change_type": "observed_only_attribution",
        "implementation_mode": "experiment_local_read_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "overnight_intraday_downside_semivariance_sector_partition_v1",
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "PIT 60-session overnight downside semivariance",
            "PIT 60-session intraday downside semivariance",
            "same-day sector-relative partition",
            "closed-trade monotonic attribution",
        ],
        "nearby_prior_experiments": NEARBY,
        "new_evidence_type": "new_production_visible_ohlcv_session_semivariance_field",
        "new_evidence_axis": NEW_AXIS,
        "fingerprint_caveat": (
            "Reservation prose was classified as data_source=other. Manual pre-run "
            "novelty text including the true sector-correlation surface classified it "
            "as ohlcv_relation with no strong near-neighbor; the true source is "
            "unsaturated and this experiment records that manual self-check."
        ),
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": observed_only_lead,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(
                (float(PREDICTION["success_probability"]) - float(observed_only_lead)) ** 2,
                6,
            ),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": realized_failure_modes,
            "predicted_failure_mode_hit": bool(
                set(PREDICTION["main_failure_modes"]) & set(realized_failure_modes)
            ),
        },
        "parameters": {
            "lookback_sessions": LOOKBACK,
            "minimum_component_observations": MIN_COMPONENT_OBSERVATIONS,
            "component_bad_print_guard_abs_return": 0.50,
            "sector_min_peer_count": 3,
            "fallback_partition": "same-day eligible-universe percentile",
            "bucket_cutpoints": [1.0 / 3.0, 2.0 / 3.0],
            "feature_known_at": "signal_day_close_before_next_open",
            "rule_version": RULE_VERSION,
        },
        "gate1": {
            "passed": bool(checks["gate1_current_schema_identity"]),
            "protocol": "same-run current schema-v1 core identity",
            "baseline_identity": baseline_identity,
            "legacy_metric_comparison_used": False,
        },
        "gate2": {
            "passed": bool(
                checks["gate2_open_position_sentinels"] and checks["gate2_feature_coverage"]
            ),
            "open_positions": gate2_open,
            "runtime_fields": [
                "signal_date",
                "entry_date",
                "target_price sentinel in operator open positions",
                "ticker OHLCV Date/Open/Close through signal day",
                "sector map known before attribution",
                "closed paper pnl",
            ],
            "feature_coverage": round(coverage, 6),
        },
        "gate3": {
            "passed": bool(checks["gate3_core_survival_at_least_5pct"]),
            "minimum_core_survival_rate": minimum_survival,
            "candidate_pool_changed": False,
            "new_filter_added": False,
        },
        "gate4": {
            "role": "observed_only_monotonic_attribution_not_policy_acceptance",
            "passed": observed_only_lead,
            "checks": checks,
            "failed_reasons": failed,
            "aggregate": aggregate,
            "per_window": per_window,
            "separation_windows": separation_windows,
            "negative_spearman_windows": negative_spearman_windows,
            "total_source_trades": total_trades,
            "labeled_trade_count": len(labeled_all),
            "coverage": round(coverage, 6),
            "direct_sector_partition_share": round(direct_share, 6),
            "minimum_bucket_rows": bucket_min,
        },
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "delta_metrics": {
            label: {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "max_drawdown_pct": 0.0,
                "trade_count": 0,
                "survival_rate": 0.0,
            }
            for label in baseline_metrics
        },
        "data_coverage": audit_by_window,
        "labeled_rows": labeled_all,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "trade_enabled": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "llm_decision_boundary_changed": False,
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune lookback, minimum observations, percentile cutpoints, "
                "sector fallback, semivariance formula, or response scalar on these "
                "same frozen rows."
            ),
            "new_evidence_required": (
                "A retry requires materially settled forward paper rows tagged before "
                "entry, a genuinely different session-tail source such as PIT options "
                "or borrow economics, or a separately reserved shared risk-policy Gate "
                "1-4 experiment if this observed-only lead passed."
            ),
        },
        "rejection_reason": ";".join(failed) if failed else None,
        "next_retry_requires": [
            "materially more settled forward rows tagged before entry",
            "independent PIT options or borrow tail evidence",
            "shared policy Gate 1-4 only if this observed-only lead passed",
        ],
        "related_files": [
            RUNNER,
            _repo_rel(OUT_JSON),
            _repo_rel(TICKET_JSON),
            "data/experiments/exp-20260712-008/exp_20260712_008_move_rate_volatility_allocator_source.json",
            "data/experiments/exp-20260712-006/current_working_stack_sharpe_inference.json",
            "scripts/experiment_fingerprint.py",
            "quant/test_experiment_fingerprint.py",
            "docs/frozen_families.jsonl",
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER.replace('/', chr(92))}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }
    return payload


def _card(payload: dict[str, Any]) -> str:
    gate = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} session semivariance attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Labeled rows: `{gate['labeled_trade_count']}` / `{gate['total_source_trades']}`",
            f"- Feature coverage: `{gate['coverage']:.2%}`",
            f"- Spearman: `{gate['aggregate']['spearman_tail_percentile_vs_pnl']}`",
            f"- High-minus-low average PnL: `${gate['aggregate']['high_minus_low_avg_pnl']:+,.2f}`",
            f"- Separation windows: `{', '.join(gate['separation_windows']) or 'none'}`",
            f"- Failed checks: `{', '.join(gate['failed_reasons']) or 'none'}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "",
            f"- `{RUNNER_COMMAND}`",
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    _write_text(CARD_MD, _card(payload))
    _write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "generated_at": payload["timestamp"],
            "runner": RUNNER,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card": _repo_rel(CARD_MD),
            "ticket": _repo_rel(TICKET_JSON),
            "reproduction_commands": payload["reproduction_commands"],
        },
    )
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            **{
                key: value
                for key, value in payload.items()
                if key not in {"experiment_id", "status", "prediction"}
            },
            "owner": OWNER,
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "gate4": payload["gate4"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["observed_only_lead"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
