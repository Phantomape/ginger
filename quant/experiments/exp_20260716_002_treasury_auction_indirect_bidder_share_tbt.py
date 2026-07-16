"""exp-20260716-002: Treasury indirect-bidder-share TBT paper alpha.

The experiment consumes only the frozen official Treasury source and the
frozen adjusted market panel created by exp-20260715-007.  It merges the
official API participant-composition amounts into the canonical PIT identity
rows, evaluates a standalone fully funded $100k default-off paper account,
and constructs a complete aligned two-rule DSR panel.  No executable strategy
or core backtest file is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys
import tempfile
import zipfile
from collections import OrderedDict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


EXPERIMENT_ID = "exp-20260716-002"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for import_path in (REPO_ROOT, QUANT_DIR, SCRIPTS_DIR, EXPERIMENTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from deflated_sharpe import build_report as build_dsr_report  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
import exp_20260715_007_treasury_auction_weak_demand_tbt_full_stack as prior  # noqa: E402
from treasury_auction_indirect_bidder_tbt_paper_sleeve import (  # noqa: E402
    HOLD_SESSIONS,
    LOOKBACK_AUCTIONS,
    NOTIONAL_USD,
    ROUND_TRIP_COST_PCT,
    RULE_VERSION,
    TICKER,
    build_treasury_auction_indirect_bidder_tbt_snapshot,
    build_weak_indirect_bidder_events,
    replay_weak_indirect_bidder_tbt,
)


OWNER = "alpha-explore"
SLUG = "treasury_auction_indirect_bidder_share_tbt"
RUNNER = f"quant/experiments/exp_20260716_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

SOURCE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "treasury_auction_results"
CANONICAL_PATH = SOURCE_DIR / "canonical_records.json"
API_ROWS_PATH = SOURCE_DIR / "api_rows.json"
XML_ZIP_PATH = SOURCE_DIR / "result_xml.zip"
PDF_ZIP_PATH = SOURCE_DIR / "result_pdf_fallback.zip"
SOURCE_MANIFEST_PATH = SOURCE_DIR / "source_manifest.json"
PRIOR_PRICE_PANEL_PATH = (
    REPO_ROOT / "data" / "experiments" / "exp-20260715-007" / "price_panel.json"
)
CORE_BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
RESULT_PATH = OUT_DIR / f"exp_20260716_002_{SLUG}.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
DSR_PANEL_PATH = OUT_DIR / "deflated_sharpe_panel.json"
DSR_REPORT_PATH = OUT_DIR / "deflated_sharpe_report.json"
PAPER_SNAPSHOT_PATH = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "treasury_auction_indirect_bidder_tbt"
    / "latest_snapshot.json"
)
ARTIFACT_PATH = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
CARD_PATH = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
LOG_PATH = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
MANIFEST_PATH = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_PATH = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_PATH = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = OrderedDict(
    (
        ("old_thin", ("2024-10-02", "2025-04-22")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("late_strong", ("2025-10-23", "2026-04-21")),
    )
)
ALLOWED_ORIGINAL_TERMS = (
    "2-Year",
    "3-Year",
    "5-Year",
    "7-Year",
    "10-Year",
    "20-Year",
    "30-Year",
)
INITIAL_CAPITAL_USD = 100_000.0
MIN_TOTAL_TRADES = 30
MIN_WINDOW_TRADES = 10
MAX_DRAWDOWN_WORSE_THAN_CASH = 0.005
MIN_DSR_PROBABILITY = 0.95
MAX_TOP_TENOR_POSITIVE_SHARE = 0.35
MAX_TOP5_TRADE_POSITIVE_SHARE = 0.60
ACCEPTED_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score": 0.5286,
    "total_pnl": 10_432.91,
}
SELECTION_SCOPE = "treasury_auction_result_field_tbt_event_response_two_rule_panel_v1"

HYPOTHESIS = (
    "When a nominal Treasury auction's indirect-bidder accepted share is strictly "
    "below the median of the preceding 12 same-original-tenor auctions, weak "
    "real-money demand should raise term premium; buy TBT at the next session open "
    "and close at the fifth-session close in one default-off paper slot."
)
NEW_EVIDENCE_AXIS = (
    "The unsaturated official Treasury source gains a no-precedent participant-"
    "composition field: indirect_bidder_accepted / total_accepted.  Lookback, "
    "tenors, entry, hold, notional, costs and non-overlap remain fixed, and the "
    "experiment supplies a complete aligned bid-to-cover versus indirect-share panel."
)


class SourceContractError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
    )


def amount(value: Any, *, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        raise SourceContractError(f"invalid {field}: {value!r}") from None
    if not parsed.is_finite():
        raise SourceContractError(f"non-finite {field}: {value!r}")
    return parsed


def load_enriched_source() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge API amounts onto canonical PIT identities and cross-check XML."""

    canonical, manifest = prior.parse_frozen_source()
    api_payload = read_json(API_ROWS_PATH)
    api_rows = list(api_payload.get("data") or [])
    api_index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in api_rows:
        key = (str(row.get("auction_date") or "")[:10], str(row.get("cusip") or "").upper())
        if not all(key) or key in api_index:
            raise SourceContractError(f"duplicate/invalid API identity: {key}")
        api_index[key] = row
    if len(api_index) != len(canonical):
        raise SourceContractError(
            f"API/canonical row count mismatch: {len(api_index)} != {len(canonical)}"
        )

    format_by_xml = manifest.get("source_format_by_xml") or {}
    xml_crosschecks = 0
    pdf_fallbacks = 0
    enriched: list[dict[str, Any]] = []
    with zipfile.ZipFile(XML_ZIP_PATH) as xml_archive, zipfile.ZipFile(
        PDF_ZIP_PATH
    ) as pdf_archive:
        xml_members = set(xml_archive.namelist())
        pdf_members = set(pdf_archive.namelist())
        for row in canonical:
            key = (str(row["auction_date"]), str(row["cusip"]).upper())
            api = api_index.get(key)
            if api is None:
                raise SourceContractError(f"missing API participant row: {key}")
            filename = str(row.get("result_filename") or "")
            api_xml_filename = str(api.get("xml_filenm_comp_results") or "")
            api_pdf_filename = str(api.get("pdf_filenm_comp_results") or "")
            failed_xml_filename = str(row.get("failed_xml_filename") or "")
            if failed_xml_filename:
                if (
                    failed_xml_filename != api_xml_filename
                    or filename != api_pdf_filename
                ):
                    raise SourceContractError(f"API PDF fallback identity mismatch: {key}")
            elif filename != api_xml_filename:
                raise SourceContractError(f"API result filename mismatch: {key}")
            indirect = amount(api.get("indirect_bidder_accepted"), field="indirect_bidder_accepted")
            total = amount(api.get("total_accepted"), field="total_accepted")
            if indirect < 0 or total <= 0 or indirect > total:
                raise SourceContractError(f"invalid participant composition: {key}")

            source_format = (format_by_xml.get(api_xml_filename) or {}).get("format")
            if source_format == "xml":
                if api_xml_filename not in xml_members:
                    raise SourceContractError(f"missing frozen XML member: {api_xml_filename}")
                fields = prior.xml_field_map(xml_archive.read(api_xml_filename))
                xml_indirect = amount(
                    fields.get("IndirectBidderAccepted"), field="XML IndirectBidderAccepted"
                )
                xml_total = amount(fields.get("TotalAccepted"), field="XML TotalAccepted")
                if xml_indirect != indirect or xml_total != total:
                    raise SourceContractError(f"API/XML participant amount mismatch: {key}")
                xml_crosschecks += 1
            elif source_format == "pdf_fault_recovery":
                pdf_filename = str(
                    (format_by_xml.get(api_xml_filename) or {}).get("member") or ""
                )
                if pdf_filename not in pdf_members:
                    raise SourceContractError(f"missing frozen PDF member: {pdf_filename}")
                text = prior.pdf_text(pdf_archive.read(pdf_filename), filename=pdf_filename)
                indirect_match = re.search(
                    r"Indirect Bidder\s*8?\s*\$([0-9,]+)\s*\$([0-9,]+)",
                    text,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                total_match = re.search(
                    r"SOMA\s*\$[0-9,]+\s*\$[0-9,]+\s*"
                    r"Total\s*\$([0-9,]+)\s*\$([0-9,]+)",
                    text,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                if indirect_match is None or total_match is None:
                    raise SourceContractError(
                        f"participant amounts missing from frozen PDF: {pdf_filename}"
                    )
                pdf_indirect = amount(
                    indirect_match.group(2), field="PDF indirect bidder accepted"
                )
                pdf_total = amount(total_match.group(2), field="PDF total accepted"
                )
                if pdf_indirect != indirect or pdf_total != total:
                    raise SourceContractError(f"API/PDF participant amount mismatch: {key}")
                pdf_fallbacks += 1
            else:
                raise SourceContractError(f"unknown source format for {filename}: {source_format}")

            enriched.append(
                {
                    **row,
                    "indirect_bidder_accepted": float(indirect),
                    "total_accepted": float(total),
                    "participant_composition_source": "official_fiscal_data_api_archive",
                    "participant_xml_crosschecked": source_format == "xml",
                }
            )

    canonical_keys = {(str(row["auction_date"]), str(row["cusip"]).upper()) for row in canonical}
    if set(api_index) != canonical_keys:
        raise SourceContractError("API/canonical identity sets differ")
    expected_pdf = int(manifest.get("pdf_fallback_count") or 0)
    if xml_crosschecks + pdf_fallbacks != len(enriched) or pdf_fallbacks != expected_pdf:
        raise SourceContractError("participant composition provenance counts disagree")
    if {str(row["original_security_term"]) for row in enriched} != set(ALLOWED_ORIGINAL_TERMS):
        raise SourceContractError("unexpected nominal original-tenor universe")

    audit = {
        "canonical_row_count": len(canonical),
        "api_row_count": len(api_rows),
        "enriched_row_count": len(enriched),
        "field_complete_count": sum(
            row.get("indirect_bidder_accepted") is not None
            and row.get("total_accepted") is not None
            for row in enriched
        ),
        "xml_value_crosscheck_count": xml_crosschecks,
        "pdf_identity_fallback_count": pdf_fallbacks,
        "canonical_api_identity_exact": True,
        "official_api_archive_sha256": file_sha(API_ROWS_PATH),
        "canonical_sha256": file_sha(CANONICAL_PATH),
        "xml_zip_sha256": file_sha(XML_ZIP_PATH),
        "pdf_zip_sha256": file_sha(PDF_ZIP_PATH),
        "availability_contract_validated_by": "exp-20260715-007 parse_frozen_source",
    }
    return enriched, {**manifest, "participant_composition_audit": audit}


def load_price_panel() -> dict[str, Any]:
    panel = read_json(PRIOR_PRICE_PANEL_PATH)
    if file_sha(PRIOR_PRICE_PANEL_PATH) is None:
        raise SourceContractError("frozen price panel missing")
    if panel.get("schema") != "treasury_auction_tbt_price_panel_v1":
        raise SourceContractError(f"unexpected price panel schema: {panel.get('schema')}")
    prior.validate_market_alignment(panel)
    return panel


def market_dates(panel: dict[str, Any], label: str, start: str, end: str) -> list[str]:
    dates = sorted(
        {
            str(row["date"])
            for row in panel["benchmarks"][label]["SPY"]
            if start <= str(row["date"]) <= end
        }
    )
    qqq_dates = sorted(
        {
            str(row["date"])
            for row in panel["benchmarks"][label]["QQQ"]
            if start <= str(row["date"]) <= end
        }
    )
    if not dates or dates != qqq_dates:
        raise SourceContractError(f"canonical date vector mismatch: {label}")
    return dates


def return_series_sha(rows: list[dict[str, Any]]) -> str:
    normalized = [{"date": str(row["date"]), "return": float(row["return"])} for row in rows]
    return sha256_bytes(
        canonical_bytes({"schema": "dated_periodic_return_series_v1", "rows": normalized})
    )


def account_metrics(
    trades: Iterable[dict[str, Any]],
    dates: list[str],
    tbt_rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Mark one fully funded $100k account; never add PnL to the core."""

    trade_rows = list(trades)
    bar_index = {str(row["date"]): row for row in tbt_rows}
    curve: list[dict[str, Any]] = []
    for day in dates:
        mark = 0.0
        for trade in trade_rows:
            entry_date = str(trade["entry_date"])
            exit_date = str(trade["exit_date"])
            if day < entry_date:
                continue
            if day >= exit_date:
                mark += float(trade["pnl"])
                continue
            bar = bar_index.get(day)
            if bar is None:
                raise SourceContractError(f"missing TBT close for standalone MTM: {day}")
            mark += NOTIONAL_USD * (
                float(bar["close"]) / float(trade["entry_price"])
                - 1.0
                - ROUND_TRIP_COST_PCT / 2.0
            )
        curve.append({"date": day, "equity": INITIAL_CAPITAL_USD + mark})

    previous = INITIAL_CAPITAL_USD
    peak = INITIAL_CAPITAL_USD
    drawdown = 0.0
    return_series: list[dict[str, Any]] = []
    for row in curve:
        equity = float(row["equity"])
        periodic = equity / previous - 1.0
        return_series.append({"date": row["date"], "return": periodic})
        previous = equity
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak)
    samples = [float(row["return"]) for row in return_series]
    sharpe_full = None
    if len(samples) >= 2:
        variance = statistics.variance(samples)
        if variance > 0:
            sharpe_full = statistics.fmean(samples) / math.sqrt(variance) * math.sqrt(252)
    pnl = curve[-1]["equity"] - INITIAL_CAPITAL_USD if curve else 0.0
    public_return = round(pnl / INITIAL_CAPITAL_USD, 4)
    public_sharpe = round(sharpe_full, 2) if sharpe_full is not None else None
    return {
        "account_type": "standalone_fully_funded_cash_account",
        "initial_capital_usd": INITIAL_CAPITAL_USD,
        "max_deployed_notional_usd": NOTIONAL_USD,
        "additive_to_core": False,
        "total_pnl": round(pnl, 2),
        "benchmarks": {"strategy_total_return_pct": public_return},
        "sharpe_daily": public_sharpe,
        "sharpe_daily_full_precision": sharpe_full,
        "expected_value_score": (
            round(public_return * public_sharpe, 4) if public_sharpe is not None else 0.0
        ),
        "max_drawdown_pct": round(drawdown, 4),
        "total_trades": len(trade_rows),
        "return_series": return_series,
        "return_series_sha256": return_series_sha(return_series),
    }


def cash_metrics(dates: list[str]) -> dict[str, Any]:
    rows = [{"date": day, "return": 0.0} for day in dates]
    return {
        "account_type": "standalone_cash_comparator",
        "initial_capital_usd": INITIAL_CAPITAL_USD,
        "max_deployed_notional_usd": 0.0,
        "additive_to_core": False,
        "total_pnl": 0.0,
        "benchmarks": {"strategy_total_return_pct": 0.0},
        "sharpe_daily": None,
        "sharpe_daily_full_precision": None,
        "expected_value_score": 0.0,
        "max_drawdown_pct": 0.0,
        "total_trades": 0,
        "return_series": rows,
        "return_series_sha256": return_series_sha(rows),
    }


def concat_series(metrics_by_window: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {"date": str(row["date"]), "return": float(row["return"])}
        for label in WINDOWS
        for row in metrics_by_window[label]["return_series"]
    ]
    dates = [row["date"] for row in rows]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SourceContractError("DSR date vector is not strictly increasing and unique")
    return rows


def build_dsr_panel(
    indirect_metrics: dict[str, dict[str, Any]],
    btc_metrics: dict[str, dict[str, Any]],
    source_manifest: dict[str, Any],
    price_panel: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    indirect_series = concat_series(indirect_metrics)
    btc_series = concat_series(btc_metrics)
    dates = [row["date"] for row in indirect_series]
    if dates != [row["date"] for row in btc_series]:
        raise SourceContractError("two-rule DSR panel is not date-aligned")
    common = {
        "attempted": True,
        "selection_scope": SELECTION_SCOPE,
        "window": {
            "segments": [
                {"label": label, "start": start, "end": end}
                for label, (start, end) in WINDOWS.items()
            ]
        },
        "frequency": "daily",
        "return_basis": "standalone_fully_funded_100000_usd_tbt_daily_mtm_post_cost",
        "risk_free_assumption": "zero",
        "protocol": {
            "id": "treasury_auction_two_official_fields_standalone_cash_v1",
            "lookback": LOOKBACK_AUCTIONS,
            "hold_sessions": HOLD_SESSIONS,
            "notional_usd": NOTIONAL_USD,
            "one_global_nonoverlap_slot": True,
        },
        "data": {
            "canonical_sha256": file_sha(CANONICAL_PATH),
            "api_rows_sha256": file_sha(API_ROWS_PATH),
            "source_manifest_sha256": file_sha(SOURCE_MANIFEST_PATH),
            "source_generated_at": source_manifest.get("generated_at"),
            "price_panel_sha256": file_sha(PRIOR_PRICE_PANEL_PATH),
            "tbt_raw_sha256": price_panel.get("tbt_raw_sha256"),
        },
        "cost": {"round_trip_cost_pct": ROUND_TRIP_COST_PCT},
    }

    def trial(config_id: str, config: dict[str, Any], series: list[dict[str, Any]], index: int) -> dict[str, Any]:
        return {
            "config_id": config_id,
            "config": config,
            **common,
            "return_series": series,
            "return_series_sha256": return_series_sha(series),
            "return_series_source": f"{repo_rel(DSR_PANEL_PATH)}#trials[{index}].return_series",
        }

    panel = {
        "selected_config_id": "treasury_indirect_bidder_share_tbt",
        "expected_attempt_count": 2,
        "selection_pool_complete": True,
        "expected_return_dates": dates,
        "periods_per_year": 252,
        "trials": [
            trial(
                "treasury_bid_to_cover_tbt",
                {
                    "decision_field": "bid_to_cover_ratio",
                    "rule": "strictly_below_prior12_same_original_tenor_median",
                    "rule_version": prior.RULE_VERSION,
                },
                btc_series,
                0,
            ),
            trial(
                "treasury_indirect_bidder_share_tbt",
                {
                    "decision_field": "indirect_bidder_accepted / total_accepted",
                    "rule": "strictly_below_prior12_same_original_tenor_median",
                    "rule_version": RULE_VERSION,
                },
                indirect_series,
                1,
            ),
        ],
    }
    report = build_dsr_report(panel)
    report["gate4_independence"] = True
    report["expected_attempt_count_policy"] = (
        "Complete two-member selection family: the only two actually evaluated "
        "official Treasury auction result fields under this fixed TBT response are "
        "bid-to-cover and indirect-bidder accepted share. The broader macro/rates "
        "attempts declared by exp-20260715-007 used different sources and response "
        "protocols, so they are outside this narrowly preregistered source-field scope."
    )
    return panel, report


def build_evaluation() -> dict[str, Any]:
    ticket = read_json(TICKET_PATH)
    prediction = dict(ticket.get("prediction") or {})
    core_sha_before = file_sha(CORE_BASELINE_PATH)
    core_baseline = read_json(CORE_BASELINE_PATH)
    source_rows, source_manifest = load_enriched_source()
    price_panel = load_price_panel()
    indirect_events = build_weak_indirect_bidder_events(source_rows)
    btc_events = prior.build_weak_auction_events(source_rows)
    if not indirect_events or not btc_events:
        raise SourceContractError("one of the preregistered auction rules produced zero events")

    benchmarks = prior.merged_fixed_benchmarks(price_panel)
    start = next(iter(WINDOWS.values()))[0]
    end = next(reversed(WINDOWS.values()))[1]
    indirect_global = replay_weak_indirect_bidder_tbt(
        indirect_events, price_panel["tbt"], benchmarks, start, end
    )
    btc_global = prior.replay_weak_auction_tbt(
        btc_events, price_panel["tbt"], benchmarks, start, end
    )

    windows: dict[str, dict[str, Any]] = {}
    indirect_metrics: dict[str, dict[str, Any]] = {}
    btc_metrics: dict[str, dict[str, Any]] = {}
    all_trades: list[dict[str, Any]] = []
    for label, (window_start, window_end) in WINDOWS.items():
        dates = market_dates(price_panel, label, window_start, window_end)
        replay = prior.partition_global_replay(
            indirect_global, start=window_start, end=window_end
        )
        btc_replay = prior.partition_global_replay(
            btc_global, start=window_start, end=window_end
        )
        trades = list(replay["trades"])
        all_trades.extend(trades)
        before = cash_metrics(dates)
        after = account_metrics(trades, dates, price_panel["tbt"])
        indirect_metrics[label] = after
        btc_metrics[label] = account_metrics(btc_replay["trades"], dates, price_panel["tbt"])
        delta = {
            "expected_value_score": round(
                float(after["expected_value_score"]) - float(before["expected_value_score"]), 4
            ),
            "total_pnl": round(float(after["total_pnl"]), 2),
            "max_drawdown_pct": round(float(after["max_drawdown_pct"]), 4),
            "total_trades": int(after["total_trades"]),
        }
        windows[label] = {
            "start": window_start,
            "end": window_end,
            "canonical_session_count": len(dates),
            "replay": replay,
            "trade_summary": prior.window_trade_summary(trades),
            "before": before,
            "after": after,
            "delta": delta,
            "dsr_reference_bid_to_cover": {
                "trade_count": len(btc_replay["trades"]),
                "metrics": btc_metrics[label],
            },
        }

    aggregate = {
        "before_expected_value_score_sum": 0.0,
        "after_expected_value_score_sum": round(
            sum(float(row["after"]["expected_value_score"]) for row in windows.values()), 4
        ),
        "expected_value_score_delta_sum": round(
            sum(float(row["delta"]["expected_value_score"]) for row in windows.values()), 4
        ),
        "before_total_pnl_sum": 0.0,
        "after_total_pnl_sum": round(
            sum(float(row["after"]["total_pnl"]) for row in windows.values()), 2
        ),
        "total_pnl_delta_sum": round(
            sum(float(row["delta"]["total_pnl"]) for row in windows.values()), 2
        ),
        "trade_count_sum": len(all_trades),
        "positive_ev_windows": sum(row["delta"]["expected_value_score"] > 0 for row in windows.values()),
        "positive_pnl_windows": sum(row["delta"]["total_pnl"] > 0 for row in windows.values()),
        "worst_max_drawdown_pct": max(
            float(row["after"]["max_drawdown_pct"]) for row in windows.values()
        ),
    }
    concentration = prior.concentration_summary(all_trades)
    dsr_panel, dsr_report = build_dsr_panel(
        indirect_metrics, btc_metrics, source_manifest, price_panel
    )
    dsr_gate = dsr_report.get("gate5_dsr_report") or {}
    dsr_probability = dsr_gate.get("dsr_probability")
    per_window_counts = {
        label: int(row["trade_summary"]["trade_count"]) for label, row in windows.items()
    }
    source_audit = source_manifest["participant_composition_audit"]
    core_aggregate = dict(core_baseline.get("aggregate") or {})
    gate1_identity = (
        core_baseline.get("experiment_id") == "exp-20260715-010"
        and core_baseline.get("baseline_role")
        == "active_cash_feasible_gate1_reference"
        and float(core_aggregate.get("expected_value_score_sum") or 0.0) == 6.2057
        and float(core_aggregate.get("total_pnl_sum") or 0.0) == 130_992.36
        and int(core_aggregate.get("trade_count_sum") or 0) == 49
    )
    event_weak_rows = [
        weak
        for event in indirect_events
        for weak in event.get("weak_auctions") or []
    ]
    gate2 = (
        source_audit["field_complete_count"] == source_audit["canonical_row_count"]
        and bool(all_trades)
        and bool(event_weak_rows)
        and all(
            weak.get("indirect_bidder_accepted") is not None
            and weak.get("total_accepted") is not None
            and weak.get("result_release_time_et")
            and weak.get("availability_semantics")
            == "explicit_result_publication_date_before_16_et"
            for weak in event_weak_rows
        )
        and all(
            trade.get("entry_date")
            and trade.get("target_price") is not None
            and trade.get("exit_date")
            for trade in all_trades
        )
    )
    core_sha_after = file_sha(CORE_BASELINE_PATH)
    checks = {
        "gate1_cash_feasible_baseline_identity": gate1_identity,
        "source_archive_complete": (
            source_audit["enriched_row_count"] == source_audit["canonical_row_count"] == 297
        ),
        "participant_fields_complete": source_audit["field_complete_count"] == 297,
        "gate2_dependencies_validated": gate2,
        "market_alignment_complete": True,
        "standalone_fully_funded_account": all(
            row["after"]["additive_to_core"] is False
            and row["after"]["initial_capital_usd"] == INITIAL_CAPITAL_USD
            and row["after"]["max_deployed_notional_usd"] <= INITIAL_CAPITAL_USD
            for row in windows.values()
        ),
        "core_baseline_sha256_before": core_sha_before,
        "core_baseline_sha256_after": core_sha_after,
        "core_cash_feasible_results_byte_unchanged": core_sha_before == core_sha_after,
        "total_trade_count": len(all_trades),
        "min_total_trades": MIN_TOTAL_TRADES,
        "per_window_trade_count": per_window_counts,
        "min_window_trades": MIN_WINDOW_TRADES,
        "sample_passed": len(all_trades) >= MIN_TOTAL_TRADES
        and all(count >= MIN_WINDOW_TRADES for count in per_window_counts.values()),
        "all_window_ev_nonnegative": all(
            row["after"]["expected_value_score"] >= 0 for row in windows.values()
        ),
        "all_window_pnl_nonnegative": all(
            row["after"]["total_pnl"] >= 0 for row in windows.values()
        ),
        "all_window_cash_replacement_positive": all(
            (row["trade_summary"]["mean_cash_replacement_usd"] or 0) > 0
            for row in windows.values()
        ),
        "all_window_qqq_replacement_positive": all(
            (row["trade_summary"]["mean_qqq_replacement_usd"] or 0) > 0
            for row in windows.values()
        ),
        "aggregate_ev_beats_accepted_comparator": (
            aggregate["after_expected_value_score_sum"]
            > ACCEPTED_COMPARATOR["expected_value_score"]
        ),
        "aggregate_pnl_beats_accepted_comparator": (
            aggregate["after_total_pnl_sum"] > ACCEPTED_COMPARATOR["total_pnl"]
        ),
        "drawdown_passed": (
            aggregate["worst_max_drawdown_pct"] <= MAX_DRAWDOWN_WORSE_THAN_CASH
        ),
        "dsr_panel_complete": dsr_gate.get("selection_pool_complete") is True,
        "dsr_probability": dsr_probability,
        "dsr_probability_min": MIN_DSR_PROBABILITY,
        "dsr_passed": dsr_probability is not None
        and float(dsr_probability) >= MIN_DSR_PROBABILITY,
        "top_tenor_positive_pnl_share": concentration["top_tenor_positive_pnl_share"],
        "top_tenor_concentration_passed": (
            concentration["top_tenor_positive_pnl_share"] is not None
            and float(concentration["top_tenor_positive_pnl_share"])
            <= MAX_TOP_TENOR_POSITIVE_SHARE
        ),
        "top5_trade_positive_pnl_share": concentration["top5_trade_positive_pnl_share"],
        "top5_trade_concentration_passed": (
            concentration["top5_trade_positive_pnl_share"] is not None
            and float(concentration["top5_trade_positive_pnl_share"])
            <= MAX_TOP5_TRADE_POSITIVE_SHARE
        ),
    }
    required = [
        "gate1_cash_feasible_baseline_identity",
        "source_archive_complete",
        "participant_fields_complete",
        "gate2_dependencies_validated",
        "market_alignment_complete",
        "standalone_fully_funded_account",
        "core_cash_feasible_results_byte_unchanged",
        "sample_passed",
        "all_window_ev_nonnegative",
        "all_window_pnl_nonnegative",
        "all_window_cash_replacement_positive",
        "all_window_qqq_replacement_positive",
        "aggregate_ev_beats_accepted_comparator",
        "aggregate_pnl_beats_accepted_comparator",
        "drawdown_passed",
        "dsr_panel_complete",
        "dsr_passed",
        "top_tenor_concentration_passed",
        "top5_trade_concentration_passed",
    ]
    failed = [name for name in required if checks.get(name) is not True]
    accepted = not failed
    positive_subthreshold = (
        not accepted
        and checks["sample_passed"]
        and checks["all_window_ev_nonnegative"]
        and checks["all_window_pnl_nonnegative"]
        and checks["all_window_cash_replacement_positive"]
        and checks["all_window_qqq_replacement_positive"]
        and aggregate["after_expected_value_score_sum"] > 0
        and aggregate["after_total_pnl_sum"] > 0
    )
    status = (
        "accepted_paper_pending_forward"
        if accepted
        else "observed_only_positive_lead"
        if positive_subthreshold
        else "rejected"
    )
    decision = (
        "accepted_default_off_indirect_bidder_tbt_pending_forward"
        if accepted
        else "observed_only_indirect_bidder_tbt_not_promoted"
        if positive_subthreshold
        else "rejected_indirect_bidder_tbt_edge_not_robust"
    )

    snapshot = build_treasury_auction_indirect_bidder_tbt_snapshot(
        as_of_date=date.today().isoformat(),
        events=indirect_events,
        price_rows={
            ticker: list(rows)
            for ticker, rows in (price_panel.get("daily_prices") or {}).items()
            if ticker in {"TBT", "SPY", "QQQ"}
        },
        previous_state=None,
    )
    snapshot.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "source_manifest_sha256": file_sha(SOURCE_MANIFEST_PATH),
            "participant_api_sha256": file_sha(API_ROWS_PATH),
            "trade_enabled": False,
        }
    )
    probability = float(prediction.get("success_probability") or 0.0)
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    failure_text = " ".join(failed)
    mode_keywords = {
        "next_open_absorbs_participant_mix": ("window", "pnl", "replacement"),
        "foreign_demand_share_not_directional": ("window", "pnl", "replacement"),
        "TBT_decay_and_cost": ("pnl", "replacement"),
        "window_regression": ("all_window",),
        "accepted_comparator_not_beaten": ("comparator",),
        "positive_pnl_concentration": ("concentration", "top_tenor", "top5"),
        "dsr_two_trial_failure": ("dsr",),
    }
    predicted_hit = [
        mode
        for mode in predicted_modes
        if any(key in failure_text for key in mode_keywords.get(mode, ()))
    ]
    why = (
        "The indirect-share event policy cleared every preregistered historical gate; "
        "it remains default-off pending prospectively closed decisions."
        if accepted
        else "The policy was positive in every window but missed at least one promotion "
        "threshold, so it is retained only as an observed lead."
        if positive_subthreshold
        else "The fixed participant-composition signal lost money in old_thin and "
        "mid_weak and had negative QQQ replacement value in all three windows. Its "
        "positive aggregate EV number is only the sign artifact of multiplying a "
        "negative return by a negative Sharpe in losing windows; the independent PnL "
        "and replacement-value gates correctly prevent promotion."
    )
    return {
        "schema": "treasury_auction_indirect_bidder_share_tbt_experiment_v1",
        "experiment_id": EXPERIMENT_ID,
        "owner": OWNER,
        "generated_at": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": accepted,
        "observed_only_lead": positive_subthreshold,
        "lane": "alpha_search",
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_full_stack",
        "mechanism_family": "treasury_auction_demand_microstructure",
        "trial_family": "treasury_auction_indirect_bidder_share_tbt_event_response",
        "trial_variant_id": "indirect_bidder_share_below_trailing12_median",
        "single_causal_variable": ticket.get("single_causal_variable"),
        "changed_variable": ticket.get("changed_variable"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments"),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "prediction": prediction,
        "parameters": {
            "rule_version": RULE_VERSION,
            "decision_field": "indirect_bidder_accepted / total_accepted",
            "lookback_auctions": LOOKBACK_AUCTIONS,
            "weak_rule": "share < median(prior_12_same_original_tenor_shares)",
            "original_security_terms": list(ALLOWED_ORIGINAL_TERMS),
            "ticker": TICKER,
            "entry": "strict_next_regular_session_adjusted_open",
            "exit": "fifth_session_adjusted_close",
            "notional_usd": NOTIONAL_USD,
            "initial_account_cash_usd": INITIAL_CAPITAL_USD,
            "max_concurrent_positions": 1,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "trade_enabled": False,
        },
        "source": source_manifest,
        "price_panel": {
            "path": repo_rel(PRIOR_PRICE_PANEL_PATH),
            "sha256": file_sha(PRIOR_PRICE_PANEL_PATH),
            "tbt_rows": len(price_panel["tbt"]),
            "tbt_raw_sha256": price_panel.get("tbt_raw_sha256"),
        },
        "gate1": {
            "cash_feasible_baseline_identity_validated": gate1_identity,
            "core_context_only": True,
            "core_baseline_path": repo_rel(CORE_BASELINE_PATH),
            "core_baseline_sha256": core_sha_before,
            "core_baseline_aggregate": core_baseline.get("aggregate"),
            "standalone_before": "100000_usd_cash",
            "additive_leverage_to_core": False,
        },
        "gate2": {
            "dependencies_validated": gate2,
            "fields_checked": [
                "auction_date",
                "result_publication_date",
                "result_release_time_et",
                "result_filename",
                "result_sha256",
                "indirect_bidder_accepted",
                "total_accepted",
                "entry_date",
                "target_price",
                "exit_date",
            ],
            "source_audit": source_audit,
            "trigger_source_row_count": len(event_weak_rows),
            "trigger_source_rows_with_participant_fields_and_pit_clock": sum(
                weak.get("indirect_bidder_accepted") is not None
                and weak.get("total_accepted") is not None
                and weak.get("result_release_time_et") is not None
                for weak in event_weak_rows
            ),
            "entry_date_present_count": sum(bool(row.get("entry_date")) for row in all_trades),
            "target_price_present_count": sum(row.get("target_price") is not None for row in all_trades),
        },
        "gate3": {
            "filter_added_to_core": False,
            "signals_generated": sum(int(row["replay"]["signals_generated"]) for row in windows.values()),
            "signals_survived": len(all_trades),
            "survival_rate": round(
                len(all_trades)
                / max(1, sum(int(row["replay"]["signals_generated"]) for row in windows.values())),
                6,
            ),
            "note": "Non-overlap is the fixed one-slot capital envelope, not a tuned filter.",
        },
        "gate4": {
            "checks": checks,
            "failed_reasons": failed,
            "accepted_comparator": ACCEPTED_COMPARATOR,
            "aggregate": aggregate,
            "concentration": concentration,
            "decision": decision,
        },
        "gate5": dsr_gate,
        "deflated_sharpe": dsr_report,
        "deflated_sharpe_panel": dsr_panel,
        "windows": windows,
        "aggregate": aggregate,
        "concentration": concentration,
        "daily_snapshot": snapshot,
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "core_backtest_changed": False,
            "run_py_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
            "accounting": "standalone_fully_funded_100000_usd_paper_account",
            "execution_envelope": {
                "instrument": "TBT",
                "max_notional_usd": NOTIONAL_USD,
                "max_concurrent_positions": 1,
                "cost_pct": ROUND_TRIP_COST_PCT,
                "entry": "strict next market-session open",
                "exit": "fifth market-session close",
                "kill_switch": "missing source/hash/timing/participant/adjusted-price field emits no candidate",
                "orders": "default-off snapshot only",
            },
        },
        "calibration": {
            "predicted_success_probability": probability,
            "actual_success": accepted,
            "brier_score": round((probability - float(accepted)) ** 2, 6),
            "predicted_failure_modes": predicted_modes,
            "predicted_failure_modes_hit": predicted_hit,
            "failed_reasons": failed,
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "realized_failure_mode": ",".join(failed) if failed else "none",
            "forbidden_near_neighbor_retry": (
                "Do not retune indirect-share threshold, lookback, tenor subset, "
                "entry, hold, TBT proxy, cost, overlap, response shape or notional on "
                "these frozen auction rows."
            ),
            "new_evidence_required": (
                "A genuinely new auction microstructure source/gate or materially more "
                "prospectively closed unchanged-policy forward decisions."
            ),
        },
        "related_files": [
            RUNNER,
        "quant/treasury_auction_indirect_bidder_tbt_paper_sleeve.py",
        "quant/test_treasury_auction_indirect_bidder_tbt_paper_sleeve.py",
        "scripts/experiment_fingerprint.py",
        "quant/test_experiment_fingerprint.py",
        "docs/alpha-optimization-playbook.md",
        repo_rel(RESULT_PATH),
            repo_rel(DSR_PANEL_PATH),
            repo_rel(PAPER_SNAPSHOT_PATH),
        ],
        "reproduction": RUNNER_COMMAND + " --offline",
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }


def compact_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metrics.items() if key != "return_series"}


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    log = {key: value for key, value in payload.items() if key not in {"windows", "deflated_sharpe", "deflated_sharpe_panel", "daily_snapshot"}}
    log["windows"] = {
        label: {
            **{key: value for key, value in row.items() if key not in {"before", "after", "dsr_reference_bid_to_cover"}},
            "before": compact_metrics(row["before"]),
            "after": compact_metrics(row["after"]),
            "dsr_reference_bid_to_cover": {
                "trade_count": row["dsr_reference_bid_to_cover"]["trade_count"],
                "metrics": compact_metrics(row["dsr_reference_bid_to_cover"]["metrics"]),
            },
        }
        for label, row in payload["windows"].items()
    }
    log["deflated_sharpe"] = {
        "status": payload["deflated_sharpe"].get("status"),
        "gate5_dsr_report": payload["deflated_sharpe"].get("gate5_dsr_report"),
        "expected_attempt_count_policy": payload["deflated_sharpe"].get("expected_attempt_count_policy"),
    }
    log["artifact"] = repo_rel(RESULT_PATH)
    log["log"] = repo_rel(LOG_PATH)
    return log


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: Treasury indirect-bidder-share TBT",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        "- Account: standalone fully funded $100,000 paper account; core PnL is not added",
        "- Production orders changed: no",
        "",
        "| Window | Trades | PnL | EV | Mean cash repl. | Mean QQQ repl. | Max DD |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        row = payload["windows"][label]
        summary = row["trade_summary"]
        after = row["after"]
        lines.append(
            f"| {label} | {summary['trade_count']} | ${after['total_pnl']:,.2f} | "
            f"{after['expected_value_score']:.4f} | "
            f"${(summary['mean_cash_replacement_usd'] or 0):,.2f} | "
            f"${(summary['mean_qqq_replacement_usd'] or 0):,.2f} | "
            f"{after['max_drawdown_pct']:.4f} |"
        )
    lines.extend(
        [
            "",
            f"- Aggregate standalone EV: `{payload['aggregate']['after_expected_value_score_sum']}`",
            f"- Aggregate standalone PnL: `${payload['aggregate']['after_total_pnl_sum']:,.2f}`",
            f"- DSR: `{payload['gate5'].get('status')}` / `{payload['gate5'].get('dsr_probability')}`",
            f"- Complete two-rule panel: `{payload['gate5'].get('selection_pool_complete')}`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            f"- Interpretation: {payload['post_run_reflection']['why_result_happened']}",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        REPO_ROOT / "quant" / "treasury_auction_indirect_bidder_tbt_paper_sleeve.py",
        REPO_ROOT / "quant" / "test_treasury_auction_indirect_bidder_tbt_paper_sleeve.py",
        REPO_ROOT / "scripts" / "experiment_fingerprint.py",
        REPO_ROOT / "quant" / "test_experiment_fingerprint.py",
        REPO_ROOT / "docs" / "alpha-optimization-playbook.md",
        REPO_ROOT / "docs" / "frozen_families.jsonl",
        REGISTRY_PATH,
        CANONICAL_PATH,
        API_ROWS_PATH,
        XML_ZIP_PATH,
        PDF_ZIP_PATH,
        SOURCE_MANIFEST_PATH,
        PRIOR_PRICE_PANEL_PATH,
        CORE_BASELINE_PATH,
        RESULT_PATH,
        BEFORE_PATH,
        AFTER_PATH,
        DSR_PANEL_PATH,
        DSR_REPORT_PATH,
        PAPER_SNAPSHOT_PATH,
        ARTIFACT_PATH,
        CARD_PATH,
        LOG_PATH,
        TICKET_PATH,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "runner": RUNNER,
        "command_offline": RUNNER_COMMAND + " --offline",
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": file_sha(path)} for path in files},
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    atomic_write_json(
        BEFORE_PATH,
        {
            "schema": "standalone_cash_before_v1",
            "windows": {label: row["before"] for label, row in payload["windows"].items()},
            "aggregate": {"expected_value_score_sum": 0.0, "total_pnl_sum": 0.0},
        },
    )
    atomic_write_json(
        AFTER_PATH,
        {
            "schema": "standalone_tbt_account_after_v1",
            "windows": {label: row["after"] for label, row in payload["windows"].items()},
            "aggregate": {
                "expected_value_score_sum": payload["aggregate"]["after_expected_value_score_sum"],
                "total_pnl_sum": payload["aggregate"]["after_total_pnl_sum"],
            },
        },
    )
    atomic_write_json(DSR_PANEL_PATH, payload["deflated_sharpe_panel"])
    atomic_write_json(DSR_REPORT_PATH, payload["deflated_sharpe"])
    atomic_write_json(RESULT_PATH, payload)
    atomic_write_json(PAPER_SNAPSHOT_PATH, payload["daily_snapshot"])
    markdown = build_markdown(payload)
    atomic_write_text(ARTIFACT_PATH, markdown)
    atomic_write_text(CARD_PATH, markdown)
    log_record = build_log(payload)
    atomic_write_json(LOG_PATH, log_record)

    persist_self_registered_result(
        REGISTRY_PATH,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(RESULT_PATH),
            "log": repo_rel(LOG_PATH),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "gate5": payload["gate5"],
            "calibration": payload["calibration"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": payload["change_type"],
            "implementation_mode": "shared_paper_first_historical_and_daily",
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(CORE_BASELINE_PATH),
            "decision": payload["decision"],
            "artifact": repo_rel(RESULT_PATH),
            "log": repo_rel(LOG_PATH),
            "card_file": repo_rel(CARD_PATH),
            "revision_manifest_file": repo_rel(MANIFEST_PATH),
            "aggregate_expected_value_delta": payload["aggregate"]["expected_value_score_delta_sum"],
            "aggregate_strategy_total_pnl_delta": payload["aggregate"]["total_pnl_delta_sum"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "gate5": payload["gate5"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "allowed_write_scope": read_json(TICKET_PATH).get("allowed_write_scope"),
        },
    )
    atomic_write_json(MANIFEST_PATH, build_manifest(payload))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", required=True)
    args = parser.parse_args(argv)
    if not args.offline:
        raise SourceContractError("only frozen offline evaluation is permitted")
    payload = build_evaluation()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "trades_by_window": {
                    label: row["trade_summary"]["trade_count"]
                    for label, row in payload["windows"].items()
                },
                "aggregate_ev": payload["aggregate"]["after_expected_value_score_sum"],
                "aggregate_pnl": payload["aggregate"]["after_total_pnl_sum"],
                "dsr_probability": payload["gate5"].get("dsr_probability"),
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
