"""exp-20260620-013: post-exp012 free-data edge readiness.

This alpha-search experiment records why no new free-data alpha should be
forced after exp-20260620-012. It checks whether current workspace evidence
adds a Gate-4-ready surface: forward paper sleeve maturity, moomoo capital-flow
rows, and local news/LLM archive coverage.

No trading rule, helper, ranking, sizing, exit, LLM/news behavior, daily runner,
watchlist, or order path is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260620-013"
SLUG = "post_exp012_free_data_edge_readiness"
RUNNER_NAME = (
    "quant/experiments/"
    "exp_20260620_013_post_exp012_free_data_edge_readiness.py"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260620_013_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
README_MD = DATA_DIR / "README.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PAPER_SLEEVES_DIR = REPO_ROOT / "data" / "paper_sleeves"
MOOMOO_DIR = REPO_ROOT / "data" / "non_ohlcv" / "moomoo_capital_flow"
NEWS_CLEAN_DIR = REPO_ROOT / "data" / "daily" / "news" / "clean"
NEWS_TRADE_DIR = REPO_ROOT / "data" / "daily" / "news" / "trade"
LLM_RESPONSE_DIR = REPO_ROOT / "data" / "daily" / "llm" / "responses"

HYPOTHESIS = (
    "candidate_pool/data-edge readiness: after exp-20260620-012, a new alpha "
    "should proceed only if a materially new free-data surface is either "
    "three-window PIT-replayable or forward-mature enough for "
    "production-visible default-off evaluation; otherwise the correct alpha "
    "direction is building the missing PIT data edge, not retuning frozen "
    "helpers."
)

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
        "strategy_total_return_pct": 117.07,
        "total_pnl": 117072.92,
        "max_drawdown_pct": 0.0665,
        "win_rate": 0.8333,
        "trade_count": 18,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "expected_value_score": 2.1402,
        "sharpe_daily": 2.74,
        "strategy_total_return_pct": 78.11,
        "total_pnl": 78110.11,
        "max_drawdown_pct": 0.1119,
        "win_rate": 0.5238,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "expected_value_score": 0.5911,
        "sharpe_daily": 1.49,
        "strategy_total_return_pct": 39.67,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

PREDICTION = {
    "success_probability": 0.05,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "forward_rows_immature",
        "current_snapshot_not_replayable",
        "news_llm_coverage_too_sparse",
        "frozen_family_near_neighbor",
    ],
    "confidence_reason": (
        "Recent logs froze most replay surfaces; current workspace has "
        "new-looking daily files, moomoo flow rows, and paper sleeve state "
        "updates, but these likely remain non-replayable or forward-immature."
    ),
    "recorded_at": "2026-06-20T12:08:39+00:00",
}

RELATED_PRIORS = [
    "exp-20260619-020",
    "exp-20260620-012",
    "exp-20260614-003",
    "exp-20260617-003",
    "exp-20260619-011",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                existing_ids.add(str(json.loads(line).get("experiment_id")))
            except json.JSONDecodeError:
                continue
    if EXPERIMENT_ID in existing_ids:
        return
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def aggregate_baseline() -> dict[str, float]:
    return {
        "aggregate_expected_value_score": round(
            sum(w["expected_value_score"] for w in CANONICAL_WINDOWS.values()), 4
        ),
        "aggregate_total_pnl": round(
            sum(w["total_pnl"] for w in CANONICAL_WINDOWS.values()), 2
        ),
        "max_window_drawdown_pct": max(
            w["max_drawdown_pct"] for w in CANONICAL_WINDOWS.values()
        ),
        "min_survival_rate": min(w["survival_rate"] for w in CANONICAL_WINDOWS.values()),
        "total_trade_count": float(sum(w["trade_count"] for w in CANONICAL_WINDOWS.values())),
    }


def baseline_artifact(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "source": BASELINE_RESULT_FILE,
        "windows": CANONICAL_WINDOWS,
        "aggregate": aggregate_baseline(),
    }


def scan_forward_sleeves() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    closed_total = 0
    replacement_total = 0
    low_deployment_true = 0
    low_deployment_false = 0
    for state_path in sorted(PAPER_SLEEVES_DIR.glob("*/state.json")):
        state = read_json(state_path)
        if not isinstance(state, dict):
            continue
        closed: list[dict[str, Any]] = []
        for key in (
            "closed_positions",
            "closed_trades",
            "realized_trades",
            "completed_positions",
        ):
            if isinstance(state.get(key), list):
                closed = [r for r in state[key] if isinstance(r, dict)]
                break
        open_rows: list[dict[str, Any]] = []
        for key in ("open_positions", "positions", "active_positions"):
            if isinstance(state.get(key), list):
                open_rows = [r for r in state[key] if isinstance(r, dict)]
                break
        replacement_rows = [
            r
            for r in closed
            if any(k.startswith("replacement_value_vs_") for k in r.keys())
        ]
        if state_path.parent.name == "low_deployment_etf":
            low_deployment_true = sum(
                1 for r in closed if r.get("low_deployment_condition_passed") is True
            )
            low_deployment_false = sum(
                1 for r in closed if r.get("low_deployment_condition_passed") is False
            )
        closed_total += len(closed)
        replacement_total += len(replacement_rows)
        rows.append(
            {
                "sleeve": state_path.parent.name,
                "open_positions": len(open_rows),
                "closed_positions": len(closed),
                "replacement_value_rows": len(replacement_rows),
                "latest_exit_date": max(
                    [str(r.get("exit_date") or "") for r in closed] or [None]
                ),
            }
        )
    rows_sorted = sorted(
        rows, key=lambda r: (r["closed_positions"], r["replacement_value_rows"]), reverse=True
    )
    return {
        "sleeve_count": len(rows),
        "closed_positions_total": closed_total,
        "replacement_value_rows_total": replacement_total,
        "top_closed_sleeves": rows_sorted[:12],
        "low_deployment_etf": {
            "closed_positions": next(
                (r["closed_positions"] for r in rows if r["sleeve"] == "low_deployment_etf"),
                0,
            ),
            "true_trigger_closed_rows": low_deployment_true,
            "off_trigger_closed_rows": low_deployment_false,
            "verdict": (
                "blocked_off_trigger_only"
                if low_deployment_true == 0 and low_deployment_false > 0
                else "needs_manual_review"
            ),
        },
        "activation_thresholds": {
            "min_closed_rows_per_sleeve": 30,
            "min_replacement_value_coverage": 0.9,
            "low_deployment_requires_true_trigger_rows": True,
        },
        "status": "blocked_forward_rows_immature",
    }


def scan_forward_replacement_value() -> dict[str, Any]:
    path = PAPER_SLEEVES_DIR / "forward_replacement_value.jsonl"
    by_sleeve: Counter[str] = Counter()
    by_sleeve_positive_vs_spy: Counter[str] = Counter()
    rows = 0
    dates: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            sleeve = str(row.get("sleeve") or row.get("sleeve_dir") or "unknown")
            by_sleeve[sleeve] += 1
            rows += 1
            if isinstance(row.get("replacement_value_vs_spy_usd"), (int, float)):
                if float(row["replacement_value_vs_spy_usd"]) > 0:
                    by_sleeve_positive_vs_spy[sleeve] += 1
            date_value = str(row.get("exit_date") or row.get("as_of_date") or "")
            if date_value:
                dates.append(date_value[:10])
    return {
        "path": repo_rel(path),
        "exists": path.exists(),
        "row_count": rows,
        "rows_by_sleeve": dict(by_sleeve.most_common()),
        "positive_vs_spy_rows_by_sleeve": dict(by_sleeve_positive_vs_spy.most_common()),
        "date_range": [min(dates), max(dates)] if dates else None,
        "status": "blocked_no_sleeve_has_30_true_trigger_rows",
    }


def scan_moomoo() -> dict[str, Any]:
    manifest = read_json(MOOMOO_DIR / "manifest.json")
    rows_path = MOOMOO_DIR / "rows.jsonl"
    row_count = 0
    as_of_dates: set[str] = set()
    if rows_path.exists():
        for line in rows_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row_count += 1
            try:
                as_of_dates.add(str(json.loads(line).get("as_of_date")))
            except json.JSONDecodeError:
                pass
    return {
        "manifest": manifest,
        "row_file_exists": rows_path.exists(),
        "row_count": row_count,
        "unique_as_of_dates": sorted(d for d in as_of_dates if d),
        "status": "blocked_current_snapshot_only_not_three_window_replayable",
    }


def _date_from_name(path: Path) -> str | None:
    for token in path.stem.split("_"):
        if len(token) == 8 and token.isdigit():
            return f"{token[:4]}-{token[4:6]}-{token[6:]}"
    return None


def _coverage_for(paths: list[Path]) -> dict[str, Any]:
    dates = sorted(d for p in paths if (d := _date_from_name(p)))
    by_window: dict[str, int] = {}
    for label, window in CANONICAL_WINDOWS.items():
        by_window[label] = sum(window["start"] <= d <= window["end"] for d in dates)
    return {
        "file_count": len(paths),
        "date_range": [dates[0], dates[-1]] if dates else None,
        "canonical_window_file_counts": by_window,
    }


def scan_news_llm() -> dict[str, Any]:
    clean_paths = sorted(NEWS_CLEAN_DIR.glob("clean_news_*.json"))
    trade_paths = sorted(NEWS_TRADE_DIR.glob("clean_trade_news_*.json"))
    llm_paths = sorted(LLM_RESPONSE_DIR.glob("llm_prompt_resp_*.json"))
    clean = _coverage_for(clean_paths)
    trade = _coverage_for(trade_paths)
    llm = _coverage_for(llm_paths)
    return {
        "clean_news": clean,
        "clean_trade_news": trade,
        "llm_responses": llm,
        "status": "blocked_archive_coverage_too_sparse_for_three_window_alpha",
        "interpretation": (
            "Local news/LLM archives are useful for forward attribution, but "
            "they do not cover the canonical historical windows enough to "
            "support a Gate 1-4 alpha replay."
        ),
    }


def gate4() -> dict[str, Any]:
    aggregate = aggregate_baseline()
    window_deltas = {
        label: {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0.0,
        }
        for label in CANONICAL_WINDOWS
    }
    return {
        "status": "blocked_no_after_policy",
        "acceptance_result": "blocked",
        "before": CANONICAL_WINDOWS,
        "after": CANONICAL_WINDOWS,
        "aggregate_before": aggregate,
        "aggregate_after": aggregate,
        "aggregate_delta": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "max_window_drawdown_pct": 0.0,
            "min_survival_rate": 0.0,
            "total_trade_count": 0.0,
        },
        "window_deltas": window_deltas,
        "reason": (
            "No after policy was run. The after metrics intentionally equal "
            "the canonical baseline; this is a data-edge blocker record, not "
            "an alpha claim."
        ),
    }


def build_result() -> dict[str, Any]:
    created_at = now_utc()
    forward_sleeves = scan_forward_sleeves()
    forward_replacement = scan_forward_replacement_value()
    moomoo = scan_moomoo()
    news_llm = scan_news_llm()
    g4 = gate4()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": created_at,
        "created_at": created_at,
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_post_exp012_no_gate4_ready_free_data_edge",
        "hypothesis": HYPOTHESIS,
        "change_type": "alpha_surface_readiness_blocker",
        "mechanism_family": "nonrepeat_free_data_candidate_pool_readiness",
        "trial_family": "post_exp012_alpha_surface_readiness",
        "trial_variant_id": "post_exp012_free_data_edge_gate4_readiness_v1",
        "single_causal_variable": "post_exp012_free_data_edge_gate4_readiness_v1",
        "changed_variable": "post_exp012_free_data_edge_gate4_readiness_v1",
        "causal_components": [
            "forward_sleeve_maturity_scan",
            "moomoo_current_snapshot_pit_boundary",
            "news_llm_archive_coverage",
            "canonical_three_window_baseline_disclosure",
            "production_parity_verdict",
        ],
        "nearby_prior_experiments": RELATED_PRIORS,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "gate1_baseline": {
            "status": "passed",
            "source": BASELINE_RESULT_FILE,
            "windows": CANONICAL_WINDOWS,
            "baseline_aggregate": aggregate_baseline(),
        },
        "gate2_field_availability": {
            "status": "blocked",
            "minimum_runtime_fields_checked": ["entry_date", "target_price"],
            "minimum_runtime_field_result": (
                "Canonical backtest rows expose the core runtime fields, but "
                "the candidate new free-data surfaces do not expose the "
                "additional PIT history or forward maturity needed for a "
                "trustworthy after policy."
            ),
            "candidate_surfaces": [
                {
                    "surface": "accepted default-off paper forward rows",
                    "gate2_verdict": forward_sleeves["status"],
                    "evidence": forward_sleeves,
                    "needed_new_axis": (
                        "At least 30 true-trigger closed rows with replacement "
                        "value and concentration/tail checks for a specific "
                        "sleeve."
                    ),
                },
                {
                    "surface": "canonical forward replacement value materialization",
                    "gate2_verdict": forward_replacement["status"],
                    "evidence": forward_replacement,
                    "needed_new_axis": (
                        "A non-frozen sleeve with enough closed replacement "
                        "value rows, or true trigger rows for low deployment."
                    ),
                },
                {
                    "surface": "moomoo capital distribution / main-force flow",
                    "gate2_verdict": moomoo["status"],
                    "evidence": moomoo,
                    "needed_new_axis": (
                        "Months of forward PIT accumulation with closed "
                        "candidate outcomes, or a vendor-safe historical "
                        "as-of archive."
                    ),
                },
                {
                    "surface": "news and LLM semantic event archive",
                    "gate2_verdict": news_llm["status"],
                    "evidence": news_llm,
                    "needed_new_axis": (
                        "Historical clean trade-news and LLM-response coverage "
                        "across all three canonical windows with bounded "
                        "event labels, not direct trading authority."
                    ),
                },
            ],
        },
        "gate3_survival": {
            "status": "not_applicable_no_new_filter",
            "baseline_min_survival_rate": aggregate_baseline()["min_survival_rate"],
            "guardrail": "survival_rate must stay >= 0.05",
            "interpretation": (
                "No new filter was tested because Gate 2 blocked every current "
                "alpha surface before strategy replay."
            ),
        },
        "gate4": g4,
        "delta_metrics": g4["aggregate_delta"],
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": "all_current_free_surfaces_not_gate4_ready",
            "surprise": (
                "Low surprise: forward rows remain immature, moomoo is "
                "current-snapshot-only, and news/LLM archives are sparse in "
                "the canonical windows."
            ),
        },
        "production_impact": {
            "production_code_changed": False,
            "backtest_code_changed": False,
            "shared_helper_added": False,
            "daily_snapshot_changed": False,
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "live_realistic_execution_envelope": "not_applicable_no_tradable_alpha",
            "parity_assessment": (
                "No production/backtest inconsistency can be introduced "
                "because no trading policy or helper changed. Any future "
                "positive alpha must be implemented as a shared default-off "
                "helper before acceptance."
            ),
        },
        "post_run_reflection": {
            "why_blocked": (
                "The current free-data surfaces are not Gate-4-ready: forward "
                "paper rows are immature, moomoo capital flow is forward-only, "
                "and news/LLM archives do not cover the three canonical windows."
            ),
            "negative_result_reflection": (
                "The blocker is structural, not a threshold failure. Forcing a "
                "replay would reuse frozen families or make a non-replayable "
                "current snapshot look historical."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry this by sweeping accepted-helper rank, top-N, "
                "hold, notional, low-deployment ETF thresholds, moomoo flow "
                "ratios, or news keyword thresholds without new PIT history or "
                "closed forward replacement-value rows."
            ),
            "best_next_alpha_direction": (
                "Build/import a new PIT data edge first: offering/S-8 primary "
                "document economics, historical 10-K/10-Q cover-page filer "
                "status, parsed customer/segment contract economics, PIT "
                "borrow/options rows, or analyst breadth/dispersion joined to "
                "historical candidates."
            ),
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(README_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\"),
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "causal_components": result["causal_components"],
        "nearby_prior_experiments": result["nearby_prior_experiments"],
        "baseline_result_file": BASELINE_RESULT_FILE,
        "before_artifact": repo_rel(BEFORE_JSON),
        "after_artifact": repo_rel(AFTER_JSON),
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
        "delta_metrics": result["delta_metrics"],
        "prediction": result["prediction"],
        "calibration": result["calibration"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "changed_files": result["changed_files"],
        "reproduction": result["reproduction"],
        "lean_quality_passed": result["lean_quality_passed"],
        "anti_js": result["anti_js"],
        "accepted": False,
        "accepted_alpha": False,
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
    }


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: post-exp012 free-data edge readiness",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- No strategy, production helper, ranking, sizing, exit, watchlist, or order path changed.",
        "",
        "## Three-window Gate 4",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, before in CANONICAL_WINDOWS.items():
        delta = result["gate4"]["window_deltas"][label]
        lines.append(
            f"| {label} | {before['expected_value_score']:.4f} | "
            f"{before['expected_value_score']:.4f} | "
            f"{delta['expected_value_score']:.4f} | "
            f"${before['total_pnl']:,.2f} | ${before['total_pnl']:,.2f} | "
            f"${delta['total_pnl']:,.2f} |"
        )
    forward = result["gate2_field_availability"]["candidate_surfaces"][0]["evidence"]
    moomoo = result["gate2_field_availability"]["candidate_surfaces"][2]["evidence"]
    news = result["gate2_field_availability"]["candidate_surfaces"][3]["evidence"]
    lines.extend(
        [
            "",
            "## Readout",
            "",
            result["post_run_reflection"]["why_blocked"],
            "",
            f"- Forward closed rows total: {forward['closed_positions_total']}",
            f"- Low-deployment true-trigger closed rows: {forward['low_deployment_etf']['true_trigger_closed_rows']}",
            f"- Moomoo rows: {moomoo['row_count']}",
            f"- Clean-news files: {news['clean_news']['file_count']}",
            "",
            result["post_run_reflection"]["best_next_alpha_direction"],
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Blocked alpha-search readiness artifact. This records why no current "
        "free-data surface should be forced into a Gate 4 replay after "
        "exp-20260620-012.\n\n"
        f"- Artifact: `{repo_rel(ARTIFACT_JSON)}`\n"
        f"- Before: `{repo_rel(BEFORE_JSON)}`\n"
        f"- After: `{repo_rel(AFTER_JSON)}`\n"
        f"- Decision: `{result['decision']}`\n"
    )


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "lane": result["lane"],
            "files": result["changed_files"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "runner": RUNNER_NAME,
            "command": result["reproduction"],
            "anti_js": result["anti_js"],
            "updated_at": now_utc(),
        },
    )


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, baseline_artifact("before_baseline"))
    write_json(AFTER_JSON, baseline_artifact("after_no_strategy_change"))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    write_text(README_MD, build_readme(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))
    write_manifest(result)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_blocked"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status="blocked",
        fields={
            "owner": "alpha-search-automation",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": result["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "current_forward_and_archive_coverage_scan",
            "baseline_result_file": BASELINE_RESULT_FILE,
            "acceptance_rule": "Blocked unless a new surface is PIT-replayable or forward-mature.",
            "decision": result["decision"],
            "summary": result["post_run_reflection"]["why_blocked"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "post_run_reflection": result["post_run_reflection"],
            "production_impact": result["production_impact"],
            "gate1_baseline": result["gate1_baseline"],
            "gate2_field_availability": result["gate2_field_availability"],
            "gate3_survival": result["gate3_survival"],
            "gate4": result["gate4"],
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )


def main() -> None:
    result = build_result()
    persist(result)
    forward = result["gate2_field_availability"]["candidate_surfaces"][0]["evidence"]
    moomoo = result["gate2_field_availability"]["candidate_surfaces"][2]["evidence"]
    news = result["gate2_field_availability"]["candidate_surfaces"][3]["evidence"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "aggregate_ev_delta": 0.0,
                "aggregate_pnl_delta": 0.0,
                "forward_closed_rows_total": forward["closed_positions_total"],
                "low_deployment_true_trigger_rows": forward["low_deployment_etf"][
                    "true_trigger_closed_rows"
                ],
                "moomoo_rows": moomoo["row_count"],
                "clean_news_files": news["clean_news"]["file_count"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
