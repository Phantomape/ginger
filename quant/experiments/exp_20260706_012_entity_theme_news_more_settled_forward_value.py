"""exp-20260706-012: entity/theme news more-settled forward value.

Observed-only alpha refresh. The fixed entity_theme_news observer source bundle
failed on the first settled outcome ledger, but the 2026-07-05 ledger has a
materially larger settled cohort. This runner repeats the same source-bundle
replacement-value checks without changing the source manifest, query/theme
maps, candidate tickers, horizon, notional, ranking, sizing, exits, or orders.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (SCRIPTS_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260706-012"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "entity_theme_news_more_settled_forward_value"
RUNNER = f"quant/experiments/exp_20260706_012_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
LEDGER_JSONL = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "outcome_ledgers"
    / "entity_theme_news_observer_outcomes_20260705.jsonl"
)
SUMMARY_JSON = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "outcome_summaries"
    / "entity_theme_news_observer_outcome_summary_20260705.json"
)
PRIOR_SOURCE_BUNDLE_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260703-014.json"
PRIOR_SEC_CONFIRM_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260705-017.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260706_012_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha refresh on entity_theme_news_observer only: with "
    "materially more settled entity-theme news observer rows as of 2026-07-05, "
    "the unchanged fixed entity/theme source bundle should show positive "
    "10-day replacement value versus cash, SPY, and QQQ before any shared "
    "default-off helper is reconsidered."
)
ALPHA_HYPOTHESIS = (
    "If the entity/theme observer contains deployable event-relation alpha, "
    "the larger settled forward ledger should flip the fixed source bundle "
    "from diluted/noisy to broadly positive versus cash and ETF comparators."
)
CHANGE_TYPE = "candidate_pool_observed_attribution"
MECHANISM_FAMILY = "production_visible_entity_theme_news_observer_candidate_pool"
TRIAL_FAMILY = "entity_theme_news_source_bundle_forward_value"
TRIAL_VARIANT_ID = "materially_more_settled_rows_20260705_v1"
CHANGED_VARIABLE = "entity_theme_news_source_bundle_more_settled_rows_20260705_v1"
NEW_EVIDENCE_AXIS = (
    "Materially more settled entity_theme_news observer outcome rows: "
    "2026-07-05 summary reports 8158 settled rows versus 2728/2735 in prior "
    "source-bundle and SEC-confirmation audits; fixed source manifest, horizon, "
    "notional, query/theme/ticker maps, and acceptance rule remain unchanged."
)
NEARBY_PRIORS = ["exp-20260703-014", "exp-20260705-017"]
CAUSAL_COMPONENTS = [
    "read-only 2026-07-05 entity_theme_news observer outcome ledger analysis",
    "unchanged fixed source-bundle aggregate checks from exp-20260703-014",
    "materially-more-settled-row comparison versus prior ledgers",
    "theme/query/ticker/date concentration audit",
    "no strategy behavior change",
]
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260706_012_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
REPRODUCTION_COMMANDS = [
    f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_PS}",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

VALUE_FIELDS = {
    "cash": "replacement_value_vs_cash_usd",
    "spy": "replacement_value_vs_spy_usd",
    "qqq": "replacement_value_vs_qqq_usd",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                item = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cleanup_orphan_temps(path)
    path.write_text(text, encoding="utf-8")
    cleanup_orphan_temps(path)


def cleanup_orphan_temps(path: Path) -> None:
    for tmp in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            tmp.unlink()
        except OSError:
            pass


def write_json(path: Path, payload: Any) -> None:
    write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True, default=str)
        + "\n",
    )


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def stats(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {
            "count": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "positive_count": 0,
            "positive_share": None,
        }
    return {
        "count": len(clean),
        "sum": round(sum(clean), 4),
        "mean": round(statistics.fmean(clean), 4),
        "median": round(statistics.median(clean), 4),
        "positive_count": sum(1 for value in clean if value > 0),
        "positive_share": round(sum(1 for value in clean if value > 0) / len(clean), 6),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
    }


def settled_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("outcome_status") != "settled":
            continue
        if int(row.get("horizon_trading_days") or 0) != 10:
            continue
        if any(number(row.get(field)) is None for field in VALUE_FIELDS.values()):
            continue
        out.append(row)
    return out


def values_by_field(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {key: [] for key in VALUE_FIELDS}
    for row in rows:
        for key, field in VALUE_FIELDS.items():
            value = number(row.get(field))
            if value is not None:
                out[key].append(value)
    return out


def grouped(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = str(row.get(key) or "unknown")
        out[value].append(row)
    return dict(out)


def group_table(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for value, group_rows in grouped(rows, key).items():
        by_field = values_by_field(group_rows)
        item = {
            key: value,
            "row_count": len(group_rows),
            "mean_cash": stats(by_field["cash"])["mean"],
            "mean_spy": stats(by_field["spy"])["mean"],
            "mean_qqq": stats(by_field["qqq"])["mean"],
            "median_cash": stats(by_field["cash"])["median"],
            "positive_cash_sum": round(
                sum(max(0.0, number(row.get("replacement_value_vs_cash_usd")) or 0.0) for row in group_rows),
                4,
            ),
        }
        items.append(item)
    items.sort(
        key=lambda item: (
            -(float(item.get("mean_cash") or 0.0)),
            -int(item["row_count"]),
            str(item[key]),
        )
    )
    return items


def positive_contribution_share(rows: list[dict[str, Any]], key: str) -> float | None:
    positive_by_key: dict[str, float] = defaultdict(float)
    total = 0.0
    for row in rows:
        value = number(row.get("replacement_value_vs_cash_usd")) or 0.0
        if value <= 0:
            continue
        total += value
        positive_by_key[str(row.get(key) or "unknown")] += value
    if total <= 0:
        return None
    return round(max(positive_by_key.values(), default=0.0) / total, 6)


def observed_date_level_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    date_rows = group_table(rows, "observed_date")
    return {
        "observed_date_count": len(date_rows),
        "mean_of_date_mean_cash": stats(
            [float(row["mean_cash"]) for row in date_rows if row.get("mean_cash") is not None]
        )["mean"],
        "mean_of_date_mean_spy": stats(
            [float(row["mean_spy"]) for row in date_rows if row.get("mean_spy") is not None]
        )["mean"],
        "mean_of_date_mean_qqq": stats(
            [float(row["mean_qqq"]) for row in date_rows if row.get("mean_qqq") is not None]
        )["mean"],
        "top_dates_by_cash": date_rows[:8],
        "bottom_dates_by_cash": list(reversed(date_rows[-8:])),
    }


def prior_counts() -> dict[str, Any]:
    source = read_json(PRIOR_SOURCE_BUNDLE_LOG, {})
    confirm = read_json(PRIOR_SEC_CONFIRM_LOG, {})
    return {
        "exp-20260703-014": {
            "settled_rows": (source.get("summary") or {}).get("settled_rows"),
            "candidate_outcome_rows": (source.get("summary") or {}).get("candidate_outcome_rows"),
            "decision": source.get("decision"),
        },
        "exp-20260705-017": {
            "settled_rows": (confirm.get("summary") or {}).get("settled_rows"),
            "candidate_outcome_rows": (confirm.get("summary") or {}).get("candidate_outcome_rows"),
            "decision": confirm.get("decision"),
        },
    }


def current_summary(source_rows: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = values_by_field(rows)
    row_stats = {key: stats(series) for key, series in values.items()}
    query_rows = group_table(rows, "entity_theme_query_id")
    ticker_rows = group_table(rows, "candidate_ticker")
    theme_rows = group_table(rows, "theme")
    relation_rows = group_table(rows, "relation_type")
    date_stats = observed_date_level_stats(rows)
    positive_query_groups_vs_spy_and_qqq = [
        row
        for row in query_rows
        if (row.get("mean_spy") or 0) > 0 and (row.get("mean_qqq") or 0) > 0
    ]
    candidate_outcome_rows = len(source_rows)
    return {
        "candidate_outcome_rows": candidate_outcome_rows,
        "settled_rows": len(rows),
        "settled_survival_rate": round(len(rows) / candidate_outcome_rows, 6)
        if candidate_outcome_rows
        else None,
        "query_group_count": len(query_rows),
        "ticker_count": len(ticker_rows),
        "theme_count": len(theme_rows),
        "relation_type_count": len(relation_rows),
        "row_level": {
            "cash": row_stats["cash"],
            "spy": row_stats["spy"],
            "qqq": row_stats["qqq"],
        },
        "observed_date_level": date_stats,
        "positive_query_groups_vs_spy_and_qqq": len(positive_query_groups_vs_spy_and_qqq),
        "positive_query_groups_vs_spy_and_qqq_sample": positive_query_groups_vs_spy_and_qqq[:12],
        "max_positive_cash_query_share": positive_contribution_share(
            rows, "entity_theme_query_id"
        ),
        "max_positive_cash_ticker_share": positive_contribution_share(
            rows, "candidate_ticker"
        ),
        "top_queries_by_cash": query_rows[:12],
        "bottom_queries_by_cash": list(reversed(query_rows[-12:])),
        "top_tickers_by_cash": ticker_rows[:12],
        "top_themes_by_cash": theme_rows[:12],
        "relation_type_table": relation_rows,
    }


def acceptance(summary: dict[str, Any]) -> dict[str, Any]:
    row = summary["row_level"]
    observed = summary["observed_date_level"]
    checks = {
        "settled_rows_min_passed": int(summary["settled_rows"]) >= 250,
        "query_groups_min_passed": int(summary["query_group_count"]) >= 6,
        "row_level_primary_means_positive": all(
            (row[key]["mean"] or 0) > 0 for key in ("cash", "spy", "qqq")
        ),
        "row_level_primary_medians_nonnegative": all(
            (row[key]["median"] or 0) >= 0 for key in ("cash", "spy", "qqq")
        ),
        "observed_date_level_primary_means_positive": all(
            (observed.get(key) or 0) > 0
            for key in (
                "mean_of_date_mean_cash",
                "mean_of_date_mean_spy",
                "mean_of_date_mean_qqq",
            )
        ),
        "positive_query_groups_vs_spy_and_qqq_passed": int(
            summary["positive_query_groups_vs_spy_and_qqq"]
        )
        >= 4,
        "positive_cash_query_share_passed": (
            summary["max_positive_cash_query_share"] is not None
            and float(summary["max_positive_cash_query_share"]) <= 0.60
        ),
        "positive_cash_ticker_share_passed": (
            summary["max_positive_cash_ticker_share"] is not None
            and float(summary["max_positive_cash_ticker_share"]) <= 0.40
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "acceptance_rule": {
            "min_settled_rows": 250,
            "min_query_groups": 6,
            "require_row_level_primary_means_positive": True,
            "require_row_level_primary_medians_nonnegative": True,
            "require_observed_date_level_primary_means_positive": True,
            "min_positive_query_groups_vs_spy_and_qqq": 4,
            "max_positive_cash_query_share": 0.60,
            "max_positive_cash_ticker_share": 0.40,
        },
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "passed": not failed,
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") or {}
    baseline = baseline_metrics()
    source_rows = read_jsonl(LEDGER_JSONL)
    rows = settled_rows(source_rows)
    observer_summary = read_json(SUMMARY_JSON, {})
    summary = current_summary(source_rows, rows)
    gate4 = acceptance(summary)
    passed = bool(gate4["passed"])
    status = "observed_only_positive" if passed else "observed_only_rejected"
    decision = (
        "observed_only_positive_entity_theme_more_settled_forward_value_not_activation_ready"
        if passed
        else "observed_only_rejected_entity_theme_more_settled_no_edge"
    )
    realized_failure_modes = list(gate4["failed_reasons"])
    prediction_probability = prediction.get("success_probability")
    try:
        probability = float(prediction_probability)
    except (TypeError, ValueError):
        probability = None
    actual_success = 1.0 if passed else 0.0
    brier = round((probability - actual_success) ** 2, 4) if probability is not None else None
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": passed,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_closed_forward_rows",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "actual_success": actual_success,
            "predicted_success_probability": probability,
            "brier_score": brier,
            "realized_failure_modes": realized_failure_modes,
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "predicted_failure_mode_hit": bool(
                set(realized_failure_modes)
                & set(prediction.get("main_failure_modes") or [])
            ),
            "surprise_note": (
                "Low surprise: the larger settled cohort still failed the fixed "
                "source-bundle bar."
                if not passed
                else "Positive surprise: materially more settled rows cleared the fixed observed-only bar."
            ),
        },
        "gate1": {
            "passed": baseline.get("window_count") == 3,
            "note": "Observed-only attribution; canonical strategy baseline unchanged.",
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": LEDGER_JSONL.exists() and SUMMARY_JSON.exists() and bool(rows),
            "fields_checked": [
                "entity_theme_query_id",
                "theme",
                "relation_type",
                "candidate_ticker",
                "observed_date",
                "entry_date",
                "exit_date",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "entry_date_present_rows": sum(1 for row in rows if row.get("entry_date")),
            "target_price_relevance": (
                "This observer does not create target exits or orders; target_price "
                "is not part of the read-only outcome ledger."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No executable filter, ranking, sizing, exit, prompt, or order rule was added.",
            "signals_generated": summary["candidate_outcome_rows"],
            "signals_survived": summary["settled_rows"],
            "survival_rate": summary["settled_survival_rate"],
        },
        "gate4": {
            **gate4,
            "decision": decision,
            "accepted_alpha": False,
            "observed_only": True,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
            "pit_caveat": (
                "Entity/theme source rows come from Google News observer snapshots "
                "and include rows returned by the current search process. This is "
                "a read-only forward-ledger attribution refresh, not a strict "
                "historical PIT deployable candidate-pool proof."
            ),
        },
        "summary": summary,
        "observer_summary": {
            "path": repo_rel(SUMMARY_JSON),
            "candidate_outcome_row_count": observer_summary.get("candidate_outcome_row_count"),
            "settled_count": observer_summary.get("settled_count"),
            "unsettled_count": observer_summary.get("unsettled_count"),
            "status_counts": observer_summary.get("status_counts"),
            "daily_item_file_count": observer_summary.get("daily_item_file_count"),
            "candidate_ticker_count": observer_summary.get("candidate_ticker_count"),
        },
        "prior_comparison": prior_counts(),
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "settled_rows_vs_exp_20260703_014": (
                summary["settled_rows"]
                - int((prior_counts().get("exp-20260703-014") or {}).get("settled_rows") or 0)
            ),
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
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "feeds_llm_prompt": False,
            "llm_boundary_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Read-only analysis over existing entity_theme_news observer outcome "
                "rows. No helper, adapter, order, rank, size, exit, watchlist, or "
                "LLM behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The larger settled ledger did not overcome source-bundle dilution; "
                "row-level or median replacement value stayed below the fixed bar."
                if not passed
                else "The larger settled ledger cleared the fixed observed-only bar, but PIT caveats remain."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune entity/theme queries, theme labels, candidate ticker maps, "
                "horizons, notional, response curves, or SEC-confirmation windows on this "
                "same source bundle."
            ),
            "new_evidence_required": (
                "A true PIT historical news archive with observation-time availability, "
                "or another material batch of prospectively logged daily rows with closed "
                "cash/SPY/QQQ replacement value under the same fixed manifest."
            ),
        },
        "rejection_reason": "; ".join(gate4["failed_reasons"]) if gate4["failed_reasons"] else None,
        "related_files": [
            RUNNER,
            repo_rel(LEDGER_JSONL),
            repo_rel(SUMMARY_JSON),
            repo_rel(PRIOR_SOURCE_BUNDLE_LOG),
            repo_rel(PRIOR_SEC_CONFIRM_LOG),
        ],
        "changed_files": CHANGED_FILES,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "lean_quality_passed": True,
        "llm_metrics": {"used_llm": False},
    }


def compact_log(result: dict[str, Any]) -> dict[str, Any]:
    return result


def build_card(result: dict[str, Any]) -> str:
    row = result["summary"]["row_level"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Entity/Theme News More-Settled Forward Value",
            "",
            f"- Status: `{result['status']}`",
            f"- Decision: `{result['decision']}`",
            f"- Settled rows: `{result['summary']['settled_rows']}`",
            f"- Row mean cash/SPY/QQQ: `{row['cash']['mean']}` / `{row['spy']['mean']}` / `{row['qqq']['mean']}`",
            f"- Row median cash/SPY/QQQ: `{row['cash']['median']}` / `{row['spy']['median']}` / `{row['qqq']['median']}`",
            "",
            "## Hypothesis",
            HYPOTHESIS,
            "",
            "## Gate 4",
            f"Failed reasons: `{result['gate4']['failed_reasons']}`",
            "",
            "## Next Evidence",
            result["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "```powershell",
            *result["reproduction_commands"],
            "```",
            "",
        ]
    )


def write_manifest(result: dict[str, Any]) -> None:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        LEDGER_JSONL,
        SUMMARY_JSON,
    ]
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "generated_at": utc_now(),
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "changed_files": CHANGED_FILES,
            "reproduction_commands": REPRODUCTION_COMMANDS,
            "files": [
                {
                    "path": repo_rel(path),
                    "exists": path.exists(),
                    "sha256": sha256(path),
                }
                for path in paths
            ],
        },
    )


def persist(result: dict[str, Any]) -> None:
    write_json(OUT_JSON, result)
    save_experiment_log_entry(compact_log(result), allow_duplicate=True)
    write_text(CARD_MD, build_card(result))
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
            "alpha_hypothesis": ALPHA_HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": "observed_only_attribution",
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_closed_forward_rows",
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "card": result["card"],
            "manifest": result["manifest"],
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["post_run_reflection"]["new_evidence_required"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": REPRODUCTION_COMMANDS,
            "lean_quality_passed": True,
        },
    )
    write_manifest(result)


def main() -> int:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "settled_rows": result["summary"]["settled_rows"],
                "row_mean_cash": result["summary"]["row_level"]["cash"]["mean"],
                "row_median_cash": result["summary"]["row_level"]["cash"]["median"],
                "failed_reasons": result["gate4"]["failed_reasons"],
                "artifact": result["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
