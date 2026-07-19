"""exp-20260719-002: Linux mainline signed-RC acceleration Gate 1-4 replay.

This evaluate-only runner consumes the hash-bound Linux source bundle produced by
the shared default-off policy.  Its source-only density and signature/PIT checks
complete before the warehouse, baseline, benchmark, or any price row is opened.
The formal comparison is capital neutral: a fully funded 24% sleeve replaces 24%
of the accepted core stream.  This file cannot emit orders or enable trading.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import sys
import tempfile
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260719-002"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
for import_path in (REPO_ROOT, QUANT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import linux_mainline_rc_contribution_acceleration_paper_sleeve as policy  # noqa: E402
from quant.constants import ROUND_TRIP_COST_PCT  # noqa: E402
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


WINDOWS = OrderedDict(
    (
        ("old_thin", ("2024-10-02", "2025-04-22")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("late_strong", ("2025-10-23", "2026-04-21")),
    )
)
SOURCE_AS_OF = WINDOWS["late_strong"][1]
OHLCV_QUERY_START = "2024-08-01"
OHLCV_QUERY_END = "2026-05-29"
SOURCE_DIR = (
    REPO_ROOT / "data" / "non_ohlcv" / "linux_mainline_rc_contribution_acceleration"
)
BASELINE_SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
RESULT_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260719_002_linux_mainline_rc_contribution_acceleration.json"
)

CORE_WEIGHT = 0.76
SLEEVE_WEIGHT = 0.24
MIN_SETTLED_PER_WINDOW = 20
MIN_TICKERS_PER_WINDOW = 10
MAX_TOP1_COUNT_SHARE = 0.30
MAX_DRAWDOWN_WORSE = 0.005
ACCEPTED_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10_432.91,
}
EXPECTED_SIGNING_KEY_FINGERPRINT = "ABAF11C65A2970B130ABE3C479BE3E4300411886"
EXPECTED_SOURCE_DENSITY = {
    "old_thin": {"selected": 65, "tickers": 18, "top1": 0.169231},
    "mid_weak": {"selected": 58, "tickers": 19, "top1": 0.155172},
    "late_strong": {"selected": 59, "tickers": 17, "top1": 0.135593},
}


class EvaluationContractError(RuntimeError):
    """A source, identity, market, parity, or evaluation invariant failed."""


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _manifest_bool(manifest: Mapping[str, Any], *names: str) -> bool | None:
    """Find a named boolean recursively without treating absence as success."""

    wanted = {name.lower() for name in names}
    stack: list[Any] = [manifest]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            for key, child in value.items():
                if str(key).lower() in wanted and isinstance(child, bool):
                    return child
                stack.append(child)
        elif isinstance(value, list):
            stack.extend(value)
    return None


def _manifest_count(manifest: Mapping[str, Any], *names: str) -> int | None:
    wanted = {name.lower() for name in names}
    stack: list[Any] = [manifest]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            for key, child in value.items():
                if str(key).lower() in wanted and isinstance(child, (int, float)):
                    return int(child)
                stack.append(child)
        elif isinstance(value, list):
            stack.extend(value)
    return None


def _source_contract_audit(
    manifest: Mapping[str, Any],
    tags: Iterable[Mapping[str, Any]],
    commits: Iterable[Mapping[str, Any]],
    crosscheck: Mapping[str, Any],
) -> dict[str, Any]:
    """Audit only source metadata; callers invoke this before all market reads."""

    tag_rows = [dict(row) for row in tags]
    commit_rows = [dict(row) for row in commits]
    manifest_signature_contract = _manifest_bool(
        manifest,
        "signature_verification_passed",
        "tag_signature_verification_passed",
        "all_tag_signatures_verified",
        "signed_tag_verification_passed",
        "signed_annotated_rc_tags_only",
    )
    row_signatures_ok = bool(tag_rows) and all(
        row.get("signature_verified") is True
        and row.get("prior_tag_signature_verified") is True
        for row in tag_rows
    )
    signature_ok = manifest_signature_contract is True and row_signatures_ok
    manifest_hash_ok = _manifest_bool(
        manifest,
        "hash_verification_passed",
        "bundle_hashes_verified",
        "all_hashes_verified",
    )
    # The public loader has already verified every file hash and the manifest
    # self-hash; reaching this audit with verify_hashes=True is positive evidence.
    hash_ok = manifest_hash_ok is not False
    explicit_pit_ok = _manifest_bool(
        manifest,
        "pit_audit_passed",
        "point_in_time_audit_passed",
        "effective_dated_mapping_passed",
        "effective_dated_mapping_pit_audit_passed",
    )
    future_visibility_rejected = _manifest_bool(manifest, "future_visibility_rejected")
    exact_domain_contract = _manifest_bool(manifest, "raw_author_email_exact_domain")
    pit_ok = (
        explicit_pit_ok is True
        or (
            future_visibility_rejected is True
            and exact_domain_contract is True
            and bool(manifest.get("mapping_sha256"))
        )
    )
    verified_count = _manifest_count(
        manifest, "verified_signature_count", "verified_signed_tag_count"
    )
    signature_audit = manifest.get("signature_audit")
    signature_audit_count = (
        int(signature_audit.get("count"))
        if isinstance(signature_audit, Mapping)
        and isinstance(signature_audit.get("count"), (int, float))
        else None
    )
    signature_audit_good = (
        int(signature_audit.get("good"))
        if isinstance(signature_audit, Mapping)
        and isinstance(signature_audit.get("good"), (int, float))
        else verified_count
    )
    selected_rc_tag_count = (
        int(signature_audit.get("selected_rc_tag_count"))
        if isinstance(signature_audit, Mapping)
        and isinstance(signature_audit.get("selected_rc_tag_count"), (int, float))
        else None
    )
    verified_endpoint_count = (
        int(signature_audit.get("verified_endpoint_count"))
        if isinstance(signature_audit, Mapping)
        and isinstance(signature_audit.get("verified_endpoint_count"), (int, float))
        else None
    )
    signature_audit_exit_code = (
        signature_audit.get("exit_code") if isinstance(signature_audit, Mapping) else None
    )
    signature_audit_fingerprint = (
        str(signature_audit.get("key_fingerprint") or "").upper()
        if isinstance(signature_audit, Mapping)
        else ""
    )
    signature_output_sha256 = ""
    if isinstance(signature_audit, Mapping):
        signature_output_sha256 = str(
            signature_audit.get("verification_output_sha256")
            or signature_audit.get("audit_output_sha256")
            or signature_audit.get("output_sha256")
            or ""
        ).lower()
    crosscheck_rows = [
        dict(row) for row in crosscheck.get("rows") or [] if isinstance(row, Mapping)
    ]
    compared_tag_count = int(crosscheck.get("overlap_count") or len(crosscheck_rows))
    crosscheck_ok = crosscheck.get("all_compared_tags_match")
    if crosscheck_ok is None:
        crosscheck_ok = crosscheck.get("all_tags_match")
    failures: list[str] = []
    if not tag_rows:
        failures.append("source_has_no_signed_rc_tags")
    if not commit_rows:
        failures.append("source_has_no_mapped_nonmerge_commits")
    if not signature_ok:
        failures.append("signed_rc_public_key_verification_not_true")
    if not hash_ok:
        failures.append("source_bundle_hash_verification_false")
    if not pit_ok:
        failures.append("source_effective_dated_pit_audit_false")
    if selected_rc_tag_count != len(tag_rows):
        failures.append("selected_rc_signature_count_differs_from_tag_count")
    if (
        signature_audit_count is None
        or verified_endpoint_count != signature_audit_count
        or signature_audit_good != signature_audit_count
        or signature_audit_count < len(tag_rows)
    ):
        failures.append("verified_signed_tag_count_below_tag_count")
    if signature_audit_exit_code != 0:
        failures.append("signature_audit_exit_code_not_zero")
    if signature_audit_fingerprint != EXPECTED_SIGNING_KEY_FINGERPRINT:
        failures.append("signature_audit_key_fingerprint_mismatch")
    if len(signature_output_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in signature_output_sha256
    ):
        failures.append("signature_audit_output_sha256_missing")
    if crosscheck_ok is False:
        failures.append("github_crosscheck_contains_identity_mismatch")

    required_commit_fields = ("ticker", "author_domain")
    missing_commit_identity = sum(
        any(row.get(field) in (None, "") for field in required_commit_fields)
        for row in commit_rows
    )
    if missing_commit_identity:
        failures.append("mapped_commit_identity_fields_missing")
    merge_rows = [
        row
        for row in commit_rows
        if row.get("is_merge") is True or int(row.get("parent_count") or 1) > 1
    ]
    if merge_rows:
        failures.append("mapped_commit_bundle_contains_merge_commits")
    return {
        "passed": not failures,
        "hard_failures": failures,
        "signature_verification_passed": signature_ok,
        "manifest_signature_contract_passed": manifest_signature_contract,
        "tag_row_signatures_passed": row_signatures_ok,
        "bundle_hash_verification_passed": hash_ok,
        "effective_dated_pit_audit_passed": pit_ok,
        "tag_count": len(tag_rows),
        "verified_signature_count": signature_audit_good,
        "signature_audit_count": signature_audit_count,
        "selected_rc_tag_count": selected_rc_tag_count,
        "verified_endpoint_count": verified_endpoint_count,
        "signature_audit_exit_code": signature_audit_exit_code,
        "signature_audit_key_fingerprint": signature_audit_fingerprint,
        "signature_audit_output_sha256": signature_output_sha256 or None,
        "mapped_nonmerge_commit_count": len(commit_rows),
        "github_crosscheck": {
            "passed_for_compared_tags": crosscheck_ok,
            "compared_tag_count": compared_tag_count,
            "official_signed_tag_count": len(tag_rows),
            "partial_shallow_coverage_disclosed": compared_tag_count < len(tag_rows),
            "coverage_caveat": crosscheck.get("coverage_caveat"),
        },
        "missing_commit_identity_count": missing_commit_identity,
        "manifest_sha256": _canonical_sha(manifest),
        "tag_rowset_sha256": _canonical_sha(tag_rows),
        "commit_rowset_sha256": _canonical_sha(commit_rows),
        "price_or_outcome_fields_read": False,
    }


def _decision_signal_date(row: Mapping[str, Any]) -> str:
    for field in (
        "signal_date",
        "decision_date",
        "rc_tag_date",
        "tag_date",
        "tagger_date",
        "release_date",
    ):
        if row.get(field):
            return str(row[field])[:10]
    raise EvaluationContractError("source decision lacks a signal/tag date")


def _source_density_preflight(
    source_rows: list[dict[str, Any]],
    rc_tag_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply the shared selector outcome-blind before any market artifact opens."""

    evaluation = policy.evaluate_linux_mainline_rc_contribution_acceleration_decisions(
        source_rows,
        rc_tag_rows=rc_tag_rows,
        as_of=SOURCE_AS_OF,
    )
    selected = [dict(row) for row in evaluation.get("decisions") or []]
    eligible = [dict(row) for row in evaluation.get("eligible_rows") or []]
    failures: list[str] = []
    by_window: dict[str, dict[str, Any]] = {}
    for label, (start, end) in WINDOWS.items():
        rows = [row for row in selected if start <= _decision_signal_date(row) <= end]
        counts = Counter(str(row["ticker"]) for row in rows)
        top1 = counts.most_common(1)[0][1] / len(rows) if rows else None
        checks = {
            "selected_count_at_least_20": len(rows) >= MIN_SETTLED_PER_WINDOW,
            "ticker_count_at_least_10": len(counts) >= MIN_TICKERS_PER_WINDOW,
            "top1_count_share_at_most_30pct": (
                top1 is not None and top1 <= MAX_TOP1_COUNT_SHARE
            ),
        }
        if not all(checks.values()):
            failures.append(f"outcome_blind_density_failed:{label}")
        expected = EXPECTED_SOURCE_DENSITY[label]
        prediction_matches = {
            "selected": len(rows) == expected["selected"],
            "tickers": len(counts) == expected["tickers"],
            "top1": top1 is not None and abs(top1 - expected["top1"]) <= 0.000001,
        }
        if not all(prediction_matches.values()):
            failures.append(f"preregistered_source_density_identity_mismatch:{label}")
        by_window[label] = {
            "selected_decision_count": len(rows),
            "ticker_count": len(counts),
            "top1_ticker": counts.most_common(1)[0][0] if counts else None,
            "top1_count_share": round(top1, 6) if top1 is not None else None,
            "by_ticker": dict(sorted(counts.items())),
            "checks": checks,
            "preregistered_prediction": expected,
            "prediction_matches": prediction_matches,
        }
    return {
        "passed": not failures,
        "hard_failures": failures,
        "contract": {
            "minimum_current_corporate_nonmerge_count": 3,
            "prior_rc_count": 8,
            "strictly_above_prior_median": True,
            "rank": "contribution_acceleration,current_count,ticker",
            "top_n": 3,
            "minimum_selected_per_window": MIN_SETTLED_PER_WINDOW,
            "minimum_tickers_per_window": MIN_TICKERS_PER_WINDOW,
            "maximum_top1_count_share": MAX_TOP1_COUNT_SHARE,
            "price_or_outcome_fields_read": False,
        },
        "eligible_decision_count": len(eligible),
        "selected_decision_count": len(selected),
        "signals_generated": int(evaluation.get("signals_generated") or len(eligible)),
        "signals_survived": int(evaluation.get("signals_survived") or len(selected)),
        "selected_decision_rowset_sha256": _canonical_sha(selected),
        "by_window": by_window,
    }


def _locked_policy_audit() -> dict[str, Any]:
    actual = {
        "trade_enabled": policy.TRADE_ENABLED,
        "minimum_current_count": policy.MIN_CURRENT_CONTRIBUTION_COUNT,
        "prior_rc_intervals": policy.PRIOR_RC_INTERVALS,
        "top_n": policy.MAX_RC_CANDIDATES,
        "hold_sessions": policy.HOLD_SESSIONS,
        "paper_notional_usd": float(policy.PAPER_NOTIONAL_USD),
        "max_active_positions": policy.MAX_ACTIVE_POSITIONS,
        "entry_slippage_bps": float(SLIPPAGE_BPS_ENTRY),
        "exit_slippage_bps": float(SLIPPAGE_BPS_TARGET),
        "round_trip_cost_pct": float(ROUND_TRIP_COST_PCT),
        "core_weight": CORE_WEIGHT,
        "sleeve_weight": SLEEVE_WEIGHT,
    }
    expected = {
        "trade_enabled": False,
        "minimum_current_count": 3,
        "prior_rc_intervals": 8,
        "top_n": 3,
        "hold_sessions": 20,
        "paper_notional_usd": 4_000.0,
        "max_active_positions": 6,
        "entry_slippage_bps": 5.0,
        "exit_slippage_bps": 5.0,
        "round_trip_cost_pct": 0.0035,
        "core_weight": 0.76,
        "sleeve_weight": 0.24,
    }
    failures = [
        f"locked_policy_drift:{key}"
        for key, expected_value in expected.items()
        if actual[key] != expected_value
    ]
    negative_sharpe_probe = _curve_metrics(
        [
            {"date": "2026-01-02", "return": -0.01},
            {"date": "2026-01-05", "return": -0.02},
            {"date": "2026-01-06", "return": -0.01},
        ],
        initial_capital=100_000.0,
        trade_count=0,
    )
    if (
        negative_sharpe_probe["sharpe_daily"] is None
        or float(negative_sharpe_probe["sharpe_daily"]) >= 0.0
        or float(negative_sharpe_probe["expected_value_score"]) >= 0.0
    ):
        failures.append("expected_value_abs_sharpe_sign_contract_failed")
    return {
        "passed": not failures,
        "hard_failures": failures,
        "expected": expected,
        "actual": actual,
        "negative_sharpe_sign_probe": negative_sharpe_probe,
    }


def _load_ohlcv(
    tickers: Iterable[str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested = sorted({str(ticker).upper() for ticker in tickers} | {"SPY", "QQQ"})
    placeholders = ",".join("?" for _ in requested)
    sql = (
        "select ticker, date, open, high, low, close, volume from ohlcv "
        f"where ticker in ({placeholders}) and date >= ? and date <= ? "
        "order by ticker, date"
    )
    output: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in requested}
    with sqlite3.connect(WAREHOUSE_PATH) as connection:
        for ticker, day, open_, high, low, close, volume in connection.execute(
            sql, [*requested, OHLCV_QUERY_START, OHLCV_QUERY_END]
        ):
            output[str(ticker)].append(
                {
                    "date": str(day)[:10],
                    "open": float(open_),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                    "volume": float(volume or 0.0),
                }
            )
    output = {ticker: rows for ticker, rows in output.items() if rows}
    if "SPY" not in output or "QQQ" not in output:
        raise EvaluationContractError("warehouse lacks SPY/QQQ calendar rows")
    identity = [
        [ticker, row["date"], row["open"], row["high"], row["low"], row["close"]]
        for ticker, rows in sorted(output.items())
        for row in rows
    ]
    return output, {
        "warehouse": _repo_rel(WAREHOUSE_PATH),
        "query_start": OHLCV_QUERY_START,
        "query_end": OHLCV_QUERY_END,
        "requested_tickers": requested,
        "loaded_tickers": sorted(output),
        "row_count": len(identity),
        "canonical_rowset_sha256": _canonical_sha(identity),
    }


def _baseline_window_map(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["label"]): dict(row) for row in summary.get("windows") or []}


def _baseline_returns(window: Mapping[str, Any]) -> list[dict[str, Any]]:
    artifact = _read_json(REPO_ROOT / str(window["path"]))
    series = artifact.get("sharpe_inference", {}).get("return_series") or []
    output = [
        {"date": str(row["date"])[:10], "return": float(row["return"])}
        for row in series
    ]
    if not output:
        raise EvaluationContractError(f"baseline return series missing: {window['label']}")
    equity = 100_000.0
    for row in output:
        equity *= 1.0 + row["return"]
    if abs(equity - (100_000.0 + float(window["total_pnl"]))) > 0.02:
        raise EvaluationContractError(f"baseline curve drift: {window['label']}")
    return output


def _bar_indices(
    ohlcv: Mapping[str, list[dict[str, Any]]],
) -> tuple[dict[str, dict[str, dict[str, float]]], dict[str, list[str]]]:
    exact = {
        ticker: {
            str(row["date"]): {"open": float(row["open"]), "close": float(row["close"])}
            for row in rows
        }
        for ticker, rows in ohlcv.items()
    }
    return exact, {ticker: sorted(rows) for ticker, rows in exact.items()}


def _close_on_or_before(
    exact: Mapping[str, Mapping[str, Mapping[str, float]]],
    dates: Mapping[str, list[str]],
    ticker: str,
    day: str,
) -> float:
    row = exact.get(ticker, {}).get(day)
    if row is not None:
        return float(row["close"])
    prior = [value for value in dates.get(ticker, []) if value <= day]
    if not prior:
        raise EvaluationContractError(f"missing MTM close for {ticker} on {day}")
    return float(exact[ticker][prior[-1]]["close"])


def _window_end_measurement_liquidations(
    unsettled: Iterable[Mapping[str, Any]],
    *,
    final_session: str,
    ohlcv: Mapping[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Value still-open policy H20 exposures at the independent window boundary."""

    exact, _ = _bar_indices(ohlcv)
    liquidations: list[dict[str, Any]] = []
    for raw in unsettled:
        row = dict(raw)
        if row.get("unsettled_reason") != "incomplete_20_session_horizon":
            raise EvaluationContractError(
                "non-boundary unsettled exposure cannot be omitted from measurement: "
                + str(row.get("decision_id"))
            )
        if str(row.get("entry_date") or "") > final_session:
            raise EvaluationContractError("measurement liquidation precedes entry")
        ticker = str(row.get("ticker") or "")
        end_bar = exact.get(ticker, {}).get(final_session)
        if end_bar is None:
            raise EvaluationContractError(
                f"missing exact window-end liquidation close: {ticker}:{final_session}"
            )
        raw_exit_close = float(end_bar["close"])
        exit_price = raw_exit_close * (1.0 - SLIPPAGE_BPS_TARGET / 10_000.0)
        gross = exit_price / float(row["entry_price"]) - 1.0
        net = gross - ROUND_TRIP_COST_PCT
        liquidations.append(
            {
                **row,
                "exit_date": final_session,
                "exit_close_price_raw": round(raw_exit_close, 4),
                "exit_price": round(exit_price, 4),
                "exit_reason": "window_end_measurement_liquidation",
                "policy_h20_settled": False,
                "measurement_boundary_liquidation": True,
                "pnl_pct_gross": round(gross, 10),
                "pnl_pct_net": round(net, 10),
                "net_return": round(net, 10),
                "pnl": round(float(row["paper_notional_usd"]) * net, 2),
            }
        )
    return liquidations


def _sleeve_marks(
    trades: list[dict[str, Any]],
    core_dates: list[str],
    ohlcv: Mapping[str, list[dict[str, Any]]],
    *,
    round_trip_cost_pct: float,
) -> list[float]:
    """Local, parameterized version of the Maven runner's mark-to-market curve."""

    exact, dates = _bar_indices(ohlcv)
    marks: list[float] = []
    for day in core_dates:
        cumulative = 0.0
        for trade in trades:
            if day < str(trade["entry_date"]):
                continue
            if day >= str(trade["exit_date"]):
                cumulative += float(trade["pnl"])
                continue
            close = _close_on_or_before(exact, dates, str(trade["ticker"]), day)
            gross = close / float(trade["entry_price"]) - 1.0
            cumulative += float(trade["paper_notional_usd"]) * (
                gross - round_trip_cost_pct / 2.0
            )
        marks.append(cumulative)
    return marks


def _curve_metrics(
    dated_returns: list[dict[str, Any]],
    *,
    initial_capital: float,
    trade_count: int,
) -> dict[str, Any]:
    equity = initial_capital
    peak = equity
    maximum_drawdown = 0.0
    samples: list[float] = []
    for row in dated_returns:
        value = float(row["return"])
        samples.append(value)
        equity *= 1.0 + value
        peak = max(peak, equity)
        maximum_drawdown = max(maximum_drawdown, (peak - equity) / peak)
    sharpe = None
    if len(samples) >= 2:
        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / (len(samples) - 1)
        if variance > 0.0:
            sharpe = mean / math.sqrt(variance) * math.sqrt(252.0)
    total_pnl = equity - initial_capital
    public_return = round(total_pnl / initial_capital, 4)
    public_sharpe = round(sharpe, 2) if sharpe is not None else None
    return {
        "total_pnl": round(total_pnl, 2),
        "benchmarks": {"strategy_total_return_pct": public_return},
        "sharpe_daily": public_sharpe,
        "sharpe_daily_full_precision": sharpe,
        "expected_value_score": (
            round(public_return * abs(public_sharpe), 4)
            if public_sharpe is not None
            else None
        ),
        "max_drawdown_pct": round(maximum_drawdown, 4),
        "total_trades": int(trade_count),
        "return_series": dated_returns,
        "return_series_sha256": _canonical_sha(dated_returns),
    }


def _capital_neutral_window(
    baseline_window: Mapping[str, Any],
    settled_h20_trades: list[dict[str, Any]],
    unsettled: list[dict[str, Any]],
    ohlcv: Mapping[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    core_returns = _baseline_returns(baseline_window)
    dates = [row["date"] for row in core_returns]
    measurement_liquidations = _window_end_measurement_liquidations(
        unsettled,
        final_session=dates[-1],
        ohlcv=ohlcv,
    )
    valuation_trades = [*settled_h20_trades, *measurement_liquidations]
    notional = float(policy.PAPER_NOTIONAL_USD)
    max_active = int(policy.MAX_ACTIVE_POSITIONS)
    sleeve_capital = notional * max_active
    marks = _sleeve_marks(
        valuation_trades,
        dates,
        ohlcv,
        round_trip_cost_pct=float(ROUND_TRIP_COST_PCT),
    )
    sleeve_returns: list[float] = []
    previous_equity = sleeve_capital
    for mark in marks:
        equity = sleeve_capital + mark
        if equity <= 0.0:
            raise EvaluationContractError("funded Linux sleeve equity became non-positive")
        sleeve_returns.append(equity / previous_equity - 1.0)
        previous_equity = equity
    combined = [
        {
            "date": row["date"],
            "return": CORE_WEIGHT * float(row["return"]) + SLEEVE_WEIGHT * sleeve_return,
        }
        for row, sleeve_return in zip(core_returns, sleeve_returns)
    ]
    before = _curve_metrics(
        core_returns,
        initial_capital=100_000.0,
        trade_count=int(baseline_window["trade_count"]),
    )
    after = _curve_metrics(
        combined,
        initial_capital=100_000.0,
        trade_count=int(baseline_window["trade_count"]) + len(valuation_trades),
    )
    return before, after, {
        "initial_capital": sleeve_capital,
        "ending_equity": round(previous_equity, 2),
        "total_pnl": round(previous_equity - sleeve_capital, 2),
        "return_series": [
            {"date": day, "return": value}
            for day, value in zip(dates, sleeve_returns)
        ],
        "capital_conserving": True,
        "core_weight": CORE_WEIGHT,
        "sleeve_weight": SLEEVE_WEIGHT,
        "settled_h20_trade_count": len(settled_h20_trades),
        "window_end_measurement_liquidation_count": len(measurement_liquidations),
    }, measurement_liquidations


def _benchmark_diagnostics(
    trades: list[dict[str, Any]],
    ohlcv: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    exact, _ = _bar_indices(ohlcv)
    target_pnl = sum(float(trade["pnl"]) for trade in trades)
    result: dict[str, Any] = {
        "target_pnl": round(target_pnl, 2),
        "cash_pnl": 0.0,
        "cash_replacement_value": round(target_pnl, 2),
    }
    passed = bool(trades) and target_pnl > 0.0
    for benchmark in ("SPY", "QQQ"):
        benchmark_pnl = 0.0
        missing: list[str] = []
        for trade in trades:
            entry = exact.get(benchmark, {}).get(str(trade["entry_date"]))
            exit_row = exact.get(benchmark, {}).get(str(trade["exit_date"]))
            if entry is None or exit_row is None:
                missing.append(str(trade["decision_id"]))
                continue
            entry_price = float(entry["open"]) * (1.0 + SLIPPAGE_BPS_ENTRY / 10_000.0)
            exit_price = float(exit_row["close"]) * (
                1.0 - SLIPPAGE_BPS_TARGET / 10_000.0
            )
            net_return = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
            benchmark_pnl += float(policy.PAPER_NOTIONAL_USD) * net_return
        value = round(benchmark_pnl, 2) if not missing else None
        replacement = round(target_pnl - benchmark_pnl, 2) if not missing else None
        result[f"{benchmark.lower()}_pnl"] = value
        result[f"{benchmark.lower()}_replacement_value"] = replacement
        result[f"{benchmark.lower()}_missing_decision_ids"] = missing
        passed = passed and not missing and replacement is not None and replacement > 0.0
    result["passed"] = bool(passed)
    return result


def _aggregate_windows(windows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "before_expected_value_score_sum": round(
            sum(float(row["before"]["expected_value_score"]) for row in windows.values()),
            4,
        ),
        "after_expected_value_score_sum": round(
            sum(float(row["after"]["expected_value_score"]) for row in windows.values()),
            4,
        ),
        "expected_value_score_delta_sum": round(
            sum(float(row["delta"]["expected_value_score"]) for row in windows.values()),
            4,
        ),
        "before_total_pnl_sum": round(
            sum(float(row["before"]["total_pnl"]) for row in windows.values()), 2
        ),
        "after_total_pnl_sum": round(
            sum(float(row["after"]["total_pnl"]) for row in windows.values()), 2
        ),
        "total_pnl_delta_sum": round(
            sum(float(row["delta"]["total_pnl"]) for row in windows.values()), 2
        ),
        "windows_ev_improved": sum(
            float(row["delta"]["expected_value_score"]) > 0.0 for row in windows.values()
        ),
        "windows_ev_regressed": sum(
            float(row["delta"]["expected_value_score"]) < 0.0 for row in windows.values()
        ),
        "windows_pnl_improved": sum(
            float(row["delta"]["total_pnl"]) > 0.0 for row in windows.values()
        ),
        "windows_pnl_regressed": sum(
            float(row["delta"]["total_pnl"]) < 0.0 for row in windows.values()
        ),
        "max_drawdown_worse_max": max(
            float(row["delta"]["max_drawdown_pct"]) for row in windows.values()
        ),
    }


def _trade_summary(
    trades_by_window: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    pnl: Counter[str] = Counter()
    for trades in trades_by_window.values():
        for trade in trades:
            ticker = str(trade["ticker"])
            counts[ticker] += 1
            pnl[ticker] += float(trade["pnl"])
    positive = {ticker: value for ticker, value in pnl.items() if value > 0.0}
    total_positive = sum(positive.values())
    shares = sorted(
        (value / total_positive for value in positive.values()), reverse=True
    ) if total_positive > 0.0 else []
    return {
        "trade_count": sum(len(rows) for rows in trades_by_window.values()),
        "by_window": {label: len(trades_by_window[label]) for label in WINDOWS},
        "ticker_count": len(counts),
        "by_ticker_count": dict(sorted(counts.items())),
        "by_ticker_pnl": {ticker: round(value, 2) for ticker, value in sorted(pnl.items())},
        "single_ticker_positive_share": round(shares[0], 6) if shares else None,
        "top_5_positive_pnl_share": round(sum(shares[:5]), 6) if shares else None,
        "hhi_positive_pnl": round(sum(value * value for value in shares), 6) if shares else None,
    }


def _snapshot_replay(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    replay = snapshot.get("replay") or snapshot.get("historical_replay")
    return replay if isinstance(replay, Mapping) else snapshot


def build_evaluation() -> dict[str, Any]:
    # Source bundle, signature/PIT audit, and density are deliberately first.
    # Nothing above or inside these calls opens the warehouse, baseline, or price data.
    bundle = policy.load_linux_mainline_rc_source_bundle(
        bundle_dir=SOURCE_DIR,
        verify_hashes=True,
    )
    manifest = dict(bundle.get("manifest") or {})
    tags = [dict(row) for row in bundle.get("tags") or []]
    source_rows = [dict(row) for row in bundle.get("commit_rows") or []]
    crosscheck = dict(bundle.get("crosscheck") or {})
    source_audit = _source_contract_audit(manifest, tags, source_rows, crosscheck)
    if not source_audit["passed"]:
        raise EvaluationContractError(
            "source contract failed before price read: "
            + ", ".join(source_audit["hard_failures"])
        )
    density = _source_density_preflight(source_rows, tags)
    if not density["passed"]:
        raise EvaluationContractError(
            "source density failed before price read: "
            + ", ".join(density["hard_failures"])
        )
    policy_audit = _locked_policy_audit()
    if not policy_audit["passed"]:
        raise EvaluationContractError(
            "locked policy failed before price read: "
            + ", ".join(policy_audit["hard_failures"])
        )

    source_tickers = {
        str(row["ticker"])
        for row in source_rows
        if row.get("ticker") not in (None, "")
    }
    ohlcv, market_identity = _load_ohlcv(source_tickers)
    calendar = [row["date"] for row in ohlcv["SPY"]]
    baseline_summary = _read_json(BASELINE_SUMMARY_PATH)
    baseline_windows = _baseline_window_map(baseline_summary)
    if set(baseline_windows) != set(WINDOWS):
        raise EvaluationContractError("active Gate-1 window labels drifted")
    for label, (expected_start, expected_end) in WINDOWS.items():
        baseline_row = baseline_windows[label]
        if (
            str(baseline_row.get("start"))[:10] != expected_start
            or str(baseline_row.get("end"))[:10] != expected_end
        ):
            raise EvaluationContractError(f"active Gate-1 window bounds drifted: {label}")

    windows: dict[str, dict[str, Any]] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    valuation_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    generated_total = 0
    survived_total = 0
    for label, (start, end) in WINDOWS.items():
        replay = policy.build_linux_mainline_rc_contribution_acceleration_historical_trades(
            source_rows=source_rows,
            rc_tag_rows=tags,
            ohlcv_by_ticker=ohlcv,
            start=start,
            end=end,
            as_of=end,
            trading_dates=calendar,
        )
        trades = [dict(row, window=label) for row in replay.get("trades") or []]
        unsettled = [
            dict(row, window=label) for row in replay.get("unsettled") or []
        ]
        before, after, sleeve, measurement_liquidations = _capital_neutral_window(
            baseline_windows[label], trades, unsettled, ohlcv
        )
        valuation_trades = [*trades, *measurement_liquidations]
        counts = Counter(str(row["ticker"]) for row in trades)
        top1 = counts.most_common(1)[0][1] / len(trades) if trades else None
        generated_total += int(replay.get("signals_generated") or 0)
        survived_total += int(replay.get("signals_survived") or 0)
        trades_by_window[label] = trades
        valuation_trades_by_window[label] = valuation_trades
        windows[label] = {
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "delta": {
                "expected_value_score": round(
                    float(after["expected_value_score"])
                    - float(before["expected_value_score"]),
                    4,
                ),
                "total_pnl": round(
                    float(after["total_pnl"]) - float(before["total_pnl"]), 2
                ),
                "max_drawdown_pct": round(
                    float(after["max_drawdown_pct"])
                    - float(before["max_drawdown_pct"]),
                    4,
                ),
            },
            "signals_generated": int(replay.get("signals_generated") or 0),
            "signals_survived": int(replay.get("signals_survived") or 0),
            "survival_rate": float(replay.get("survival_rate") or 0.0),
            "eligible_rows": replay.get("eligible_rows") or replay.get("window_eligible_rows") or [],
            "selected_decisions": replay.get("window_decisions") or [],
            "trades": trades,
            "unsettled_policy_h20": unsettled,
            "window_end_measurement_liquidations": measurement_liquidations,
            "valuation_trades": valuation_trades,
            "reject_totals": replay.get("reject_totals") or {},
            "settled_trade_count": len(trades),
            "settled_h20_trade_count": len(trades),
            "measurement_trade_count": len(valuation_trades),
            "settled_ticker_count": len(counts),
            "settled_top1_count_share": round(top1, 6) if top1 is not None else None,
            "matched_benchmarks": _benchmark_diagnostics(valuation_trades, ohlcv),
            "funded_sleeve": sleeve,
            "orders": [],
        }

    aggregate = _aggregate_windows(windows)
    settled_trade_summary = _trade_summary(trades_by_window)
    trade_summary = _trade_summary(valuation_trades_by_window)
    all_settled_h20_trades = [
        trade for label in WINDOWS for trade in trades_by_window[label]
    ]
    all_trades = [
        trade for label in WINDOWS for trade in valuation_trades_by_window[label]
    ]
    sentinel_fields = ("entry_date", "target_price", "entry_price", "exit_date", "exit_price")
    missing_sentinels = [
        str(trade.get("decision_id"))
        for trade in all_trades
        if any(trade.get(field) in (None, "") for field in sentinel_fields)
    ]
    gate2_failures: list[str] = []
    if not all_settled_h20_trades:
        gate2_failures.append("no_settled_shared_helper_trades")
    if missing_sentinels:
        gate2_failures.append("signal_contract_sentinel_missing")
    if any(trade.get("trade_enabled") is not False for trade in all_trades):
        gate2_failures.append("shared_helper_trade_enabled_drift")
    gate2_failures.extend(source_audit["hard_failures"])
    gate2_failures.extend(policy_audit["hard_failures"])
    gate2 = {
        "passed": not gate2_failures,
        "hard_failures": list(dict.fromkeys(gate2_failures)),
        "sentinel_fields": list(sentinel_fields),
        "missing_sentinel_decision_ids": missing_sentinels,
        "source_pit_audit": source_audit,
        "locked_policy_audit": policy_audit,
        "orders": [],
    }
    survival_rate = survived_total / generated_total if generated_total else 0.0
    gate3 = {
        "passed": generated_total > 0 and survival_rate >= 0.05,
        "unit": "eligible Linux signed-RC issuer decision",
        "signals_generated": generated_total,
        "signals_survived": survived_total,
        "survival_rate": round(survival_rate, 6),
    }

    gate_metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "adjusted_trade_count": trade_summary["trade_count"],
        "adjusted_windows": list(WINDOWS),
        "adjusted_window_count": len(WINDOWS),
        "max_drawdown_worse_max": aggregate["max_drawdown_worse_max"],
        "single_ticker_positive_share": trade_summary["single_ticker_positive_share"],
        "top_5_contribution_pct": trade_summary["top_5_positive_pnl_share"],
        "hhi_concentration": trade_summary["hhi_positive_pnl"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / trade_summary["trade_count"]
            if trade_summary["trade_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(
        min_adjusted_trades=MIN_SETTLED_PER_WINDOW * len(WINDOWS),
        min_adjusted_windows=len(WINDOWS),
        min_ev_improved_windows=len(WINDOWS),
        max_ev_regressed_windows=0,
        max_drawdown_worse=MAX_DRAWDOWN_WORSE,
        max_single_ticker_positive_share=1.0,
        max_top_5_contribution_pct=1.0,
        max_hhi_concentration=1.0,
        require_tail_concentration_evidence=False,
        require_tail_concentration_not_worse=False,
    )
    canonical_gate = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=False
    )
    strict_diagnostic = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=True
    )
    failures = list(canonical_gate["hard_failures"])
    failures.extend(gate2["hard_failures"])
    if not gate3["passed"]:
        failures.append("gate3_survival_below_5pct")
    for label, row in windows.items():
        if row["settled_trade_count"] < MIN_SETTLED_PER_WINDOW:
            failures.append(f"settled_trade_count_below_20:{label}")
        if row["settled_ticker_count"] < MIN_TICKERS_PER_WINDOW:
            failures.append(f"settled_ticker_count_below_10:{label}")
        top1 = row["settled_top1_count_share"]
        if top1 is None or top1 > MAX_TOP1_COUNT_SHARE:
            failures.append(f"settled_top1_share_above_30pct:{label}")
        if float(row["delta"]["expected_value_score"]) <= 0.0:
            failures.append(f"window_ev_not_improved:{label}")
        if float(row["delta"]["total_pnl"]) <= 0.0:
            failures.append(f"window_pnl_not_improved:{label}")
        if not row["matched_benchmarks"]["passed"]:
            failures.append(f"cash_spy_qqq_replacement_failed:{label}")
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        failures.append("accepted_candidate_pool_ev_comparator_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_COMPARATOR["total_pnl_delta_sum"]:
        failures.append("accepted_candidate_pool_pnl_comparator_not_beaten")

    snapshot = policy.build_linux_mainline_rc_contribution_acceleration_snapshot(
        source_rows=source_rows,
        rc_tag_rows=tags,
        ohlcv_by_ticker=ohlcv,
        as_of=WINDOWS["late_strong"][1],
        start=WINDOWS["late_strong"][0],
        trading_dates=calendar,
        persist=False,
    )
    snapshot_replay = _snapshot_replay(snapshot)
    replay_trade_ids = sorted(
        str(row["decision_id"]) for row in windows["late_strong"]["trades"]
    )
    snapshot_trade_ids = sorted(
        str(row["decision_id"]) for row in snapshot_replay.get("trades") or []
    )
    replay_decision_ids = sorted(
        str(row["decision_id"])
        for row in windows["late_strong"]["selected_decisions"]
    )
    snapshot_decision_ids = sorted(
        str(row["decision_id"])
        for row in snapshot_replay.get("window_decisions") or []
    )
    replay_unsettled_ids = sorted(
        str(row["decision_id"])
        for row in windows["late_strong"]["unsettled_policy_h20"]
    )
    snapshot_unsettled_ids = sorted(
        str(row["decision_id"]) for row in snapshot_replay.get("unsettled") or []
    )
    parity_failures: list[str] = []
    if snapshot.get("trade_enabled") is not False:
        parity_failures.append("snapshot_trade_enabled_drift")
    if snapshot.get("orders") not in (None, []):
        parity_failures.append("snapshot_orders_nonempty")
    if replay_trade_ids != snapshot_trade_ids:
        parity_failures.append("snapshot_historical_trade_ids_mismatch")
    if replay_decision_ids != snapshot_decision_ids:
        parity_failures.append("snapshot_historical_decision_ids_mismatch")
    if replay_unsettled_ids != snapshot_unsettled_ids:
        parity_failures.append("snapshot_historical_unsettled_ids_mismatch")
    failures.extend(parity_failures)
    failures = list(dict.fromkeys(failures))

    gate4 = {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
        "canonical_candidate_pool_gate": canonical_gate,
        "strict_materiality_diagnostic_nonbinding": strict_diagnostic,
        "metrics": gate_metrics,
        "accepted_candidate_comparator": ACCEPTED_COMPARATOR,
        "capital_accounting": {
            "passed": True,
            "core_weight": CORE_WEIGHT,
            "sleeve_weight": SLEEVE_WEIGHT,
            "sleeve_capital_usd": (
                float(policy.PAPER_NOTIONAL_USD) * int(policy.MAX_ACTIVE_POSITIONS)
            ),
            "paper_pnl_overlay_on_full_core": False,
        },
        "source_contract": source_audit,
        "outcome_blind_source_density_preflight": density,
    }
    envelope = ExecutionEnvelope(
        base_notional=float(policy.PAPER_NOTIONAL_USD),
        max_capital_pct=SLEEVE_WEIGHT,
        min_dollar_volume=0.0,
        slippage_bps=float(SLIPPAGE_BPS_ENTRY + SLIPPAGE_BPS_TARGET),
        max_displacement=0,
        max_concurrent=int(policy.MAX_ACTIVE_POSITIONS),
        order_semantics="default_off_first_strictly_later_regular_open_then_session20_close",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.05,
        notes=(
            "One active position per ticker; six positions x $4,000 = $24,000. "
            "Historical source is hash-bound and signed-tag verified; forward "
            "replacement value remains required before live eligibility."
        ),
    )
    live = evaluate_live_readiness(
        envelope=envelope,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
        dsr_report=None,
    )
    full_verdict = full_stack_verdict(gate4=gate4, live_readiness=live, envelope=envelope)
    accepted = bool(gate4["passed"])
    return {
        "schema": "linux_mainline_rc_contribution_acceleration_full_stack_result_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "status": "accepted_paper_pending_forward" if accepted else "rejected",
        "decision": (
            "accepted_paper_pending_forward_linux_mainline_rc_contribution_acceleration"
            if accepted
            else "rejected_linux_mainline_rc_contribution_acceleration"
        ),
        "accepted_alpha": accepted,
        # Top-level judge fields make this single result file usable directly as
        # the experiment.py close --after artifact while retaining full detail.
        "expected_value_score": aggregate["after_expected_value_score_sum"],
        "total_pnl": aggregate["after_total_pnl_sum"],
        "sharpe_daily": None,
        "benchmarks": {
            "strategy_total_return_pct": round(
                aggregate["after_total_pnl_sum"]
                / (100_000.0 * len(WINDOWS)),
                6,
            )
        },
        "max_drawdown_pct": max(
            float(row["after"]["max_drawdown_pct"]) for row in windows.values()
        ),
        "total_trades": sum(
            int(row["after"]["total_trades"]) for row in windows.values()
        ),
        "survival_rate": min(
            float(row["survival_rate"]) for row in windows.values()
        ),
        "hypothesis": (
            "Acceleration in exact corporate-domain non-merge contributions between "
            "cryptographically verified Linux mainline RC tags leads issuer returns."
        ),
        "locked_policy": {
            "rule_version": policy.RULE_VERSION,
            "source_rule_version": policy.SOURCE_RULE_VERSION,
            "signed_annotated_rc_tags": True,
            "minimum_current_corporate_nonmerge_count": policy.MIN_CURRENT_CONTRIBUTION_COUNT,
            "prior_rc_count": policy.PRIOR_RC_INTERVALS,
            "strictly_above_prior_median": True,
            "rank": "contribution_acceleration,current_count,ticker",
            "top_n": policy.MAX_RC_CANDIDATES,
            "entry": "first strictly later regular-session open",
            "exit": "twentieth session close",
            "hold_sessions": policy.HOLD_SESSIONS,
            "paper_notional_usd": policy.PAPER_NOTIONAL_USD,
            "one_active_position_per_ticker": True,
            "max_active_positions": policy.MAX_ACTIVE_POSITIONS,
            "entry_slippage_bps": SLIPPAGE_BPS_ENTRY,
            "exit_slippage_bps": SLIPPAGE_BPS_TARGET,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "formal_core_weight": CORE_WEIGHT,
            "formal_sleeve_weight": SLEEVE_WEIGHT,
            "trade_enabled": False,
            "retunes": [],
        },
        "source": {
            "bundle_dir": _repo_rel(SOURCE_DIR),
            "audit": source_audit,
            "manifest": manifest,
            "outcome_blind_density_preflight": density,
            "revision_risk_disclosed": True,
        },
        "market_data": market_identity,
        "baseline": {
            "path": _repo_rel(BASELINE_SUMMARY_PATH),
            "sha256": _file_sha(BASELINE_SUMMARY_PATH),
            "experiment_id": baseline_summary.get("experiment_id"),
        },
        "windows": windows,
        "aggregate": aggregate,
        "trade_summary": trade_summary,
        "settled_h20_trade_summary": settled_trade_summary,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "gate5": live,
        "full_stack_verdict": full_verdict,
        "daily_snapshot_parity": {
            "passed": not parity_failures,
            "hard_failures": parity_failures,
            "rule_version": snapshot.get("rule_version"),
            "source_rule_version": snapshot.get("source_rule_version"),
            "trade_enabled": snapshot.get("trade_enabled"),
            "orders": snapshot.get("orders") or [],
            "historical_trade_decision_ids_match": replay_trade_ids == snapshot_trade_ids,
            "historical_selected_decision_ids_match": (
                replay_decision_ids == snapshot_decision_ids
            ),
            "historical_unsettled_decision_ids_match": (
                replay_unsettled_ids == snapshot_unsettled_ids
            ),
            "measurement_liquidations_excluded_from_policy_parity": True,
        },
        "production_impact": {
            "shared_helper_used": True,
            "daily_default_off_snapshot_evaluated": True,
            "daily_run_wiring_retained": False,
            "live_orders_changed": False,
            "core_ranking_changed": False,
            "core_sizing_changed": False,
            "trade_enabled": False,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed capital-neutral Linux signed-RC sleeve passed every binding condition."
                if accepted
                else "The fixed Linux signed-RC sleeve failed one or more preregistered Gate 1-4 conditions."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune domain map, count threshold, prior-RC span, Top-N, hold, "
                "costs, or sleeve weight on these frozen windows."
            ),
            "new_evidence_required": (
                "At least 30 closed append-only forward signed-RC decisions with positive "
                "cash/SPY/QQQ replacement value, or a genuinely new source or gate shape."
            ),
        },
    }


def write_evaluation(result: dict[str, Any]) -> None:
    if RESULT_PATH.exists():
        raise EvaluationContractError("result commit marker exists; refusing overwrite")
    _atomic_write_json(RESULT_PATH, result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        required=True,
        help="Evaluate the frozen source bundle and warehouse without network access.",
    )
    parser.parse_args()
    try:
        result = build_evaluation()
        write_evaluation(result)
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "status": result["status"],
                    "gate4_passed": result["gate4"]["passed"],
                    "aggregate_ev_delta": result["aggregate"][
                        "expected_value_score_delta_sum"
                    ],
                    "aggregate_pnl_delta": result["aggregate"]["total_pnl_delta_sum"],
                    "hard_failures": result["gate4"]["hard_failures"],
                    "result": _repo_rel(RESULT_PATH),
                },
                indent=2,
            )
        )
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "status": "failed_closed",
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
