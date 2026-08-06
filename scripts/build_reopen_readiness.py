"""Build data/reopen_readiness.json: machine-readable reopen counters for parked lanes.

Experiment: exp-20260721-004 (measurement_repair, alpha-enabling tooling).

Every parked lane in this repo declares a quantitative reopen_condition, but the
counters live scattered across ticket reflections, park notes, and memory files.
Each scheduled session re-derives them by hand (30+ min) and has already misread
one threshold (Q5>=12 experiment acceptance vs the governing Q5>=20 frozen-family
reopen). This builder computes every machine-derivable counter from canonical
ledgers, carries manual lanes with their last hand-verified values, and flags
lanes whose counters have stopped advancing (park deadlock candidates).

Contract:
- read-only over ledgers; the only write is data/reopen_readiness.json;
- per-lane fail-open: a broken ledger schema marks that lane status=error and
  never crashes the whole build;
- thresholds carry a threshold_source citation so the next agent can audit the
  transcription instead of trusting it;
- history: prior snapshots are kept (capped) so days_since_progress can flag
  structurally stalled reopen conditions per the park-expiry concern.

Run:
    .\\.venv\\Scripts\\python.exe -B scripts\\build_reopen_readiness.py
"""

from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(REPO_ROOT, "data", "reopen_readiness.json")
SCHEMA_VERSION = 1
HISTORY_CAP = 60


def _read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _latest(pattern):
    files = sorted(glob.glob(os.path.join(REPO_ROOT, pattern)))
    return files[-1] if files else None


def _required_nonnegative_int(mapping, key, *, source):
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{source}.{key} must be a non-negative integer")
    return value


def _select_effective_intraday_outcomes(rows):
    """Mirror the canonical latest-pre-execution-cohort aggregation rule.

    A retry can emit multiple immutable primary rows for the same ticker,
    execution timestamp, and horizon.  Readiness must count the latest
    attributable decision in that economic cohort, including when the latest
    row is still pending; filtering to closed rows first would resurrect a
    stale settlement from an earlier retry.
    """

    buckets = {}
    for index, row in enumerate(rows):
        execution_time = str(row.get("execution_time") or "").strip()
        horizon = str(row.get("horizon") or "").strip()
        ticker = str(row.get("ticker") or "").upper().strip()
        if execution_time and ticker:
            key = ("execution", ticker, execution_time, horizon)
        else:
            observation_id = str(row.get("observation_id") or f"row-{index}")
            key = ("observation", observation_id, horizon, str(index))
        buckets.setdefault(key, []).append((index, row))

    selected = []
    for group in buckets.values():
        selected.append(max(
            group,
            key=lambda item: (
                str(item[1].get("decision_timestamp") or ""),
                str(item[1].get("observation_id") or ""),
                item[0],
            ),
        ))
    selected.sort(key=lambda item: item[0])
    return [row for _, row in selected]


def _has_completed_intraday_close(row):
    """Return true only for a completed regular-session five-minute close bar.

    Intraday outcome timestamps are New York-local wall-clock values.  The
    normal-session close bar begins at 15:55 ET.  Malformed or missing times
    fail closed.  Early-close sessions intentionally remain pending until the
    shared outcome contract gains auditable calendar-aware close semantics.
    """

    text = str(row.get("horizon_time") or "").strip()
    if not text:
        return False
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return False
    return (stamp.hour, stamp.minute, stamp.second) == (15, 55, 0)


def _intraday_final_action(row):
    action = row.get("final_action")
    if not isinstance(action, str) or not action.strip():
        raise ValueError(
            "strict intraday readiness rows require a non-empty final_action"
        )
    return action.strip().upper()


def _intraday_chronological_halves(rows):
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.get("decision_timestamp") or ""),
            str(row.get("execution_time") or ""),
            str(row.get("ticker") or "").upper(),
            str(row.get("observation_id") or ""),
        ),
    )
    split = len(ordered) // 2
    return ordered[:split], ordered[split:]


def lane_intraday_triage_completed_close_settlement():
    """Canonical cohort and active-action bars for the intraday surface.

    exp-20260725-001 found that a partial 13:05 ET target session had been
    labelled as ``next_close``.  This lane defensively requires both canonical
    economic-cohort selection and a completed 15:55 ET close bar before a
    next-close row can satisfy the frozen alpha-promotion threshold.

    exp-20260725-002 subsequently froze the power contract for the selected
    REDUCE_RISK hypothesis: at least 20 settled active reductions, with at
    least five in each chronological half.  Counting 100 mostly neutral rows
    cannot identify the treatment and must not mark the lane ready.
    """

    path = _latest(
        "data/daily/intraday/backtests/outcome_ledgers/"
        "intraday_triage_outcomes_*.jsonl"
    )
    if path is None:
        raise FileNotFoundError("intraday outcome ledger is missing")
    rows = _read_jsonl(path)
    outcome_rule_versions = {
        str(row.get("outcome_rule_version") or "").strip() for row in rows
    }
    expected_outcome_rule = "intraday_triage_counterfactual_outcome_v2"
    if outcome_rule_versions != {expected_outcome_rule}:
        raise ValueError(
            "intraday readiness requires one canonical v2 outcome ledger; "
            f"found {sorted(outcome_rule_versions)!r}"
        )
    raw = [
        row for row in rows
        if row.get("primary_ticker_day_decision")
        and row.get("horizon") == "next_close"
    ]
    effective = _select_effective_intraday_outcomes(raw)
    raw_closed = [row for row in raw if row.get("status") == "closed"]
    effective_closed = [
        row for row in effective if row.get("status") == "closed"
    ]
    raw_strict = [row for row in raw_closed if _has_completed_intraday_close(row)]
    effective_strict = [
        row for row in effective_closed if _has_completed_intraday_close(row)
    ]
    first_half, second_half = _intraday_chronological_halves(effective_strict)
    reduce_risk_total = sum(
        _intraday_final_action(row) == "REDUCE_RISK" for row in effective_strict
    )
    first_half_reduce_risk = sum(
        _intraday_final_action(row) == "REDUCE_RISK" for row in first_half
    )
    second_half_reduce_risk = sum(
        _intraday_final_action(row) == "REDUCE_RISK" for row in second_half
    )
    counters = {
        "raw_primary_next_close_rows": len(raw),
        "effective_next_close_rows": len(effective),
        "raw_closed_next_close_rows": len(raw_closed),
        "effective_closed_next_close_rows": len(effective_closed),
        "raw_strict_completed_next_close_settlements": len(raw_strict),
        "strict_effective_next_close_settlements": len(effective_strict),
        "duplicate_economic_rows_excluded": len(raw) - len(effective),
        "incomplete_closed_effective_rows_excluded": (
            len(effective_closed) - len(effective_strict)
        ),
        "strict_effective_next_close_reduce_risk_settlements": reduce_risk_total,
        "first_half_strict_effective_next_close_reduce_risk_settlements": (
            first_half_reduce_risk
        ),
        "second_half_strict_effective_next_close_reduce_risk_settlements": (
            second_half_reduce_risk
        ),
    }
    # exp-20260730-003 consumed the 100/20/5/5 reopen and REJECTED the
    # machine-default REDUCE_RISK attribution on chronological-half
    # instability and positive-value concentration.  The declared new bar is
    # 48 settled active reductions (2x the rejected run's 24, +24 absolute)
    # with at least twelve per chronological half; do not re-reserve below it.
    thresholds = {
        "strict_effective_next_close_settlements": 100,
        "strict_effective_next_close_reduce_risk_settlements": 48,
        "first_half_strict_effective_next_close_reduce_risk_settlements": 12,
        "second_half_strict_effective_next_close_reduce_risk_settlements": 12,
    }
    checks = {
        key: counters[key] >= threshold
        for key, threshold in thresholds.items()
    }
    return {
        "counters": counters,
        "thresholds": thresholds,
        "checks": checks,
        "status": "ready" if all(checks.values()) else "not_ready",
        "threshold_source": (
            "exp-20260714-010 frozen reopen contract (100 effective primary "
            "next-close economic cohorts), corrected by exp-20260725-001 to "
            "require a completed 15:55 ET five-minute close bar, strengthened "
            "by exp-20260725-002/003 (20 settled REDUCE_RISK with five per "
            "chronological half), consumed and REJECTED by exp-20260730-003 "
            "(first-half mean negative, max positive-value ticker share 49% > "
            "40%); new bar from that reflection: 48 settled active reductions "
            "with at least twelve per chronological half"
        ),
        "counter_source": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
        "note": (
            "Readiness is outcome-direction blind. Closed rows with missing, malformed, "
            "or pre-15:55 ET horizon_time are excluded; early-close sessions fail closed "
            "until calendar-aware close semantics are implemented. Power checks use "
            "only decision chronology and final_action; they do not read PnL or returns. "
            "Concentration deadlock risk: even at 48/12/12 the exp-20260730-003 "
            "rejection also requires the max positive-value ticker share to clear "
            "40% at the next evaluation."
        ),
    }


def lane_exit_lifecycle_advisory():
    """Parked exit-advisory lane. The 101/20/8 bar was consumed and rejected by
    exp-20260722-001, then the 212/30/21 bar was consumed and rejected by
    exp-20260806-001 (both adverse_pnl_concentration_too_high; the second probe
    passed every separation/monotonicity/date-support check but concentrated
    59.8% of adverse PnL in one name, cap 50%). New reopen bar from the
    exp-20260806-001 reflection: same post-2026-06-30 cohort settled>=422,
    advisory>=60, hard_stop>=33 (>= +50% and +10 absolute from 281/40/22)."""
    path = _latest("data/exit_lifecycle/outcome_ledgers/exit_lifecycle_outcomes_*.jsonl")
    rows = _read_jsonl(path)
    post = [r for r in rows if str(r.get("observed_date", "")).replace("-", "") > "20260630"]
    closed = [r for r in post if r.get("h5_status") == "closed"]
    adv = Counter(r.get("advisory_bucket") for r in closed)
    advisory_total = adv.get("hard_stop", 0) + adv.get("high_urgency", 0)
    pending_adv = [
        r for r in post
        if r.get("h5_status") != "closed"
        and r.get("advisory_bucket") in ("hard_stop", "high_urgency")
    ]
    counters = {
        "settled": len(closed),
        "hard_stop": adv.get("hard_stop", 0),
        "high_urgency": adv.get("high_urgency", 0),
        "advisory_total": advisory_total,
        "pending_advisory_in_pipeline": len(pending_adv),
    }
    thresholds = {"settled": 422, "hard_stop": 33, "advisory_total": 60}
    ready = all(counters[k] >= v for k, v in thresholds.items())
    return {
        "counters": counters,
        "thresholds": thresholds,
        "status": "ready" if ready else "not_ready",
        "threshold_source": (
            "exp-20260806-001 post_run_reflection new_evidence_required (the "
            "212/30/21 bar matured, was validated, and REJECTED on "
            "adverse_pnl_concentration_too_high at 59.8% vs the 50% cap while "
            "every separation check passed; do not re-reserve below 422/60/33)"
        ),
        "counter_source": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
        "note": (
            "Pending advisory rows settle on an h5 horizon. Any future policy "
            "promotion also requires slot-reuse/winner-collateral accounting and "
            "a shared default-off helper (exp-20260722-001)."
        ),
    }


def lane_short_volume_q5_soft_tilt():
    """Rejected exp-20260716-007. Governing reopen (exp-20260716-007 reflection):
    >=20 PIT-tagged Q5 closed forward rows AND max single-ticker Q5 share <=40%."""
    path = os.path.join(REPO_ROOT, "data", "paper_sleeves", "forward_replacement_value.jsonl")
    rows = _read_jsonl(path)
    uniq = {r["decision_id"]: r for r in rows}
    settled = [
        r for r in uniq.values()
        if r.get("exit_date") and r.get("replacement_value_vs_cash_usd") is not None
    ]
    tagged = [r for r in settled if r.get("entry_short_volume_status") == "ok"]
    q5 = [r for r in tagged if r.get("entry_short_volume_quintile") == 5]
    shares = Counter(r.get("ticker") for r in q5)
    top_ticker, top_n = (shares.most_common(1)[0] if q5 else (None, 0))
    max_share = round(top_n / len(q5), 4) if q5 else 0.0
    counters = {
        "tagged_settled": len(tagged),
        "q5_settled": len(q5),
        "max_q5_ticker_share": max_share,
        "max_q5_ticker": top_ticker,
    }
    thresholds = {"q5_settled": 20, "max_q5_ticker_share_max": 0.40}
    ready = len(q5) >= 20 and max_share <= 0.40
    concentration_blocked = len(q5) > 0 and max_share > 0.40
    return {
        "counters": counters,
        "thresholds": thresholds,
        "status": "ready" if ready else "not_ready",
        "threshold_source": (
            "exp-20260716-007 post_run_reflection (Q5>=20 AND max ticker share <=40%); "
            "NOTE the ticket's own acceptance_rule said Q5>=12 -- the reflection is governing"
        ),
        "counter_source": "data/paper_sleeves/forward_replacement_value.jsonl",
        "note": (
            "Concentration currently breached (deadlock risk): even at Q5>=20 the lane "
            "stays blocked while one ticker holds >40% of Q5 rows."
            if concentration_blocked
            else "Both count and concentration must pass together."
        ),
    }


def lane_move_relief_forward():
    """Accepted MOVE relief sleeve (exp-20260711-004); live activation waits on
    ~30 settled forward rows (project memory move-relief-sleeve-accepted-2026-07-11)."""
    path = os.path.join(
        REPO_ROOT, "data", "paper_sleeves", "move_rate_volatility_relief", "snapshots.jsonl"
    )
    rows = _read_jsonl(path)
    last = rows[-1] if rows else {}
    counters = {
        "closed_position_count": int(last.get("closed_position_count") or 0),
        "pending_count": int(last.get("new_pending_count") or 0),
        "snapshot_asof": last.get("asof_date"),
    }
    thresholds = {"closed_position_count": 30}
    return {
        "counters": counters,
        "thresholds": thresholds,
        "status": "ready" if counters["closed_position_count"] >= 30 else "not_ready",
        "threshold_source": "live-activation bar noted at exp-20260711-004 acceptance (~30 forward rows)",
        "counter_source": "data/paper_sleeves/move_rate_volatility_relief/snapshots.jsonl",
        "note": "Sleeve only fires on MOVE relief trigger days; zero rows is trigger drought, not breakage.",
    }


def lane_prediction_market_postfix():
    """Outcome-blind reopen contract for the post-fetch-repair cohort.

    exp-20260718-002 froze a seven-part bar after the old endpoint had starved
    the observer.  Market identity is provider_market_id; only markets whose
    first persisted daily snapshot is on/after the repair date can contribute.
    Candidate decisions retain the repair audit's economic identity
    (market, ticker, observed date, horizon), so a market returned by two query
    groups cannot inflate the settled count.
    """

    cutoff = "2026-07-18"
    daily_paths = sorted(glob.glob(os.path.join(
        REPO_ROOT,
        "data/non_ohlcv/prediction_market_event_observer/daily/"
        "prediction_market_event_observer_*.json",
    )))
    if not daily_paths:
        raise FileNotFoundError("prediction-market daily snapshots are missing")

    first_seen_by_market = {}
    probability_by_market_date = {}
    postfix_observation_rows = 0
    for daily_path in daily_paths:
        name = os.path.basename(daily_path)
        date_tag = name.removeprefix(
            "prediction_market_event_observer_"
        ).removesuffix(".json")
        try:
            file_date = datetime.strptime(date_tag, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(
                f"prediction-market daily filename has invalid date: {name}"
            ) from exc
        with open(daily_path, encoding="utf-8-sig") as fh:
            items = json.load(fh)
        if not isinstance(items, list):
            raise ValueError(f"prediction-market daily snapshot must be an array: {name}")
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(
                    f"prediction-market daily item {name}[{index}] must be an object"
                )
            market_id = str(item.get("provider_market_id") or "").strip()
            if not market_id:
                raise ValueError(
                    f"prediction-market daily item {name}[{index}] lacks provider_market_id"
                )
            previous = first_seen_by_market.get(market_id)
            first_seen_by_market[market_id] = min(previous, file_date) if previous else file_date
            probability = item.get("yes_probability")
            if probability is None:
                continue
            if isinstance(probability, bool) or not isinstance(probability, (int, float)):
                raise ValueError(
                    f"prediction-market probability {name}[{index}] must be numeric or null"
                )
            value = float(probability)
            if value < 0.0 or value > 1.0:
                raise ValueError(
                    f"prediction-market probability {name}[{index}] must be in [0, 1]"
                )
            observations = probability_by_market_date.setdefault(market_id, {})
            prior_value = observations.get(file_date)
            if prior_value is not None and abs(prior_value - value) > 1e-12:
                raise ValueError(
                    "prediction-market duplicate market/date carries conflicting probabilities: "
                    f"{market_id} {file_date}"
                )
            observations[file_date] = value

    postfix_markets = {
        market_id
        for market_id, first_seen in first_seen_by_market.items()
        if first_seen >= cutoff
    }
    for daily_path in daily_paths:
        name = os.path.basename(daily_path)
        date_tag = name.removeprefix(
            "prediction_market_event_observer_"
        ).removesuffix(".json")
        file_date = datetime.strptime(date_tag, "%Y%m%d").strftime("%Y-%m-%d")
        if file_date < cutoff:
            continue
        with open(daily_path, encoding="utf-8-sig") as fh:
            items = json.load(fh)
        postfix_observation_rows += sum(
            str(item.get("provider_market_id") or "").strip() in postfix_markets
            for item in items
        )

    path = _latest(
        "data/non_ohlcv/prediction_market_event_observer/outcome_ledgers/"
        "prediction_market_event_observer_outcomes_*.jsonl"
    )
    if path is None:
        raise FileNotFoundError("prediction-market outcome ledger is missing")
    rows = _read_jsonl(path)
    unique_settled = {}
    duplicate_rows_excluded = 0
    for index, row in enumerate(rows):
        if str(row.get("outcome_status") or "").lower() != "settled":
            continue
        market_id = str(row.get("provider_market_id") or "").strip()
        observed_date = str(row.get("observed_date") or "").strip()
        if market_id not in postfix_markets:
            continue
        try:
            canonical_observed_date = datetime.strptime(
                observed_date, "%Y-%m-%d"
            ).strftime("%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(
                f"prediction-market settled row {index} has invalid observed_date"
            ) from exc
        if canonical_observed_date != observed_date:
            raise ValueError(
                f"prediction-market settled row {index} has invalid observed_date"
            )
        if canonical_observed_date < cutoff:
            continue
        ticker = str(row.get("candidate_ticker") or "").upper().strip()
        query_id = str(row.get("prediction_market_query_id") or "").strip().lower()
        horizon = row.get("horizon_trading_days")
        if (
            not ticker
            or not query_id
            or isinstance(horizon, bool)
            or not isinstance(horizon, int)
            or horizon <= 0
            or not row.get("exit_date")
        ):
            raise ValueError(
                f"prediction-market settled row {index} lacks canonical identity fields"
            )
        if canonical_observed_date < first_seen_by_market[market_id]:
            continue
        identity = (market_id, ticker, canonical_observed_date, horizon)
        if identity in unique_settled:
            duplicate_rows_excluded += 1
            continue
        unique_settled[identity] = {
            "candidate_ticker": ticker,
            "prediction_market_query_id": query_id,
            "observed_date": canonical_observed_date,
        }

    settled = list(unique_settled.values())
    ticker_counts = Counter(str(row["candidate_ticker"]).upper() for row in settled)
    query_counts = Counter(str(row["prediction_market_query_id"]) for row in settled)
    top_ticker_share = (
        round(ticker_counts.most_common(1)[0][1] / len(settled), 6)
        if settled
        else None
    )
    top_query_share = (
        round(query_counts.most_common(1)[0][1] / len(settled), 6)
        if settled
        else None
    )

    changed_markets = 0
    five_point_markets = 0
    for market_id in postfix_markets:
        values = [
            value
            for _, value in sorted(
                probability_by_market_date.get(market_id, {}).items()
            )
        ]
        deltas = [abs(current - prior) for prior, current in zip(values, values[1:])]
        changed_markets += any(delta > 1e-12 for delta in deltas)
        five_point_markets += any(delta >= 0.05 - 1e-12 for delta in deltas)

    counters = {
        "postfix_observation_rows": postfix_observation_rows,
        "postfix_unique_markets": len(postfix_markets),
        "raw_settled_candidate_rows": len(settled) + duplicate_rows_excluded,
        "unique_settled_candidates": len(settled),
        "duplicate_candidate_rows_excluded": duplicate_rows_excluded,
        "decision_date_count": len({row["observed_date"] for row in settled}),
        "query_group_count": len(query_counts),
        "top_ticker_share": top_ticker_share,
        "top_query_share": top_query_share,
        "markets_with_any_probability_change": changed_markets,
        "markets_with_any_5pp_move": five_point_markets,
    }
    thresholds = {
        "unique_settled_candidates": 60,
        "decision_date_count": 10,
        "query_group_count": 3,
        "top_ticker_share_max": 0.15,
        "top_query_share_max": 0.50,
        "markets_with_any_probability_change": 20,
        "markets_with_any_5pp_move": 10,
    }
    checks = {
        "unique_settled_candidates_at_least_60": len(settled) >= 60,
        "decision_dates_at_least_10": counters["decision_date_count"] >= 10,
        "query_groups_at_least_3": counters["query_group_count"] >= 3,
        "top_ticker_share_at_most_15pct": (
            top_ticker_share <= 0.15 if top_ticker_share is not None else False
        ),
        "top_query_share_at_most_50pct": (
            top_query_share <= 0.50 if top_query_share is not None else False
        ),
        "markets_with_probability_change_at_least_20": changed_markets >= 20,
        "markets_with_5pp_move_at_least_10": five_point_markets >= 10,
    }
    return {
        "counters": counters,
        "thresholds": thresholds,
        "checks": checks,
        "status": "ready" if all(checks.values()) else "not_ready",
        "threshold_source": (
            "exp-20260718-002 post_run_reflection new_evidence_required: post-repair "
            "first-seen markets only; >=60 unique settled candidates, >=10 decision "
            "dates, >=3 query groups, top ticker <=15%, top query <=50%, >=20 "
            "markets with a nonzero probability change, and >=10 with a >=5pp move"
        ),
        "counter_source": (
            "data/non_ohlcv/prediction_market_event_observer/daily/"
            "prediction_market_event_observer_*.json; "
            + os.path.relpath(path, REPO_ROOT).replace("\\", "/")
        ),
        "note": (
            "Readiness is outcome-direction blind. The settled identity reproduces the "
            "exp-20260718-002 repair audit (provider market, ticker, observed date, "
            "horizon); duplicate query mappings cannot inflate it. Decision-date is the "
            "audit's observed-date breadth, not the shared next-session execution date."
        ),
    }


def lane_entity_theme_axis_c():
    """Observed-only refresh exp-20260729-006 baseline: 73275 settled rows.
    Axis-(c) requires >=+50% growth (>=109913) before a same-face re-probe."""
    path = os.path.join(
        REPO_ROOT, "data", "non_ohlcv", "entity_theme_news_observer", "latest_outcome_summary.json"
    )
    d = json.load(open(path, encoding="utf-8"))
    baseline = 73275
    current = int(d.get("settled_count") or 0)
    counters = {
        "settled_count": current,
        "baseline_at_last_probe": baseline,
        "growth_pct": round((current - baseline) / baseline * 100, 2),
    }
    thresholds = {"settled_count": (baseline * 3 + 1) // 2}
    return {
        "counters": counters,
        "thresholds": thresholds,
        "status": "ready" if current >= thresholds["settled_count"] else "not_ready",
        "threshold_source": "AGENTS.md section 2.4 axis (c): >=+50% and >=+10 settled rows vs exp-20260729-006 baseline",
        "counter_source": "data/non_ohlcv/entity_theme_news_observer/latest_outcome_summary.json",
        "note": None,
    }


def lane_flow_options_lead():
    """exp-20260721-001 lead. Reopen: >=10 additional genuine forward PIT flow
    collection dates (after 2026-07-20) AND >=20 settled paired disagreement
    decisions. Only the collection-date half is machine-derivable here."""
    path = os.path.join(REPO_ROOT, "data", "non_ohlcv", "moomoo_capital_flow_day", "rows.jsonl")
    first_fetch_by_date = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            fd = str(r.get("flow_date", ""))
            if fd <= "2026-07-20":
                continue
            fa = str(r.get("fetched_at", ""))[:10]
            prev = first_fetch_by_date.get(fd)
            if prev is None or fa < prev:
                first_fetch_by_date[fd] = fa
    pit_dates = [
        fd for fd, fa in first_fetch_by_date.items()
        if fa and (datetime.fromisoformat(fa) - datetime.fromisoformat(fd)).days <= 2
    ]
    counters = {
        "forward_pit_flow_dates_post_20260720": len(pit_dates),
        "settled_paired_disagreement_decisions": None,
    }
    thresholds = {"forward_pit_flow_dates_post_20260720": 10, "settled_paired_disagreement_decisions": 20}
    return {
        "counters": counters,
        "thresholds": thresholds,
        "status": "not_ready",
        "threshold_source": "exp-20260721-001 post_run_reflection new_evidence_required",
        "counter_source": "data/non_ohlcv/moomoo_capital_flow_day/rows.jsonl (flow archive confirmed daily-refreshing 2026-07-21)",
        "note": (
            "Paired-disagreement settlement count is not machine-derivable from a single "
            "ledger yet; recount it manually (owner codex-root) before declaring ready."
        ),
    }


def lane_allocator_cross_source_conflict():
    """Parked exp-20260720-004. Reopen: >=20 settled forward same-day core-entry x
    sleeve-candidate conflict rows, or a genuinely new allocator funding mechanism."""
    return {
        "counters": {"settled_conflict_rows_last_manual": 9},
        "thresholds": {"settled_conflict_rows": 20},
        "status": "manual_check_required",
        "threshold_source": "exp-20260720-004 park declaration",
        "counter_source": "manual join over allocator forward face (last hand-verified 2026-07-20: 9 closed, conflict rate ~0)",
        "note": "No single canonical ledger exposes the conflict join; automate only if the lane matters again.",
    }


def lane_news_propagation_negative_side():
    """Inverted-polarity news propagation lead. Reopen: 200 closed negative-side
    forward rows before reading direction again (do not re-slice earlier)."""
    return {
        "counters": {"negative_side_closed_last_manual": 56},
        "thresholds": {"negative_side_closed": 200},
        "status": "manual_check_required",
        "threshold_source": "news-propagation line park note (project memory, 2026-07-19: 56/200, early mean excess_10d ~ -946bp)",
        "counter_source": "manual count over news propagation forward ledger (polarity field mapping unresolved)",
        "note": "Early direction is OPPOSITE the replay lead; record-only until 200 rows.",
    }


def lane_phase2_estimate_revision():
    """Discovery-layer Phase 2 NO-GO (exp-20260721-002). Reopen requires ALL of:
    >=30 qualified non-flat independent decisions, >=10 mapped tickers, >=10
    structured actual cash conflicts, >=30 settled decisions at each of H5/H10/H20,
    passing source contracts, and a fresh outcome-blind D0-D3 scope that selects."""
    path = os.path.join(
        REPO_ROOT,
        "data",
        "non_ohlcv",
        "estimate_revision_readiness_latest.json",
    )
    with open(path, encoding="utf-8") as fh:
        readiness = json.load(fh)
    if not isinstance(readiness, dict):
        raise ValueError("estimate-revision readiness root must be an object")
    expected_surface = "analyst_estimate_revision_forward_decisions"
    if readiness.get("surface_id") != expected_surface:
        raise ValueError(
            "estimate-revision readiness surface_id must be "
            f"{expected_surface!r}"
        )
    settled = readiness.get("settled_independent_decisions_by_horizon")
    if not isinstance(settled, dict):
        raise ValueError(
            "estimate-revision readiness settled_independent_decisions_by_horizon "
            "must be an object"
        )
    counters = {
        "qualified_nonflat_decisions": _required_nonnegative_int(
            readiness,
            "independent_decisions",
            source="estimate_revision_readiness",
        ),
        "mapped_tickers": _required_nonnegative_int(
            readiness,
            "mapped_ticker_count",
            source="estimate_revision_readiness",
        ),
        "actual_cash_conflicts": _required_nonnegative_int(
            readiness,
            "actual_cash_conflict_decisions",
            source="estimate_revision_readiness",
        ),
        "settled_h5": _required_nonnegative_int(
            settled,
            "h5",
            source="estimate_revision_readiness.settled_independent_decisions_by_horizon",
        ),
        "settled_h10": _required_nonnegative_int(
            settled,
            "h10",
            source="estimate_revision_readiness.settled_independent_decisions_by_horizon",
        ),
        "settled_h20": _required_nonnegative_int(
            settled,
            "h20",
            source="estimate_revision_readiness.settled_independent_decisions_by_horizon",
        ),
    }
    thresholds = {
        "qualified_nonflat_decisions": 30,
        "mapped_tickers": 10,
        "actual_cash_conflicts": 10,
        "settled_h5": 30,
        "settled_h10": 30,
        "settled_h20": 30,
    }
    ready = all(counters[key] >= threshold for key, threshold in thresholds.items())
    return {
        "counters": counters,
        "thresholds": thresholds,
        "status": "ready" if ready else "not_ready",
        "threshold_source": "docs/alpha_search_phase1_handoff.md Phase 1.5 (exp-20260721-002)",
        "counter_source": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
        "note": (
            "Counters come from the canonical default-off readiness artifact. Legacy rows "
            "remain quarantined and do not count. Passing these numeric bars still requires "
            "source-contract checks plus a fresh outcome-blind D0-D3 scope and verified "
            "promotion before any alpha experiment."
        ),
    }


def _unique_decisions(rows):
    by_id = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        decision_id = str(row.get("decision_id") or "").strip()
        if decision_id:
            by_id[decision_id] = row
    return by_id


def _drawdown_daily_snapshots(path):
    """Return one canonical snapshot per as-of date.

    Daily jobs may be retried, so summing the append-only file directly would
    inflate Gate-3 coverage.  The last row for a date is the canonical retry.
    """

    if not os.path.exists(path):
        return []
    latest_by_date = {}
    for row in _read_jsonl(path):
        if not isinstance(row, dict):
            continue
        asof = str(row.get("asof_date") or "").strip()
        if asof:
            latest_by_date[asof] = row
    return [latest_by_date[key] for key in sorted(latest_by_date)]


def _minimum_per_explicit_evaluation_window(selected, closed):
    """Compute window-density only when state rows carry explicit labels.

    The accepted observer did not define calendar buckets in its state schema.
    Guessing month/half boundaries here would manufacture a pass.  A future
    promotion run can annotate ``evaluation_window`` on every decision, at
    which point this builder will compute the requirement without a schema
    change.  Until then both values remain unknown.
    """

    selected_rows = list(selected.values())
    closed_rows = list(closed.values())
    if not selected_rows:
        return None, None, 0
    if any(not str(row.get("evaluation_window") or "").strip() for row in selected_rows):
        return None, None, 0
    if any(not str(row.get("evaluation_window") or "").strip() for row in closed_rows):
        return None, None, 0
    selected_counts = Counter(
        str(row["evaluation_window"]).strip() for row in selected_rows
    )
    settled_counts = Counter(
        str(row["evaluation_window"]).strip() for row in closed_rows
    )
    windows = sorted(selected_counts)
    return (
        min(selected_counts[window] for window in windows),
        min(settled_counts.get(window, 0) for window in windows),
        len(windows),
    )


def _drawdown_outcome_metrics(closed, *, minimum_closed):
    """Read outcome direction only after the declared forward reopen count."""

    rows = list(closed.values())
    if len(rows) < minimum_closed:
        return None, None, None
    rows.sort(
        key=lambda row: (
            str(row.get("exit_date") or ""),
            str(row.get("entry_date") or ""),
            str(row.get("decision_id") or ""),
        )
    )
    values = []
    for row in rows:
        # The frozen paper state records round-trip-cost-adjusted PnL.  Cash has
        # zero return over the same single-slot envelope, so this is its net
        # replacement value versus cash.  Prefer an explicit field if a future
        # schema adds one.
        value = row.get("replacement_value_vs_cash_usd")
        if value is None:
            value = row.get("pnl")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None, None, None
        values.append(float(value))
    split = len(rows) // 2
    if split == 0 or split == len(rows):
        return None, None, None
    first_half = round(sum(values[:split]), 2)
    second_half = round(sum(values[split:]), 2)

    positive_by_ticker = Counter()
    for row, value in zip(rows, values):
        if value <= 0:
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            return first_half, second_half, None
        positive_by_ticker[ticker] += value
    positive_total = sum(positive_by_ticker.values())
    max_share = (
        round(max(positive_by_ticker.values()) / positive_total, 6)
        if positive_total > 0
        else None
    )
    return first_half, second_half, max_share


def lane_core_drawdown_flow_put_stabilization():
    """Accepted default-off observer from exp-20260723-004.

    The forward paper state is the only source for decision and outcome counts.
    The exp-20260723-004 replay artifact is cited for the frozen rule and reopen
    contract only; its retrospective recent folds never contribute forward
    rows here.
    """

    state_path = os.path.join(
        REPO_ROOT,
        "data",
        "paper_sleeves",
        "core_drawdown_flow_put_stabilization",
        "state.json",
    )
    snapshots_path = os.path.join(
        REPO_ROOT,
        "data",
        "paper_sleeves",
        "core_drawdown_flow_put_stabilization",
        "snapshots.jsonl",
    )
    state_exists = os.path.exists(state_path)
    if state_exists:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
        if not isinstance(state, dict):
            raise ValueError("core drawdown paper state root must be an object")
    else:
        state = {}

    state_lists = {}
    for key in ("pending_entries", "open_positions", "closed_positions", "skipped_entries"):
        value = state.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"core drawdown paper state {key} must be an array")
        state_lists[key] = value
    closed = _unique_decisions(state_lists["closed_positions"])
    selected = _unique_decisions(
        state_lists["pending_entries"]
        + state_lists["open_positions"]
        + state_lists["closed_positions"]
        + state_lists["skipped_entries"]
    )

    snapshots = _drawdown_daily_snapshots(snapshots_path)
    generated = 0
    survived = 0
    for snapshot in snapshots:
        stages = snapshot.get("stage_counts")
        if not isinstance(stages, dict):
            continue
        generated_value = stages.get("price_stabilized")
        survived_value = stages.get("options_complete")
        if (
            isinstance(generated_value, int)
            and not isinstance(generated_value, bool)
            and generated_value >= 0
        ):
            generated += generated_value
        if (
            isinstance(survived_value, int)
            and not isinstance(survived_value, bool)
            and survived_value >= 0
        ):
            survived += survived_value
    survival_rate = round(survived / generated, 6) if generated > 0 else None

    minimum_closed = 20
    first_half, second_half, max_positive_share = _drawdown_outcome_metrics(
        closed,
        minimum_closed=minimum_closed,
    )
    min_selected_window, min_settled_window, window_count = (
        _minimum_per_explicit_evaluation_window(selected, closed)
    )
    counters = {
        "independent_selected_decisions": len(selected),
        "independent_closed_decisions": len(closed),
        "daily_price_stabilized_signals": generated,
        "daily_options_complete_signals": survived,
        "survival_rate": survival_rate,
        "first_half_net_replacement_value_usd": first_half,
        "second_half_net_replacement_value_usd": second_half,
        "max_single_ticker_positive_pnl_share": max_positive_share,
        "minimum_selected_decisions_per_evaluation_window": min_selected_window,
        "minimum_settled_decisions_per_evaluation_window": min_settled_window,
        "explicit_evaluation_window_count": window_count,
    }
    thresholds = {
        "independent_closed_decisions": minimum_closed,
        "survival_rate": 0.05,
        "first_half_net_replacement_value_usd": 0.0,
        "second_half_net_replacement_value_usd": 0.0,
        "max_single_ticker_positive_pnl_share_max": 0.40,
        "minimum_selected_decisions_per_evaluation_window": 5,
        "minimum_settled_decisions_per_evaluation_window": 5,
    }
    checks = {
        "independent_closed_decisions_at_least_20": len(closed) >= minimum_closed,
        "survival_rate_at_least_5pct": (
            survival_rate >= 0.05 if survival_rate is not None else None
        ),
        "positive_net_replacement_value_both_chronological_halves": (
            first_half > 0 and second_half > 0
            if first_half is not None and second_half is not None
            else None
        ),
        "single_ticker_positive_pnl_share_at_most_40pct": (
            max_positive_share <= 0.40 if max_positive_share is not None else None
        ),
        "at_least_5_selected_and_5_settled_per_evaluation_window": (
            min_selected_window >= 5 and min_settled_window >= 5
            if min_selected_window is not None and min_settled_window is not None
            else None
        ),
    }
    ready = all(value is True for value in checks.values())
    unknown = [name for name, value in checks.items() if value is None]
    missing_state_note = (
        "Canonical state does not exist yet, so the truthful forward closed count is 0. "
        if not state_exists
        else ""
    )
    unknown_note = (
        "Unknown checks remain fail-closed: " + ", ".join(unknown) + ". "
        if unknown
        else ""
    )
    return {
        "counters": counters,
        "thresholds": thresholds,
        "threshold_semantics": {
            "first_half_net_replacement_value_usd": "strictly_greater_than",
            "second_half_net_replacement_value_usd": "strictly_greater_than",
            "max_single_ticker_positive_pnl_share_max": "less_than_or_equal",
        },
        "checks": checks,
        "status": "ready" if ready else "not_ready",
        "threshold_source": (
            "exp-20260723-004 frozen contract and "
            "data/experiments/exp-20260723-004/"
            "exp_20260723_004_core_drawdown_flow_put_observer.json reopen_condition; "
            "ticket next_retry_requires supplies the >=5 selected/settled per-window bar"
        ),
        "counter_source": (
            "data/paper_sleeves/core_drawdown_flow_put_stabilization/state.json; "
            "data/paper_sleeves/core_drawdown_flow_put_stabilization/snapshots.jsonl"
        ),
        "note": (
            missing_state_note
            + unknown_note
            + "Retrospective exp-20260723-004 folds are provenance only and never count "
            "as forward decisions. Outcome direction stays unread until 20 independent "
            "closed decisions. Evaluation-window density stays unknown until decisions "
            "carry explicit evaluation_window labels."
        ),
    }


def lane_form4_sale_overhang_forward():
    """Prospective Form 4 context decisions with fixed 10d/20d outcomes.

    exp-20260728-007 repaired a structurally starved observer.  Only rows in
    its append-only post-effective-date ledger may advance this lane; the 622
    historical ticker-context snapshots are provenance and never forward
    evidence.  Observer health is a binding fail-closed check.
    """

    state_path = os.path.join(
        REPO_ROOT,
        "data",
        "non_ohlcv",
        "form4_sale_overhang_forward",
        "state.json",
    )
    state_exists = os.path.exists(state_path)
    if state_exists:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
        if not isinstance(state, dict):
            raise ValueError("Form4 forward state root must be an object")
    else:
        state = {}

    progress = state.get("forward_reopen_progress") or {}
    if not isinstance(progress, dict):
        raise ValueError("Form4 forward_reopen_progress must be an object")
    health = state.get("health") or {}
    if not isinstance(health, dict):
        raise ValueError("Form4 forward health must be an object")

    def _count(key):
        value = progress.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"Form4 forward progress {key} must be a non-negative integer")
        return value

    closed = _count("closed_forward_rows_current")
    high_closed = _count("high_sale_overhang_closed_forward_rows_current")
    complete = _count("replacement_value_complete_closed_rows_current")
    unique_tickers = _count("unique_tickers_closed_forward_rows")
    share = progress.get("max_single_ticker_closed_forward_row_share")
    if share is not None and (
        isinstance(share, bool)
        or not isinstance(share, (int, float))
        or share < 0
        or share > 1
    ):
        raise ValueError("Form4 max single-ticker share must be null or in [0, 1]")

    counters = {
        "closed_forward_rows": closed,
        "high_sale_overhang_closed_forward_rows": high_closed,
        "replacement_value_complete_closed_rows": complete,
        "unique_tickers_closed_forward_rows": unique_tickers,
        "max_single_ticker_closed_forward_row_share": share,
        "observer_health_fail_closed": bool(health.get("fail_closed", True)),
    }
    thresholds = {
        "closed_forward_rows": 25,
        "high_sale_overhang_closed_forward_rows": 8,
        "replacement_value_complete_closed_rows": 25,
        "max_single_ticker_closed_forward_row_share_max": 0.40,
    }
    checks = {
        "closed_forward_rows_at_least_25": closed >= 25,
        "high_sale_overhang_closed_forward_rows_at_least_8": high_closed >= 8,
        "all_closed_rows_have_cash_spy_qqq_replacement_values": (
            complete == closed and closed >= 25
        ),
        "single_ticker_share_at_most_40pct": (
            share <= 0.40 if share is not None and closed else False
        ),
        "observer_health_ok": (
            state_exists
            and not bool(health.get("fail_closed", True))
            and str(health.get("status") or "").startswith("ok")
        ),
    }
    ready = all(checks.values())
    missing_note = (
        "Forward state does not exist yet; all counters truthfully remain zero. "
        if not state_exists
        else ""
    )
    return {
        "counters": counters,
        "thresholds": thresholds,
        "checks": checks,
        "status": "ready" if ready else "not_ready",
        "threshold_source": (
            "exp-20260629-003 and exp-20260707-018 frozen Form4 reopen contract; "
            "exp-20260728-007 makes observer health binding and excludes every "
            "pre-effective-date reconstruction from forward evidence"
        ),
        "counter_source": (
            "data/non_ohlcv/form4_sale_overhang_forward/state.json"
        ),
        "note": (
            missing_note
            + "Readiness is outcome-direction blind. Only immutable prospective "
            "decisions at or after the exp-20260728-007 effective date and their "
            "fixed 10d/20d cash/SPY/QQQ settlements count. A missing or stale "
            "candidate/context producer fails closed."
        ),
    }


def lane_massive_dividend_restart_forward():
    """Frozen >=30 settled restart-decision bar from exp-20260803-002.

    Readiness counts only unique settlement events.  The summary is used for
    producer health and an independent count cross-check; replacement values,
    returns, and comparator outcomes are deliberately never read here.
    """

    root = os.path.join(
        REPO_ROOT,
        "data",
        "non_ohlcv",
        "massive_dividend_restart_forward",
    )
    ledger_path = os.path.join(root, "settlement_ledger.jsonl")
    summary_path = os.path.join(root, "latest_settlement_summary.json")
    ledger_exists = os.path.exists(ledger_path)
    summary_exists = os.path.exists(summary_path)

    rows = _read_jsonl(ledger_path) if ledger_exists else []
    if summary_exists:
        with open(summary_path, encoding="utf-8") as fh:
            summary = json.load(fh)
        if not isinstance(summary, dict):
            raise ValueError("Massive dividend-restart settlement summary must be an object")
    else:
        summary = {}

    settlements_by_decision = {}
    duplicate_settlement_events = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(
                f"Massive dividend-restart settlement row {index} must be an object"
            )
        if row.get("record_type") != "settlement":
            continue
        decision_key = str(row.get("decision_key") or "").strip()
        if not decision_key:
            raise ValueError(
                f"Massive dividend-restart settlement row {index} lacks decision_key"
            )
        if decision_key in settlements_by_decision:
            duplicate_settlement_events += 1
            continue
        settlements_by_decision[decision_key] = row

    settled_restart = [
        row
        for row in settlements_by_decision.values()
        if row.get("settled") is True
        and row.get("gap_variant") == "restart_after_observed_gap"
    ]

    summary_count = summary.get("settled_restart_decision_count", 0)
    if (
        isinstance(summary_count, bool)
        or not isinstance(summary_count, int)
        or summary_count < 0
    ):
        raise ValueError(
            "Massive dividend-restart summary settled_restart_decision_count "
            "must be a non-negative integer"
        )
    if summary_exists:
        reopen_progress = summary.get("reopen_progress")
        if not isinstance(reopen_progress, dict):
            raise ValueError(
                "Massive dividend-restart summary reopen_progress must be an object"
            )
        progress_required = _required_nonnegative_int(
            reopen_progress,
            "required",
            source="massive_dividend_restart_summary.reopen_progress",
        )
        progress_count = _required_nonnegative_int(
            reopen_progress,
            "settled_restart_decisions",
            source="massive_dividend_restart_summary.reopen_progress",
        )
    else:
        progress_required = 0
        progress_count = 0
    expected_required = 30
    contract_identity_ok = (
        summary_exists
        and summary.get("scope")
        == "default_off_massive_dividend_restart_forward_settlement"
        and summary.get("source_experiment") == "exp-20260803-002"
        and summary.get("target_gap_variant") == "restart_after_observed_gap"
        and summary.get("reopen_required_settled_decisions") == expected_required
        and progress_required == expected_required
        and summary.get("observer_only") is True
        and summary.get("trade_enabled") is False
    )
    producer_health_ok = (
        summary_exists
        and summary.get("status") == "ok"
        and summary.get("alert") is False
    )
    summary_ledger_aligned = (
        summary_exists
        and summary_count == len(settled_restart)
        and progress_count == len(settled_restart)
    )

    counters = {
        "unique_settlement_events": len(settlements_by_decision),
        "duplicate_settlement_events_excluded": duplicate_settlement_events,
        "settled_restart_decisions": len(settled_restart),
        "summary_settled_restart_decisions": summary_count,
        "summary_reopen_progress_required": progress_required,
        "summary_reopen_progress_settled_restart_decisions": progress_count,
    }
    thresholds = {"settled_restart_decisions": expected_required}
    checks = {
        "settlement_ledger_exists": ledger_exists,
        "settlement_summary_exists": summary_exists,
        "producer_health_ok": producer_health_ok,
        "frozen_contract_identity_ok": contract_identity_ok,
        "summary_ledger_counts_aligned": summary_ledger_aligned,
        "settled_restart_decisions_at_least_30": (
            len(settled_restart) >= expected_required
        ),
    }
    missing = []
    if not ledger_exists:
        missing.append("settlement ledger")
    if not summary_exists:
        missing.append("settlement summary")
    missing_note = (
        "Missing " + " and ".join(missing) + "; readiness remains fail-closed. "
        if missing
        else ""
    )
    return {
        "counters": counters,
        "thresholds": thresholds,
        "checks": checks,
        "status": "ready" if all(checks.values()) else "not_ready",
        "threshold_source": (
            "exp-20260803-002 accepted first-build settlement contract and "
            "post_run_reflection: reopen only at >=30 settled "
            "restart_after_observed_gap H10 decisions"
        ),
        "counter_source": (
            "data/non_ohlcv/massive_dividend_restart_forward/settlement_ledger.jsonl; "
            "data/non_ohlcv/massive_dividend_restart_forward/"
            "latest_settlement_summary.json"
        ),
        "note": (
            missing_note
            + "Readiness is outcome-direction blind. Only record_type=settlement, "
            "settled=true, gap_variant=restart_after_observed_gap rows count, with "
            "decision_key deduplication and an independent healthy-summary alignment "
            "check. Membership, selection, comparator, and settlement policies remain "
            "frozen."
        ),
    }


LANES = {
    "core_drawdown_flow_put_stabilization": lane_core_drawdown_flow_put_stabilization,
    "form4_sale_overhang_forward": lane_form4_sale_overhang_forward,
    "intraday_triage_completed_close_settlement": lane_intraday_triage_completed_close_settlement,
    "exit_lifecycle_advisory": lane_exit_lifecycle_advisory,
    "short_volume_q5_soft_tilt": lane_short_volume_q5_soft_tilt,
    "move_relief_forward": lane_move_relief_forward,
    "prediction_market_postfix": lane_prediction_market_postfix,
    "massive_dividend_restart_forward": lane_massive_dividend_restart_forward,
    "entity_theme_axis_c": lane_entity_theme_axis_c,
    "flow_options_lead": lane_flow_options_lead,
    "allocator_cross_source_conflict": lane_allocator_cross_source_conflict,
    "news_propagation_negative_side": lane_news_propagation_negative_side,
    "phase2_estimate_revision": lane_phase2_estimate_revision,
}

STALL_DAYS = 7  # counters unchanged this long => flag as potential park deadlock


def _load_previous():
    if os.path.exists(OUTPUT_PATH):
        try:
            return json.load(open(OUTPUT_PATH, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _numeric_counters(counters):
    return {k: v for k, v in counters.items() if isinstance(v, (int, float))}


def build():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now[:10]
    prev = _load_previous()
    prev_lanes = {l["lane"]: l for l in (prev or {}).get("lanes", [])}

    lanes_out = []
    for name, fn in LANES.items():
        try:
            lane = fn()
        except Exception as exc:  # per-lane fail-open by contract
            lane = {
                "counters": {},
                "thresholds": {},
                "status": "error",
                "threshold_source": None,
                "counter_source": None,
                "note": f"builder error: {type(exc).__name__}: {exc}",
            }
        lane["lane"] = name

        history = list(prev_lanes.get(name, {}).get("history", []))
        numeric = _numeric_counters(lane["counters"])
        if not history or _numeric_counters(history[-1].get("counters", {})) != numeric:
            history.append({"as_of": today, "counters": numeric})
        history = history[-HISTORY_CAP:]
        lane["history"] = history

        last_change = history[-1]["as_of"] if history else today
        days_stale = (datetime.fromisoformat(today) - datetime.fromisoformat(last_change)).days
        lane["days_since_progress"] = days_stale
        lane["stalled"] = (
            days_stale >= STALL_DAYS and lane["status"] not in ("ready", "error")
        )
        lanes_out.append(lane)

    order = {"ready": 0, "not_ready": 1, "accumulating": 2, "manual_check_required": 3, "error": 4}
    lanes_out.sort(key=lambda l: (order.get(l["status"], 9), l["lane"]))

    out = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now,
        "generator": (
            "scripts/build_reopen_readiness.py "
            "(exp-20260721-004; Form4 lane exp-20260728-007; "
            "prediction/Massive contract registration exp-20260804-001)"
        ),
        "stall_flag_days": STALL_DAYS,
        "lanes": lanes_out,
    }
    tmp = OUTPUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, OUTPUT_PATH)
    return out


def main():
    out = build()
    print(f"wrote {os.path.relpath(OUTPUT_PATH, REPO_ROOT)}  ({len(out['lanes'])} lanes)")
    width = max(len(l["lane"]) for l in out["lanes"]) + 2
    for l in out["lanes"]:
        gaps = []
        for k, bar in l["thresholds"].items():
            if k.endswith("_max"):
                cur = l["counters"].get(k[: -len("_max")])
                if isinstance(cur, (int, float)) and cur > bar:
                    gaps.append(f"{k[:-4]}={cur}>{bar}")
                continue
            cur = l["counters"].get(k)
            if isinstance(cur, (int, float)) and cur < bar:
                gaps.append(f"{k}={cur}/{bar}")
        flag = " [STALLED]" if l.get("stalled") else ""
        print(f"  {l['lane']:<{width}} {l['status']:<22} {'; '.join(gaps) or '-'}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
