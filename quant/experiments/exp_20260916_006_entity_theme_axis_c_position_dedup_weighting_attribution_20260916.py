"""exp-20260916-006: equal-weight unique-position collapse attribution of the
consumed exp-20260914-001 entity/theme axis-C cohort (loss_attribution / analysis_only).

Developmental diagnosis of an already-consumed fixed result.  The unchanged
208492-row settled cohort bound by exp-20260914-001 is one row per news item x
candidate ticker; rows that share (candidate_ticker, entry_date, exit_date,
horizon_trading_days) describe the same 4000-USD position and therefore carry the
same cash/SPY/QQQ replacement values.  The cohort is collapsed to one equal-weight
value per unique position and the unchanged base stats arithmetic is applied, so
the question "is the consumed benchmark-relative positivity a property of
tradeable positions or of news-count weighting" is answered without any retune,
price fetch, reopen-condition or threshold change.  Result ceiling observed_only;
new_alpha_evidence is false by construction.
"""

from __future__ import annotations

import collections
import hashlib
import importlib.util
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

BASE_RUNNER = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260706_012_entity_theme_news_more_settled_forward_value.py"
)


def _load_base() -> Any:
    spec = importlib.util.spec_from_file_location("exp_20260706_012_base", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load base recipe: {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = _load_base()
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)

EXPERIMENT_ID = "exp-20260916-006"
UID = "expuid-c4d1e442ee054f27"
OWNER = "claude-scheduled-alpha"
LANE = "loss_attribution"
CHANGE_TYPE = "analysis_only"
TRIAL_FAMILY = "entity_theme_consumed_cohort_position_dedup_attribution"
SLUG = "entity_theme_axis_c_position_dedup_weighting_attribution_20260916"
RUNNER = f"quant/experiments/exp_20260916_006_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260916_006_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

LEDGER = (
    REPO_ROOT
    / "data/non_ohlcv/entity_theme_news_observer/outcome_ledgers"
    / "entity_theme_news_observer_outcomes_20260913.jsonl"
)
ARTIFACT_0914 = (
    REPO_ROOT
    / "data/experiments/exp-20260914-001"
    / "exp_20260914_001_entity_theme_news_axis_c4_more_settled_forward_value_20260914.json"
)
PROTOCOL = REPO_ROOT / "docs" / "quant_agent_protocol_v2.md"

# Input identity pinned at freeze time (card measurement plan, 2026-09-16T16:2xZ).
PINS = {
    "ledger": "1593fa0360aeb745f60232492fff685aa2c215a263a4f92c8e0f1701ece1c2e0",
    "base_runner": "0b50bd27eca6a17c1a63969cef59e08267bff2fcbeb81e4bab647acfdb32b7a0",
    "artifact_0914": "c0be97c7184892db688d88c44b56fbc68e555befb40657381ba47ed4d782df6d",
}
POSITION_FIELDS = ("candidate_ticker", "entry_date", "exit_date", "horizon_trading_days")
QUERY_POSITION_FIELDS = ("entity_theme_query_id",) + POSITION_FIELDS
# Consumed values (read again from the pinned artifact at runtime and cross-checked).
CONSUMED_0914 = {
    "settled_rows": 208492,
    "mean": {"cash": 48.4422, "spy": 24.0684, "qqq": 20.8692},
    "median": {"cash": 8.01, "spy": 3.12, "qqq": -1.50},
}
# Outcome-blind identity counts recorded before reservation (2026-09-16T16:14Z).
EXPECTED_UNIQUE_POSITIONS = 3490
EXPECTED_UNIQUE_QUERY_POSITIONS = 3915
C0_USD_TOLERANCE = 0.01
WITHIN_POSITION_TOLERANCE = 0.01

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260916_006_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
REPRODUCTION_COMMANDS = [
    f"python -B -m py_compile {RUNNER_PS}",
    f"python -B {RUNNER_PS}",
    "python -B scripts\\experiment.py audit --lean-strict",
]

FORBIDDEN_RETRY = (
    "Do not reserve a position-level, news-count-weighted, news-intensity, per-query, "
    "per-theme or per-ticker re-slice of this bundle as a separate face; do not retune "
    "queries, ticker maps, horizon, row size, response curves or thresholds; do not treat "
    "this diagnostic as alpha evidence or as a change to the frozen family reopen bar."
)
REFLECTION = {
    "weighting_artifact": {
        "why_result_happened": (
            "Collapsed to one equal-weight value per unique (ticker, entry, exit, horizon) "
            "position, the consumed cohort's replacement value versus SPY and versus QQQ is "
            "not positive, so the benchmark-relative positivity reported by exp-20260914-001 "
            "was carried by news-count weighting (positions with many news rows outperformed) "
            "rather than by the tradeable positions themselves; the row-level read overstated "
            "both the effect and the effective sample (about 3.5 thousand positions, not "
            "208 thousand rows)."
        ),
        "forbidden_near_neighbor_retry": FORBIDDEN_RETRY,
        "new_evidence_required": (
            "The existing 312738 settled-row bar under the unchanged manifest stands; a "
            "separately pre-registered contract review (not enacted here) may require the "
            "fifth same-face read to report equal-weight position-level statistics alongside "
            "the row-level acceptance arithmetic; otherwise a true canonical PIT historical "
            "news archive or a materially richer independent entity-relation source."
        ),
    },
    "position_level_no_edge": {
        "why_result_happened": (
            "Collapsed to one equal-weight value per unique position, the cohort keeps the "
            "consumed read's qualitative shape (benchmark-relative means not both "
            "non-positive, but medians not all non-negative), so the row-level statistics "
            "were a fair summary of the positions and the median failure is a property of "
            "the positions, not of news-count weighting; the effective sample is about 3.5 "
            "thousand positions rather than 208 thousand rows."
        ),
        "forbidden_near_neighbor_retry": FORBIDDEN_RETRY,
        "new_evidence_required": (
            "No change: the existing 312738 settled-row bar under the unchanged manifest, a "
            "true canonical PIT historical news archive, or a materially richer independent "
            "entity-relation source remain the only reopen paths."
        ),
    },
    "position_level_passes": {
        "why_result_happened": (
            "Collapsed to one equal-weight value per unique position, the cohort has positive "
            "means and non-negative medians versus cash, SPY and QQQ while the row-level read "
            "failed its median bars, so news-count weighting dragged the consumed medians "
            "down; reported only, because a position-level acceptance arithmetic on the same "
            "source bundle is a forbidden re-slice under exp-20260914-001."
        ),
        "forbidden_near_neighbor_retry": FORBIDDEN_RETRY,
        "new_evidence_required": (
            "The existing 312738 settled-row bar under the unchanged manifest, a true "
            "canonical PIT historical news archive, or a materially richer independent "
            "entity-relation source; any position-level measurement change needs its own "
            "pre-registered contract review plus the family's observed-only override."
        ),
    },
    "identity_mismatch": {
        "why_result_happened": (
            "The pooled rows did not reproduce the consumed exp-20260914-001 read within "
            "0.01 USD, or rows sharing one position key did not carry identical replacement "
            "values, so the collapse assumption is wrong for this ledger and no weighting "
            "classification is reported."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not loosen the C0 tolerance or redefine the position key after seeing values; "
            "do not reserve any re-slice of this bundle."
        ),
        "new_evidence_required": (
            "An identity-level explanation of why rows sharing ticker, entry, exit and horizon "
            "carry different replacement values (or why the pooled read drifted), registered "
            "as measurement_repair."
        ),
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def position_key(row: dict[str, Any]) -> tuple:
    return tuple(row.get(field) for field in POSITION_FIELDS)


def query_position_key(row: dict[str, Any]) -> tuple:
    return tuple(row.get(field) for field in QUERY_POSITION_FIELDS)


def slim_summary(summary: dict[str, Any]) -> dict[str, Any]:
    observed = summary["observed_date_level"]
    return {
        "settled_rows": summary["settled_rows"],
        "query_group_count": summary["query_group_count"],
        "ticker_count": summary["ticker_count"],
        "row_level": summary["row_level"],
        "observed_date_level": {
            "observed_date_count": observed.get("observed_date_count"),
            "mean_of_date_mean_cash": observed.get("mean_of_date_mean_cash"),
            "mean_of_date_mean_spy": observed.get("mean_of_date_mean_spy"),
            "mean_of_date_mean_qqq": observed.get("mean_of_date_mean_qqq"),
        },
        "positive_query_groups_vs_spy_and_qqq": summary["positive_query_groups_vs_spy_and_qqq"],
        "max_positive_cash_query_share": summary["max_positive_cash_query_share"],
        "max_positive_cash_ticker_share": summary["max_positive_cash_ticker_share"],
        "query_group_table": [
            {
                "entity_theme_query_id": row.get("entity_theme_query_id"),
                "row_count": row.get("row_count"),
                "mean_cash": row.get("mean_cash"),
                "mean_spy": row.get("mean_spy"),
                "mean_qqq": row.get("mean_qqq"),
                "median_cash": row.get("median_cash"),
            }
            for row in summary["top_queries_by_cash"]
        ],
    }


def collapse(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse settled rows to unique positions; verify within-position value identity."""
    groups: dict[tuple, list[dict[str, Any]]] = collections.OrderedDict()
    for row in rows:
        groups.setdefault(position_key(row), []).append(row)
    positions: list[dict[str, Any]] = []
    mismatches = 0
    max_within_range = 0.0
    for key, group_rows in groups.items():
        item: dict[str, Any] = {field: key[index] for index, field in enumerate(POSITION_FIELDS)}
        item["row_count"] = len(group_rows)
        mismatched = False
        for name, field in base.VALUE_FIELDS.items():
            values = [base.number(row.get(field)) for row in group_rows]
            spread = max(values) - min(values)
            max_within_range = max(max_within_range, spread)
            if spread > WITHIN_POSITION_TOLERANCE:
                mismatched = True
            item[name] = values[0]
        if mismatched:
            mismatches += 1
        positions.append(item)
    return {
        "positions": positions,
        "within_position_value_mismatches": mismatches,
        "max_within_position_value_range_usd": round(max_within_range, 6),
    }


def position_stats(positions: list[dict[str, Any]]) -> dict[str, Any]:
    return {name: base.stats([item[name] for item in positions]) for name in base.VALUE_FIELDS}


def weighted_means(positions: list[dict[str, Any]]) -> dict[str, float]:
    total = sum(item["row_count"] for item in positions)
    return {
        name: round(sum(item["row_count"] * item[name] for item in positions) / total, 4)
        for name in base.VALUE_FIELDS
    }


def rows_per_position_profile(positions: list[dict[str, Any]]) -> dict[str, Any]:
    counts = sorted(item["row_count"] for item in positions)
    total = sum(counts)
    top = max(1, int(0.1 * len(counts)))
    return {
        "unique_positions": len(counts),
        "rows": total,
        "min": counts[0],
        "median": statistics.median(counts),
        "mean": round(total / len(counts), 4),
        "p90": counts[int(0.9 * (len(counts) - 1))],
        "max": counts[-1],
        "single_row_positions": sum(1 for count in counts if count == 1),
        "top_decile_positions_row_share": round(sum(counts[-top:]) / total, 6),
    }


def _average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        stop = index
        while stop + 1 < len(order) and values[order[stop + 1]] == values[order[index]]:
            stop += 1
        rank = (index + stop) / 2 + 1
        for position in range(index, stop + 1):
            ranks[order[position]] = rank
        index = stop + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3 or len(x) != len(y):
        return None
    rx, ry = _average_ranks(x), _average_ranks(y)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return None
    return round(cov / (vx * vy) ** 0.5, 6)


def classify(level: dict[str, Any]) -> str:
    means = {name: float(level[name]["mean"]) for name in base.VALUE_FIELDS}
    medians = {name: float(level[name]["median"]) for name in base.VALUE_FIELDS}
    if means["spy"] <= 0 and means["qqq"] <= 0:
        return "weighting_artifact"
    if all(value > 0 for value in means.values()) and all(value >= 0 for value in medians.values()):
        return "position_level_passes"
    return "position_level_no_edge"


def c0_check(
    pooled_row_level: dict[str, Any],
    settled_count: int,
    weighted: dict[str, float],
    collapsed: dict[str, Any],
) -> dict[str, Any]:
    checks = {"count_exact": settled_count == CONSUMED_0914["settled_rows"]}
    deltas: dict[str, float] = {}
    for stat in ("mean", "median"):
        for name in base.VALUE_FIELDS:
            delta = round(float(pooled_row_level[name][stat]) - float(CONSUMED_0914[stat][name]), 4)
            deltas[f"{stat}_{name}"] = delta
            checks[f"{stat}_{name}_within_tolerance"] = abs(delta) <= C0_USD_TOLERANCE
    for name in base.VALUE_FIELDS:
        delta = round(weighted[name] - float(pooled_row_level[name]["mean"]), 4)
        deltas[f"weighted_position_mean_minus_row_mean_{name}"] = delta
        checks[f"weighted_position_mean_{name}_matches_row_mean"] = abs(delta) <= C0_USD_TOLERANCE
    checks["within_position_values_identical"] = collapsed["within_position_value_mismatches"] == 0
    return {
        "settled_count": settled_count,
        "deltas_usd": deltas,
        "within_position_value_mismatches": collapsed["within_position_value_mismatches"],
        "max_within_position_value_range_usd": collapsed["max_within_position_value_range_usd"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def _toy_row(value: float, ticker: str, copies: int, query: str = "q1") -> list[dict[str, Any]]:
    return [
        {
            "outcome_status": "settled",
            "horizon_trading_days": 10,
            "replacement_value_vs_cash_usd": value,
            "replacement_value_vs_spy_usd": value,
            "replacement_value_vs_qqq_usd": value,
            "observed_date": "2026-01-01",
            "entry_date": "2026-01-02",
            "exit_date": "2026-01-16",
            "entity_theme_query_id": query,
            "candidate_ticker": ticker,
            "candidate_item_index": index,
            "url": f"u{ticker}{index}",
            "published_at": "2026-01-01T00:00:00Z",
            "theme": "t",
            "relation_type": "r",
        }
        for index in range(copies)
    ]


def synthetic_self_test() -> dict[str, Any]:
    # Hand-checked: A = 3 rows of +10, B = 1 row of -20 -> row mean +2.5, position mean -5.
    rows = base.settled_rows(_toy_row(10, "A", 3) + _toy_row(-20, "B", 1))
    collapsed = collapse(rows)
    level = position_stats(collapsed["positions"])
    row_level = base.stats(base.values_by_field(rows)["cash"])
    assert row_level["mean"] == 2.5 and level["cash"]["mean"] == -5.0
    assert weighted_means(collapsed["positions"])["cash"] == 2.5
    assert collapsed["within_position_value_mismatches"] == 0
    assert classify(level) == "weighting_artifact"
    # A = 3 x +10, B = 1 x -8 -> row mean 5.5, position mean +1, median +1 -> passes.
    rows = base.settled_rows(_toy_row(10, "A", 3) + _toy_row(-8, "B", 1))
    level = position_stats(collapse(rows)["positions"])
    assert level["cash"]["mean"] == 1.0 and level["cash"]["median"] == 1.0
    assert classify(level) == "position_level_passes"
    # A = 3 x +10, B = 1 x -1, C = 1 x -2 -> position mean +2.3333, median -1 -> no edge.
    rows = base.settled_rows(_toy_row(10, "A", 3) + _toy_row(-1, "B", 1) + _toy_row(-2, "C", 1))
    level = position_stats(collapse(rows)["positions"])
    assert level["cash"]["mean"] == 2.3333 and level["cash"]["median"] == -1.0
    assert classify(level) == "position_level_no_edge"
    # Within-position mismatch must be detected (same key, different value).
    bad = _toy_row(10, "A", 1) + _toy_row(11, "A", 1)
    bad[1]["candidate_item_index"] = 9
    assert collapse(base.settled_rows(bad))["within_position_value_mismatches"] == 1
    # Spearman on a monotone pair is 1.0; profile counts rows.
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    profile = rows_per_position_profile(collapse(rows)["positions"])
    assert profile["unique_positions"] == 3 and profile["rows"] == 5 and profile["max"] == 3
    return {
        "passed": True,
        "cases": [
            "A 3x+10, B 1x-20: row mean +2.5, position mean -5 -> weighting_artifact; weighted position mean reproduces row mean",
            "A 3x+10, B 1x-8: position mean +1, median +1 -> position_level_passes",
            "A 3x+10, B 1x-1, C 1x-2: position mean +2.3333, median -1 -> position_level_no_edge",
            "same position key with values 10 and 11 -> 1 within-position mismatch",
        ],
    }


def verify_pins() -> dict[str, str]:
    actual = {
        "ledger": digest(LEDGER),
        "base_runner": digest(BASE_RUNNER),
        "artifact_0914": digest(ARTIFACT_0914),
    }
    drift = {name: (PINS[name], actual[name]) for name in PINS if PINS[name] != actual[name]}
    if drift:
        raise RuntimeError(f"input hash drift, stop before output: {drift}")
    return actual


def consumed_from_artifact(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    row = payload["summary"]["row_level"]
    return {
        "settled_rows": int(payload["summary"]["settled_rows"]),
        "mean": {key: row[key]["mean"] for key in ("cash", "spy", "qqq")},
        "median": {key: row[key]["median"] for key in ("cash", "spy", "qqq")},
        "decision": payload.get("decision"),
        "failed_reasons": (payload.get("gate4") or {}).get("failed_reasons"),
    }


def build_result() -> dict[str, Any]:
    if OUT_JSON.exists():
        raise RuntimeError("one-shot artifact already exists; do not overwrite or rerun")
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8-sig"))
    expected = (UID, "claimed", OWNER, LANE, CHANGE_TYPE, TRIAL_FAMILY)
    actual = (
        ticket.get("experiment_uid"),
        ticket.get("status"),
        ticket.get("owner"),
        ticket.get("lane"),
        ticket.get("change_type"),
        ticket.get("trial_family"),
    )
    if actual != expected:
        raise RuntimeError(f"ticket identity mismatch: expected {expected}, got {actual}")
    ticket_sha = digest(TICKET_JSON)
    card_sha = digest(CARD_MD)
    pins = verify_pins()
    self_test = synthetic_self_test()
    consumed_0914 = consumed_from_artifact(ARTIFACT_0914)
    if consumed_0914["settled_rows"] != CONSUMED_0914["settled_rows"]:
        raise RuntimeError("exp-20260914-001 settled_rows drift vs frozen constant")
    for stat in ("mean", "median"):
        for key in ("cash", "spy", "qqq"):
            if abs(float(consumed_0914[stat][key]) - float(CONSUMED_0914[stat][key])) > 1e-6:
                raise RuntimeError(f"exp-20260914-001 {stat} {key} drift vs frozen constant")

    source_rows = base.read_jsonl(LEDGER)
    settled = base.settled_rows(source_rows)
    pooled_summary = base.current_summary(settled, settled)
    pooled_row_level = pooled_summary["row_level"]

    collapsed = collapse(settled)
    positions = collapsed["positions"]
    level = position_stats(positions)
    weighted = weighted_means(positions)
    profile = rows_per_position_profile(positions)
    query_positions = len({query_position_key(row) for row in settled})
    identity = {
        "position_fields": list(POSITION_FIELDS),
        "pooled_settled_rows": len(settled),
        "unique_positions": len(positions),
        "unique_positions_expected_outcome_blind": EXPECTED_UNIQUE_POSITIONS,
        "unique_query_positions": query_positions,
        "unique_query_positions_expected_outcome_blind": EXPECTED_UNIQUE_QUERY_POSITIONS,
        "ticker_count": len({item["candidate_ticker"] for item in positions}),
        "entry_date_count": len({item["entry_date"] for item in positions}),
        "rows_per_position": profile,
    }
    if len(positions) != EXPECTED_UNIQUE_POSITIONS or query_positions != EXPECTED_UNIQUE_QUERY_POSITIONS:
        raise RuntimeError(f"identity collapse drift vs outcome-blind count: {identity}")

    c0 = c0_check(pooled_row_level, len(settled), weighted, collapsed)
    if c0["passed"]:
        classification = classify(level)
        disposition = "developmental_diagnosis"
    else:
        classification = None
        disposition = "identity_mismatch"
    reflection_key = classification or "identity_mismatch"
    reflection = dict(REFLECTION[reflection_key])
    reflection["realized_failure_mode"] = {
        "weighting_artifact": "news_volume_weighting_carries_row_means",
        "position_level_no_edge": "position_level_median_nonnegative_fails",
        "position_level_passes": "position_level_passes_report_only",
        None: "within_position_value_mismatch",
    }[classification]

    # Descriptive extras (zero verdict weight).
    first_rows: dict[tuple, dict[str, Any]] = collections.OrderedDict()
    for row in settled:
        first_rows.setdefault(query_position_key(row), row)
    query_position_rows = list(first_rows.values())
    query_position_summary = base.current_summary(query_position_rows, query_position_rows)
    query_position_acceptance = base.acceptance(query_position_summary)
    position_first_rows: dict[tuple, dict[str, Any]] = collections.OrderedDict()
    for row in settled:
        position_first_rows.setdefault(position_key(row), row)
    position_ticker_table = base.group_table(list(position_first_rows.values()), "candidate_ticker")
    descriptive = {
        "position_level_positive_share": {name: level[name]["positive_share"] for name in base.VALUE_FIELDS},
        "row_count_weighted_position_means": weighted,
        "spearman_row_count_vs_position_value": {
            name: spearman(
                [float(item["row_count"]) for item in positions],
                [float(item[name]) for item in positions],
            )
            for name in base.VALUE_FIELDS
        },
        "query_position_level": {
            "note": "one representative row per unique (query, position); unchanged exp-20260719-004 summary and acceptance arithmetic; report only",
            "summary": slim_summary(query_position_summary),
            "acceptance": query_position_acceptance,
        },
        "position_level_ticker_table": [
            {
                "candidate_ticker": row.get("candidate_ticker"),
                "position_count": row.get("row_count"),
                "mean_cash": row.get("mean_cash"),
                "mean_spy": row.get("mean_spy"),
                "mean_qqq": row.get("mean_qqq"),
                "median_cash": row.get("median_cash"),
            }
            for row in position_ticker_table
        ],
    }

    result = {
        "experiment_id": EXPERIMENT_ID,
        "experiment_uid": UID,
        "owner": OWNER,
        "lane": LANE,
        "change_type": CHANGE_TYPE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": ticket.get("trial_variant_id"),
        "mechanism_family": ticket.get("mechanism_family"),
        "record_type": "consumed_result_attribution",
        "status": "observed_only",
        "decision": "observed_only",
        "disposition": disposition,
        "classification": classification,
        "timestamp": utc_now(),
        "hypothesis": ticket.get("hypothesis"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "changed_variable": ticket.get("changed_variable"),
        "causal_components": ticket.get("causal_components"),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "prior_trial_count": ticket.get("prior_trial_count"),
        "new_alpha_evidence": False,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "paper_live_eligible": False,
        "trade_enabled": False,
        "order_intent_count": 0,
        "economic_progress": False,
        "gate_applicability": (
            "All checks are descriptive diagnostics of an already-consumed result; they are "
            "not strategy Gate metrics, not alpha acceptance evidence, and change no reopen "
            "condition or threshold."
        ),
        "metrics": {
            key: None
            for key in (
                "expected_value_score",
                "max_drawdown_pct",
                "sharpe",
                "sharpe_daily",
                "survival_rate",
                "total_pnl",
                "total_return_pct",
                "trade_count",
                "win_rate",
            )
        },
        "runtime": {
            "worktree": REPO_ROOT.as_posix(),
            "branch": "fix/alpha-score-sleeve-same-day-idempotency",
            "head": "f978e063a91b2621ac5c75341d868eca7eed5bf0",
            "authoritative_state_ref": "refs/heads/automation/edge-v2",
            "operational_role": "production_maintenance lane running a root-frozen fixed-result attribution",
            "protocol_path": repo_rel(PROTOCOL),
            "protocol_sha256": digest(PROTOCOL),
            "python": sys.version.split()[0],
        },
        "code": {"path": RUNNER, "sha256": digest(REPO_ROOT / RUNNER)},
        "claimed_ticket_sha256": ticket_sha,
        "measurement_plan_card_sha256_before_run": card_sha,
        "inputs": {
            "ledger": {"path": repo_rel(LEDGER), "sha256": pins["ledger"], "role": "exact cohort bound by exp-20260914-001"},
            "base_runner": {"path": repo_rel(BASE_RUNNER), "sha256": pins["base_runner"], "role": "unchanged stats, summary and acceptance arithmetic"},
            "artifact_0914": {"path": repo_rel(ARTIFACT_0914), "sha256": pins["artifact_0914"], "consumed": consumed_0914},
        },
        "synthetic_self_test": self_test,
        "identity_collapse": identity,
        "c0_pooled_reproduction_and_collapse_identity": c0,
        "classification_rule": {
            "weighting_artifact": "equal-weight position-level mean versus SPY and versus QQQ both at most 0",
            "position_level_passes": "position-level means versus cash, SPY and QQQ all positive and position-level medians all at least 0",
            "position_level_no_edge": "otherwise",
            "gated_on": "C0 passed",
        },
        "pooled_row_level": pooled_row_level,
        "position_level_equal_weight": level,
        "descriptive": descriptive,
        "limitations": [
            "Fixed-result diagnosis of consumed rows; no fresh alpha evidence, no independent sample count.",
            "Positions overlap in holding periods across entry dates and share tickers; the position level is still not an independent sample.",
            "The representative-row query-position summary reuses the observed_date of the first ledger row per key; it is descriptive only.",
            "Original family status, streak and reopen conditions remain unchanged by this ticket.",
        ],
        "budget": {"attribution_executions": 1, "new_strategy_variants": 0, "external_spend": 0, "http_requests": 0},
        "prediction": ticket.get("prediction"),
        "post_run_reflection": reflection,
        "next_retry_requires": reflection["new_evidence_required"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "related_files": [repo_rel(ARTIFACT_0914), repo_rel(OUT_JSON)],
        "research_refs": [],
        "notes": (
            "Developmental diagnosis of the consumed exp-20260914-001 result only; no new alpha "
            "evidence, no strategy change, no reopen-condition change; observed_only ceiling."
        ),
    }
    return result


def build_card_section(result: dict[str, Any]) -> str:
    c0 = result["c0_pooled_reproduction_and_collapse_identity"]
    level = result["position_level_equal_weight"]
    row = result["pooled_row_level"]
    profile = result["identity_collapse"]["rows_per_position"]
    lines = [
        "",
        "## Result (single execution)",
        "",
        f"- Status: `{result['status']}` / disposition `{result['disposition']}` / classification `{result['classification']}`",
        f"- Identity collapse: `{result['identity_collapse']['pooled_settled_rows']}` rows -> `{result['identity_collapse']['unique_positions']}` unique positions (`{result['identity_collapse']['ticker_count']}` tickers x `{result['identity_collapse']['entry_date_count']}` entry dates); rows per position median `{profile['median']}` mean `{profile['mean']}` max `{profile['max']}`; top-decile positions hold `{profile['top_decile_positions_row_share']}` of rows",
        f"- C0: passed `{c0['passed']}`; within-position mismatches `{c0['within_position_value_mismatches']}`; deltas USD `{c0['deltas_usd']}`",
        f"- Row level (consumed) mean cash/SPY/QQQ: `{row['cash']['mean']}` / `{row['spy']['mean']}` / `{row['qqq']['mean']}`; medians `{row['cash']['median']}` / `{row['spy']['median']}` / `{row['qqq']['median']}`",
        f"- Position level (equal weight) mean cash/SPY/QQQ: `{level['cash']['mean']}` / `{level['spy']['mean']}` / `{level['qqq']['mean']}`; medians `{level['cash']['median']}` / `{level['spy']['median']}` / `{level['qqq']['median']}`; positive share `{level['cash']['positive_share']}` / `{level['spy']['positive_share']}` / `{level['qqq']['positive_share']}`",
        f"- Spearman(row count, position value) cash/SPY/QQQ: `{result['descriptive']['spearman_row_count_vs_position_value']}`",
        f"- Artifact: `{result['artifact']}`",
        "",
        "### Reflection",
        "",
        f"- Why: {result['post_run_reflection']['why_result_happened']}",
        f"- Forbidden near-neighbor retry: {result['post_run_reflection']['forbidden_near_neighbor_retry']}",
        f"- New evidence required: {result['post_run_reflection']['new_evidence_required']}",
        "",
    ]
    return "\n".join(lines)


def write_manifest(result: dict[str, Any]) -> None:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        LEDGER,
        BASE_RUNNER,
        ARTIFACT_0914,
    ]
    base.write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "experiment_uid": UID,
            "status": result["status"],
            "decision": result["decision"],
            "classification": result["classification"],
            "generated_at": utc_now(),
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "changed_files": CHANGED_FILES,
            "reproduction_commands": REPRODUCTION_COMMANDS,
            "files": [
                {"path": repo_rel(path), "exists": path.exists(), "sha256": base.sha256(path)}
                for path in paths
            ],
        },
    )


def persist(result: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n"
    with OUT_JSON.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    save_experiment_log_entry(result, allow_duplicate=False, expected_experiment_id=EXPERIMENT_ID)
    with CARD_MD.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(build_card_section(result))
    persist_self_registered_result(
        base.REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=result["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": False,
            "decision": result["decision"],
            "disposition": result["disposition"],
            "classification": result["classification"],
            "artifact": result["artifact"],
            "artifact_sha256": digest(OUT_JSON),
            "log": result["log"],
            "runner": RUNNER,
            "c0": result["c0_pooled_reproduction_and_collapse_identity"],
            "position_level_equal_weight": result["position_level_equal_weight"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "implementation_mode": "consumed_result_attribution",
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "card": result["card"],
            "manifest": result["manifest"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["next_retry_requires"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": REPRODUCTION_COMMANDS,
            "lean_quality_passed": True,
        },
    )
    write_manifest(result)


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        print(json.dumps(synthetic_self_test(), ensure_ascii=False))
        return 0
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "disposition": result["disposition"],
                "classification": result["classification"],
                "c0_passed": result["c0_pooled_reproduction_and_collapse_identity"]["passed"],
                "artifact": result["artifact"],
                "artifact_sha256": digest(OUT_JSON),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
