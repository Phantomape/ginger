"""exp-20260816-002: observed-only signed-news Hawkes attribution.

The outcome-blind contract is frozen in
``data/alpha_search/hawkes_news_polarity_readiness_20260816.json``.
This runner verifies the frozen input hashes, reconstructs the fixed bivariate
daily Hawkes state, asserts the preregistered cohort counts, and only then reads
the already materialized H10 SPY-excess outcomes.

Repro:
    .\.venv\Scripts\python.exe -B -m quant.experiments.exp_20260816_002_hawkes_news_polarity_intensity
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np


EXPERIMENT_ID = "exp-20260816-002"
LEDGER = Path("data/non_ohlcv/news_event_exposure_observations/rows.jsonl")
MANIFEST = Path("data/non_ohlcv/news_event_exposure_observations/manifest.json")
SIC_INDEX = Path("data/non_ohlcv/entity_exposure_map/sic_peer_index.json")
THEME_OVERLAY = Path("data/non_ohlcv/entity_exposure_map/theme_overlay.json")
READINESS = Path("data/alpha_search/hawkes_news_polarity_readiness_20260816.json")
BASELINE = Path(
    "data/backtests/"
    "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
OUT = Path(
    "data/experiments/exp-20260816-002/"
    "exp_20260816_002_hawkes_news_polarity_intensity.json"
)

FORWARD_START = date(2026, 7, 1)
FIT_END = date(2026, 7, 20)
OOS_START = date(2026, 7, 21)
OOS_END = date(2026, 8, 15)
HALF_LIFE_DAYS = 2.0
ROUND_TRIP_COST_PCT = 0.0045
GROUP_DATE_NOTIONAL_USD = 4_000.0
MIN_CLOSED_UNIQUE_LEGS = 3
CONCENTRATION_CAP = 0.40
BASELINE_FLOOR = 1e-6
ROW_BRANCHING_CAP = 0.90


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _economic_group(match_bases: set[str]) -> str:
    sic_codes = sorted(
        value.split(":", 1)[1]
        for value in match_bases
        if value.startswith("sic:") and ":" in value
    )
    if sic_codes:
        return f"SIC4:{sic_codes[0]}"
    themes = sorted(
        value.split(":", 1)[1]
        for value in match_bases
        if value.startswith("theme_membership:") and ":" in value
    )
    if themes:
        return f"theme:{themes[0]}"
    raise SystemExit(f"event has no deterministic SIC4/theme identity: {match_bases}")


def _load_frozen_inputs() -> tuple[dict, list[dict]]:
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    expected = readiness["artifacts"]
    checks = {
        LEDGER: expected["ledger"]["sha256"],
        MANIFEST: expected["manifest"]["sha256"],
        SIC_INDEX: expected["sic_peer_index"]["sha256"],
        THEME_OVERLAY: expected["theme_overlay"]["sha256"],
        BASELINE: expected["active_baseline"]["sha256"],
    }
    for path, expected_hash in checks.items():
        actual = _sha256(path)
        if actual != expected_hash:
            raise SystemExit(
                f"frozen input hash mismatch for {path}: {actual} != {expected_hash}"
            )
    rows = [
        json.loads(line)
        for line in LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return readiness, rows


def _events_and_rows(rows: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    raw_events: dict[str, dict] = {}
    rows_by_event: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        raw_date = str(row.get("event_date") or "")
        if not raw_date:
            continue
        event_date = date.fromisoformat(raw_date)
        if event_date < FORWARD_START or event_date > OOS_END:
            continue
        event_id = str(row["event_id"])
        polarity = str(row.get("event_polarity") or "")
        if polarity not in {"positive", "negative"}:
            continue
        record = raw_events.setdefault(
            event_id,
            {
                "event_id": event_id,
                "event_date": event_date,
                "polarity": polarity,
                "first_order_ticker": str(row.get("first_order_ticker") or ""),
                "match_bases": set(),
            },
        )
        if record["event_date"] != event_date or record["polarity"] != polarity:
            raise SystemExit(f"inconsistent event identity fields for {event_id}")
        record["match_bases"].add(str(row.get("match_basis") or ""))
        rows_by_event[event_id].append(row)

    events: list[dict] = []
    for event in raw_events.values():
        event["group"] = _economic_group(event.pop("match_bases"))
        event["mark"] = 0 if event["polarity"] == "positive" else 1
        events.append(event)
    events.sort(key=lambda item: (item["event_date"], item["event_id"]))
    return events, rows_by_event


def _design(
    events: list[dict], groups: list[str], start: date, end: date
) -> tuple[np.ndarray, np.ndarray]:
    """Return daily counts and strictly lagged exponential-kernel features."""

    group_index = {group: idx for idx, group in enumerate(groups)}
    days = _date_range(start, end)
    y = np.zeros((len(groups), len(days), 2), dtype=float)
    for event in events:
        if start <= event["event_date"] <= end:
            day_idx = (event["event_date"] - start).days
            y[group_index[event["group"]], day_idx, event["mark"]] += 1.0

    decay = math.exp(-math.log(2.0) / HALF_LIFE_DAYS)
    kernel_mass = 1.0 - decay
    state = np.zeros((len(groups), 2), dtype=float)
    x = np.zeros_like(y)
    for day_idx in range(len(days)):
        x[:, day_idx, :] = state * kernel_mass
        state = decay * state + y[:, day_idx, :]
    return y, x


def _poisson_log_likelihood(
    y: np.ndarray, x: np.ndarray, mu: np.ndarray, amplitude: np.ndarray
) -> float:
    total = 0.0
    for target_mark in range(2):
        intensity = mu[:, target_mark, None] + np.sum(
            amplitude[target_mark][None, None, :] * x, axis=2
        )
        if np.any(intensity <= 0):
            raise SystemExit("non-positive Hawkes intensity")
        total += float(
            np.sum(y[:, :, target_mark] * np.log(intensity) - intensity)
        )
    return total


def _fit_hawkes(
    y: np.ndarray, x: np.ndarray
) -> tuple[np.ndarray, np.ndarray, int, float]:
    """Coordinate-Newton nonnegative Poisson MLE with a row branching cap."""

    mu_independent = np.maximum(y.sum(axis=1) / y.shape[1], BASELINE_FLOOR)
    mu = mu_independent.copy()
    amplitude = np.zeros((2, 2), dtype=float)
    iterations = 0
    for outer in range(100):
        previous = np.concatenate((mu.ravel(), amplitude.ravel()))
        for target_mark in range(2):
            for group_idx in range(y.shape[0]):
                intensity = (
                    mu[group_idx, target_mark]
                    + x[group_idx] @ amplitude[target_mark]
                )
                target = y[group_idx, :, target_mark]
                gradient = float(np.sum(target / intensity - 1.0))
                hessian = float(-np.sum(target / (intensity**2)))
                if hessian < -1e-12:
                    mu[group_idx, target_mark] = max(
                        BASELINE_FLOOR,
                        mu[group_idx, target_mark] - gradient / hessian,
                    )

            for source_mark in range(2):
                intensity = mu[:, target_mark, None] + np.sum(
                    amplitude[target_mark][None, None, :] * x, axis=2
                )
                feature = x[:, :, source_mark]
                target = y[:, :, target_mark]
                gradient = float(np.sum(feature * (target / intensity - 1.0)))
                hessian = float(
                    -np.sum(target * feature**2 / (intensity**2))
                )
                if hessian < -1e-12:
                    other = amplitude[target_mark, 1 - source_mark]
                    amplitude[target_mark, source_mark] = max(
                        0.0,
                        min(
                            ROW_BRANCHING_CAP - other,
                            amplitude[target_mark, source_mark]
                            - gradient / hessian,
                        ),
                    )
        iterations = outer + 1
        current = np.concatenate((mu.ravel(), amplitude.ravel()))
        if float(np.max(np.abs(current - previous))) < 1e-9:
            break

    independent_ll = _poisson_log_likelihood(
        y, x, mu_independent, np.zeros((2, 2), dtype=float)
    )
    fitted_ll = _poisson_log_likelihood(y, x, mu, amplitude)
    return mu, amplitude, iterations, fitted_ll - independent_ll


def _scores_by_group_date(
    events: list[dict], groups: list[str], mu: np.ndarray, amplitude: np.ndarray
) -> dict[tuple[str, date], float]:
    """Forecast the next arrival sign after all same-day public events are known."""

    group_index = {group: idx for idx, group in enumerate(groups)}
    by_date: dict[date, list[dict]] = defaultdict(list)
    for event in events:
        by_date[event["event_date"]].append(event)
    decay = math.exp(-math.log(2.0) / HALF_LIFE_DAYS)
    kernel_mass = 1.0 - decay
    state = np.zeros((len(groups), 2), dtype=float)
    scores: dict[tuple[str, date], float] = {}
    for current_date in _date_range(FORWARD_START, OOS_END):
        for event in by_date.get(current_date, []):
            state[group_index[event["group"]], event["mark"]] += 1.0
        for group in groups:
            group_idx = group_index[group]
            feature = state[group_idx] * kernel_mass
            intensity = mu[group_idx] + amplitude @ feature
            denominator = float(np.sum(intensity))
            signed = (
                float((intensity[0] - intensity[1]) / denominator)
                if denominator > 0
                else 0.0
            )
            scores[(group, current_date)] = max(signed, 0.0)
        state *= decay
    return scores


def _closed_leg_values(
    event_ids: set[str], rows_by_event: dict[str, list[dict]]
) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for event_id in sorted(event_ids):
        for row in rows_by_event[event_id]:
            if row.get("outcome_status") != "closed" or row.get("excess_10d") is None:
                continue
            if not row.get("entry_date"):
                raise SystemExit(f"closed row is missing entry_date: {event_id}")
            values[str(row["exposure_ticker"])].append(float(row["excess_10d"]))
    # Same group-date/ticker can be reached from multiple same-day events. Its
    # entry/exit bars are identical; average duplicate materializations after
    # checking that they agree to warehouse precision.
    unique: dict[str, float] = {}
    for ticker, ticker_values in values.items():
        if max(ticker_values) - min(ticker_values) > 1e-9:
            raise SystemExit(
                f"same group-date ticker has inconsistent H10 settlement: {ticker}"
            )
        unique[ticker] = statistics.fmean(ticker_values)
    return unique


def _decision_cohort(
    events: list[dict],
    rows_by_event: dict[str, list[dict]],
    scores: dict[tuple[str, date], float],
    *,
    positive_score_only: bool,
) -> list[dict]:
    grouped: dict[tuple[str, date], list[dict]] = defaultdict(list)
    for event in events:
        if not (OOS_START <= event["event_date"] <= OOS_END):
            continue
        key = (event["group"], event["event_date"])
        if positive_score_only and scores[key] <= 0:
            continue
        grouped[key].append(event)

    decisions: list[dict] = []
    for (group, event_date), same_day_events in sorted(grouped.items()):
        event_ids = {event["event_id"] for event in same_day_events}
        legs = _closed_leg_values(event_ids, rows_by_event)
        if len(legs) < MIN_CLOSED_UNIQUE_LEGS:
            continue
        decisions.append(
            {
                "group": group,
                "event_date": event_date,
                "score": scores[(group, event_date)],
                "event_ids": event_ids,
                "source_tickers": {
                    event["first_order_ticker"] for event in same_day_events
                },
                "leg_count": len(legs),
                "gross_excess_10d": statistics.fmean(legs.values()),
            }
        )
    return decisions


def _positive_mass_share(values: list[float]) -> float | None:
    positive = [value for value in values if value > 0]
    if not positive:
        return None
    return max(positive) / sum(positive)


def main() -> None:
    readiness, rows = _load_frozen_inputs()
    events, rows_by_event = _events_and_rows(rows)
    groups = sorted({event["group"] for event in events})
    train_events = [event for event in events if event["event_date"] <= FIT_END]
    oos_events = [event for event in events if event["event_date"] >= OOS_START]

    y_train, x_train = _design(events, groups, FORWARD_START, FIT_END)
    mu, amplitude, iterations, train_ll_improvement = _fit_hawkes(
        y_train, x_train
    )
    decay = math.exp(-math.log(2.0) / HALF_LIFE_DAYS)
    branching = amplitude / decay
    scores = _scores_by_group_date(events, groups, mu, amplitude)

    positive_score_events = [
        event
        for event in oos_events
        if scores[(event["group"], event["event_date"])] > 0
    ]
    positive_score_events_with_closed = [
        event
        for event in positive_score_events
        if any(
            row.get("outcome_status") == "closed"
            for row in rows_by_event[event["event_id"]]
        )
    ]
    treatment = _decision_cohort(
        events, rows_by_event, scores, positive_score_only=True
    )
    all_oos = _decision_cohort(
        events, rows_by_event, scores, positive_score_only=False
    )

    density = readiness["candidate_density"]
    group_counts = Counter(item["group"] for item in treatment)
    decision_dates = sorted({item["event_date"] for item in treatment})
    source_tickers = {
        ticker for item in treatment for ticker in item["source_tickers"]
    }
    source_decision_counts: Counter[str] = Counter()
    for item in treatment:
        for ticker in item["source_tickers"]:
            source_decision_counts[ticker] += 1
    closed_unique_legs = sum(item["leg_count"] for item in treatment)
    max_group_share = max(group_counts.values()) / len(treatment)
    max_source_share = max(source_decision_counts.values()) / len(treatment)

    assertions = {
        "events_total": len(events) == readiness["event_only_fit"]["events_total"],
        "groups_total": len(groups)
        == readiness["event_only_fit"]["economic_groups_total"],
        "train_events": len(train_events)
        == readiness["event_only_fit"]["train_events"],
        "oos_events": len(oos_events)
        == readiness["event_only_fit"]["out_of_sample_events"],
        "train_ll_improvement": abs(
            train_ll_improvement
            - readiness["event_only_fit"][
                "train_log_likelihood_improvement_vs_independent_poisson"
            ]
        )
        <= 1e-5,
        "negative_to_positive_branching": abs(
            float(branching[0, 1])
            - readiness["event_only_fit"]["branching_matrix_target_by_source"][0][1]
        )
        <= 1e-4,
        "positive_score_oos_events": len(positive_score_events)
        == readiness["event_only_fit"]["positive_score_out_of_sample_events"],
        "positive_score_events_with_closed": len(
            positive_score_events_with_closed
        )
        == readiness["event_only_fit"][
            "positive_score_events_with_closed_exposures"
        ],
        "independent_decisions": len(treatment)
        == density["independent_group_date_decisions"],
        "decision_dates": len(decision_dates) == density["unique_decision_dates"],
        "economic_groups": len(group_counts) == density["unique_economic_groups"],
        "first_order_tickers": len(source_tickers)
        == density["unique_first_order_tickers"],
        "closed_unique_peer_legs": closed_unique_legs
        == density["closed_unique_peer_legs"],
        "max_group_share": abs(max_group_share - density["max_group_decision_share"])
        <= 1e-9,
        "max_source_ticker_share": abs(
            max_source_share - density["max_first_order_ticker_decision_share"]
        )
        <= 1e-9,
    }
    if not all(assertions.values()):
        raise SystemExit(f"frozen cohort/model assertion failed: {assertions}")

    for item in treatment:
        item["net_rate"] = item["gross_excess_10d"] - ROUND_TRIP_COST_PCT
        item["notional_usd"] = GROUP_DATE_NOTIONAL_USD * item["score"]
        item["contribution_usd"] = item["notional_usd"] * item["net_rate"]
    for item in all_oos:
        item["net_rate"] = item["gross_excess_10d"] - ROUND_TRIP_COST_PCT

    total_notional = sum(item["notional_usd"] for item in treatment)
    total_pnl = sum(item["contribution_usd"] for item in treatment)
    primary_net_rate = total_pnl / total_notional
    positive_cohort_equal_net = statistics.fmean(
        item["net_rate"] for item in treatment
    )
    all_oos_equal_net = statistics.fmean(item["net_rate"] for item in all_oos)
    contributions = [item["contribution_usd"] for item in treatment]

    median_date = decision_dates[(len(decision_dates) - 1) // 2]
    half1 = [item for item in treatment if item["event_date"] <= median_date]
    half2 = [item for item in treatment if item["event_date"] > median_date]
    half1_pnl = sum(item["contribution_usd"] for item in half1)
    half2_pnl = sum(item["contribution_usd"] for item in half2)

    group_pnl: dict[str, float] = defaultdict(float)
    for item in treatment:
        group_pnl[item["group"]] += item["contribution_usd"]
    positive_groups = sum(value > 0 for value in group_pnl.values())
    max_group_positive_pnl_share = _positive_mass_share(list(group_pnl.values()))
    max_decision_positive_pnl_share = _positive_mass_share(contributions)

    frozen_oos_ll_improvement = readiness["event_only_fit"][
        "out_of_sample_log_likelihood_improvement_vs_independent_poisson"
    ]
    bars = {
        "B0_event_arrival_oos_ll_improvement_positive": frozen_oos_ll_improvement
        > 0,
        "B1_mean_decision_contribution_positive": statistics.fmean(contributions)
        > 0,
        "B2_median_decision_contribution_positive": statistics.median(contributions)
        > 0,
        "B3_weighted_net_beats_equal_positive_cohort": primary_net_rate
        > positive_cohort_equal_net,
        "B4_weighted_net_beats_equal_all_oos_cohort": primary_net_rate
        > all_oos_equal_net,
        "B5_both_chronological_halves_positive": half1_pnl > 0 and half2_pnl > 0,
        "B6_at_least_four_groups_positive": positive_groups >= 4,
        "B7_group_positive_pnl_concentration_at_most_40pct": (
            max_group_positive_pnl_share is not None
            and max_group_positive_pnl_share <= CONCENTRATION_CAP
        ),
        "B8_decision_positive_pnl_concentration_at_most_40pct": (
            max_decision_positive_pnl_share is not None
            and max_decision_positive_pnl_share <= CONCENTRATION_CAP
        ),
    }
    passed = all(bars.values())
    failed_bars = sorted(name for name, value in bars.items() if not value)

    group_public = {
        group: {
            "decisions": group_counts[group],
            "aggregate_contribution_usd": group_pnl[group],
        }
        for group in sorted(group_pnl)
    }
    artifact = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "decision": (
            "observed_only_hawkes_edge_supported"
            if passed
            else "rejected_hawkes_return_edge"
        ),
        "result_ceiling": "observed_only",
        "trade_enabled": False,
        "production_impact": {
            "strategy_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "shared_policy_changed": False,
        },
        "frozen_input_hashes": {
            "ledger": _sha256(LEDGER),
            "manifest": _sha256(MANIFEST),
            "sic_peer_index": _sha256(SIC_INDEX),
            "theme_overlay": _sha256(THEME_OVERLAY),
            "active_baseline": _sha256(BASELINE),
        },
        "model": {
            "marks": ["positive", "negative"],
            "half_life_calendar_days": HALF_LIFE_DAYS,
            "fit_window": [str(FORWARD_START), str(FIT_END)],
            "oos_window": [str(OOS_START), str(OOS_END)],
            "optimizer_iterations": iterations,
            "amplitude_matrix_target_by_source": amplitude.tolist(),
            "branching_matrix_target_by_source": branching.tolist(),
            "train_log_likelihood_improvement_vs_independent_poisson": train_ll_improvement,
            "frozen_oos_log_likelihood_improvement_vs_independent_poisson": frozen_oos_ll_improvement,
        },
        "cohort": {
            "events_total": len(events),
            "train_events": len(train_events),
            "oos_events": len(oos_events),
            "positive_score_oos_events": len(positive_score_events),
            "positive_score_events_with_closed_exposures": len(
                positive_score_events_with_closed
            ),
            "independent_group_date_decisions": len(treatment),
            "unique_decision_dates": len(decision_dates),
            "unique_economic_groups": len(group_counts),
            "unique_first_order_tickers": len(source_tickers),
            "closed_unique_peer_legs": closed_unique_legs,
            "all_oos_control_decisions": len(all_oos),
            "max_group_decision_share": max_group_share,
            "max_first_order_ticker_decision_share": max_source_share,
            "group_counts": dict(sorted(group_counts.items())),
            "frozen_assertions": assertions,
        },
        "economics": {
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "group_date_notional_cap_usd": GROUP_DATE_NOTIONAL_USD,
            "total_deployed_notional_usd": total_notional,
            "aggregate_contribution_usd": total_pnl,
            "score_weighted_net_excess_return_per_deployed_dollar": primary_net_rate,
            "equal_notional_positive_score_cohort_net_return": positive_cohort_equal_net,
            "equal_notional_all_oos_group_date_net_return": all_oos_equal_net,
            "mean_decision_contribution_usd": statistics.fmean(contributions),
            "median_decision_contribution_usd": statistics.median(contributions),
            "win_rate": sum(value > 0 for value in contributions) / len(contributions),
        },
        "stability": {
            "median_split_date": str(median_date),
            "half1_decisions": len(half1),
            "half1_contribution_usd": half1_pnl,
            "half2_decisions": len(half2),
            "half2_contribution_usd": half2_pnl,
            "positive_groups": positive_groups,
            "total_groups": len(group_pnl),
            "max_group_positive_pnl_share": max_group_positive_pnl_share,
            "max_decision_positive_pnl_share": max_decision_positive_pnl_share,
            "groups": group_public,
        },
        "acceptance_bars": bars,
        "all_acceptance_bars_pass": passed,
        "failed_bars": failed_bars,
        "gate_notes": {
            "gate1": "Active cash-feasible baseline hash verified; attribution comparator is zero SPY excess plus equal-notional cohorts.",
            "gate2": "All selected closed legs have entry_date. target_price is intentionally not applicable to this fixed H10 observer settlement; no strategy signal contract was changed.",
            "gate3": "Not an entry filter; outcome-blind density passed at 25 independent decisions, 12 dates, 7 groups, and 297 unique settled legs.",
            "gate4": "Canonical Gate 4 is not claimed. This is a settled-forward observed-only attribution with no production change.",
        },
        "reopen_condition_if_rejected": readiness["reopen_condition_if_rejected"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": artifact["decision"],
                "all_acceptance_bars_pass": passed,
                "failed_bars": failed_bars,
                "artifact": str(OUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
