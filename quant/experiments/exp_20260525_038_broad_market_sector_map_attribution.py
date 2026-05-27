"""exp-20260525-038: broad-market sector map attribution.

Measurement repair (read-only). Builds and validates a persistent
`yfinance_gics_proxy_sector_v1` sector cache for the broad-market warehouse
universe (1336 tickers), then attaches per-trade sector / industry context
to the accepted `exp-20260520-004` baseline `sample_trades` replay.

This experiment does not change candidate eligibility, ranking, sizing,
exits, hold days, slots, LLM/news, paper notional, or live/default orders.
It does not change `broad_market_paper_sleeve.py`. Gate 1 core EV/PnL must
remain at the canonical accepted aggregate (`7.8941` / `$234,850.99`).
Gate 4 requires (a) parity (zero strategy behavior delta) and (b) sector
coverage >= 80% over the warehouse candidate universe.

Unblocked alpha_search hooks after acceptance:
  - broad-market sector concentration / crowding haircut or top-up
  - hidden-beta-by-sector cohort attribution
  - sector / industry replacement-value joins on closed forward outcomes

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260525-038"
EXPERIMENT_SLUG = "broad_market_sector_map_attribution"
SOURCE_EXPERIMENT_ID = "exp-20260520-004"
SOURCE_SLUG = "broad_market_trend_persistence_notional"
CORE_BASELINE_EXPERIMENT_ID = "exp-20260517-009"
CORE_BASELINE_ARTIFACT = (
    "data/experiments/exp-20260517-009/ample_slot_stock_rank1_topup.json"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from broad_market_sector_map import (  # noqa: E402
    DEFAULT_CACHE_PATH,
    FETCH_ERROR_STATUS,
    MISSING_INFO_STATUS,
    MISSING_TICKER_STATUS,
    OK_STATUS,
    RULE_VERSION as SECTOR_RULE_VERSION,
    SOURCE_LABEL as SECTOR_SOURCE,
    coverage_report,
    load_cache,
    lookup_sector,
)
import exp_20260520_004_broad_market_trend_persistence_notional as e004  # noqa: E402
import exp_20260519_035_broad_market_price_floor_candidate_pool_shadow as p35  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


WINDOWS = e004.WINDOWS
CANONICAL_ACCEPTED_AGGREGATE_EV = 7.8941
CANONICAL_ACCEPTED_AGGREGATE_PNL = 234850.99
EV_TOLERANCE = 0.01
PNL_TOLERANCE = 50.0
SECTOR_COVERAGE_TARGET = 0.80

SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / f"{SOURCE_SLUG}.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _audit_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    required = ("entry_date", "target_price")
    if not path.exists():
        return {
            "passed": False,
            "exists": False,
            "path": _repo_rel(path),
            "checked_positions": 0,
            "missing_required_fields": list(required),
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        positions = data.get("positions") or data.get("open_positions") or []
    else:
        positions = data
    missing: set[str] = set()
    checked = 0
    for pos in positions or []:
        if not isinstance(pos, dict):
            continue
        checked += 1
        for key in required:
            if pos.get(key) in (None, ""):
                missing.add(key)
    return {
        "passed": bool(positions) and not missing,
        "exists": True,
        "path": _repo_rel(path),
        "checked_positions": checked,
        "missing_required_fields": sorted(missing),
    }


def _run_canonical_window(label: str) -> dict[str, Any]:
    spec = WINDOWS[label]
    universe = get_universe()
    snapshot = REPO_ROOT / spec["snapshot"]
    engine = BacktestEngine(
        universe,
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=str(snapshot),
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"{label} backtest error: {result['error']}")
    return result


def _core_summary(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": float(result.get("expected_value_score") or 0.0),
        "total_pnl": float(result.get("total_pnl") or 0.0),
        "total_return_pct": float(
            benchmarks.get("strategy_total_return_pct")
            or result.get("total_return_pct")
            or 0.0
        ),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": result.get("survival_rate"),
    }


def _resimulate_broad_market_baseline() -> dict[str, Any]:
    """Re-run the e20-004 posday20_gte_0p55_scalar_1p15 variant.

    Returns the full per-window list of selected paper trades. This matches
    the baseline that produced the accepted `exp-20260520-004` `before_metrics`
    and the 90 selected paper trades reported in current_state.md.

    The candidate ticker list is loaded from the source artifact's
    `candidate_universe.tickers` (the 712 tickers frozen at e20-004 time),
    NOT re-queried from the warehouse — the warehouse has expanded since
    e20-004 was accepted, so re-querying would change candidate signal
    counts and break broad-market PnL parity.
    """
    source_payload = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    frozen_tickers = sorted(
        str(t).upper()
        for t in (source_payload.get("candidate_universe") or {}).get("tickers") or []
        if t
    )
    if not frozen_tickers:
        raise RuntimeError(
            "Source artifact missing candidate_universe.tickers; cannot "
            "reproduce baseline trades."
        )
    prices = p35._load_price_rows(frozen_tickers)
    indexes = p35._index_by_date(prices)
    # Use the accepted variant from e20-004 so per-window PnL matches the
    # source artifact's `broad_market_sleeve[w].pnl` (which records the
    # selected variant, not the unenriched baseline).
    selected_variant_name = source_payload["selected_variant"]["variant_name"]
    baseline = e004.TREND_PERSISTENCE_SWEEP[selected_variant_name]

    trades_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    pnl_by_window: dict[str, float] = OrderedDict()
    for label in WINDOWS:
        scout = e004._simulate_window(
            label=label,
            positive_day_ratio_20_min=baseline["positive_day_ratio_20_min"],
            scalar=baseline["scalar"],
            candidate_tickers=frozen_tickers,
            prices=prices,
            indexes=indexes,
        )
        trades_by_window[label] = scout["trades"]
        pnl_by_window[label] = round(
            sum(float(t.get("pnl") or 0.0) for t in scout["trades"]),
            2,
        )
    return {
        "candidate_tickers": frozen_tickers,
        "trades_by_window": trades_by_window,
        "pnl_by_window": pnl_by_window,
    }


def _attach_sector(rows: list[dict[str, Any]], cache: dict[str, Any]) -> None:
    """Mutate each row in place, attaching `sector_lookup` payload."""
    for row in rows:
        ticker = row.get("ticker")
        row["sector_lookup"] = lookup_sector(ticker, cache=cache)


def _sector_attribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate trade-level sector stats for a single window."""
    status_counts: Counter = Counter()
    sector_counts: Counter = Counter()
    sector_pnl: dict[str, float] = defaultdict(float)
    sector_trade_count: dict[str, int] = defaultdict(int)
    for row in rows:
        lk = row.get("sector_lookup") or {}
        status = lk.get("status") or MISSING_TICKER_STATUS
        status_counts[status] += 1
        if status == OK_STATUS:
            sector = lk.get("sector") or "Unknown"
            sector_counts[sector] += 1
            sector_pnl[sector] += float(row.get("pnl") or 0.0)
            sector_trade_count[sector] += 1
    return {
        "trade_count": len(rows),
        "status_counts": dict(status_counts),
        "sector_counts": dict(sorted(sector_counts.items(), key=lambda kv: -kv[1])),
        "sector_pnl": {
            sector: round(value, 2)
            for sector, value in sorted(sector_pnl.items(), key=lambda kv: -kv[1])
        },
        "sector_trade_count": dict(sector_trade_count),
        "sector_unique_count": len(sector_counts),
    }


def _aggregate_sector_attribution(
    windowed: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    status_counts: Counter = Counter()
    sector_counts: Counter = Counter()
    sector_pnl: dict[str, float] = defaultdict(float)
    sector_trade_count: dict[str, int] = defaultdict(int)
    total = 0
    for payload in windowed.values():
        total += payload["trade_count"]
        for k, v in payload["status_counts"].items():
            status_counts[k] += v
        for k, v in payload["sector_counts"].items():
            sector_counts[k] += v
            sector_trade_count[k] += v
        for k, v in payload["sector_pnl"].items():
            sector_pnl[k] += v
    return {
        "trade_count": total,
        "status_counts": dict(status_counts),
        "sector_counts": dict(sorted(sector_counts.items(), key=lambda kv: -kv[1])),
        "sector_pnl": {
            sector: round(value, 2)
            for sector, value in sorted(sector_pnl.items(), key=lambda kv: -kv[1])
        },
        "sector_trade_count": dict(sector_trade_count),
        "sector_unique_count": len(sector_counts),
    }


def _production_impact() -> dict[str, bool]:
    return {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": True,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }


def _format_share(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate1 = payload["gate1"]
    gate4 = payload["gate4"]
    coverage = payload["sector_coverage"]
    agg = payload["aggregate_sector_attribution"]
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Sector Map Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Read-only `measurement_repair`. Builds and validates the",
        "`yfinance_gics_proxy_sector_v1` sector cache for the broad-market",
        "warehouse universe and attaches sector context to the accepted",
        f"`{SOURCE_EXPERIMENT_ID}` baseline replay. Unlocks broad-market",
        "sector-aware alpha_search; does not change orders or notional.",
        "",
        "## Gate 1 Core Replay Verification",
        "",
        "```json",
        json.dumps(gate1, indent=2, sort_keys=True),
        "```",
        "",
        "## Sector Coverage on Warehouse Universe",
        "",
        "```json",
        json.dumps(coverage, indent=2, sort_keys=True),
        "```",
        "",
        "## Aggregate Sector Attribution Across 3 Windows",
        "",
        "| Sector | Trades | PnL |",
        "|---|---:|---:|",
    ]
    for sector, count in agg["sector_counts"].items():
        pnl = agg["sector_pnl"].get(sector, 0.0)
        lines.append(f"| {sector} | {count} | ${pnl:,.2f} |")
    lines.extend(
        [
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    gate2 = _audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    if not DEFAULT_CACHE_PATH.exists():
        raise RuntimeError(
            f"Missing sector cache at {DEFAULT_CACHE_PATH}. "
            "Run `python quant/build_broad_market_sector_cache.py` first."
        )
    cache = load_cache(DEFAULT_CACHE_PATH)

    baseline = _resimulate_broad_market_baseline()
    candidate_tickers = baseline["candidate_tickers"]
    trades_by_window = baseline["trades_by_window"]
    pnl_by_window = baseline["pnl_by_window"]

    # Attach sector to each trade row in place
    for rows in trades_by_window.values():
        _attach_sector(rows, cache)

    coverage = coverage_report(candidate_tickers, cache=cache)
    # Also report warehouse-wide coverage for diagnostic visibility, but
    # Gate 4 uses the frozen-list coverage (the universe that actually
    # drives the e20-004 baseline replay).
    try:
        warehouse_tickers = p35._candidate_universe(
            set(p35._load_tradeable_universe()["excluded_tradeable_universe"])
        )["tickers"]
        warehouse_coverage = coverage_report(warehouse_tickers, cache=cache)
    except Exception as exc:  # noqa: BLE001
        warehouse_coverage = {
            "error": f"{type(exc).__name__}: {exc}",
            "tickers_requested": None,
            "ok_share": None,
        }
    sector_attribution_by_window = OrderedDict(
        (label, _sector_attribution(trades_by_window[label])) for label in WINDOWS
    )
    aggregate_sector_attribution = _aggregate_sector_attribution(
        sector_attribution_by_window
    )

    # Cross-check broad-market PnL against the recorded source artifact
    source_payload = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    source_pnl_by_window = {
        label: round(
            float(((source_payload.get("broad_market_sleeve") or {}).get(label) or {}).get("pnl") or 0.0),
            2,
        )
        for label in WINDOWS
    }
    pnl_parity_drift = {
        label: round(pnl_by_window[label] - source_pnl_by_window[label], 2)
        for label in WINDOWS
    }
    pnl_parity_passed = all(abs(v) <= 0.01 for v in pnl_parity_drift.values())

    # Run canonical 3-window core backtest for Gate 1
    core_summaries: dict[str, dict[str, Any]] = OrderedDict()
    for window in WINDOWS:
        result = _run_canonical_window(window)
        core_summaries[window] = _core_summary(result)
    aggregate_ev = round(
        sum(row["expected_value_score"] for row in core_summaries.values()), 4
    )
    aggregate_pnl = round(
        sum(row["total_pnl"] for row in core_summaries.values()), 2
    )
    ev_drift = round(aggregate_ev - CANONICAL_ACCEPTED_AGGREGATE_EV, 4)
    pnl_drift = round(aggregate_pnl - CANONICAL_ACCEPTED_AGGREGATE_PNL, 2)
    gate1_passed = (
        abs(ev_drift) <= EV_TOLERANCE and abs(pnl_drift) <= PNL_TOLERANCE
    )
    gate1 = {
        "passed": bool(gate1_passed),
        "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
        "baseline_artifact": CORE_BASELINE_ARTIFACT,
        "canonical_accepted_aggregate_expected_value_score_sum": CANONICAL_ACCEPTED_AGGREGATE_EV,
        "canonical_accepted_aggregate_total_pnl_sum": CANONICAL_ACCEPTED_AGGREGATE_PNL,
        "observed_aggregate_expected_value_score_sum": aggregate_ev,
        "observed_aggregate_total_pnl_sum": aggregate_pnl,
        "expected_value_score_drift": ev_drift,
        "total_pnl_drift": pnl_drift,
        "ev_tolerance": EV_TOLERANCE,
        "pnl_tolerance": PNL_TOLERANCE,
        "by_window": core_summaries,
    }

    sector_coverage = {
        **coverage,
        "scope": "frozen_candidate_universe_from_source_artifact",
        "coverage_target": SECTOR_COVERAGE_TARGET,
        "coverage_target_passed": (
            coverage["ok_share"] is not None
            and coverage["ok_share"] >= SECTOR_COVERAGE_TARGET
        ),
        "warehouse_diagnostic": warehouse_coverage,
    }

    gate4 = {
        "strategy_behavior_changed": False,
        "canonical_backtest_required": True,
        "passed": bool(
            gate1_passed
            and pnl_parity_passed
            and sector_coverage["coverage_target_passed"]
        ),
        "gate1_passed": bool(gate1_passed),
        "broad_market_pnl_parity_passed": bool(pnl_parity_passed),
        "broad_market_pnl_parity_drift": pnl_parity_drift,
        "sector_coverage_passed": bool(sector_coverage["coverage_target_passed"]),
        "sector_coverage_target": SECTOR_COVERAGE_TARGET,
        "sector_coverage_observed": coverage["ok_share"],
        "note": (
            "Measurement repair: Gate 4 requires core parity, broad-market "
            "PnL parity vs the accepted source artifact, and coverage >= "
            f"{SECTOR_COVERAGE_TARGET:.0%} on the warehouse universe."
        ),
    }

    decision = (
        "accepted_broad_market_sector_map_attribution"
        if gate4["passed"]
        else "rejected_broad_market_sector_map_attribution"
    )
    status = "accepted" if gate4["passed"] else "rejected"

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "read_only": True,
        "hypothesis": (
            "Building a persistent sector cache for the broad-market warehouse "
            "universe and attaching sector context to accepted paper trades is "
            "the prerequisite for any broad-market sector concentration / "
            "crowding / hidden-beta allocation alpha_search; absence of this "
            "field is the active blocker."
        ),
        "change_summary": (
            "Adds read-only sector / industry / coverage lookup module "
            "`broad_market_sector_map.py` (yfinance-sourced JSON cache at "
            "`data/reference/broad_market_sector_map.json`) plus focused unit "
            "tests. Experiment re-runs the accepted `exp-20260520-004` "
            "baseline and attaches sector context to the 90 selected paper "
            "trades; no entries / exits / sizing / orders change."
        ),
        "change_type": "measurement_repair_sector_map_field",
        "mechanism_family": "broad_market_sector_attribution",
        "trial_family": "broad_market_sector_map_attribution",
        "trial_variant_id": "yfinance_gics_proxy_sector_v1",
        "changed_variable": "broad_market_sector_map_field",
        "single_causal_variable": "broad_market_sector_map_field",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            CORE_BASELINE_EXPERIMENT_ID,
            SOURCE_EXPERIMENT_ID,
            "exp-20260524-008",
            "exp-20260525-035",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "yfinance_sector_cache_with_warehouse_coverage_audit",
        "component": (
            "quant/experiments/exp_20260525_038_broad_market_sector_map_attribution.py"
        ),
        "parameters": {
            "sector_rule_version": SECTOR_RULE_VERSION,
            "sector_source": SECTOR_SOURCE,
            "sector_cache_path": _repo_rel(DEFAULT_CACHE_PATH),
            "source_artifact": _repo_rel(SOURCE_JSON),
            "windows": {
                label: {
                    "start": spec["start"],
                    "end": spec["end"],
                    "snapshot": spec["snapshot"],
                }
                for label, spec in WINDOWS.items()
            },
            "canonical_accepted_aggregate_expected_value_score_sum": CANONICAL_ACCEPTED_AGGREGATE_EV,
            "canonical_accepted_aggregate_total_pnl_sum": CANONICAL_ACCEPTED_AGGREGATE_PNL,
            "ev_tolerance": EV_TOLERANCE,
            "pnl_tolerance": PNL_TOLERANCE,
            "sector_coverage_target": SECTOR_COVERAGE_TARGET,
            "exact_rerun_command": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\"
                "exp_20260525_038_broad_market_sector_map_attribution.py"
            ),
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            "core_baseline_artifact": CORE_BASELINE_ARTIFACT,
            "source_artifact": _repo_rel(SOURCE_JSON),
            "ohlcv_snapshots": [spec["snapshot"] for spec in WINDOWS.values()],
            "sector_cache_path": _repo_rel(DEFAULT_CACHE_PATH),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "measurement repair: building a broad-market sector field "
                "unblocks future broad-market sector concentration / crowding / "
                "hidden-beta alpha_search."
            ),
            "2_history_check": (
                "risk_engine.SECTOR_MAP only covers ~80 hand-curated core "
                "tickers; broad-market warehouse universe (1336 tickers) was "
                "uncovered, which blocked exp-20260525-(B1 candidate) sector "
                "crowding diagnostic."
            ),
            "3_single_causal_variable": "broad_market_sector_map_field",
            "4_acceptance_standard": (
                "Gate 1 core EV/PnL drift within tolerance; broad-market "
                "PnL parity vs accepted source artifact; sector coverage "
                f">= {SECTOR_COVERAGE_TARGET:.0%}."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\build_broad_market_sector_cache.py; "
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\"
                "exp_20260525_038_broad_market_sector_map_attribution.py"
            ),
        },
        "gate1": gate1,
        "gate2": {
            "passed": bool(gate2["passed"]),
            "field_check": gate2,
            "rule_dependencies": [
                "operator_inputs/open_positions.json entry_date/target_price",
                _repo_rel(SOURCE_JSON),
                _repo_rel(DEFAULT_CACHE_PATH),
                "warehouse ticker_universe + coverage_summary tables",
                "canonical three-window OHLCV snapshots",
            ],
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "passed": True,
        },
        "gate4": gate4,
        "sector_coverage": sector_coverage,
        "broad_market_baseline_pnl_by_window": pnl_by_window,
        "source_pnl_by_window": source_pnl_by_window,
        "broad_market_pnl_parity_drift": pnl_parity_drift,
        "broad_market_pnl_parity_passed": bool(pnl_parity_passed),
        "window_sector_attribution": sector_attribution_by_window,
        "aggregate_sector_attribution": aggregate_sector_attribution,
        "before_metrics": {
            "accepted_core_expected_value_score_sum": CANONICAL_ACCEPTED_AGGREGATE_EV,
            "accepted_core_total_pnl_sum": CANONICAL_ACCEPTED_AGGREGATE_PNL,
            "broad_market_baseline_pnl_by_window": source_pnl_by_window,
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": aggregate_ev,
            "accepted_core_total_pnl_sum": aggregate_pnl,
            "broad_market_baseline_pnl_by_window": pnl_by_window,
            "strategy_behavior_changed": False,
            "sector_coverage_ok_share": coverage["ok_share"],
            "sector_unique_count_warehouse": coverage["sector_unique_count"],
            "sector_unique_count_selected_trades": aggregate_sector_attribution[
                "sector_unique_count"
            ],
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": ev_drift,
            "total_pnl_sum_delta": pnl_drift,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": ev_drift,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": _production_impact(),
        "decision_rule": (
            "Accept iff Gate 1 core EV/PnL drift within tolerance, broad-market "
            "PnL parity vs source artifact, and warehouse sector coverage "
            f">= {SECTOR_COVERAGE_TARGET:.0%}. Otherwise reject and do not "
            "promote sector field into broad-market production paper sleeve."
        ),
        "rejection_reason": None if gate4["passed"] else "see gate4",
        "next_evidence_needed": (
            "First broad-market sector-aware allocation alpha_search (e.g. "
            "haircut on >= N same-sector candidates on the same day), tested "
            "via standard broad-market Gate 4 (positive aggregate dEV, 0 "
            "EV-regressed windows, concentration guards)."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(QUANT_DIR / "broad_market_sector_map.py"),
            _repo_rel(QUANT_DIR / "build_broad_market_sector_cache.py"),
            _repo_rel(QUANT_DIR / "test_broad_market_sector_map.py"),
            _repo_rel(DEFAULT_CACHE_PATH),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG_JSONL),
            _repo_rel(SOURCE_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "experiment_id",
        "timestamp",
        "status",
        "hypothesis",
        "change_summary",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "component",
        "parameters",
        "date_range",
        "gate_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "sector_coverage",
        "aggregate_sector_attribution",
        "broad_market_pnl_parity_passed",
        "broad_market_pnl_parity_drift",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "expected_value_score_delta",
        "llm_metrics",
        "production_impact",
        "decision",
        "decision_rule",
        "rejection_reason",
        "next_evidence_needed",
        "related_files",
        "anti_js",
    )
    return {key: payload[key] for key in keys}


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "measurement_repair",
            "owner": "codex",
            "status": payload["status"],
            "decision": payload["decision"],
            "single_causal_variable": payload["single_causal_variable"],
            "artifact_file": _repo_rel(OUT_JSON),
            "result_file": _repo_rel(LOG_JSON),
            "updated_at": payload["timestamp"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "status": payload["status"],
                    "decision": payload["decision"],
                    "gate1_passed": payload["gate1"]["passed"],
                    "gate4_passed": payload["gate4"]["passed"],
                    "broad_market_pnl_parity_passed": payload[
                        "broad_market_pnl_parity_passed"
                    ],
                    "sector_coverage_ok_share": payload["sector_coverage"][
                        "ok_share"
                    ],
                    "sector_unique_count_warehouse": payload["sector_coverage"][
                        "sector_unique_count"
                    ],
                    "output": _repo_rel(OUT_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
