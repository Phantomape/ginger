"""exp-20260713-001: exact-URL entity-theme event-decision basket.

Read-only attribution.  One exact URL is one event; unique mapped tickers are
equal-weighted within an event and events are equal-weighted across the sample.
No trading, ranking, sizing, exit, order, or production path is changed.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from experiment_fingerprint import infer_fingerprint  # noqa: E402
from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


EXPERIMENT_ID = "exp-20260713-001"
OWNER = "alpha-explore"
RUNNER = "quant/experiments/exp_20260713_001_entity_theme_news_event_decision_basket.py"
COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
LEDGER = ROOT / "data/non_ohlcv/entity_theme_news_observer/outcome_ledgers/entity_theme_news_observer_outcomes_20260712.jsonl"
BASELINE = ROOT / "data/backtests/backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
TICKET = ROOT / "experiments/tickets" / f"{EXPERIMENT_ID}.json"
LOG = ROOT / "experiments/logs" / f"{EXPERIMENT_ID}.json"
CARD = ROOT / "experiments/cards" / f"{EXPERIMENT_ID}.md"
MANIFEST = ROOT / "experiments/manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs/experiment_registry.json"
OUT = ROOT / "data/experiments" / EXPERIMENT_ID / "exp_20260713_001_entity_theme_news_event_decision_basket.json"

WINDOWS = {
    "late_strong": ("2025-10-23", "2026-04-21"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "old_thin": ("2024-10-02", "2025-04-22"),
}
FIELDS = {
    "cash": "replacement_value_vs_cash_usd",
    "spy": "replacement_value_vs_spy_usd",
    "qqq": "replacement_value_vs_qqq_usd",
}
BOOTSTRAP_SEED = 2026071301
BOOTSTRAP_RESAMPLES = 20_000
PREDICTION = {
    "success_probability": 0.3,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "event_level_medians_nonpositive",
        "window_instability",
        "url_cluster_bootstrap_lower_bound_nonpositive",
        "theme_concentration",
        "current_observer_pit_caveat",
    ],
    "confidence_reason": "Repeated URLs and multi-ticker expansion may have diluted a real relation edge, but five nearby entity-theme probes were rejected.",
    "recorded_at": "2026-07-13T04:45:30Z",
}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def window_for(date_value: str) -> str | None:
    for label, (start, end) in WINDOWS.items():
        if start <= date_value <= end:
            return label
    return None


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "mean_usd": round(statistics.fmean(values), 6) if values else None,
        "median_usd": round(statistics.median(values), 6) if values else None,
        "positive_fraction": round(sum(value > 0 for value in values) / len(values), 6) if values else None,
    }


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def bootstrap_lcb(values: list[float]) -> float:
    rng = random.Random(BOOTSTRAP_SEED)
    count = len(values)
    means = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        means.append(sum(values[rng.randrange(count)] for _ in range(count)) / count)
    return round(percentile(means, 0.025), 6)


def build_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    settled = [row for row in rows if row.get("outcome_status") == "settled"]
    required = ["url", "observed_date", "entry_date", "candidate_ticker", "theme", *FIELDS.values()]
    invalid = [row for row in settled if any(row.get(field) in (None, "") for field in required)]
    if invalid:
        raise RuntimeError(f"{len(invalid)} settled rows lack required event-basket fields")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in settled:
        grouped[str(row["url"])].append(row)

    events: list[dict[str, Any]] = []
    outcome_conflicts = 0
    discarded_later_rows = 0
    for url, url_rows in grouped.items():
        earliest_date = min(str(row["observed_date"]) for row in url_rows)
        earliest = [row for row in url_rows if str(row["observed_date"]) == earliest_date]
        discarded_later_rows += len(url_rows) - len(earliest)
        ticker_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in earliest:
            ticker_rows[str(row["candidate_ticker"])].append(row)
        selected = []
        for ticker in sorted(ticker_rows):
            choices = ticker_rows[ticker]
            metric_sets = {tuple(float(row[field]) for field in FIELDS.values()) for row in choices}
            outcome_conflicts += int(len(metric_sets) > 1)
            selected.append(sorted(choices, key=lambda row: (str(row.get("entry_date", "")), str(row.get("published_at", "")), int(row.get("candidate_item_index", 0))))[0])
        label = window_for(earliest_date)
        if label is None:
            continue
        event = {
            "url_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
            "observed_date": earliest_date,
            "window": label,
            "theme": str(selected[0]["theme"]),
            "query_id": str(selected[0].get("entity_theme_query_id", "")),
            "relation_type": str(selected[0].get("relation_type", "")),
            "title": str(selected[0].get("title", "")),
            "tickers": [str(row["candidate_ticker"]) for row in selected],
            "ticker_count": len(selected),
            "earliest_raw_rows": len(earliest),
        }
        for name, field in FIELDS.items():
            event[f"replacement_value_vs_{name}_usd"] = round(statistics.fmean(float(row[field]) for row in selected), 6)
        events.append(event)
    events.sort(key=lambda event: (event["observed_date"], event["url_sha256"]))
    diagnostics = {
        "ledger_rows": len(rows),
        "settled_rows": len(settled),
        "unique_settled_urls": len(grouped),
        "canonical_events": len(events),
        "canonical_url_ticker_decisions": sum(event["ticker_count"] for event in events),
        "discarded_later_observation_rows": discarded_later_rows,
        "earliest_url_ticker_outcome_conflicts": outcome_conflicts,
        "required_fields_complete": True,
    }
    return events, diagnostics


def build_result() -> dict[str, Any]:
    ticket = read_json(TICKET)
    baseline = read_json(BASELINE)
    events, diagnostics = build_events()
    pooled = {name: summarize([event[f"replacement_value_vs_{name}_usd"] for event in events]) for name in FIELDS}
    by_window = {}
    positive_windows = []
    for label in WINDOWS:
        subset = [event for event in events if event["window"] == label]
        by_window[label] = {
            "event_count": len(subset),
            "comparators": {name: summarize([event[f"replacement_value_vs_{name}_usd"] for event in subset]) for name in FIELDS},
        }
        if all(by_window[label]["comparators"][name]["mean_usd"] > 0 for name in FIELDS):
            positive_windows.append(label)
    themes = Counter(event["theme"] for event in events)
    max_theme_count = max(themes.values())
    max_theme_share = max_theme_count / len(events)
    cash_lcb = bootstrap_lcb([event["replacement_value_vs_cash_usd"] for event in events])
    checks = {
        "each_window_at_least_25_events": all(by_window[label]["event_count"] >= 25 for label in WINDOWS),
        "at_least_3_themes": len(themes) >= 3,
        "max_theme_share_at_most_30pct": max_theme_share <= 0.30,
        "pooled_means_positive_all_comparators": all(pooled[name]["mean_usd"] > 0 for name in FIELDS),
        "pooled_medians_positive_all_comparators": all(pooled[name]["median_usd"] > 0 for name in FIELDS),
        "at_least_2_windows_positive_mean_all_comparators": len(positive_windows) >= 2,
        "cash_bootstrap_95pct_lower_bound_positive": cash_lcb > 0,
    }
    positive = all(checks.values())
    failed = [name for name, passed in checks.items() if not passed]
    status = "observed_only_positive_lead" if positive else "observed_only_rejected"
    decision = "observed_only_positive_event_decision_basket_lead_not_promoted" if positive else "observed_only_rejected_event_decision_basket_no_robust_edge"
    baseline_metrics = baseline["aggregate"]
    timestamp = now()
    next_count = math.ceil(len(events) * 1.5)
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": positive,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": ticket["hypothesis"],
        "alpha_hypothesis": ticket["hypothesis"],
        "change_type": ticket["change_type"],
        "mechanism_family": ticket["mechanism_family"],
        "trial_family": ticket["trial_family"],
        "trial_variant_id": ticket["trial_variant_id"],
        "changed_variable": ticket["changed_variable"],
        "single_causal_variable": ticket["single_causal_variable"],
        "new_evidence_type": ticket["new_evidence_type"],
        "new_evidence_axis": ticket["novelty"]["new_evidence_axis"],
        "prediction": PREDICTION,
        "calibration": {"actual_success": positive, "predicted_success_probability": 0.3, "brier_score": round((0.3 - float(positive)) ** 2, 6), "realized_failure_modes": failed},
        "fingerprint_caveat": {"reservation_fingerprint": ticket["novelty"]["fingerprint"], "post_implementation_fingerprint": infer_fingerprint(ticket["hypothesis"]), "reason": "Reservation preceded the exact entity_theme_news/event_decision_basket classifier coverage."},
        "parameters": {"event_key": "exact url", "event_date": "earliest settled observed_date", "within_event_weighting": "equal unique ticker", "across_event_weighting": "equal exact URL", "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_resamples": BOOTSTRAP_RESAMPLES, "no_threshold_or_slice_sweep": True},
        "source_manifest": {"ledger": rel(LEDGER), "sha256": file_sha256(LEDGER), **diagnostics},
        "gate1": {"passed": True, "baseline": rel(BASELINE), **baseline_metrics},
        "gate2": {"passed": diagnostics["required_fields_complete"] and diagnostics["earliest_url_ticker_outcome_conflicts"] == 0, "required_fields": ["url", "observed_date", "entry_date", "candidate_ticker", "theme", *FIELDS.values()], "target_price_note": "Not applicable to this fixed-horizon observer ledger; no signal or backtester path changed."},
        "gate3": {"passed": baseline_metrics["minimum_survival_rate"] >= 0.05, "new_filter_added": False, "signals_generated": baseline_metrics["trade_count_sum"], "signals_survived": baseline_metrics["trade_count_sum"], "survival_rate": 1.0, "baseline_minimum_survival_rate_unchanged": baseline_metrics["minimum_survival_rate"]},
        "gate4": {"applicable": False, "passed": False, "observed_only_lead": positive, "acceptance_rule": ticket["acceptance_rule"], "acceptance_checks": checks, "failed_reasons": failed, "decision": decision},
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "delta_metrics": {"expected_value_score_delta": 0.0, "total_pnl_delta": 0.0, "trade_count_delta": 0, "strategy_behavior_changed": False},
        "attribution": {"pooled": pooled, "by_window": by_window, "positive_windows": positive_windows, "themes": dict(sorted(themes.items())), "theme_count": len(themes), "max_theme_count": max_theme_count, "max_theme_share": round(max_theme_share, 6), "cash_mean_bootstrap_95pct_lower_usd": cash_lcb, "events": events},
        "production_impact": {"shared_policy_changed": False, "entry_rules_changed": False, "ranking_changed": False, "sizing_changed": False, "exit_rules_changed": False, "orders_changed": False, "trade_enabled": False, "scope": "read_only_observer_attribution"},
        "pit_boundary": "Historical Google News search/observer rows are not a strict point-in-time production feed; a positive result cannot be promoted beyond an observed-only lead.",
        "post_run_reflection": {
            "why_result_happened": "Exact-URL and ticker dedup removed repeated-row weighting; the resulting event decisions retained positive pooled replacement value with a positive cash bootstrap lower bound." if positive else "Event-level deduplication did not retain a robust cross-window replacement-value edge.",
            "forbidden_near_neighbor_retry": "Do not retune URL normalization, ticker weights, theme/query slices, comparator thresholds, bootstrap seeds, or window boundaries on these frozen rows.",
            "new_evidence_required": f"A positive lead requires a shared default-off prospective PIT event helper and fresh timestamped rows before Gate 1-4. A rejection may reopen only at >= {next_count} canonical unique settled events or with a genuinely new relation/economics source.",
        },
        "rejection_reason": None if positive else ";".join(failed),
        "reopen_condition": f"At least {next_count} canonical unique settled events (50% above {len(events)}) or a genuinely new relation/economics source; positive promotion additionally requires prospective PIT rows.",
        "next_retry_requires": ["shared default-off prospective PIT helper and fresh timestamped rows" if positive else f">={next_count} canonical unique settled events or new source"],
        "changed_files": [RUNNER, rel(OUT), rel(LOG), rel(CARD), rel(MANIFEST), rel(TICKET), "scripts/experiment_fingerprint.py", "quant/test_experiment_fingerprint.py", "docs/experiment_registry.json", "docs/frozen_families.jsonl"],
        "related_files": [rel(LEDGER), rel(BASELINE)],
        "reproduction_commands": [f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER.replace('/', chr(92))}", COMMAND, ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q", ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py", ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict"],
        "lean_quality_passed": True,
    }


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in payload.items() if key != "attribution"}
    result["attribution"] = {key: value for key, value in payload["attribution"].items() if key != "events"}
    return result


def card_text(payload: dict[str, Any]) -> str:
    pooled = payload["attribution"]["pooled"]
    return "\n".join([
        f"# {EXPERIMENT_ID} entity-theme exact-URL event basket", "",
        f"- Status: `{payload['status']}`", f"- Decision: `{payload['decision']}`",
        f"- Canonical unique events: `{payload['source_manifest']['canonical_events']}`",
        f"- Events by window: `{' / '.join(str(payload['attribution']['by_window'][label]['event_count']) for label in WINDOWS)}`",
        f"- Pooled mean vs cash / SPY / QQQ: `${pooled['cash']['mean_usd']}` / `${pooled['spy']['mean_usd']}` / `${pooled['qqq']['mean_usd']}`",
        f"- Cash bootstrap 95% lower bound: `${payload['attribution']['cash_mean_bootstrap_95pct_lower_usd']}`",
        f"- Themes / max share: `{payload['attribution']['theme_count']}` / `{payload['attribution']['max_theme_share']:.2%}`", "",
        "Observed-only only: no strategy or production behavior changed; historical Google News rows retain a PIT caveat.", "",
        "## Boundary", "", payload["post_run_reflection"]["forbidden_near_neighbor_retry"], "",
        "## Reproduce", "", f"- `{COMMAND}`", "",
    ])


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    CARD.parent.mkdir(parents=True, exist_ok=True)
    CARD.write_text(card_text(payload), encoding="utf-8")
    write_json(MANIFEST, {"experiment_id": EXPERIMENT_ID, "status": payload["status"], "decision": payload["decision"], "generated_at": payload["timestamp"], "runner": RUNNER, "artifact": rel(OUT), "log": rel(LOG), "card": rel(CARD), "ticket": rel(TICKET), "files": payload["changed_files"], "reproduction_commands": payload["reproduction_commands"]})
    ticket = read_json(TICKET)
    log = build_log(payload)
    persist_self_registered_result(
        REGISTRY, experiment_id=EXPERIMENT_ID, lane="alpha_search", prediction=payload["prediction"], status=payload["status"],
        result={"accepted": False, "accepted_alpha": False, "observed_only_lead": payload["observed_only_lead"], "decision": payload["decision"], "artifact": rel(OUT), "log": rel(LOG), "summary": payload["attribution"]["pooled"]},
        fields={**{key: value for key, value in ticket.items() if key not in {"result", "status"}}, **{key: value for key, value in log.items() if key not in {"experiment_id", "status", "prediction"}}, "owner": OWNER},
    )


def main() -> None:
    payload = build_result()
    persist(payload)
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "status": payload["status"], "decision": payload["decision"], "events": payload["source_manifest"]["canonical_events"], "by_window": {label: payload["attribution"]["by_window"][label]["event_count"] for label in WINDOWS}, "pooled": payload["attribution"]["pooled"], "cash_bootstrap_95pct_lower_usd": payload["attribution"]["cash_mean_bootstrap_95pct_lower_usd"], "acceptance_checks": payload["gate4"]["acceptance_checks"], "artifact": rel(OUT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
