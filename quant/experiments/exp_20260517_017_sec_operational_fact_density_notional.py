"""exp-20260517-017: SEC operational fact density notional.

Alpha search on one causal variable: a paper-notional multiplier for covered
SEC financial-report T+1 paper-sleeve candidates whose archived filing text
shows high operational-fact density without high narrative vagueness.

This is a new playbook direction derived from the suggested
`operational_fact_density_bucket` and `narrative_vagueness_bucket` fields.
It keeps the accepted SEC sleeve, queue, hold days, max positions, base
notional, periodic-report scalars, and live orders fixed.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260517-017"
STEM = "exp_20260517_017_sec_operational_fact_density_notional"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260516_033_sec_financial_report_neutral_language_notional as parent  # noqa: E402
from sec_event_queue import language_features  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_operational_fact_density_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

FACT_DENSITY_SCALAR_VARIANTS = (1.10, 1.25, 1.50)
BASELINE_SCALAR = 1.0
MIN_ADJUSTED_TRADES = 8
MIN_WINDOWS_PRESENT = 3
MAX_DRAWDOWN_WORSENING = 0.005
MAX_SINGLE_POSITIVE_PNL_SHARE = 0.55

DOC_RE = re.compile(r"(?:^| )DOCUMENT ([^ ]+) ")
NUMERIC_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")

FACT_TERMS = (
    "revenue",
    "net income",
    "earnings per share",
    "eps",
    "ebitda",
    "gross margin",
    "operating margin",
    "free cash flow",
    "cash flow",
    "backlog",
    "bookings",
    "arr",
    "annual recurring revenue",
    "guidance",
    "outlook",
    "forecast",
    "orders",
    "deliveries",
    "production",
    "customers",
    "subscribers",
)
VAGUE_TERMS = (
    "positioned",
    "we believe",
    "believe",
    "confident",
    "confidence",
    "opportunity",
    "opportunities",
    "strategic",
    "transformative",
    "excited",
    "encouraged",
    "pleased",
    "disciplined",
    "long-term",
    "long term",
    "durable",
    "momentum",
    "leader",
    "leadership",
    "differentiated",
    "expanding market",
    "remains focused",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _safe(value: Any) -> Any:
    return parent._safe(value)


def _round(value: Any, ndigits: int = 6) -> float | None:
    return parent._round(value, ndigits)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_text_rows() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    rows_by_accession: dict[str, dict[str, Any]] = {}
    load_stats: list[dict[str, Any]] = []
    paths = [parent.TEXT_ARCHIVE_JSONL]
    if not parent.TEXT_ARCHIVE_JSONL.exists():
        paths = sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_text_*.jsonl"))

    for path in paths:
        if not path.exists() or path.stat().st_size <= 0:
            continue
        loaded = 0
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            accession = parent._accession(row)
            if not accession:
                continue
            rows_by_accession[accession] = row
            loaded += 1
        load_stats.append(
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "bytes": path.stat().st_size,
                "rows_loaded": loaded,
            }
        )
        if path == parent.TEXT_ARCHIVE_JSONL:
            break
    return rows_by_accession, load_stats


def _semantic_text(row: dict[str, Any]) -> str:
    combined = str(row.get("combined_text") or row.get("text") or "")
    if not combined:
        return ""
    primary = str(row.get("primary_document") or "").lower()
    parts: list[str] = []
    for match in DOC_RE.finditer(combined):
        start = match.end()
        next_match = DOC_RE.search(combined, start)
        end = next_match.start() if next_match else len(combined)
        name = match.group(1).lower()
        if "index-headers" in name or re.fullmatch(r"r\d+\.htm", name):
            continue
        if re.search(r"(ex[-_]?99|exhibit[-_]?99|ex99|ex991|e991|exhibit99)", name) or (
            primary and name == primary
        ):
            parts.append(combined[start:end].strip())
    return (" ".join(parts) if parts else combined)[:120000]


def _text_buckets(text: str) -> tuple[float, float, str, str]:
    lowered = text.lower()
    fact_term_hits = sum(lowered.count(term) for term in FACT_TERMS)
    vague_term_hits = sum(lowered.count(term) for term in VAGUE_TERMS)
    numeric_hits = len(NUMERIC_TOKEN_RE.findall(lowered))
    operational_fact_score = fact_term_hits + min(numeric_hits, 12) / 3
    vagueness_score = float(vague_term_hits)
    fact_bucket = (
        "high"
        if operational_fact_score >= 8
        else "medium"
        if operational_fact_score >= 4
        else "low"
    )
    vagueness_bucket = (
        "high" if vagueness_score >= 6 else "medium" if vagueness_score >= 3 else "low"
    )
    return operational_fact_score, vagueness_score, fact_bucket, vagueness_bucket


def _annotate_semantic_fields(
    exp100: dict[str, Any],
    text_rows_by_accession: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    annotated = json.loads(json.dumps(exp100))
    for window in annotated.get("windows", {}).values():
        for row in window.get("candidate_rows") or []:
            accession = parent._accession(row)
            text_row = text_rows_by_accession.get(accession)
            if not text_row:
                row["sec_text_coverage_status"] = "missing_text_archive"
                row["operational_fact_density_bucket"] = None
                row["narrative_vagueness_bucket"] = None
                row["language_bucket"] = None
                continue
            features = language_features(text_row)
            semantic_text = _semantic_text(text_row)
            fact_score, vague_score, fact_bucket, vague_bucket = _text_buckets(semantic_text)
            row["sec_text_coverage_status"] = "covered"
            row["sec_text_pit_caveat"] = text_row.get("pit_caveat")
            row["language_bucket"] = features.get("language_bucket")
            row["text_event_type"] = features.get("text_event_type")
            row["operational_fact_density_score"] = fact_score
            row["narrative_vagueness_score"] = vague_score
            row["operational_fact_density_bucket"] = fact_bucket
            row["narrative_vagueness_bucket"] = vague_bucket
    return annotated


def _semantic_coverage_summary(exp100: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, Any] = {}
    aggregate_status = Counter()
    aggregate_fact_bucket = Counter()
    aggregate_vague_bucket = Counter()
    total = 0
    for label, window in exp100.get("windows", {}).items():
        rows = window.get("candidate_rows") or []
        status = Counter(str(row.get("sec_text_coverage_status") or "unknown") for row in rows)
        fact_bucket = Counter(
            str(row.get("operational_fact_density_bucket") or "uncovered") for row in rows
        )
        vague_bucket = Counter(
            str(row.get("narrative_vagueness_bucket") or "uncovered") for row in rows
        )
        total += len(rows)
        aggregate_status.update(status)
        aggregate_fact_bucket.update(fact_bucket)
        aggregate_vague_bucket.update(vague_bucket)
        by_window[label] = {
            "candidate_count": len(rows),
            "coverage_status": dict(sorted(status.items())),
            "operational_fact_density_bucket": dict(sorted(fact_bucket.items())),
            "narrative_vagueness_bucket": dict(sorted(vague_bucket.items())),
        }
    covered = int(aggregate_status.get("covered") or 0)
    return {
        "aggregate": {
            "candidate_count": total,
            "covered_candidate_count": covered,
            "coverage_rate": _round(covered / total, 4) if total else None,
            "coverage_status": dict(sorted(aggregate_status.items())),
            "operational_fact_density_bucket": dict(sorted(aggregate_fact_bucket.items())),
            "narrative_vagueness_bucket": dict(sorted(aggregate_vague_bucket.items())),
        },
        "by_window": by_window,
    }


def _is_target_position(position: dict[str, Any]) -> bool:
    candidate = parent._source_candidate(position)
    return (
        str(candidate.get("sec_text_coverage_status") or "") == "covered"
        and str(candidate.get("operational_fact_density_bucket") or "") == "high"
        and str(candidate.get("narrative_vagueness_bucket") or "") != "high"
    )


def _baseline_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
) -> dict[str, Any]:
    original = parent._is_neutral_language_position
    parent._is_neutral_language_position = _is_target_position
    try:
        return parent._run_variant(
            core_results=core_results,
            exp100=exp100,
            neutral_language_scalar=BASELINE_SCALAR,
        )
    finally:
        parent._is_neutral_language_position = original


def _run_variant_with_scalar(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    scalar: float,
) -> dict[str, Any]:
    original = parent._is_neutral_language_position
    parent._is_neutral_language_position = _is_target_position
    try:
        row = parent._run_variant(
            core_results=core_results,
            exp100=exp100,
            neutral_language_scalar=scalar,
        )
    finally:
        parent._is_neutral_language_position = original
    row["operational_fact_density_notional_scalar"] = scalar
    return row


def _window_deltas(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    for label in parent.WINDOWS:
        after_metrics = after["by_window"][label]["combined_metrics"]
        before_metrics = before["by_window"][label]["combined_metrics"]
        deltas[label] = {
            "expected_value_score": _round(
                float(after_metrics["expected_value_score"])
                - float(before_metrics["expected_value_score"]),
                6,
            ),
            "total_pnl": _round(
                float(after_metrics["total_pnl"]) - float(before_metrics["total_pnl"]),
                2,
            ),
            "max_drawdown_pct": _round(
                float(after_metrics["max_drawdown_pct"])
                - float(before_metrics["max_drawdown_pct"]),
                6,
            ),
            "sharpe_daily": _round(
                float(after_metrics["sharpe_daily"])
                - float(before_metrics["sharpe_daily"]),
                6,
            ),
        }
    return deltas


def _variant_summary(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = parent._delta(row["aggregate"], baseline["aggregate"])
    by_window = _window_deltas(row, baseline)
    return {
        "operational_fact_density_notional_scalar": row[
            "operational_fact_density_notional_scalar"
        ],
        "aggregate_delta": aggregate_delta,
        "by_window": by_window,
        "ev_positive_windows": sum(
            1 for item in by_window.values() if (item["expected_value_score"] or 0.0) > 0
        ),
        "pnl_positive_windows": sum(
            1 for item in by_window.values() if (item["total_pnl"] or 0.0) > 0
        ),
        "max_drawdown_delta_max": max(
            float(item["max_drawdown_pct"] or 0.0) for item in by_window.values()
        ),
    }


def _closed_positions_for_scalar(
    exp100: dict[str, Any],
    *,
    scalar: float,
) -> list[dict[str, Any]]:
    original = parent._is_neutral_language_position
    parent._is_neutral_language_position = _is_target_position
    rows: list[dict[str, Any]] = []
    try:
        for label, window in parent.WINDOWS.items():
            prices_by_date = parent._load_snapshot_prices(window["snapshot"])
            candidates_by_t1 = parent._rows_by_t1_date(exp100["windows"][label])
            state = parent.empty_sec_financial_report_event_sleeve_state()
            skipped_entries: list[dict[str, Any]] = []
            for as_of, prices in prices_by_date.items():
                candidates = candidates_by_t1.get(as_of, [])
                queue = {
                    "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_QUEUE_REPLAY",
                    "rule_version": f"{EXPERIMENT_ID}-replay",
                    "enabled": False,
                    "asof_date": as_of,
                    "candidate_count": len(candidates),
                    "candidates": candidates,
                    "data_source": {"status": "replay", "window": label},
                }
                snapshot = parent.build_sec_financial_report_event_sleeve_snapshot(
                    sec_financial_report_t1_queue=queue,
                    as_of=as_of,
                    open_prices=prices["open"],
                    current_prices=prices["close"],
                    state=state,
                    config={
                        "max_positions": parent.DEFAULT_MAX_POSITIONS,
                        "event_notional_usd": parent.DEFAULT_EVENT_NOTIONAL_USD,
                        "periodic_report_notional_scalar": parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
                        "tenq_periodic_report_notional_scalar": parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
                    },
                    persist=False,
                )
                skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
                state = parent._rebuild_sleeve_state(snapshot, skipped_entries)

            for position in state.get("closed_positions") or []:
                if not _is_target_position(position):
                    continue
                candidate = parent._source_candidate(position)
                baseline_pnl = parent._pnl_for_position(
                    position,
                    neutral_language_scalar=BASELINE_SCALAR,
                    closed=True,
                )
                adjusted_pnl = parent._pnl_for_position(
                    position,
                    neutral_language_scalar=scalar,
                    closed=True,
                )
                rows.append(
                    {
                        "window": label,
                        "ticker": candidate.get("ticker"),
                        "entry_date": position.get("entry_date"),
                        "exit_date": position.get("exit_date"),
                        "event_family": candidate.get("event_family"),
                        "form_base": candidate.get("form_base") or candidate.get("form_type"),
                        "language_bucket": candidate.get("language_bucket"),
                        "operational_fact_density_bucket": candidate.get(
                            "operational_fact_density_bucket"
                        ),
                        "narrative_vagueness_bucket": candidate.get(
                            "narrative_vagueness_bucket"
                        ),
                        "baseline_pnl": _round(baseline_pnl, 2),
                        "adjusted_pnl": _round(adjusted_pnl, 2),
                        "incremental_pnl": _round(adjusted_pnl - baseline_pnl, 2),
                    }
                )
    finally:
        parent._is_neutral_language_position = original
    return rows


def _selection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window = Counter(str(row["window"]) for row in rows)
    by_ticker = Counter(str(row["ticker"]) for row in rows)
    pnl_by_window: dict[str, float] = {}
    pnl_by_ticker: dict[str, float] = {}
    positive_incremental = []
    for row in rows:
        pnl = float(row.get("incremental_pnl") or 0.0)
        pnl_by_window[str(row["window"])] = pnl_by_window.get(str(row["window"]), 0.0) + pnl
        pnl_by_ticker[str(row["ticker"])] = pnl_by_ticker.get(str(row["ticker"]), 0.0) + pnl
        if pnl > 0:
            positive_incremental.append(pnl)
    positive_total = sum(positive_incremental)
    max_positive = max(positive_incremental) if positive_incremental else 0.0
    return {
        "adjusted_trade_count": len(rows),
        "windows_present": len(by_window),
        "by_window_count": dict(sorted(by_window.items())),
        "by_window_incremental_pnl": {
            key: _round(value, 2) for key, value in sorted(pnl_by_window.items())
        },
        "by_ticker_count": dict(sorted(by_ticker.items())),
        "by_ticker_incremental_pnl": {
            key: _round(value, 2) for key, value in sorted(pnl_by_ticker.items())
        },
        "max_single_positive_incremental_pnl": _round(max_positive, 2),
        "max_single_positive_pnl_share": (
            _round(max_positive / positive_total, 4) if positive_total > 0 else None
        ),
        "positive_incremental_pnl": _round(positive_total, 2),
        "sample_rows": rows[:20],
    }


def _gate(summary: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    aggregate = summary["aggregate_delta"]
    metric_gate_passed = (
        (aggregate.get("expected_value_score_sum_delta") or 0.0) > 0
        and (aggregate.get("total_pnl_sum_delta") or 0.0) > 0
        and summary["ev_positive_windows"] == 3
        and summary["pnl_positive_windows"] == 3
        and summary["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSENING
    )
    sample_guard_passed = (
        selection["adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and selection["windows_present"] >= MIN_WINDOWS_PRESENT
    )
    concentration_guard_passed = (
        selection["max_single_positive_pnl_share"] is not None
        and selection["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_PNL_SHARE
    )
    return {
        "aggregate_delta": aggregate,
        "by_window": summary["by_window"],
        "metric_gate_passed": metric_gate_passed,
        "sample_guard_passed": sample_guard_passed,
        "concentration_guard_passed": concentration_guard_passed,
        "passed": metric_gate_passed and sample_guard_passed and concentration_guard_passed,
        "rules": {
            "metric_gate": (
                "aggregate EV/PnL positive, all three windows EV/PnL positive, and "
                "max drawdown worsening <= 0.5 percentage points"
            ),
            "sample_guard": {
                "min_adjusted_trades": MIN_ADJUSTED_TRADES,
                "min_windows_present": MIN_WINDOWS_PRESENT,
            },
            "concentration_guard": {
                "max_single_positive_pnl_share": MAX_SINGLE_POSITIVE_PNL_SHARE
            },
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload["gate"]
    selection = payload["selection"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Operational Fact Density Notional",
        "",
        f"- decision: `{payload['decision']}`",
        f"- status: `{payload['status']}`",
        f"- expected_value_score_delta: `{payload['expected_value_score_delta']}`",
        f"- total_pnl_delta: `{payload['total_pnl_delta']}`",
        f"- adjusted_trades: `{selection['adjusted_trade_count']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Aggregate Delta",
        "",
        "```json",
        json.dumps(_safe(gate["aggregate_delta"]), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Window Delta",
        "",
        "```json",
        json.dumps(_safe(gate["by_window"]), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Selection",
        "",
        "```json",
        json.dumps(_safe(selection), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Decision",
        "",
        payload["interpretation"],
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    timestamp = _utc_now()
    text_rows_by_accession, text_load_stats = _load_text_rows()
    exp100 = _annotate_semantic_fields(parent._load_exp100(), text_rows_by_accession)
    semantic_coverage = _semantic_coverage_summary(exp100)
    gate2_fields = parent._gate2_open_position_field_check()

    core_results: dict[str, dict[str, Any]] = {}
    for label, window in parent.WINDOWS.items():
        result = parent._run_core_backtest(window)
        core_results[label] = {
            "metrics": parent._core_metrics(result),
            "equity_curve": parent._normalise_core_curve(result),
        }

    baseline = _baseline_variant(core_results=core_results, exp100=exp100)
    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    summaries: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for scalar in FACT_DENSITY_SCALAR_VARIANTS:
        key = f"high_fact_nonhigh_vague_scalar_{scalar:.2f}"
        row = _run_variant_with_scalar(
            core_results=core_results,
            exp100=exp100,
            scalar=scalar,
        )
        variants[key] = row
        summaries[key] = _variant_summary(row, baseline)

    best_key = max(
        summaries,
        key=lambda name: (
            summaries[name]["aggregate_delta"].get("expected_value_score_sum_delta")
            or -999.0,
            summaries[name]["aggregate_delta"].get("total_pnl_sum_delta") or -999999.0,
        ),
    )
    best_summary = summaries[best_key]
    best_scalar = float(best_summary["operational_fact_density_notional_scalar"])
    selection = _selection_summary(_closed_positions_for_scalar(exp100, scalar=best_scalar))
    gate = _gate(best_summary, selection)

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "rejected",
        "lane": "alpha_search",
        "hypothesis": (
            "Inside the SEC financial-report T+1 paper sleeve, filings with high "
            "operational fact density and without high narrative vagueness should "
            "carry higher-quality continuation alpha than the undifferentiated sleeve."
        ),
        "change_summary": (
            "Sweep a paper-notional scalar for covered SEC financial-report rows "
            "whose filing text lands in the new high-fact / non-high-vagueness cohort."
        ),
        "change_type": "alpha_search_semantic_field_allocation",
        "component": "quant/experiments",
        "changed_variable": "operational_fact_density_non_high_vagueness_notional_scalar",
        "single_causal_variable": (
            "paper-notional scalar for the high operational-fact-density / non-high "
            "narrative-vagueness SEC financial-report cohort"
        ),
        "parameters": {
            "baseline_scalar": BASELINE_SCALAR,
            "scalar_variants": list(FACT_DENSITY_SCALAR_VARIANTS),
            "best_scalar": best_scalar,
            "base_event_notional_usd": parent.DEFAULT_EVENT_NOTIONAL_USD,
            "periodic_report_scalar": parent.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "tenq_periodic_report_scalar": parent.ACCEPTED_10Q_PERIODIC_REPORT_SCALAR,
            "max_positions": parent.DEFAULT_MAX_POSITIONS,
            "field_definition": {
                "operational_fact_density_bucket": "high if fact_term_hits + min(numeric_hits,12)/3 >= 8",
                "narrative_vagueness_bucket": "exclude only rows with vague_term_hits >= 6",
            },
            "source_candidate_artifact": str(parent.SOURCE_EXP100_JSON.relative_to(REPO_ROOT)),
            "text_archive": str(parent.TEXT_ARCHIVE_JSONL.relative_to(REPO_ROOT)),
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus SEC financial-report production paper-sleeve replay over the same "
            "OHLCV snapshots."
        ),
        "windows": parent.WINDOWS,
        "gate2_required_fields": gate2_fields,
        "text_load_stats": text_load_stats,
        "semantic_coverage_summary": semantic_coverage,
        "before_metrics": baseline["aggregate"],
        "after_metrics": variants[best_key]["aggregate"],
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["by_window"],
        },
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "total_pnl_delta": gate["aggregate_delta"].get("total_pnl_sum_delta"),
        "best_variant": best_key,
        "variant_summaries": summaries,
        "selection": selection,
        "gate": gate,
        "decision": "rejected_operational_fact_density_notional",
        "rejection_reason": (
            "The best scalar stayed negative on aggregate EV and PnL, with losses in "
            "late_strong and mid_weak and only small positive contribution from two "
            "JPM rows in old_thin."
        ),
        "next_evidence_needed": (
            "Do not retry nearby operational-fact-density scalars on frozen windows. "
            "If this research lane resumes, it needs a materially new semantic field "
            "such as explicit KPI delta extraction or cross-channel inconsistency."
        ),
        "interpretation": (
            "This unexplored playbook branch is now tested and rejected on the current "
            "SEC sleeve. High fact density without high vagueness did not identify "
            "better continuation rows; the cohort was small, finance-heavy, and "
            "aggregate negative even before concentration became the main concern."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "promotion_requirement": (
                "Any future positive result would need shared queue fields and the "
                "same paper sleeve consumed by run.py and backtester.py before promotion."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "Mechanical index/passive-flow events remain blocked by missing PIT "
                "history across the three standard windows, so this experiment uses "
                "deterministic SEC text fields with full archive coverage instead."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "SEC/earnings semantic field allocation: high operational-fact-density "
                "and non-high-vagueness filings should deserve more paper notional."
            ),
            "2_history_check": (
                "No prior experiment in docs/experiment_log.jsonl or experiments "
                "used the playbook's operational_fact_density_bucket or "
                "narrative_vagueness_bucket. The nearest related runs were "
                "exp-20260516-033 neutral-language notional and exp-20260517-012 "
                "neutral-language moderate-reaction notional."
            ),
            "3_single_causal_variable": (
                "operational_fact_density_non_high_vagueness_notional_scalar"
            ),
            "4_acceptance_standard": gate["rules"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "why_not_other_changes": (
            "The playbook's mechanical index/passive-flow branch is currently blocked "
            "because repo news history does not cover all three fixed windows. "
            "Rotation/event notional retunes are already anti-repeat or forward-only. "
            "This run therefore tests one fresh, fully replayable SEC semantic field branch."
        ),
        "related_files": [
            f"quant/experiments/{STEM}.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(DOC_LOG.relative_to(REPO_ROOT)),
            str(DOC_TICKET.relative_to(REPO_ROOT)),
            str(DOC_ARTIFACT.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG_JSONL.relative_to(REPO_ROOT)),
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "alpha-search",
            "status": payload["status"],
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["single_causal_variable"],
            "acceptance_rule": gate["rules"],
            "result": {
                "decision": payload["decision"],
                "artifact_file": str(OUT_JSON.relative_to(REPO_ROOT)),
                "result_file": str(DOC_LOG.relative_to(REPO_ROOT)),
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "metric_gate_passed": gate["metric_gate_passed"],
                "sample_guard_passed": gate["sample_guard_passed"],
                "concentration_guard_passed": gate["concentration_guard_passed"],
            },
            "updated_at": timestamp,
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps(_safe(gate), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {payload['decision']} best={best_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
