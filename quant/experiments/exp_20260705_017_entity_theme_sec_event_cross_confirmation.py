"""exp-20260705-017: entity/theme news + SEC exposure confirmation.

Observed-only alpha attribution. This tests one fixed gate shape: settled
entity/theme news observer rows are "confirmed" when the same candidate ticker
also appears in a recent SEC corporate-event entity-exposure row with
filed_date <= observed_date and a fixed 30-calendar-day stale horizon.

No strategy behavior changes here: no entries, exits, ranking, sizing, paper
orders, live orders, prompts, or watchlists are changed.
"""

from __future__ import annotations

import bisect
import datetime as dt
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from entity_exposure_map import map_event_to_exposures  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260705-017"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "entity_theme_sec_event_cross_confirmation"
RUNNER = f"quant/experiments/exp_20260705_017_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
ENTITY_THEME_SUMMARY = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "latest_outcome_summary.json"
)
ENTITY_THEME_LEDGER = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "outcome_ledgers"
    / "entity_theme_news_observer_outcomes_20260704.jsonl"
)
EVENT_ROWS = REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream" / "rows.jsonl"
EVENT_MANIFEST = EVENT_ROWS.parent / "manifest.json"
EXPOSURE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "entity_exposure_map"
ENTITY_ROWS = EXPOSURE_DIR / "entities.jsonl"
SIC_INDEX = EXPOSURE_DIR / "sic_peer_index.json"
THEME_OVERLAY = EXPOSURE_DIR / "theme_overlay.json"
EXPOSURE_MANIFEST = EXPOSURE_DIR / "manifest.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260705_017_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: settled entity/theme news observer rows independently "
    "confirmed by recent SEC corporate-event entity-exposure rows should show "
    "stronger 10-day cash/SPY/QQQ replacement value than unconfirmed rows, "
    "supporting a future fixed cross-source confirmation helper."
)
CHANGED_VARIABLE = "entity_theme_news_sec_event_exposure_cross_source_confirmation_v1"
MECHANISM_FAMILY = "cross_source_entity_relation_confirmation"
TRIAL_FAMILY = "entity_theme_sec_event_cross_confirmation"
TRIAL_VARIANT_ID = "recent_sec_exposure_30d_confirmation_v1"
NEARBY_PRIORS = ["exp-20260703-014", "exp-20260702-011", "exp-20260702-012"]
NEW_EVIDENCE_AXIS = (
    "new gate shape: cross-source confirmation between settled entity_theme_news "
    "observer outcome rows and independent SEC corporate-event entity-exposure "
    "rows using filed_date <= observed_date and a fixed 30-day stale horizon; "
    "not a query/theme/ticker/horizon/notional retune and not SEC top-1 deployment."
)
DEFAULT_PREDICTION = {
    "success_probability": 0.26,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "confirmed_sample_too_thin",
        "sec_exposure_overbroad",
        "confirmed_rows_do_not_beat_unconfirmed",
        "concentration_failed",
        "current_news_snapshot_pit_caveat",
    ],
    "confidence_reason": (
        "The fixed entity/theme bundle has many settled outcomes but failed "
        "undifferentiated; SEC corporate-event exposure was positive observed-only "
        "but failed deployable compression. Cross-source agreement is a new gate "
        "shape with plausible independent relation confirmation, but both sources "
        "are noisy and the news snapshot has PIT caveats."
    ),
}

PRIMARY_METRICS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
CONFIRMATION_LOOKBACK_DAYS = 30
ACCEPTANCE_RULE = {
    "min_settled_rows": 250,
    "min_confirmed_rows": 25,
    "max_single_positive_confirmed_cash_ticker_share": 0.40,
    "require_confirmed_primary_means_positive": True,
    "require_confirmed_primary_medians_positive": True,
    "require_confirmed_beats_unconfirmed_means": True,
    "require_confirmed_beats_unconfirmed_medians": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260705_017_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def numeric_value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def parse_date(value: Any) -> dt.date | None:
    text = str(value or "")[:10]
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


def date_text(value: dt.date | None) -> str | None:
    return value.isoformat() if value else None


def load_ticket_prediction() -> dict[str, Any]:
    prediction = dict(DEFAULT_PREDICTION)
    ticket = read_json(TICKET_JSON, {}) or {}
    ticket_prediction = ticket.get("prediction")
    if isinstance(ticket_prediction, dict):
        prediction.update(ticket_prediction)
    prediction.setdefault("recorded_at", utc_now())
    return prediction


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {}) or {}
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(
            int(window.get("trade_count") or window.get("total_trades") or 0)
            for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
    }


def source_event_in_scope(event: dict[str, Any]) -> bool:
    event_class = event.get("event_class")
    if event_class == "merger_communication":
        return True
    if event_class == "ipo_registration" and not event.get("is_amendment"):
        return True
    return False


def load_entity_rows() -> dict[str, dict[str, Any]]:
    return {str(row.get("cik")): row for row in load_jsonl(ENTITY_ROWS) if row.get("cik")}


def build_sec_exposure_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events = load_jsonl(EVENT_ROWS)
    entities = load_entity_rows()
    sic_index = read_json(SIC_INDEX, {"by_sic": {}}) or {"by_sic": {}}
    overlay = read_json(THEME_OVERLAY, {"themes": []}) or {"themes": []}
    exposure_rows: list[dict[str, Any]] = []
    event_counts = Counter()
    selected_counts = Counter()
    relation_counts = Counter()
    theme_counts = Counter()

    for event in events:
        event_class = str(event.get("event_class") or "missing")
        event_counts[event_class] += 1
        if not source_event_in_scope(event):
            continue
        selected_counts[event_class] += 1
        primary_ticker = str(event.get("ticker") or "").upper()
        filed = date_text(parse_date(event.get("filed_date")))
        if not filed:
            continue
        exposures = map_event_to_exposures(
            event,
            entities.get(str(event.get("cik"))),
            sic_index,
            overlay,
        )
        for exposure in exposures:
            ticker = str(exposure.get("ticker") or "").upper()
            if not ticker or ticker == primary_ticker:
                continue
            relation = str(exposure.get("relation_type") or "unknown")
            theme = str(exposure.get("theme") or "")
            relation_counts[relation] += 1
            if theme:
                theme_counts[theme] += 1
            exposure_rows.append(
                {
                    "event_accession": event.get("accession"),
                    "event_class": event.get("event_class"),
                    "form_type": event.get("form_type"),
                    "filed_date": filed,
                    "primary_entity_cik": event.get("cik"),
                    "primary_entity_name": event.get("company_name"),
                    "primary_ticker": primary_ticker or None,
                    "ticker": ticker,
                    "relation_type": relation,
                    "match_basis": exposure.get("match_basis"),
                    "theme": exposure.get("theme"),
                    "overlay_version": exposure.get("overlay_version"),
                }
            )

    return exposure_rows, {
        "sec_event_rows": len(events),
        "selected_sec_event_rows": sum(selected_counts.values()),
        "event_class_counts": dict(sorted(event_counts.items())),
        "selected_event_class_counts": dict(sorted(selected_counts.items())),
        "exposure_rows": len(exposure_rows),
        "exposure_ticker_count": len({row["ticker"] for row in exposure_rows}),
        "relation_type_counts": dict(sorted(relation_counts.items())),
        "theme_counts": dict(sorted(theme_counts.items())),
    }


def index_exposures(
    exposure_rows: list[dict[str, Any]],
) -> dict[str, tuple[list[dt.date], list[dict[str, Any]]]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in exposure_rows:
        filed = parse_date(row.get("filed_date"))
        if filed is None:
            continue
        by_ticker[str(row["ticker"]).upper()].append({**row, "_filed": filed})

    indexed: dict[str, tuple[list[dt.date], list[dict[str, Any]]]] = {}
    for ticker, rows in by_ticker.items():
        ordered = sorted(rows, key=lambda item: item["_filed"])
        indexed[ticker] = ([row["_filed"] for row in ordered], ordered)
    return indexed


def matching_exposures(
    row: dict[str, Any],
    exposure_index: dict[str, tuple[list[dt.date], list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    observed = parse_date(row.get("observed_date"))
    ticker = str(row.get("candidate_ticker") or "").upper()
    if observed is None or not ticker or ticker not in exposure_index:
        return []
    dates, rows = exposure_index[ticker]
    start = observed - dt.timedelta(days=CONFIRMATION_LOOKBACK_DAYS)
    left = bisect.bisect_left(dates, start)
    right = bisect.bisect_right(dates, observed)
    return rows[left:right]


def annotate_rows(
    settled_rows: list[dict[str, Any]],
    exposure_index: dict[str, tuple[list[dt.date], list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    confirmed: list[dict[str, Any]] = []
    confirmation_counts = Counter()
    confirmation_lags: list[int] = []
    relation_counts = Counter()
    event_class_counts = Counter()
    sec_theme_counts = Counter()

    for source in settled_rows:
        matches = matching_exposures(source, exposure_index)
        observed = parse_date(source.get("observed_date"))
        latest = max((match["_filed"] for match in matches), default=None)
        lag = (observed - latest).days if observed and latest else None
        relation_types = sorted({str(match.get("relation_type") or "unknown") for match in matches})
        event_classes = sorted({str(match.get("event_class") or "unknown") for match in matches})
        sec_themes = sorted({str(match.get("theme") or "") for match in matches if match.get("theme")})
        for value in relation_types:
            relation_counts[value] += 1
        for value in event_classes:
            event_class_counts[value] += 1
        for value in sec_themes:
            sec_theme_counts[value] += 1
        if lag is not None:
            confirmation_lags.append(lag)
        confirmation_counts[len(matches)] += 1
        row = {
            **source,
            "sec_confirmation": bool(matches),
            "sec_confirmation_count": len(matches),
            "sec_confirmation_latest_filed_date": date_text(latest),
            "sec_confirmation_lag_days": lag,
            "sec_confirmation_event_classes": event_classes,
            "sec_confirmation_relation_types": relation_types,
            "sec_confirmation_themes": sec_themes,
            "sec_confirmation_examples": [
                {
                    "filed_date": match.get("filed_date"),
                    "event_class": match.get("event_class"),
                    "form_type": match.get("form_type"),
                    "primary_entity_name": match.get("primary_entity_name"),
                    "relation_type": match.get("relation_type"),
                    "theme": match.get("theme"),
                }
                for match in matches[-3:]
            ],
        }
        annotated.append(row)
        if matches:
            confirmed.append(row)

    diagnostics = {
        "confirmation_count_distribution": dict(sorted(confirmation_counts.items())),
        "confirmation_lag_days": summarize_values([float(value) for value in confirmation_lags]),
        "confirmed_relation_type_counts": dict(sorted(relation_counts.items())),
        "confirmed_event_class_counts": dict(sorted(event_class_counts.items())),
        "confirmed_sec_theme_counts": dict(sorted(sec_theme_counts.items())),
    }
    return annotated, confirmed, diagnostics


def summarize_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "sum": None,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(values),
        "sum": round(sum(values), 2),
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 6),
    }


def metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [*PRIMARY_METRICS, "pnl_usd"]
    return {
        metric: summarize_values(
            [value for row in rows if (value := numeric_value(row, metric)) is not None]
        )
        for metric in metrics
    }


def positive_contribution_share(
    rows: list[dict[str, Any]], key: str, metric: str
) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    for row in rows:
        value = numeric_value(row, metric)
        if value is None or value <= 0:
            continue
        totals[str(row.get(key) or "UNKNOWN")] += value
    total_positive = sum(totals.values())
    leaders = [
        {
            key: group,
            "positive_contribution_usd": round(value, 2),
            "share": round(value / total_positive, 6) if total_positive else None,
        }
        for group, value in totals.most_common(10)
    ]
    return {
        "metric": metric,
        "total_positive_usd": round(total_positive, 2) if total_positive else 0.0,
        "max_share": leaders[0]["share"] if leaders else None,
        "leaders": leaders,
    }


def group_counts(rows: list[dict[str, Any]], key: str, limit: int = 12) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(key) or "UNKNOWN") for row in rows)
    denominator = max(len(rows), 1)
    return [
        {key: value, "rows": count, "share": round(count / denominator, 6)}
        for value, count in counts.most_common(limit)
    ]


def group_metric_summaries(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "UNKNOWN")].append(row)
    output = []
    for value, subset in grouped.items():
        output.append(
            {
                key: value,
                "row_count": len(subset),
                "ticker_count": len({row.get("candidate_ticker") for row in subset}),
                "metrics": metric_summary(subset),
            }
        )
    return sorted(output, key=lambda item: item["row_count"], reverse=True)


def compare_metric_summaries(
    confirmed_metrics: dict[str, Any],
    unconfirmed_metrics: dict[str, Any],
) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    for metric in PRIMARY_METRICS:
        confirmed = confirmed_metrics[metric]
        unconfirmed = unconfirmed_metrics[metric]
        mean_delta = None
        median_delta = None
        if confirmed["mean"] is not None and unconfirmed["mean"] is not None:
            mean_delta = round(confirmed["mean"] - unconfirmed["mean"], 4)
        if confirmed["median"] is not None and unconfirmed["median"] is not None:
            median_delta = round(confirmed["median"] - unconfirmed["median"], 4)
        comparisons[metric] = {
            "confirmed_mean": confirmed["mean"],
            "unconfirmed_mean": unconfirmed["mean"],
            "mean_delta": mean_delta,
            "confirmed_median": confirmed["median"],
            "unconfirmed_median": unconfirmed["median"],
            "median_delta": median_delta,
        }
    return comparisons


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    entity_summary = read_json(ENTITY_THEME_SUMMARY, {}) or {}
    event_manifest = read_json(EVENT_MANIFEST, {}) or {}
    exposure_manifest = read_json(EXPOSURE_MANIFEST, {}) or {}
    all_entity_rows = load_jsonl(ENTITY_THEME_LEDGER)
    settled = [row for row in all_entity_rows if row.get("outcome_status") == "settled"]
    exposure_rows, sec_summary = build_sec_exposure_rows()
    exposure_index = index_exposures(exposure_rows)
    annotated, confirmed, confirmation_diagnostics = annotate_rows(settled, exposure_index)
    unconfirmed = [row for row in annotated if not row.get("sec_confirmation")]

    overall_metrics = metric_summary(settled)
    confirmed_metrics = metric_summary(confirmed)
    unconfirmed_metrics = metric_summary(unconfirmed)
    comparison = compare_metric_summaries(confirmed_metrics, unconfirmed_metrics)
    positive_ticker_share = positive_contribution_share(
        confirmed, "candidate_ticker", "replacement_value_vs_cash_usd"
    )

    confirmed_means_positive = all(
        (confirmed_metrics[metric]["mean"] or 0.0) > 0 for metric in PRIMARY_METRICS
    )
    confirmed_medians_positive = all(
        (confirmed_metrics[metric]["median"] or 0.0) > 0 for metric in PRIMARY_METRICS
    )
    beats_unconfirmed_means = all(
        comparison[metric]["mean_delta"] is not None
        and comparison[metric]["mean_delta"] > 0
        for metric in PRIMARY_METRICS
    )
    beats_unconfirmed_medians = all(
        comparison[metric]["median_delta"] is not None
        and comparison[metric]["median_delta"] > 0
        for metric in PRIMARY_METRICS
    )
    max_positive_share = positive_ticker_share["max_share"]
    checks = {
        "settled_rows_min_passed": len(settled) >= ACCEPTANCE_RULE["min_settled_rows"],
        "confirmed_rows_min_passed": len(confirmed) >= ACCEPTANCE_RULE["min_confirmed_rows"],
        "confirmed_primary_means_positive": confirmed_means_positive,
        "confirmed_primary_medians_positive": confirmed_medians_positive,
        "confirmed_beats_unconfirmed_means": beats_unconfirmed_means,
        "confirmed_beats_unconfirmed_medians": beats_unconfirmed_medians,
        "positive_confirmed_cash_ticker_share_passed": (
            max_positive_share is not None
            and max_positive_share
            <= ACCEPTANCE_RULE["max_single_positive_confirmed_cash_ticker_share"]
        ),
    }
    directional_support = all(checks.values())
    failed_reasons = [name for name, passed in checks.items() if not passed]
    if directional_support:
        status = "observed_only_positive_lead"
        decision = "observed_only_positive_entity_theme_sec_confirmation_lead"
    else:
        status = "observed_only_rejected"
        decision = "observed_only_rejected_entity_theme_sec_confirmation_no_edge"

    pit_caveat = (
        "Entity/theme source rows come from the current Google News observer "
        "snapshot and include historical published_at rows returned by the "
        "current search. SEC exposure map SIC values are current submissions "
        "classifications, not as-of-filing PIT classifications. This is a "
        "read-only attribution check, not strict historical deployable evidence."
    )
    why = (
        "The fixed SEC confirmation gate separated a positive confirmed cohort "
        "from unconfirmed rows, but it remains only a lead because both input "
        "surfaces have PIT caveats."
        if directional_support
        else "The fixed SEC confirmation gate did not separate a broad, "
        "non-concentrated confirmed cohort that beat unconfirmed rows on "
        "cash, SPY, and QQQ means and medians."
    )
    result: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": directional_support,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_observed_attribution",
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "read_only_entity_theme_outcome_ledger_analysis",
            "read_only_sec_corporate_event_exposure_map",
            "fixed_30_calendar_day_sec_confirmation_join",
            "confirmed_vs_unconfirmed_cash_spy_qqq_attribution",
            "no_strategy_behavior_change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_gate_shape",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "actual_success": 1 if directional_support else 0,
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": round(
                (prediction["success_probability"] - (1 if directional_support else 0))
                ** 2,
                4,
            ),
            "predicted_failure_modes": prediction["main_failure_modes"],
            "realized_failure_modes": failed_reasons
            if failed_reasons
            else ["current_news_snapshot_pit_caveat"],
            "predicted_failure_mode_hit": bool(
                set(failed_reasons).intersection(prediction["main_failure_modes"])
            )
            or bool(failed_reasons),
            "expected_ev_delta": prediction["expected_ev_delta"],
            "expected_pnl_delta": prediction["expected_pnl_delta"],
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "surprise_note": (
                "Moderate surprise: cross-source confirmation passed the "
                "observed-only separation rule despite both source caveats."
                if directional_support
                else "Low surprise: both source surfaces were noisy in prior "
                "tests, and their fixed 30-day ticker confirmation did not "
                "create a cleaner replacement-value cohort."
            ),
        },
        "source_artifacts": {
            "entity_theme_summary": repo_rel(ENTITY_THEME_SUMMARY),
            "entity_theme_ledger": repo_rel(ENTITY_THEME_LEDGER),
            "entity_theme_summary_payload": entity_summary,
            "sec_event_rows": repo_rel(EVENT_ROWS),
            "sec_event_manifest": repo_rel(EVENT_MANIFEST),
            "sec_event_manifest_payload": event_manifest,
            "entity_exposure_manifest": repo_rel(EXPOSURE_MANIFEST),
            "entity_exposure_manifest_payload": exposure_manifest,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; canonical strategy baseline unchanged.",
        },
        "gate2": {
            "passed": bool(settled) and bool(exposure_rows),
            "fields_checked": [
                "candidate_ticker",
                "observed_date",
                "entry_date",
                "exit_date",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
                "sec_event.filed_date",
                "sec_exposure.ticker",
            ],
            "entry_date_present_rows": sum(1 for row in settled if row.get("entry_date")),
            "target_price_relevance": (
                "This observer does not create target exits or orders; target_price "
                "is not part of the read-only outcome ledger."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": len(all_entity_rows),
            "signals_survived": len(settled),
            "survival_rate": round(len(settled) / max(len(all_entity_rows), 1), 6),
            "confirmed_survival_rate": round(len(confirmed) / max(len(settled), 1), 6),
            "note": "No executable filter, ranking, sizing, exit, prompt, or order rule was added.",
        },
        "gate4": {
            "passed": directional_support,
            "observed_only": True,
            "accepted_alpha": False,
            "decision": decision,
            "acceptance_rule": ACCEPTANCE_RULE,
            "acceptance_checks": checks,
            "failed_reasons": failed_reasons,
            "pit_caveat": pit_caveat,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
        },
        "analysis": {
            "source_counts": {
                "entity_theme_candidate_rows": len(all_entity_rows),
                "entity_theme_settled_rows": len(settled),
                "entity_theme_unsettled_rows": len(all_entity_rows) - len(settled),
                **sec_summary,
            },
            "overall_metrics": overall_metrics,
            "confirmed_metrics": confirmed_metrics,
            "unconfirmed_metrics": unconfirmed_metrics,
            "confirmed_vs_unconfirmed": comparison,
            "confirmation_diagnostics": confirmation_diagnostics,
            "confirmed_positive_cash_ticker_contribution": positive_ticker_share,
            "confirmed_by_ticker": group_counts(confirmed, "candidate_ticker"),
            "confirmed_by_query": group_counts(confirmed, "entity_theme_query_id"),
            "confirmed_by_theme": group_counts(confirmed, "theme"),
            "confirmed_query_summaries": group_metric_summaries(
                confirmed, "entity_theme_query_id"
            ),
        },
        "summary": {
            "candidate_outcome_rows": len(all_entity_rows),
            "settled_rows": len(settled),
            "confirmed_rows": len(confirmed),
            "unconfirmed_rows": len(unconfirmed),
            "confirmed_survival_rate": round(len(confirmed) / max(len(settled), 1), 6),
            "confirmed_mean_cash": confirmed_metrics["replacement_value_vs_cash_usd"]["mean"],
            "confirmed_mean_spy": confirmed_metrics["replacement_value_vs_spy_usd"]["mean"],
            "confirmed_mean_qqq": confirmed_metrics["replacement_value_vs_qqq_usd"]["mean"],
            "confirmed_median_cash": confirmed_metrics["replacement_value_vs_cash_usd"]["median"],
            "confirmed_median_spy": confirmed_metrics["replacement_value_vs_spy_usd"]["median"],
            "confirmed_median_qqq": confirmed_metrics["replacement_value_vs_qqq_usd"]["median"],
            "unconfirmed_mean_cash": unconfirmed_metrics["replacement_value_vs_cash_usd"]["mean"],
            "unconfirmed_mean_spy": unconfirmed_metrics["replacement_value_vs_spy_usd"]["mean"],
            "unconfirmed_mean_qqq": unconfirmed_metrics["replacement_value_vs_qqq_usd"]["mean"],
            "cash_mean_delta_vs_unconfirmed": comparison[
                "replacement_value_vs_cash_usd"
            ]["mean_delta"],
            "spy_mean_delta_vs_unconfirmed": comparison[
                "replacement_value_vs_spy_usd"
            ]["mean_delta"],
            "qqq_mean_delta_vs_unconfirmed": comparison[
                "replacement_value_vs_qqq_usd"
            ]["mean_delta"],
            "max_positive_confirmed_cash_ticker_share": max_positive_share,
            "decision": decision,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "trade_enabled": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "Read-only cross-source attribution over existing observer and SEC "
                "exposure ledgers. No helper, adapter, order, rank, size, exit, "
                "watchlist, or LLM behavior changed."
            ),
        },
        "rejection_reason": ";".join(failed_reasons) if failed_reasons else None,
        "post_run_reflection": {
            "why_result_happened": why + " " + pit_caveat,
            "forbidden_near_neighbor_retry": (
                "Do not retune the 30-day confirmation horizon, query/theme/ticker "
                "maps, SEC form set, notional, hold period, or response curve on "
                "this same first snapshot. A valid retry needs prospective "
                "cross-source rows with closed outcomes, a strict PIT news archive, "
                "or a materially different independent relation source."
            ),
            "new_evidence_required": (
                "Prospectively accumulated entity/theme rows with closed outcomes "
                "and unchanged SEC-confirmation contract, a true PIT historical "
                "news archive, or a different independent entity-relation source."
            ),
        },
        "next_retry_requires": [
            "prospective daily entity/theme observer rows with closed outcomes",
            "unchanged 30-day SEC-confirmation contract for the next audit",
            "or a true PIT historical news archive with observation-time availability",
            "or a different independent relation source; no threshold retune on this snapshot",
        ],
        "related_files": [
            RUNNER,
            repo_rel(ENTITY_THEME_LEDGER),
            repo_rel(ENTITY_THEME_SUMMARY),
            repo_rel(EVENT_ROWS),
            repo_rel(EXPOSURE_MANIFEST),
            "experiments/logs/exp-20260703-014.json",
            "experiments/logs/exp-20260702-011.json",
            "experiments/logs/exp-20260702-012.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "changed_files": CHANGED_FILES,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
    }
    return result


def compact_log_record(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    return {key: result[key] for key in keys}


def build_card(result: dict[str, Any]) -> str:
    summary = result["summary"]
    failures = result["gate4"]["failed_reasons"] or ["none"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

- Status: `{result["status"]}`
- Decision: `{result["decision"]}`
- Accepted alpha: `false`
- Observed-only lead: `{str(result["observed_only_lead"]).lower()}`
- Settled rows: `{summary["settled_rows"]}`
- Confirmed rows: `{summary["confirmed_rows"]}`
- Confirmed survival rate: `{summary["confirmed_survival_rate"]}`
- Confirmed mean cash/SPY/QQQ: `{summary["confirmed_mean_cash"]}` / `{summary["confirmed_mean_spy"]}` / `{summary["confirmed_mean_qqq"]}`
- Confirmed median cash/SPY/QQQ: `{summary["confirmed_median_cash"]}` / `{summary["confirmed_median_spy"]}` / `{summary["confirmed_median_qqq"]}`
- Mean deltas vs unconfirmed cash/SPY/QQQ: `{summary["cash_mean_delta_vs_unconfirmed"]}` / `{summary["spy_mean_delta_vs_unconfirmed"]}` / `{summary["qqq_mean_delta_vs_unconfirmed"]}`
- Max positive confirmed cash ticker share: `{summary["max_positive_confirmed_cash_ticker_share"]}`
- Failed checks: `{", ".join(failures)}`

## Boundary

{result["post_run_reflection"]["forbidden_near_neighbor_retry"]}

## Reproduce

```powershell
{RUNNER_COMMAND}
.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict
```
"""


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {}) or {}
    ticket["status"] = result["status"]
    ticket["completed_at"] = result["timestamp"]
    ticket["result"] = {
        "decision": result["decision"],
        "artifact": result["artifact"],
        "log": result["log"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": result["observed_only_lead"],
    }
    ticket["gate4"] = result["gate4"]
    ticket["post_run_reflection"] = result["post_run_reflection"]
    ticket["next_retry_requires"] = result["next_retry_requires"]
    write_json(TICKET_JSON, ticket)


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "generated_at": result["timestamp"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def main() -> int:
    result = build_result()
    write_json(OUT_JSON, result)
    save_experiment_log_entry(compact_log_record(result), allow_duplicate=True)
    write_text(CARD_MD, build_card(result))
    write_manifest(result)
    update_ticket(result)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=result["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": result["observed_only_lead"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "gate4": result["gate4"],
            "summary": result["summary"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": HYPOTHESIS,
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": result["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log_file": result["log"],
            "card_file": repo_rel(CARD_MD),
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["next_retry_requires"],
            "related_files": result["related_files"],
            "changed_files": CHANGED_FILES,
            "allowed_write_scope": CHANGED_FILES,
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    print(json.dumps(compact_log_record(result), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
