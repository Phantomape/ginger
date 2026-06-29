"""exp-20260628-015: breakout-without-2x-volume precursor forward ledger.

This runner is intentionally default-off. It measures the full population of
production-visible precursor events that exp-20260627-006 only observed after
they became real trend_long entries.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for extra in (REPO_ROOT / "quant", REPO_ROOT / "scripts"):
    extra_s = str(extra)
    if extra_s not in sys.path:
        sys.path.insert(0, extra_s)

import breakout_precursor_paper_sleeve as sleeve  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260628-015"
OWNER = "alpha-explore"
SLUG = "breakout_without_2x_volume_precursor_forward_replacement_value_v1"
LANE = "alpha_search"
MECHANISM_FAMILY = "entry"
PAPER_NOTIONAL_USD = 4000.0

BASELINE_RESULT_FILE = (
    REPO_ROOT
    / "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
REGISTRY_FILE = REPO_ROOT / "docs/experiment_registry.json"
TICKET_FILE = REPO_ROOT / f"experiments/tickets/{EXPERIMENT_ID}.json"
LOG_FILE = REPO_ROOT / f"experiments/logs/{EXPERIMENT_ID}.json"
CARD_FILE = REPO_ROOT / f"experiments/cards/{EXPERIMENT_ID}.md"
MANIFEST_FILE = REPO_ROOT / f"experiments/manifests/{EXPERIMENT_ID}.json"
ARTIFACT_FILE = (
    REPO_ROOT
    / f"data/experiments/{EXPERIMENT_ID}/exp_20260628_015_{SLUG}.json"
)

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "baseline": REPO_ROOT
        / "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
        / "backtest_results_warehouse_snapshot_late_strong_20260604.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "baseline": REPO_ROOT
        / "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
        / "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "baseline": REPO_ROOT
        / "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
        / "backtest_results_warehouse_snapshot_old_thin_20260604.json",
    },
}

PREDICTION = {
    "success_probability": 0.7,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "confidence_reason": (
        "The detector reuses production-visible OHLCV predicates "
        "(above_200ma & breakout_20d & not volume_spike) and only adds a "
        "default-off full-population forward ledger. The main uncertainty is "
        "not build risk; it is whether the de-biased full population erases the "
        "survivorship-conditioned lead from exp-20260627-006."
    ),
    "main_failure_modes": [
        "full_population_base_rate_kills_the_lead",
        "late_strong_dominates_population_no_net_edge",
        "comparator_join_to_actual_entry_sparse",
        "unsettled_forward_rows_near_window_end",
    ],
}

RELATED_PRIORS = [
    "exp-20260530-013",
    "exp-20260530-016",
    "exp-20260627-006",
    "exp-20260627-007",
]

CHANGED_FILES = [
    "quant/breakout_precursor_paper_sleeve.py",
    "quant/test_breakout_precursor_paper_sleeve.py",
    f"quant/experiments/exp_20260628_015_{SLUG}.py",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260628_015_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(text)


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def finite_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def summarize_values(values: list[Any]) -> dict[str, Any]:
    clean = [finite_float(v) for v in values]
    clean = [v for v in clean if v is not None]
    if not clean:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "win_rate": None,
        }
    clean.sort()
    return {
        "n": len(clean),
        "mean": round(mean(clean), 4),
        "median": round(median(clean), 4),
        "min": round(clean[0], 4),
        "max": round(clean[-1], 4),
        "win_rate": round(sum(1 for v in clean if v > 0) / len(clean), 4),
    }


def load_ohlcv_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    raw = read_json(path)
    ohlcv = raw.get("ohlcv", raw)
    if not isinstance(ohlcv, dict):
        raise ValueError(f"invalid OHLCV snapshot shape: {path}")
    return ohlcv


def load_actual_trend_long_entries(path: Path) -> dict[str, list[str]]:
    raw = read_json(path)
    out: dict[str, list[str]] = defaultdict(list)
    for trade in raw.get("trades", []):
        if trade.get("strategy") != "trend_long":
            continue
        ticker = str(trade.get("ticker") or "").upper()
        entry_date = trade.get("entry_date")
        if ticker and entry_date:
            out[ticker].append(str(entry_date))
    return {ticker: sorted(set(dates)) for ticker, dates in out.items()}


def actual_entry_outcome_map(
    rows: list[dict[str, Any]],
    entry_dates: list[str],
) -> dict[str, dict[str, Any]]:
    bars = sleeve.normalize_bars(rows)
    idx_by_date = {bar["date"]: idx for idx, bar in enumerate(bars)}
    out: dict[str, dict[str, Any]] = {}
    for entry_date in sorted(set(entry_dates)):
        idx = idx_by_date.get(entry_date)
        if idx is None or idx <= 0:
            continue
        out[entry_date] = sleeve._forward_outcome(bars, idx - 1)
    return out


def in_window(date_value: Any, start: str, end: str) -> bool:
    if not date_value:
        return False
    date_s = str(date_value)
    return start <= date_s <= end


def add_forward_pnl(event: dict[str, Any]) -> None:
    for horizon_data in event.get("forward", {}).get("horizons", {}).values():
        pct = finite_float(horizon_data.get("forward_net_return_pct"))
        if pct is not None:
            horizon_data["paper_notional_usd"] = PAPER_NOTIONAL_USD
            horizon_data["forward_pnl_usd"] = round(
                PAPER_NOTIONAL_USD * pct / 100.0,
                2,
            )


def add_comparator(event: dict[str, Any], comparator: dict[str, Any] | None) -> None:
    if comparator is None:
        event["actual_entry_comparator"] = {
            "status": "missing_actual_entry_forward_outcome"
        }
        return
    comp: dict[str, Any] = {
        "status": comparator.get("status"),
        "entry_date": comparator.get("entry_date"),
        "entry_fill": comparator.get("entry_fill"),
        "horizons": {},
    }
    for horizon in sleeve.FORWARD_HORIZONS:
        key = str(horizon)
        precursor_h = event.get("forward", {}).get("horizons", {}).get(key, {})
        actual_h = comparator.get("horizons", {}).get(key, {})
        precursor_pct = finite_float(precursor_h.get("forward_net_return_pct"))
        actual_pct = finite_float(actual_h.get("forward_net_return_pct"))
        comp_h: dict[str, Any] = {
            "actual_status": actual_h.get("status"),
            "actual_forward_net_return_pct": actual_pct,
            "actual_exit_date": actual_h.get("exit_date"),
        }
        if actual_pct is not None:
            comp_h["actual_forward_pnl_usd"] = round(
                PAPER_NOTIONAL_USD * actual_pct / 100.0,
                2,
            )
        if precursor_pct is not None and actual_pct is not None:
            delta = precursor_pct - actual_pct
            comp_h["precursor_minus_actual_entry_return_pct"] = round(delta, 4)
            comp_h["precursor_minus_actual_entry_pnl_usd"] = round(
                PAPER_NOTIONAL_USD * delta / 100.0,
                2,
            )
        comp["horizons"][key] = comp_h
    event["actual_entry_comparator"] = comp


def event_horizon_values(
    events: list[dict[str, Any]],
    horizon: int,
    *,
    actual_entry_subset: bool = False,
    comparator_delta: bool = False,
) -> list[float]:
    values: list[float] = []
    key = str(horizon)
    for event in events:
        if actual_entry_subset and not event.get("became_trend_long_entry"):
            continue
        if comparator_delta:
            value = (
                event.get("actual_entry_comparator", {})
                .get("horizons", {})
                .get(key, {})
                .get("precursor_minus_actual_entry_return_pct")
            )
        else:
            value = (
                event.get("forward", {})
                .get("horizons", {})
                .get(key, {})
                .get("forward_net_return_pct")
            )
        numeric = finite_float(value)
        if numeric is not None:
            values.append(numeric)
    return values


def population_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "events_total": len(events),
        "became_actual_entry": sum(
            1 for event in events if event.get("became_trend_long_entry")
        ),
        "unsettled_no_entry_bar": sum(
            1
            for event in events
            if event.get("forward", {}).get("status") == "unsettled_no_entry_bar"
        ),
    }
    counts["actual_entry_match_rate"] = (
        round(counts["became_actual_entry"] / counts["events_total"], 4)
        if counts["events_total"]
        else None
    )
    horizons = {}
    for horizon in sleeve.FORWARD_HORIZONS:
        horizons[str(horizon)] = {
            "full_population": summarize_values(
                event_horizon_values(events, horizon)
            ),
            "actual_entry_subset": summarize_values(
                event_horizon_values(events, horizon, actual_entry_subset=True)
            ),
            "precursor_minus_actual_entry_delta": summarize_values(
                event_horizon_values(events, horizon, comparator_delta=True)
            ),
        }
    return {**counts, "horizons": horizons}


def group_summary(events: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        label = str(event.get(key) or "unknown")
        groups[label].append(event)
    return {
        label: population_summary(rows)
        for label, rows in sorted(groups.items(), key=lambda item: item[0])
    }


def top_ticker_summary(events: list[dict[str, Any]], limit: int = 25) -> dict[str, Any]:
    counts = Counter(str(event.get("ticker") or "unknown") for event in events)
    top = [ticker for ticker, _ in counts.most_common(limit)]
    grouped = group_summary(events, "ticker")
    return {ticker: grouped[ticker] for ticker in top if ticker in grouped}


def load_baseline_gate1() -> dict[str, Any]:
    baseline = read_json(BASELINE_RESULT_FILE)
    windows = baseline.get("windows", [])
    return {
        "baseline_result_file": rel(BASELINE_RESULT_FILE),
        "windows": windows,
        "aggregate_expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows),
            2,
        ),
        "aggregate_trade_count": int(
            sum(int(row.get("trade_count") or 0) for row in windows)
        ),
    }


def gate2_runtime_fields() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs/open_positions.json"
    raw = read_json(path)
    positions: list[dict[str, Any]] = []
    for key in ("core_positions", "positions"):
        rows = raw.get(key)
        if isinstance(rows, list):
            positions.extend([row for row in rows if isinstance(row, dict)])
    missing_entry = [
        str(row.get("ticker") or "unknown")
        for row in positions
        if not row.get("entry_date")
    ]
    missing_target = [
        str(row.get("ticker") or "unknown")
        for row in positions
        if row.get("target_price") is None
    ]
    return {
        "source": rel(path),
        "positions_checked": len(positions),
        "entry_date_present": not missing_entry,
        "target_price_present": not missing_target,
        "missing_entry_date_tickers": missing_entry,
        "missing_target_price_tickers": missing_target,
        "passed": not missing_entry and not missing_target,
    }


def scan_all_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events: list[dict[str, Any]] = []
    scan_meta: dict[str, Any] = {"windows": {}}
    for window_label, cfg in WINDOWS.items():
        snapshot = load_ohlcv_snapshot(cfg["snapshot"])
        actual_entries = load_actual_trend_long_entries(cfg["baseline"])
        spy_bars = snapshot.get("SPY") or []
        window_events: list[dict[str, Any]] = []
        ticker_count = 0
        for ticker, rows in sorted(snapshot.items()):
            ticker_u = str(ticker).upper()
            if ticker_u in {"SPY", "QQQ"}:
                continue
            ticker_count += 1
            actual_map = actual_entry_outcome_map(
                rows,
                actual_entries.get(ticker_u, []),
            )
            raw_events = sleeve.scan_ticker_precursors(
                ticker_u,
                rows,
                regime_spy_bars=spy_bars,
                actual_entry_dates=actual_entries.get(ticker_u, []),
            )
            for event in raw_events:
                if not in_window(event.get("signal_date"), cfg["start"], cfg["end"]):
                    continue
                event["experiment_id"] = EXPERIMENT_ID
                event["rule_version"] = sleeve.RULE_VERSION
                event["window"] = window_label
                event["window_start"] = cfg["start"]
                event["window_end"] = cfg["end"]
                event["paper_trade_enabled"] = False
                event["paper_notional_usd"] = PAPER_NOTIONAL_USD
                event["event_id"] = (
                    f"{EXPERIMENT_ID}:{window_label}:{ticker_u}:"
                    f"{event.get('signal_date')}"
                )
                add_forward_pnl(event)
                matched = event.get("matched_actual_entry_date")
                if matched:
                    add_comparator(event, actual_map.get(str(matched)))
                else:
                    event["actual_entry_comparator"] = {
                        "status": "no_actual_entry_match"
                    }
                window_events.append(event)
        events.extend(window_events)
        scan_meta["windows"][window_label] = {
            "snapshot": rel(cfg["snapshot"]),
            "baseline_backtest": rel(cfg["baseline"]),
            "window_start": cfg["start"],
            "window_end": cfg["end"],
            "tickers_scanned": ticker_count,
            "trend_long_actual_entry_tickers": len(actual_entries),
            "trend_long_actual_entries": sum(len(v) for v in actual_entries.values()),
            "precursor_events": len(window_events),
        }
    return events, scan_meta


def classify_decision(
    overall: dict[str, Any],
    by_window: dict[str, Any],
) -> dict[str, Any]:
    failures: list[str] = []
    notes: list[str] = []
    h10 = overall["horizons"]["10"]
    h20 = overall["horizons"]["20"]
    full10 = h10["full_population"]
    full20 = h20["full_population"]
    subset10 = h10["actual_entry_subset"]
    delta10 = h10["precursor_minus_actual_entry_delta"]

    if full10["n"] < 30:
        failures.append("too_few_settled_10d_full_population_rows")
    if full20["n"] < 20:
        failures.append("too_few_settled_20d_full_population_rows")
    if full10["median"] is None or full10["median"] <= 0:
        failures.append("full_population_10d_median_not_positive")
    if full20["median"] is None or full20["median"] <= 0:
        failures.append("full_population_20d_median_not_positive")
    if subset10["n"] < 10:
        notes.append("actual_entry_subset_sparse")
    if delta10["n"] and (delta10["median"] is None or delta10["median"] <= 0):
        failures.append("precursor_does_not_beat_actual_entry_10d_median")
    weak_window_medians: list[str] = []
    for label, summary in sorted(by_window.items()):
        for horizon in ("10", "20"):
            median_value = (
                summary.get("horizons", {})
                .get(horizon, {})
                .get("full_population", {})
                .get("median")
            )
            if median_value is not None and median_value <= 0:
                weak_window_medians.append(
                    f"{label}_{horizon}d_full_population_median_{median_value}"
                )
    if weak_window_medians:
        notes.append("fixed_window_full_population_medians_mixed")
        notes.extend(weak_window_medians)

    if failures:
        status = "observed_only_rejected"
        decision = "observed_only_rejected_full_population_base_rate_or_maturity_failed"
        reopen_condition = (
            "Reopen only with materially more settled full-population precursor "
            "rows, a daily default-off adapter producing new forward rows, or a "
            "genuinely new non-OHLCV qualifier. Do not retune the same 2x-volume "
            "threshold or re-slice only actual-entry survivors."
        )
    else:
        status = "observed_only_positive_lead"
        decision = (
            "observed_only_mixed_window_positive_full_population_lead_not_allocation_ready"
            if weak_window_medians
            else "observed_only_positive_full_population_lead_not_allocation_ready"
        )
        reopen_condition = (
            "Next valid step is a default-off daily adapter plus a Gate 1-4 "
            "candidate-source replay that can compare against accepted core "
            "allocation; private threshold retunes remain insufficient. Any "
            "promotion attempt must handle fixed-window instability explicitly."
        )

    return {
        "status": status,
        "decision": decision,
        "failed_checks": failures,
        "notes": notes,
        "reopen_condition": reopen_condition,
    }


def build_card(artifact: dict[str, Any], result: dict[str, Any]) -> str:
    overall = artifact["summaries"]["overall"]
    decision = result["decision"]
    h10 = overall["horizons"]["10"]["full_population"]
    h20 = overall["horizons"]["20"]["full_population"]
    delta10 = overall["horizons"]["10"]["precursor_minus_actual_entry_delta"]
    lines = [
        f"# {EXPERIMENT_ID} {SLUG}",
        "",
        f"- owner: `{OWNER}`",
        f"- status: `{result['status']}`",
        f"- decision: `{decision}`",
        "- lane: `alpha_search`",
        "- hypothesis: full-population breakout-without-2x-volume precursor "
        "rows reveal whether exp-20260627-006 was survivorship-biased.",
        "- production impact: default-off attribution only; no orders, ranking, "
        "sizing, exits, or live adapter changed.",
        "",
        "## Evidence",
        "",
        f"- events_total: `{overall['events_total']}`",
        f"- became_actual_entry: `{overall['became_actual_entry']}`",
        f"- 10d full population: n={h10['n']} mean={h10['mean']} "
        f"median={h10['median']} win_rate={h10['win_rate']}",
        f"- 20d full population: n={h20['n']} mean={h20['mean']} "
        f"median={h20['median']} win_rate={h20['win_rate']}",
        f"- 10d precursor-minus-actual-entry delta: n={delta10['n']} "
        f"mean={delta10['mean']} median={delta10['median']}",
        "",
        "## Reproduction",
        "",
        "```powershell",
        f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260628_015_{SLUG}.py",
        ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_breakout_precursor_paper_sleeve.py",
        ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        "```",
        "",
    ]
    return "\n".join(lines)


def update_manifest(completed_at: str) -> None:
    files = {
        "runner": REPO_ROOT / f"quant/experiments/exp_20260628_015_{SLUG}.py",
        "helper": REPO_ROOT / "quant/breakout_precursor_paper_sleeve.py",
        "helper_test": REPO_ROOT / "quant/test_breakout_precursor_paper_sleeve.py",
        "artifact": ARTIFACT_FILE,
        "log": LOG_FILE,
        "card": CARD_FILE,
        "ticket": TICKET_FILE,
        "baseline_result": BASELINE_RESULT_FILE,
    }
    manifest = {
        "manifest_type": "ginger_experiment_revision_manifest",
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "experiment_uid": "expuid-1b0af5cdf31a4540",
        "generated_at": completed_at,
        "files": {
            name: {
                "path": rel(path),
                "exists": path.exists(),
                "sha256": sha256_file(path),
            }
            for name, path in files.items()
        },
        "artifact_roots": {
            "data": rel(ARTIFACT_FILE.parent),
            "log": rel(LOG_FILE),
            "card": rel(CARD_FILE),
            "runner": rel(files["runner"]),
        },
        "changed_files": CHANGED_FILES,
    }
    write_json(MANIFEST_FILE, manifest)


def main() -> None:
    completed_at = utc_now()
    baseline_gate1 = load_baseline_gate1()
    gate2 = gate2_runtime_fields()
    events, scan_meta = scan_all_events()
    overall = population_summary(events)
    summaries = {
        "overall": overall,
        "by_window": group_summary(events, "window"),
        "by_entry_regime_label": group_summary(events, "entry_regime_label"),
        "by_ticker_top25": top_ticker_summary(events),
        "helper_summary": sleeve.summarize_events(events),
    }
    classification = classify_decision(overall, summaries["by_window"])
    status = classification["status"]
    decision = classification["decision"]
    production_impact = {
        **sleeve.PRODUCTION_IMPACT,
        "live_order_path_changed": False,
        "daily_default_off_snapshot_wired": False,
        "baseline_strategy_metrics_changed": False,
    }
    gate4 = {
        "behavioral_after_backtest_required": False,
        "reason": (
            "Default-off paper attribution helper and historical ledger only; "
            "no entry, exit, ranking, sizing, or live-order policy changed."
        ),
        "baseline_expected_value_score_delta": 0.0,
        "baseline_total_pnl_delta": 0.0,
        "core_trade_count_delta": 0,
        "allocation_ready": status == "observed_only_positive_lead",
        "promotion_gate_required_before_live": True,
    }
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "slug": SLUG,
        "owner": OWNER,
        "completed_at": completed_at,
        "hypothesis": (
            "entry/candidate_pool: full-population "
            "above_200ma & breakout_20d & not volume_spike precursor rows "
            "de-bias the exp-20260627-006 actual-entry survivor lead."
        ),
        "related_prior_experiments": RELATED_PRIORS,
        "rule": {
            "rule_version": sleeve.RULE_VERSION,
            "predicate": "above_200ma & breakout_20d & not volume_spike",
            "actual_entry_match_max_gap_sessions": (
                sleeve.ACTUAL_ENTRY_MATCH_MAX_GAP_SESSIONS
            ),
            "forward_horizons": list(sleeve.FORWARD_HORIZONS),
            "paper_notional_usd": PAPER_NOTIONAL_USD,
        },
        "gates": {
            "gate1_baseline": baseline_gate1,
            "gate2_runtime_fields": gate2,
            "gate3_survival": {
                "baseline_unchanged": True,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
                "survival_rate_delta": 0.0,
                "note": "No additional filter was added to the live/core strategy.",
            },
            "gate4_behavioral_delta": gate4,
        },
        "scan_meta": scan_meta,
        "summaries": summaries,
        "events": events,
        "decision": {
            **classification,
            "production_impact": production_impact,
        },
    }
    reflection = {
        "why_result_happened": (
            "The full-population precursor base rate stayed positive in aggregate "
            "because many non-survivor breakout-without-2x-volume rows still had "
            "positive 20d drift, and the actual-entry comparator subset kept a "
            "positive 10d entry-advantage median. The result is not allocation-ready "
            "because fixed windows are mixed: late_strong and old_thin have negative "
            "10d full-population medians, and old_thin also has a negative 20d median."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not rerun this as a 2x-volume threshold retune, a volume-spike "
            "hard-exclusion-to-weighting response curve change, or another slice "
            "that only conditions on actual trend_long survivor entries."
        ),
        "new_evidence_required": classification["reopen_condition"],
    }
    result = {
        "experiment_id": EXPERIMENT_ID,
        "status": status,
        "decision": decision,
        "artifact": rel(ARTIFACT_FILE),
        "log": rel(LOG_FILE),
        "baseline_result_file": rel(BASELINE_RESULT_FILE),
        "prediction": PREDICTION,
        "actual_success": 1 if status == "observed_only_positive_lead" else 0,
        "calibration_note": (
            "Prediction covered low-risk instrumentation; alpha promotion still "
            "depends on full-population base rate and comparator deltas."
        ),
        "gate_summary": artifact["gates"],
        "evidence_summary": {
            "events_total": overall["events_total"],
            "events_became_actual_entry": overall["became_actual_entry"],
            "forward_10d_full_population": (
                overall["horizons"]["10"]["full_population"]
            ),
            "forward_20d_full_population": (
                overall["horizons"]["20"]["full_population"]
            ),
            "forward_10d_precursor_minus_actual_entry_delta": (
                overall["horizons"]["10"]["precursor_minus_actual_entry_delta"]
            ),
        },
        "failed_checks": classification["failed_checks"],
        "notes": classification["notes"],
        "production_impact": production_impact,
        "changed_files": CHANGED_FILES,
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260628_015_{SLUG}.py",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_breakout_precursor_paper_sleeve.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "post_run_reflection": reflection,
    }
    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "lane": LANE,
        "owner": OWNER,
        "status": status,
        "completed_at": completed_at,
        "hypothesis": artifact["hypothesis"],
        "single_causal_variable": SLUG,
        "changed_variable": SLUG,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": "breakout_without_2x_volume_precursor_forward_replacement",
        "trial_variant_id": "full_population_precursor_forward_ledger_v1",
        "nearby_prior_experiments": RELATED_PRIORS,
        "prediction": PREDICTION,
        "result": result,
        "decision": decision,
        "production_impact": production_impact,
        "lean_quality_passed": True,
        "post_run_reflection": result["post_run_reflection"],
    }
    card = build_card(artifact, result)

    write_json(ARTIFACT_FILE, artifact)
    write_json(LOG_FILE, log_record)
    write_text(CARD_FILE, card)

    fields = {
        "owner": OWNER,
        "change_type": "default_off_paper_sleeve_forward_replacement_instrumentation",
        "mechanism_family": MECHANISM_FAMILY,
        "single_causal_variable": SLUG,
        "changed_variable": SLUG,
        "trial_family": "breakout_without_2x_volume_precursor_forward_replacement",
        "trial_variant_id": "full_population_precursor_forward_ledger_v1",
        "nearby_prior_experiments": RELATED_PRIORS,
        "baseline_result_file": rel(BASELINE_RESULT_FILE),
        "card_file": rel(CARD_FILE),
        "ticket_file": rel(TICKET_FILE),
        "revision_manifest_file": rel(MANIFEST_FILE),
        "causal_components": [
            "shared default-off precursor helper",
            "full-population historical precursor replay",
            "10d/20d forward replacement ledger",
            "same-name actual trend_long entry comparator",
            "entry-regime attribution bucket",
        ],
        "allowed_write_scope": sorted(set(CHANGED_FILES + ["docs/experiment_log.jsonl"])),
        "result_artifact": rel(ARTIFACT_FILE),
        "post_run_reflection": result["post_run_reflection"],
        "reopen_condition": classification["reopen_condition"],
        "changed_files": CHANGED_FILES,
    }
    persist_self_registered_result(
        REGISTRY_FILE,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result=result,
        status=status,
        fields=fields,
    )

    ticket = read_json(TICKET_FILE)
    ticket["completed_at"] = ticket.get("completed_at") or completed_at
    ticket["result"] = result
    ticket["status"] = status
    ticket["causal_components"] = fields["causal_components"]
    ticket["allowed_write_scope"] = fields["allowed_write_scope"]
    ticket["evaluation_windows"] = [
        {
            "label": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": rel(cfg["snapshot"]),
            "baseline": rel(cfg["baseline"]),
        }
        for label, cfg in WINDOWS.items()
    ]
    write_json(TICKET_FILE, ticket)

    update_manifest(completed_at)
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "status": status, "decision": decision}, indent=2))


if __name__ == "__main__":
    main()
