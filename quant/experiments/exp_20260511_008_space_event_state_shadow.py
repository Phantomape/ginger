"""exp-20260511-008: SPACE_CATALYST event-state shadow attribution.

The static space pool was already rejected as live evidence because it was
selected with 2026 knowledge and carried large drawdowns. This experiment starts
the valid next path: event-dated, observe-only attribution that separates
fundamental/regulatory/contract catalysts from attention-only catalysts.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from space_catalyst_sleeve import (  # noqa: E402
    SPACE_CATALYST_LLM_EVENT_FIELDS,
    SPACE_CATALYST_PROMOTION_GATES,
)


EXPERIMENT_ID = "exp-20260511-008"
STEM = "space_event_state_shadow"
INITIAL_NOTIONAL = 10_000.0
HORIZONS = (1, 5, 10, 20)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": (
                    "data/experiments/exp-20260510-028/ohlcv/"
                    "exp-20260510-028_late_strong_with_space_catalyst.json"
                ),
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": (
                    "data/experiments/exp-20260510-028/ohlcv/"
                    "exp-20260510-028_mid_weak_with_space_catalyst.json"
                ),
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": (
                    "data/experiments/exp-20260510-028/ohlcv/"
                    "exp-20260510-028_old_thin_with_space_catalyst.json"
                ),
            },
        ),
    ]
)

SPACE_OPERATING_TICKERS = (
    "RKLB",
    "ASTS",
    "LUNR",
    "PL",
    "RDW",
    "BKSY",
    "IRDM",
    "VSAT",
    "GSAT",
    "SATS",
)
BENCHMARKS = ("SPY", "QQQ", "ARKX", "UFO")

# Seed events intentionally mix mature historical events and fresh current
# catalysts. Fresh rows are expected to remain pending until future OHLCV is
# added, which is the point of the forward shadow ledger.
SEED_EVENTS = (
    {
        "event_id": "lunr_nasa_clps_20260324",
        "event_date": "2026-03-24",
        "tickers": ["LUNR"],
        "semantic_bucket": "fundamental_contract_regulatory",
        "event_fields": ["government_space_contract", "customer_win"],
        "description": "NASA CLPS award for Lunar South Pole payload delivery.",
        "source_url": (
            "https://www.nasdaq.com/press-release/"
            "intuitive-machines-expands-lunar-surface-operations-1804-million-nasa-clps-award-2026"
        ),
    },
    {
        "event_id": "asts_fcc_d2d_authorization_20260421",
        "event_date": "2026-04-21",
        "tickers": ["ASTS"],
        "semantic_bucket": "fundamental_contract_regulatory",
        "event_fields": ["customer_win"],
        "description": "FCC authorization for AST direct-to-device constellation/SCS service.",
        "source_url": "https://docs.fcc.gov/public/attachments/DOC-420983A1.pdf",
    },
    {
        "event_id": "golden_dome_sbi_awards_20260424",
        "event_date": "2026-04-24",
        "tickers": list(SPACE_OPERATING_TICKERS),
        "semantic_bucket": "defense_budget_theme",
        "event_fields": ["government_space_contract"],
        "description": "Space Force SBI/Golden Dome awards validate defense-space budget attention.",
        "source_url": (
            "https://www.ssc.spaceforce.mil/Newsroom/Article-Display/Article/4470337/"
            "space-forces-space-based-interceptor-program-to-counter-growing-speed-and-maneu"
        ),
    },
    {
        "event_id": "rklb_record_backlog_launch_deal_20260507",
        "event_date": "2026-05-07",
        "tickers": ["RKLB"],
        "semantic_bucket": "fundamental_contract_regulatory",
        "event_fields": ["customer_win"],
        "description": "Rocket Lab reported record Q1 revenue/backlog and a large Neutron/Electron launch deal.",
        "source_url": (
            "https://www.globenewswire.com/news-release/2026/05/07/3290605/0/en/"
            "rocket-lab-s-biggest-launch-deal-yet-confidential-customer-books-multiple-neutron-and-electron-launches.html"
        ),
    },
    {
        "event_id": "uap_release_attention_20260508",
        "event_date": "2026-05-08",
        "tickers": ["ARKX", "UFO"],
        "semantic_bucket": "attention_only",
        "event_fields": ["uap_attention_spike"],
        "description": "Department of War initial release of UAP/UFO files; attention catalyst only.",
        "source_url": (
            "https://www.war.gov/News/Releases/Release/Article/4480582/"
            "department-of-war-releases-unidentified-anomalous-phenomena-files-in-historic-t/"
        ),
    },
    {
        "event_id": "spacex_ipo_attention_20260507",
        "event_date": "2026-05-07",
        "tickers": ["ARKX", "UFO", "RKLB"],
        "semantic_bucket": "attention_only",
        "event_fields": ["spacex_ipo_proxy"],
        "description": "SpaceX IPO attention proxy; not direct public-company fundamentals.",
        "source_url": "https://www.marketwatch.com/",
    },
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
SEED_JSONL = OUT_DIR / f"{STEM}_seed_events.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS = REPO_ROOT / "operator_inputs" / "open_positions.json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as fh:
        return json.load(fh)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    needle = f'"experiment_id":"{payload["experiment_id"]}"'
    spaced_needle = f'"experiment_id": "{payload["experiment_id"]}"'
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if needle in existing or spaced_needle in existing:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _round(value: Any, digits: int = 6) -> Any:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return round(value, digits)


def _close_map(snapshot: dict[str, Any], ticker: str) -> dict[str, float]:
    rows = (snapshot.get("ohlcv") or {}).get(ticker) or []
    out: dict[str, float] = {}
    for row in rows:
        date = row.get("Date")
        close = _round(row.get("Close"))
        if date and close and close > 0:
            out[str(date)] = float(close)
    return out


def _trading_dates(snapshot: dict[str, Any]) -> list[str]:
    return sorted(_close_map(snapshot, "SPY"))


def _next_trading_date(dates: list[str], event_date: str) -> str | None:
    for date in dates:
        if date > event_date:
            return date
    return None


def _horizon_date(dates: list[str], entry_date: str, horizon: int) -> str | None:
    try:
        idx = dates.index(entry_date)
    except ValueError:
        return None
    target_idx = idx + horizon
    if target_idx >= len(dates):
        return None
    return dates[target_idx]


def _basket_return(
    snapshot: dict[str, Any],
    tickers: list[str],
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    returns: dict[str, float] = {}
    missing: list[str] = []
    for ticker in tickers:
        closes = _close_map(snapshot, ticker)
        start = closes.get(start_date)
        end = closes.get(end_date)
        if start is None or end is None or start <= 0:
            missing.append(ticker)
            continue
        returns[ticker] = end / start - 1.0
    if not returns:
        return {
            "return": None,
            "pnl_proxy": None,
            "available_tickers": [],
            "missing_tickers": sorted(missing),
        }
    avg_return = mean(returns.values())
    return {
        "return": _round(avg_return),
        "pnl_proxy": _round(avg_return * INITIAL_NOTIONAL, 2),
        "available_tickers": sorted(returns),
        "missing_tickers": sorted(missing),
        "ticker_returns": {ticker: _round(value) for ticker, value in sorted(returns.items())},
    }


def _event_window_label(event_date: str) -> str | None:
    for label, spec in WINDOWS.items():
        if spec["start"] <= event_date <= spec["end"]:
            return label
    # Fresh forward rows belong to the latest available augmented snapshot until
    # a new forward OHLCV snapshot is created.
    if event_date > WINDOWS["late_strong"]["end"]:
        return "late_strong"
    return None


def _open_position_field_audit() -> dict[str, Any]:
    if not OPEN_POSITIONS.exists():
        return {
            "path": str(OPEN_POSITIONS.relative_to(REPO_ROOT)),
            "exists": False,
            "position_count": 0,
            "missing_entry_date_or_target_price": None,
            "passed": False,
        }
    payload = _load_json(OPEN_POSITIONS)
    positions = payload.get("positions") or []
    missing = [
        pos.get("ticker")
        for pos in positions
        if not pos.get("entry_date") or not pos.get("target_price")
    ]
    return {
        "path": str(OPEN_POSITIONS.relative_to(REPO_ROOT)),
        "exists": True,
        "position_count": len(positions),
        "missing_entry_date_or_target_price": missing,
        "passed": not missing,
    }


def _evaluate_event(event: dict[str, Any], snapshots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    label = _event_window_label(event["event_date"])
    row = {
        **event,
        "window": label,
        "initial_notional": INITIAL_NOTIONAL,
        "outcome_status": "pending",
        "entry_date": None,
        "horizons": {},
    }
    if not label or label not in snapshots:
        row["pending_reason"] = "event_outside_available_windows"
        return row

    snapshot = snapshots[label]
    dates = _trading_dates(snapshot)
    entry_date = _next_trading_date(dates, event["event_date"])
    row["entry_date"] = entry_date
    if not entry_date:
        row["pending_reason"] = "no_trading_date_after_event_in_snapshot"
        return row

    matured = 0
    for horizon in HORIZONS:
        exit_date = _horizon_date(dates, entry_date, horizon)
        horizon_key = f"{horizon}d"
        if not exit_date:
            row["horizons"][horizon_key] = {
                "status": "pending",
                "pending_reason": "horizon_not_mature_in_snapshot",
            }
            continue

        event_outcome = _basket_return(snapshot, list(event["tickers"]), entry_date, exit_date)
        benchmarks = {
            ticker: _basket_return(snapshot, [ticker], entry_date, exit_date)
            for ticker in BENCHMARKS
        }
        same_theme = _basket_return(
            snapshot,
            list(SPACE_OPERATING_TICKERS),
            entry_date,
            exit_date,
        )
        result = {
            "status": "mature",
            "exit_date": exit_date,
            "event": event_outcome,
            "benchmarks": benchmarks,
            "same_theme_basket": same_theme,
            "cash_relative_pnl": event_outcome.get("pnl_proxy"),
            "same_theme_replacement_value": None,
            "ufo_relative_value": None,
            "arkx_relative_value": None,
            "spy_relative_value": None,
            "qqq_relative_value": None,
        }
        event_return = event_outcome.get("return")
        if event_return is not None:
            if same_theme.get("return") is not None:
                result["same_theme_replacement_value"] = _round(
                    (event_return - same_theme["return"]) * INITIAL_NOTIONAL,
                    2,
                )
            for benchmark in BENCHMARKS:
                bench_return = benchmarks[benchmark].get("return")
                if bench_return is not None:
                    result[f"{benchmark.lower()}_relative_value"] = _round(
                        (event_return - bench_return) * INITIAL_NOTIONAL,
                        2,
                    )
            matured += 1
        row["horizons"][horizon_key] = result

    if matured:
        row["outcome_status"] = "partially_mature" if matured < len(HORIZONS) else "mature"
    else:
        row["pending_reason"] = "no_mature_horizons"
    return row


def _summarize(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "avg": None, "median": None, "win_rate": None}
    return {
        "count": len(values),
        "avg": _round(mean(values)),
        "median": _round(median(values)),
        "win_rate": _round(sum(1 for value in values if value > 0) / len(values), 4),
    }


def _aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    overall: dict[str, list[float]] = defaultdict(list)
    mature_event_count = 0
    for row in rows:
        has_mature = False
        bucket = row["semantic_bucket"]
        for horizon_key, horizon in row.get("horizons", {}).items():
            if horizon.get("status") != "mature":
                continue
            event_return = (horizon.get("event") or {}).get("return")
            same_theme_value = horizon.get("same_theme_replacement_value")
            ufo_value = horizon.get("ufo_relative_value")
            if event_return is not None:
                by_bucket[bucket][f"{horizon_key}_return"].append(float(event_return))
                overall[f"{horizon_key}_return"].append(float(event_return))
                has_mature = True
            if same_theme_value is not None:
                by_bucket[bucket][f"{horizon_key}_same_theme_value"].append(float(same_theme_value))
                overall[f"{horizon_key}_same_theme_value"].append(float(same_theme_value))
            if ufo_value is not None:
                by_bucket[bucket][f"{horizon_key}_ufo_relative_value"].append(float(ufo_value))
                overall[f"{horizon_key}_ufo_relative_value"].append(float(ufo_value))
        if has_mature:
            mature_event_count += 1
    return {
        "event_count": len(rows),
        "mature_event_count": mature_event_count,
        "pending_event_count": len(rows) - mature_event_count,
        "overall": {key: _summarize(values) for key, values in sorted(overall.items())},
        "by_semantic_bucket": {
            bucket: {key: _summarize(values) for key, values in sorted(metrics.items())}
            for bucket, metrics in sorted(by_bucket.items())
        },
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    rows = payload["event_rows"]
    lines = [
        f"# {EXPERIMENT_ID} SPACE_CATALYST Event-State Shadow",
        "",
        "Status: observed only.",
        "",
        "This starts the valid forward attribution path for the space theme. It does not enable live slots, change ranking, change sizing, or route orders.",
        "",
        "## Seed Events",
        "",
        "| Event | Date | Bucket | Tickers | Status | 5d return | 5d vs UFO |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        h5 = row.get("horizons", {}).get("5d", {})
        event_return = None
        ufo_value = None
        if h5.get("status") == "mature":
            event_return = ((h5.get("event") or {}).get("return") or 0.0) * 100
            ufo_value = h5.get("ufo_relative_value")
        lines.append(
            "| {event_id} | {date} | {bucket} | {tickers} | {status} | {ret} | {ufo} |".format(
                event_id=row["event_id"],
                date=row["event_date"],
                bucket=row["semantic_bucket"],
                tickers=", ".join(row["tickers"]),
                status=row["outcome_status"],
                ret="" if event_return is None else f"{event_return:.2f}%",
                ufo="" if ufo_value is None else f"${ufo_value:,.2f}",
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            payload["decision_summary"],
            "",
            "## Production Impact",
            "",
            "```text",
            "production_impact:",
            "  shared_policy_changed: false",
            "  backtester_adapter_changed: false",
            "  run_adapter_changed: false",
            "  replay_only: true",
            "  alters_orders: false",
            "  alters_signal_generation: false",
            "  alters_candidate_ranking: false",
            "  alters_sizing: false",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def run_experiment() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    snapshots = {
        label: _load_json(REPO_ROOT / spec["snapshot"])
        for label, spec in WINDOWS.items()
    }
    rows = [_evaluate_event(dict(event), snapshots) for event in SEED_EVENTS]
    aggregate = _aggregate_rows(rows)
    gate_passed = (
        aggregate["mature_event_count"] >= SPACE_CATALYST_PROMOTION_GATES["minimum_closed_decisions"]
        and (aggregate["overall"].get("10d_return") or {}).get("avg", 0) > 0
        and (aggregate["overall"].get("10d_same_theme_value") or {}).get("avg", -1) > 0
        and (aggregate["overall"].get("10d_ufo_relative_value") or {}).get("avg", -1) > 0
    )
    decision_summary = (
        "Do not promote. The ledger is now running, but only "
        f"{aggregate['mature_event_count']} seed events have any mature outcome versus the "
        f"{SPACE_CATALYST_PROMOTION_GATES['minimum_closed_decisions']} closed-decision gate. "
        "Use this harness for forward collection and require fundamental/regulatory/contract "
        "events to beat cash, UFO/ARKX, and same-theme alternatives before specialist promotion."
    )
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": "observed_only_forward_collection_started",
        "lane": "alpha_search",
        "hypothesis": (
            "Space catalysts deserve a separate specialist strategy only if official "
            "contract/regulatory/customer events beat cash, UFO/ARKX, and same-theme "
            "alternatives; attention-only UAP/SpaceX IPO headlines should remain attribution-only."
        ),
        "change_type": "event_state_shadow_attribution_harness",
        "changed_variable": "space_event_semantic_bucket_outcome_tracking",
        "single_causal_variable": "classify seed space catalysts by semantic event bucket and track forward outcomes",
        "parameters": {
            "initial_notional": INITIAL_NOTIONAL,
            "horizons_trading_days": list(HORIZONS),
            "semantic_buckets": sorted({event["semantic_bucket"] for event in SEED_EVENTS}),
            "event_fields": list(SPACE_CATALYST_LLM_EVENT_FIELDS),
            "promotion_gates": SPACE_CATALYST_PROMOTION_GATES,
            "locked_variables": [
                "core universe",
                "signal generation",
                "entry filters",
                "ranking",
                "sizing",
                "exits",
                "live pilot slots",
                "LLM hard risk authority",
            ],
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}"
            for label, spec in WINDOWS.items()
        },
        "snapshots": {label: spec["snapshot"] for label, spec in WINDOWS.items()},
        "gate_results": {
            "gate1": "Uses accepted core baseline; no core behavior changed.",
            "gate2": _open_position_field_audit(),
            "gate3": "No new filter added; this is an observe-only attribution ledger.",
            "gate4": {
                "passed": gate_passed,
                "reason": "Forward promotion gate requires mature closed decisions and positive direct/replacement outcomes.",
            },
        },
        "historical_experiment_check": {
            "exp-20260511-002": "Static space pool raw-positive but rejected for hindsight selection and drawdown.",
            "exp-20260511-003": "Production-visible default-off space shadow surface already exists.",
            "not_repeated": [
                "static pool promotion",
                "adjacent ticker mining",
                "live slot enablement",
                "RS20 scalar retune",
            ],
        },
        "event_rows": rows,
        "aggregate": aggregate,
        "decision": "observed_only_forward_collection_started",
        "decision_summary": decision_summary,
        "rejection_reason": (
            "Insufficient mature event outcomes for promotion; attention-only events are not "
            "valid trading evidence."
        ),
        "next_evidence_needed": [
            "Add forward event rows from daily news/filing review with the same schema.",
            "Compute direct, cash-relative, UFO/ARKX-relative, and same-theme replacement value after 1/5/10/20 trading days.",
            "Only consider SPACE_CATALYST_SPECIALIST after at least 10 mature closed decisions or 30 active signal days.",
        ],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none; event fields are deterministic seed labels in this experiment",
            "future_llm_attribution": (
                "LLM may later populate the same event_fields, but trading/risk/exit remains code-owned."
            ),
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(SEED_JSONL.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def main() -> None:
    payload = run_experiment()
    seed_rows = [
        {
            **event,
            "experiment_id": EXPERIMENT_ID,
            "record_type": "space_catalyst_seed_event",
        }
        for event in SEED_EVENTS
    ]
    _write_json(OUT_JSON, payload)
    _write_jsonl(SEED_JSONL, seed_rows)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "SPACE_CATALYST event-state shadow attribution",
            "status": payload["status"],
            "lane": payload["lane"],
            "created_at": payload["timestamp"],
            "problem": "Space theme needs event-dated attribution before any specialist or aggressive live sleeve.",
            "result": {
                "decision": payload["decision"],
                "mature_event_count": payload["aggregate"]["mature_event_count"],
                "pending_event_count": payload["aggregate"]["pending_event_count"],
                "gate_passed": payload["gate_results"]["gate4"]["passed"],
            },
            "next_steps": payload["next_evidence_needed"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_build_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
