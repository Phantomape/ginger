"""exp-20260625-010: SEC13F active-manager active-flow historical scout.

Private replay scout. This tests one fixed candidate-pool hypothesis: names
whose latest fully ended SEC 13F window shows concentrated active-manager
ownership plus positive quarter-over-quarter active-holder and active-value
flow, confirmed by liquid price leadership, may be better next-open 10-session
paper candidates than generic liquid momentum.

This extends the exp-20260625-009 Kova forward active-flow lead onto the
canonical historical windows using the raw manager-level SEC 13F ZIP cache. It
does not promote production behavior. A numeric pass is only a replay lead
until a shared historical/daily helper proves the same PIT feature builder and
daily default-off snapshot behavior.

No JavaScript is used.
"""

from __future__ import annotations

import csv
import io
import itertools
import json
import math
import sys
import zipfile
from collections import Counter, OrderedDict, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]
for import_path in (ROOT / "quant", ROOT / "quant" / "experiments", ROOT / "scripts"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from sec13f_coownership_edges import discover_window_labels, window_end_date  # noqa: E402
from sec13f_universe_map import load_company_name_index, normalize_issuer_name  # noqa: E402


EXPERIMENT_ID = "exp-20260625-010"
STEM = "sec13f_active_flow_historical_scout"
TRIAL_FAMILY = "sec13f_active_manager_flow_historical_candidate_pool"
TRIAL_VARIANT_ID = "raw_manager_active_flow_liquid_leadership_top1_10d_v1"
CHANGED_VARIABLE = "sec13f_active_manager_flow_historical_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-explore"

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260625_010_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"
SEC13F_CACHE = ROOT / "data" / "non_ohlcv" / "sec13f_institutional" / "source_cache"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

ACTIVE_MANAGER_MIN_HOLDINGS = 5
ACTIVE_MANAGER_MAX_HOLDINGS = 100
MIN_ACTIVE_FLOW_SCORE = 0.67
MIN_ACTIVE_SCORE_COMPONENTS = 4
MIN_ACTIVE_HOLDER_COUNT = 3
MIN_ACTIVE_HOLDER_DELTA = 1
MIN_ACTIVE_VALUE_LOG_DELTA = 0.0

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_HISTORY_SESSIONS = 60
MIN_SIGNAL_RETURN = 0.0
MAX_SIGNAL_RETURN = 0.08
MIN_RET5 = -0.05
MAX_RET5 = 0.15
MIN_RET20_EXCESS_SPY = 0.0
MIN_RET60_EXCESS_SPY = -0.02
MIN_CLOSE_LOCATION = 0.55
MIN_VOLUME_RATIO_20D = 0.65
MAX_VOLUME_RATIO_20D = 3.0
MAX_REALIZED_VOL_20D = 0.08

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ETF_OR_INDEX_TICKERS = {
    "ARKX",
    "BIL",
    "CPER",
    "DIA",
    "GLD",
    "IAU",
    "IBIT",
    "IEF",
    "IWM",
    "QQQ",
    "SHY",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "VIXM",
    "VIXY",
    "VXX",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
}

ACCEPTED_ALLOCATOR_COMPARATOR = {
    "experiment_id": "exp-20260611-005",
    "decision": "accepted_source_consensus_allocator_extension",
    "expected_value_score_delta_sum": 2.1849,
    "total_pnl_delta_sum": 40397.21,
    "note": (
        "Promotion comparator only. This private SEC13F active-flow scout is "
        "lead-only without a shared historical/daily helper even if numeric "
        "Gate 4 passes."
    ),
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 4_000.0,
    "main_failure_modes": [
        "window_regression",
        "drawdown_drift",
        "13f_staleness",
        "not_incremental",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Exp-20260625-009 found positive observed-only Kova forward separation "
        "from raw manager-level SEC13F active-flow. Confidence is still low: "
        "the same surface may be stale in historical quarterly windows, may "
        "proxy liquid momentum already captured by the core, and this private "
        "runner lacks shared-helper daily parity."
    ),
    "recorded_at": "2026-06-25T09:01:00Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "implementation_mode": "private_replay_scout",
    "private_replay_scout_escape_reason": (
        "Raw manager-level SEC13F active-flow historical feature shape is still "
        "being validated. Numeric positives must be reproduced by a shared "
        "historical/daily default-off helper before any production exposure."
    ),
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_sec_13f": True,
    "uses_raw_manager_level_sec13f_zip": True,
    "uses_free_ohlcv": True,
    "live_realism_evaluated": False,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation envelope pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": (
            "missing active-flow 13F pair, OHLCV, next open, or 10-session exit "
            "bar rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result remains "
        "a replay lead until a shared default-off helper computes raw SEC13F "
        "active-manager classification, active-flow deltas, OHLCV confirmation, "
        "core-overlap exclusion, next-open entry, exit, costs, cooldown, and "
        "ledger fields identically in historical replay and daily snapshots."
    ),
}

NEW_EVIDENCE_AXIS = (
    "Canonical fixed-window PIT coverage using raw manager-level SEC13F active-"
    "manager classification plus quarter-over-quarter active-holder and active-"
    "value flow deltas from cached structured ZIPs. This follows the exp-"
    "20260625-009 forward lead but is not a same-forward-row retune, not "
    "aggregate holder/value sponsorship, not coownership, not options cross-"
    "evidence, and not a top-N/hold/cooldown/notional threshold sweep."
)

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC13F active-manager quarter-over-quarter flow "
        "plus liquid leadership confirmation may form a PIT historical "
        "default-off candidate pool that validates the Kova forward active-flow "
        "lead before shared-helper promotion."
    ),
    "2_history_check": {
        "exp-20260624-018": (
            "Observed-only aggregate SEC13F sponsorship forward lead; it used "
            "holder/value fields, not raw manager-level active-flow."
        ),
        "exp-20260624-019": (
            "Rejected coownership peer-network attribution; this run does not "
            "use shared-manager peer lift/Jaccard/co-held edges."
        ),
        "exp-20260625-009": (
            "Positive observed-only Kova forward lead from active-manager flow; "
            "this run validates that evidence axis on canonical historical "
            "windows instead of re-bucketing the same forward rows."
        ),
        "exp-20260613-014": (
            "Prior historical SEC13F sponsorship scout used aggregate holder "
            "and value growth, not active-manager identity and flow deltas."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Numeric Gate 4 must "
        "show positive aggregate EV/PnL, no window EV/PnL regression, at least "
        "20 paper trades across all 3 windows, survival >=5%, drawdown drift "
        "<=0.5pp, and concentration pass. Even if numeric Gate4 passes this is "
        "only a positive replay lead, not accepted alpha, until shared daily "
        "parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260625_010_sec13f_active_flow_historical_scout.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round(value: Any, digits: int = 6) -> float | None:
    number = _float(value)
    return None if number is None else round(number, digits)


def _safe_date(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def _safe_key(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
        upper = key.upper()
        if upper in row and row[upper] not in (None, ""):
            return row[upper]
        lower = key.lower()
        if lower in row and row[lower] not in (None, ""):
            return row[lower]
    return None


def _iter_zip_table(
    archive: zipfile.ZipFile,
    name: str,
) -> Iterator[dict[str, Any]]:
    with archive.open(name) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
        first_line = text.readline()
        delimiter = "\t" if "\t" in first_line else ","
        reader = csv.DictReader(itertools.chain([first_line], text), delimiter=delimiter)
        yield from reader


def _configure_framework_globals() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    framework.sleeve.STEM = STEM
    framework.sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.sleeve.HOLD_DAYS = HOLD_DAYS
    framework.sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.sleeve.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.sleeve.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.sleeve.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.sleeve.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.sleeve.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI


def _manager_key(row: dict[str, Any]) -> str:
    return str(row.get("manager_cik") or row.get("manager_name") or "").strip()


def _load_active_window(
    label: str,
    *,
    name_index: dict[str, str],
    universe: set[str],
) -> dict[str, Any]:
    zip_path = SEC13F_CACHE / f"{label}_form13f.zip"
    if not zip_path.exists():
        return {
            "window_label": label,
            "zip_path": _repo_rel(zip_path),
            "zip_exists": False,
            "ticker_features": {},
        }
    asof = window_end_date(label).isoformat()
    allowed = {ticker.upper() for ticker in universe}
    positions: list[dict[str, Any]] = []
    manager_tickers: dict[str, set[str]] = defaultdict(set)
    rows_parsed = 0
    put_call_rows = 0
    unmapped_rows = 0
    outside_universe_rows = 0
    no_manager_rows = 0
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        info_name = next(
            (
                name
                for name in names
                if name.upper().endswith("INFOTABLE.TSV")
                or name.upper().endswith("INFOTABLE.CSV")
            ),
            None,
        )
        sub_name = next(
            (
                name
                for name in names
                if name.upper().endswith("SUBMISSION.TSV")
                or name.upper().endswith("SUBMISSION.CSV")
            ),
            None,
        )
        if not info_name:
            raise ValueError(f"SEC 13F zip missing INFOTABLE table: {zip_path}")
        submissions = {}
        if sub_name:
            submissions = {
                str(_safe_key(row, "ACCESSION_NUMBER", "accession_number") or ""): row
                for row in _iter_zip_table(archive, sub_name)
            }
        for row in _iter_zip_table(archive, info_name):
            rows_parsed += 1
            accession = str(_safe_key(row, "ACCESSION_NUMBER", "accession_number") or "")
            submission = submissions.get(accession, {})
            filing_date = str(
                _safe_key(submission, "FILING_DATE", "filing_date")
                or _safe_key(row, "FILING_DATE", "filing_date")
                or ""
            )[:10]
            if filing_date and filing_date > asof:
                continue
            if str(_safe_key(row, "PUTCALL", "putcall") or "").strip():
                put_call_rows += 1
                continue
            issuer = _safe_key(row, "NAMEOFISSUER", "nameofissuer", "name_of_issuer")
            ticker = name_index.get(normalize_issuer_name(issuer))
            if not ticker:
                unmapped_rows += 1
                continue
            ticker = str(ticker).upper()
            if ticker not in allowed:
                outside_universe_rows += 1
                continue
            manager = str(
                _safe_key(
                    submission,
                    "CIK",
                    "cik",
                    "manager_cik",
                    "FILINGMANAGER_NAME",
                    "filingmanager_name",
                    "manager_name",
                )
                or ""
            ).strip()
            if not manager:
                no_manager_rows += 1
                continue
            positions.append(
                {
                    "ticker": ticker,
                    "manager": manager,
                    "value_usd": _float(_safe_key(row, "VALUE", "value")) or 0.0,
                    "shares": _float(_safe_key(row, "SSHPRNAMT", "sshprnamt", "shares"))
                    or 0.0,
                }
            )
            manager_tickers[manager].add(ticker)

    active_managers = {
        manager
        for manager, tickers in manager_tickers.items()
        if ACTIVE_MANAGER_MIN_HOLDINGS <= len(tickers) <= ACTIVE_MANAGER_MAX_HOLDINGS
    }
    aggregates: dict[str, dict[str, Any]] = {}
    total_managers: dict[str, set[str]] = defaultdict(set)
    active_managers_by_ticker: dict[str, set[str]] = defaultdict(set)
    for pos in positions:
        ticker = pos["ticker"]
        manager = pos["manager"]
        entry = aggregates.setdefault(
            ticker,
            {
                "ticker": ticker,
                "total_position_row_count": 0,
                "total_value_usd": 0.0,
                "total_shares": 0.0,
                "active_position_row_count": 0,
                "active_value_usd": 0.0,
                "active_shares": 0.0,
            },
        )
        entry["total_position_row_count"] += 1
        entry["total_value_usd"] += pos["value_usd"]
        entry["total_shares"] += pos["shares"]
        total_managers[ticker].add(manager)
        if manager in active_managers:
            entry["active_position_row_count"] += 1
            entry["active_value_usd"] += pos["value_usd"]
            entry["active_shares"] += pos["shares"]
            active_managers_by_ticker[ticker].add(manager)

    features: dict[str, dict[str, Any]] = {}
    for ticker, entry in aggregates.items():
        total_holder_count = len(total_managers[ticker])
        active_holder_count = len(active_managers_by_ticker[ticker])
        total_value = float(entry["total_value_usd"])
        active_value = float(entry["active_value_usd"])
        total_shares = float(entry["total_shares"])
        active_shares = float(entry["active_shares"])
        features[ticker] = {
            "ticker": ticker,
            "active13f_window_label": label,
            "active13f_window_end": asof,
            "active13f_total_holder_count": total_holder_count,
            "active13f_active_holder_count": active_holder_count,
            "active13f_active_holder_share": active_holder_count / total_holder_count
            if total_holder_count
            else None,
            "active13f_total_position_row_count": entry["total_position_row_count"],
            "active13f_active_position_row_count": entry["active_position_row_count"],
            "active13f_active_position_row_share": entry["active_position_row_count"]
            / entry["total_position_row_count"]
            if entry["total_position_row_count"]
            else None,
            "active13f_total_value_usd": round(total_value, 2),
            "active13f_active_value_usd": round(active_value, 2),
            "active13f_active_value_share": active_value / total_value if total_value else None,
            "active13f_total_shares": round(total_shares, 2),
            "active13f_active_shares": round(active_shares, 2),
            "active13f_active_share_count_share": active_shares / total_shares
            if total_shares
            else None,
        }

    return {
        "window_label": label,
        "window_end": asof,
        "zip_path": _repo_rel(zip_path),
        "zip_exists": True,
        "rows_parsed": rows_parsed,
        "mapped_long_rows": len(positions),
        "put_call_rows_excluded": put_call_rows,
        "unmapped_long_rows": unmapped_rows,
        "outside_universe_rows": outside_universe_rows,
        "no_manager_rows": no_manager_rows,
        "manager_count": len(manager_tickers),
        "active_manager_count": len(active_managers),
        "active_manager_rule": {
            "min_universe_holdings": ACTIVE_MANAGER_MIN_HOLDINGS,
            "max_universe_holdings": ACTIVE_MANAGER_MAX_HOLDINGS,
            "basis": "unique mapped long-equity production-universe tickers per manager",
        },
        "ticker_count": len(features),
        "ticker_features": features,
    }


def _percentile_by_ticker(features: dict[str, dict[str, Any]], field: str) -> dict[str, float]:
    pairs = [
        (ticker, _float(row.get(field)))
        for ticker, row in features.items()
        if _float(row.get(field)) is not None
    ]
    pairs = [(ticker, value) for ticker, value in pairs if value is not None]
    pairs.sort(key=lambda item: (item[1], item[0]))
    if not pairs:
        return {}
    if len(pairs) == 1:
        return {pairs[0][0]: 1.0}
    out: dict[str, float] = {}
    index = 0
    while index < len(pairs):
        end = index + 1
        while end < len(pairs) and pairs[end][1] == pairs[index][1]:
            end += 1
        rank = ((index + end - 1) / 2.0) / (len(pairs) - 1)
        for pos in range(index, end):
            out[pairs[pos][0]] = rank
        index = end
    return out


def _assign_active_flow_scores(features: dict[str, dict[str, Any]]) -> None:
    score_fields = [
        "active13f_active_value_share",
        "active13f_active_holder_share",
        "active13f_active_value_log_delta",
        "active13f_active_holder_count_delta",
    ]
    ranks = {field: _percentile_by_ticker(features, field) for field in score_fields}
    for ticker, row in features.items():
        parts = [mapping[ticker] for mapping in ranks.values() if ticker in mapping]
        row["active13f_active_flow_score"] = sum(parts) / len(parts) if parts else None
        row["active13f_score_component_count"] = len(parts)
        row["active13f_score_definition"] = (
            "Average percentile rank of active_value_share, active_holder_share, "
            "active_value_log_delta, and active_holder_count_delta among mapped "
            "production-universe tickers in the same SEC13F window."
        )


def _build_active_flow_history(universe: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    name_index = load_company_name_index()
    labels = discover_window_labels(SEC13F_CACHE)
    labels = [label for label in labels if (SEC13F_CACHE / f"{label}_form13f.zip").exists()]
    labels.sort(key=window_end_date)
    max_signal_date = max(_safe_date(str(cfg["end"])) for cfg in framework.WINDOWS.values())
    labels = [label for label in labels if window_end_date(label) <= max_signal_date]
    loaded = {}
    for label in labels:
        print(f"[{EXPERIMENT_ID}] loading raw active-manager 13F window {label}", flush=True)
        loaded[label] = _load_active_window(label, name_index=name_index, universe=universe)
        print(
            f"[{EXPERIMENT_ID}] loaded {label}: "
            f"{loaded[label].get('ticker_count', 0)} tickers, "
            f"{loaded[label].get('active_manager_count', 0)} active managers",
            flush=True,
        )

    active_windows: list[dict[str, Any]] = []
    for index, label in enumerate(labels):
        current = loaded[label]
        prior = loaded[labels[index - 1]] if index > 0 else None
        current_features = current.get("ticker_features", {})
        prior_features = prior.get("ticker_features", {}) if prior else {}
        joined: dict[str, dict[str, Any]] = {}
        for ticker in sorted(set(current_features) | set(prior_features)):
            cur = current_features.get(ticker, {})
            old = prior_features.get(ticker, {})
            active_value = _float(cur.get("active13f_active_value_usd")) or 0.0
            prior_active_value = _float(old.get("active13f_active_value_usd")) or 0.0
            active_holders = _float(cur.get("active13f_active_holder_count")) or 0.0
            prior_active_holders = _float(old.get("active13f_active_holder_count")) or 0.0
            row = dict(cur) if cur else {"ticker": ticker}
            row.update(
                {
                    "active13f_window_label": label,
                    "active13f_window_end": current.get("window_end"),
                    "active13f_prior_window_label": prior.get("window_label") if prior else None,
                    "active13f_prior_window_end": prior.get("window_end") if prior else None,
                    "active13f_prior_active_holder_count": old.get(
                        "active13f_active_holder_count"
                    ),
                    "active13f_prior_active_value_usd": old.get(
                        "active13f_active_value_usd"
                    ),
                    "active13f_active_value_log_delta": math.log1p(active_value)
                    - math.log1p(prior_active_value),
                    "active13f_active_holder_count_delta": active_holders
                    - prior_active_holders,
                    "active13f_has_current": bool(cur),
                    "active13f_has_prior": bool(old),
                }
            )
            joined[ticker] = row
        _assign_active_flow_scores(joined)
        active_windows.append(
            {
                "window_label": label,
                "window_end": current.get("window_end"),
                "prior_window_label": prior.get("window_label") if prior else None,
                "prior_window_end": prior.get("window_end") if prior else None,
                "ticker_features": joined,
                "source_summary": {
                    key: value for key, value in current.items() if key != "ticker_features"
                },
            }
        )

    summary = {
        "rule_version": RULE_VERSION,
        "source_cache": _repo_rel(SEC13F_CACHE),
        "universe_size": len(universe),
        "window_count_loaded": len(active_windows),
        "windows_loaded": [
            {
                **window["source_summary"],
                "prior_window_label": window["prior_window_label"],
                "prior_window_end": window["prior_window_end"],
                "scored_ticker_count": len(window["ticker_features"]),
            }
            for window in active_windows
        ],
        "active_manager_rule": {
            "min_universe_holdings": ACTIVE_MANAGER_MIN_HOLDINGS,
            "max_universe_holdings": ACTIVE_MANAGER_MAX_HOLDINGS,
            "basis": "unique mapped long-equity production-universe tickers per manager",
        },
    }
    active_windows.sort(key=lambda row: row["window_end"] or "")
    return active_windows, summary


def _latest_active_flow_window(
    signal_date: str,
    ordered_windows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    signal = _safe_date(signal_date)
    available = [
        row
        for row in ordered_windows
        if row.get("prior_window_label") and _safe_date(row["window_end"]) <= signal
    ]
    return available[-1] if available else None


def _excluded_ticker(ticker: str) -> bool:
    return (
        ticker in ETF_OR_INDEX_TICKERS
        or ticker in getattr(framework, "EXCLUDED_TICKERS", set())
        or "." in ticker
        or "-" in ticker
    )


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    active_window: dict[str, Any],
) -> dict[str, Any] | None:
    if _excluded_ticker(ticker):
        return None
    feature = active_window["ticker_features"].get(ticker)
    if not feature or not feature.get("active13f_has_current") or not feature.get("active13f_has_prior"):
        return None
    active_flow_score = _float(feature.get("active13f_active_flow_score"))
    score_components = int(feature.get("active13f_score_component_count") or 0)
    active_holders = _float(feature.get("active13f_active_holder_count")) or 0.0
    holder_delta = _float(feature.get("active13f_active_holder_count_delta")) or 0.0
    value_log_delta = _float(feature.get("active13f_active_value_log_delta")) or 0.0
    if active_flow_score is None or active_flow_score < MIN_ACTIVE_FLOW_SCORE:
        return None
    if score_components < MIN_ACTIVE_SCORE_COMPONENTS:
        return None
    if active_holders < MIN_ACTIVE_HOLDER_COUNT:
        return None
    if holder_delta < MIN_ACTIVE_HOLDER_DELTA:
        return None
    if value_log_delta <= MIN_ACTIVE_VALUE_LOG_DELTA:
        return None

    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < MIN_HISTORY_SESSIONS or spy_idx < MIN_HISTORY_SESSIONS:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol = framework._realized_vol(rows, idx)
    required = [
        signal_return,
        close_location,
        volume_ratio,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol,
    ]
    if any(value is None for value in required):
        return None
    ret20_excess_spy = float(ret20) - float(spy_ret20)
    ret60_excess_spy = float(ret60) - float(spy_ret60)
    if float(signal_return) < MIN_SIGNAL_RETURN or float(signal_return) > MAX_SIGNAL_RETURN:
        return None
    if float(ret5) < MIN_RET5 or float(ret5) > MAX_RET5:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if float(close_location) < MIN_CLOSE_LOCATION:
        return None
    if float(volume_ratio) < MIN_VOLUME_RATIO_20D:
        return None
    if float(volume_ratio) > MAX_VOLUME_RATIO_20D:
        return None
    if float(realized_vol) > MAX_REALIZED_VOL_20D:
        return None

    score = (
        2.00 * float(active_flow_score)
        + 0.30 * min(value_log_delta, 8.0)
        + 0.03 * min(holder_delta, 20.0)
        + 1.10 * ret20_excess_spy
        + 0.35 * ret60_excess_spy
        + 0.30 * float(close_location)
        + 0.08 * min(float(volume_ratio), 2.0)
        + 0.05 * math.log10(max(float(adv20), 1.0) / 1_000_000.0)
        - 0.30 * max(float(ret5), 0.0)
        - 0.45 * float(realized_vol)
    )
    sector_meta = sector_entries.get(ticker, {})
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "SEC13F_ACTIVE_MANAGER_FLOW_LIQUID_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": _round(signal_return),
        "candidate_ret5": _round(ret5),
        "candidate_ret20": _round(ret20),
        "candidate_ret60": _round(ret60),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_close_location": _round(close_location),
        "candidate_avg_dollar_volume_20d": round(float(adv20), 2),
        "candidate_volume_ratio_20d": _round(volume_ratio),
        "candidate_realized_vol_20d": _round(realized_vol),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        **{
            key: value
            for key, value in feature.items()
            if key.startswith("active13f_") and key != "active13f_score_definition"
        },
    }


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("active13f_active_flow_score") or 0.0),
        -float(row.get("active13f_active_holder_count_delta") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("ticker") or ""),
    )


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
    active_windows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    dates = [
        value
        for value in framework.shadow._trading_dates(snapshot)
        if cfg["start"] <= value <= cfg["end"]
    ]
    indices = {ticker: framework.shadow._row_index(rows) for ticker, rows in snapshot.items()}
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    scan = {
        "trading_day_count": len(dates),
        "days_with_active_flow_window": 0,
        "days_with_raw_active_flow_candidates": 0,
        "raw_active_flow_candidates": 0,
        "days_without_active_flow_window": 0,
        "rule_version": RULE_VERSION,
    }
    for signal_date in dates:
        active_window = _latest_active_flow_window(signal_date, active_windows)
        if active_window is None:
            scan["days_without_active_flow_window"] += 1
            continue
        scan["days_with_active_flow_window"] += 1
        ab_entries = entries_by_date.get(signal_date, [])
        same_day_core = {str(entry.get("ticker") or "").upper() for entry in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            if ticker not in snapshot:
                continue
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                active_window=active_window,
            )
            if row is None:
                continue
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = ticker in same_day_core
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(key=_candidate_sort_key)
        candidates.extend(day_rows)
        scan["days_with_raw_active_flow_candidates"] += 1
        scan["raw_active_flow_candidates"] += len(day_rows)
        top = day_rows[0]
        contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "active13f_window_label": active_window["window_label"],
                "active13f_prior_window_label": active_window["prior_window_label"],
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_active_flow_score": top["active13f_active_flow_score"],
                "top_active_holder_delta": top["active13f_active_holder_count_delta"],
                "top_active_value_log_delta": top["active13f_active_value_log_delta"],
            }
        )
    candidates.sort(key=lambda row: (row["date"], *_candidate_sort_key(row)))
    return candidates, contexts, scan


def _select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    dates = framework.shadow._trading_dates(snapshot)
    date_pos = {date_value: idx for idx, date_value in enumerate(dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        trade = framework.sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    return selected, filtered


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    gate["failed_reasons"] = failed
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec13f_active_manager_flow"
        if gate["passed"]
        else "rejected_sec13f_active_manager_flow_candidate_pool"
    )
    gate["accepted_allocator_comparator"] = ACCEPTED_ALLOCATOR_COMPARATOR
    gate["comparator_note"] = "Comparator is promotion context only, not a private-scout pass/fail rule."
    return gate


def _blocked_payload(
    *,
    timestamp: str,
    gate2_open_positions: dict[str, Any],
    history_summary: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_sec13f_active_flow_historical_data_unavailable",
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "private_replay_scout_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_sec_13f_active_manager_flow_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260613-014",
            "exp-20260624-018",
            "exp-20260624-019",
            "exp-20260625-009",
        ],
        "prior_trial_count": 5,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "raw_sec13f_active_manager_flow_historical_pit_coverage",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "gate1": {"passed": False, "reason": reason},
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "raw SEC13F source ZIP manager_cik/manager_name",
                "raw SEC13F name_of_issuer/value/shares/put_call",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": bool(gate2_open_positions.get("passed")),
        },
        "gate3": {"passed": False, "reason": reason},
        "gate4": {"passed": False, "failed_reasons": [reason]},
        "sec13f_history_summary": history_summary,
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": "Historical active-flow SEC13F coverage was insufficient to run Gate 4.",
        "rejection_reason": reason,
        "post_run_reflection": {
            "why_result_happened": "The required cached SEC13F active-flow windows were not available.",
            "forbidden_near_neighbor_retry": (
                "Do not replace this with active-flow threshold sweeps on the same "
                "forward rows or frozen windows."
            ),
            "new_evidence_required": (
                "A valid retry needs the missing raw SEC13F windows or a shared "
                "daily helper with PIT active-flow coverage."
            ),
        },
        "related_files": _related_files(),
        "anti_js": "No JavaScript was used.",
    }


def _build_payload() -> dict[str, Any]:
    _configure_framework_globals()
    timestamp = _utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(framework.get_universe())
    sector_entries_all = framework._load_sector_entries()
    active_windows, history_summary = _build_active_flow_history(set(sector_entries_all))
    if len([row for row in active_windows if row.get("prior_window_label")]) < 3:
        return _blocked_payload(
            timestamp=timestamp,
            gate2_open_positions=gate2_open_positions,
            history_summary=history_summary,
            reason="historical_active_flow_window_count_too_low",
        )

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    contexts_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline and PIT SEC13F active-flow replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries_all),
        )
        sector_entries = {
            ticker: meta
            for ticker, meta in sector_entries_all.items()
            if ticker in snapshot
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
            "sec13f_active_flow_windows_loaded": history_summary["window_count_loaded"],
        }
        candidates, contexts, scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
            active_windows=active_windows,
        )
        selected_trades, filtered_candidates = _select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        for trade in selected_trades:
            trade["window"] = label
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        contexts_by_window[label] = contexts[:200]
        context_scan_by_window[label] = scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "candidate_day_count": scan.get("days_with_raw_active_flow_candidates", 0),
            "days_with_active_flow_window": scan.get("days_with_active_flow_window", 0),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework.sleeve._aggregate(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    passed = bool(gate4["passed"])
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": passed,
        "actual_success": 1 if passed else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    interpretation = (
        "The SEC13F active-manager active-flow source cleared numeric Gate 4, "
        "but remains only a private replay lead because shared historical/daily "
        "default-off parity has not been implemented."
        if passed
        else (
            "The SEC13F active-manager active-flow candidate pool failed Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). Do not "
            "sweep adjacent active-flow, leadership, top-N, hold, cooldown, or "
            "notional thresholds on the same frozen windows."
        )
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "private_replay_scout_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "raw manager-level SEC13F active-manager classification",
            "quarter-over-quarter active-holder and active-value flow deltas",
            "fixed liquid leadership OHLCV confirmation",
            "same-ticker core-overlap exclusion",
            "next-open 10-session paper replay",
        ],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_sec_13f_active_manager_flow_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260613-014",
            "exp-20260624-018",
            "exp-20260624-019",
            "exp-20260625-009",
        ],
        "prior_trial_count": 5,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "raw_sec13f_active_manager_flow_historical_pit_coverage",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": {
            **PREDICTION,
            "actual_success": 1 if passed else 0,
            "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
            "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
            "brier_score": calibration["brier_score"],
        },
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "experiment-local PIT SEC13F active-manager flow paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "sec13f_provenance": (
                "Cached SEC structured Form 13F filing-window ZIP files. A "
                "signal day uses the latest cached window whose end date is <= "
                "signal date and compares it with the prior fully ended window. "
                "This historical scout does not model actual 13F filing-delay "
                "availability, so positive results require shared-helper PIT "
                "hardening before promotion."
            ),
            "replay_llm": False,
            "replay_news": False,
            "execution_model": (
                "Signal uses active-flow SEC13F features from the latest fully "
                "ended window plus signal-date OHLCV after the close. Paper "
                "entry is next available open with existing entry slippage; exit "
                "is the close 10 trading days after signal with target-side sell "
                "slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "active_manager_min_holdings": ACTIVE_MANAGER_MIN_HOLDINGS,
            "active_manager_max_holdings": ACTIVE_MANAGER_MAX_HOLDINGS,
            "min_active_flow_score": MIN_ACTIVE_FLOW_SCORE,
            "min_active_score_components": MIN_ACTIVE_SCORE_COMPONENTS,
            "min_active_holder_count": MIN_ACTIVE_HOLDER_COUNT,
            "min_active_holder_delta": MIN_ACTIVE_HOLDER_DELTA,
            "min_active_value_log_delta": MIN_ACTIVE_VALUE_LOG_DELTA,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_history_sessions": MIN_HISTORY_SESSIONS,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_ret5": MIN_RET5,
            "max_ret5": MAX_RET5,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "same_ticker_core_overlap_excluded": True,
            "single_causal_variable": CHANGED_VARIABLE,
        },
        "sec13f_history_summary": history_summary,
        "gate_questions": PRE_RUN_QUESTIONS,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "raw SEC13F source ZIP manager_cik/manager_name",
                "raw SEC13F name_of_issuer/value/shares/put_call",
                "SEC13F active manager unique mapped universe-holding count",
                "SEC13F active_holder_count and active_value_usd",
                "SEC13F active_holder_count_delta and active_value_log_delta",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
                "SPY OHLCV for relative strength",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "survival_rate_by_window": {
                label: before_metrics[label].get("survival_rate") for label in before_metrics
            },
            "passed": min_survival >= 0.05,
            "note": (
                "No core entry filter is added. The 13F active-flow source is "
                "additive default-off paper; core signals and survival are "
                "unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "context_scan_by_window": context_scan_by_window,
        "contexts_by_window": contexts_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "implementation_mode": "private_replay_scout",
        "observed_only_lead": False,
        "numeric_gate4_passed": passed,
        "lean_quality_passed": True,
        "interpretation": interpretation,
        "rejection_reason": None if passed else "; ".join(gate4["failed_reasons"]),
        "next_evidence_needed": (
            "A valid retry needs shared historical/daily active-flow helper "
            "coverage with true PIT filing-delay controls, enough closed forward "
            "10d rows, non-quarterly active-flow provenance, or borrow/loan "
            "availability cross-evidence. Do not sweep active-holder/value/share/"
            "delta, price-confirmation, top-N, hold, cooldown, or notional "
            "thresholds on these frozen windows."
        ),
        "post_run_reflection": {
            "why_result_happened": interpretation,
            "outcome_summary": (
                "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
                "max drawdown drift {:+.4f}; {} paper trades.".format(
                    aggregate["expected_value_score_delta_sum"],
                    aggregate["total_pnl_delta_sum"],
                    float(aggregate["max_drawdown_delta_max"] or 0.0),
                    target_summary["total_trade_count"],
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry SEC13F active-holder share, active-value share, "
                "active-flow deltas, aggregate sponsorship, coownership network, "
                "options cross-evidence, Companyfacts quality, top-N, hold, "
                "cooldown, notional, or allocator thresholds on the same frozen "
                "windows or the same exp017 partial forward rows."
            ),
            "new_evidence_required": (
                "A retry needs shared-helper PIT filing-delay controls, materially "
                "more closed 10d forward rows, non-quarterly active-manager flow "
                "provenance, or borrow/loan availability cross-evidence."
            ),
        },
        "related_files": _related_files(),
        "changed_files": _related_files(),
        "anti_js": "No JavaScript was used.",
    }


def _related_files() -> list[str]:
    return [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
        _repo_rel(SEC13F_CACHE),
    ]


def _window_metric_row(payload: dict[str, Any], label: str) -> str:
    before = payload.get("before_metrics", {}).get(label, {})
    after = payload.get("after_metrics", {}).get(label, {})
    delta = payload.get("delta_metrics", {}).get("by_window", {}).get(label, {})
    scan = payload.get("context_scan_by_window", {}).get(label, {})
    trades = len(payload.get("target_trades_by_window", {}).get(label, []))
    return (
        "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
        "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
        "{flow_days} | {cand_days} | {trades} |"
    ).format(
        label=label,
        bev=float(before.get("expected_value_score") or 0.0),
        aev=float(after.get("expected_value_score") or 0.0),
        dev=float(delta.get("expected_value_score") or 0.0),
        bpnl=float(before.get("total_pnl") or 0.0),
        apnl=float(after.get("total_pnl") or 0.0),
        dpnl=float(delta.get("total_pnl") or 0.0),
        dd=float(delta.get("max_drawdown_pct") or 0.0),
        flow_days=scan.get("days_with_active_flow_window", 0),
        cand_days=scan.get("days_with_raw_active_flow_candidates", 0),
        trades=trades,
    )


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Active-flow days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if payload["status"] != "blocked":
        for label in framework.WINDOWS:
            rows.append(_window_metric_row(payload, label))
        aggregate = payload["delta_metrics"]["aggregate"]
        aggregate_lines = [
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
        ]
    else:
        aggregate_lines = ["- Blocked reason: `{}`".format(payload["rejection_reason"])]
    history = payload["sec13f_history_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC13F Active-Manager Active-Flow Scout",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json.dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=True, indent=2),
            "",
            "## 13F Active-Flow History",
            "",
            "- Loaded cached windows: `{}`".format(history["window_count_loaded"]),
            "- Source cache: `{}`".format(history["source_cache"]),
            "- Active-manager rule: `{}`-`{}` mapped universe holdings".format(
                ACTIVE_MANAGER_MIN_HOLDINGS,
                ACTIVE_MANAGER_MAX_HOLDINGS,
            ),
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            *aggregate_lines,
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload.get("delta_metrics", {}).get("aggregate", {})
    windows: list[dict[str, Any]] = []
    if payload["status"] != "blocked":
        for label in framework.WINDOWS:
            windows.append(
                {
                    "label": label,
                    "expected_value_before": payload["before_metrics"][label][
                        "expected_value_score"
                    ],
                    "expected_value_after": payload["after_metrics"][label][
                        "expected_value_score"
                    ],
                    "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                        "expected_value_score"
                    ],
                    "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                        "total_pnl"
                    ],
                    "days_with_active_flow_window": payload["context_scan_by_window"][label].get(
                        "days_with_active_flow_window"
                    ),
                    "candidate_day_count": payload["context_scan_by_window"][label].get(
                        "days_with_raw_active_flow_candidates"
                    ),
                    "target_trade_count": len(payload["target_trades_by_window"][label]),
                }
            )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": bool(payload.get("gate4", {}).get("passed")),
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload.get("backtest_protocol"),
        "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate.get("expected_value_score_delta_sum", 0.0),
        "aggregate_expected_value_delta_pct": aggregate.get("expected_value_score_delta_pct"),
        "aggregate_strategy_total_pnl_delta": aggregate.get("total_pnl_delta_sum", 0.0),
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "gate1": payload.get("gate1"),
        "gate2": payload.get("gate2"),
        "gate3": payload.get("gate3"),
        "gate4": payload.get("gate4"),
        "windows": windows,
        "sec13f_history_summary": payload.get("sec13f_history_summary"),
        "prediction": payload.get("prediction"),
        "calibration": payload.get("calibration"),
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "negative_reflection": None
        if payload.get("gate4", {}).get("passed")
        else payload["post_run_reflection"]["why_result_happened"],
        "post_run_reflection": payload["post_run_reflection"],
        "lean_quality_passed": payload.get("lean_quality_passed", True),
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket_before = _load_json(TICKET_JSON)
    aggregate = payload.get("delta_metrics", {}).get("aggregate", {})
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": bool(payload.get("gate4", {}).get("passed")),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate.get("expected_value_score_delta_sum", 0.0),
        "aggregate_strategy_total_pnl_delta": aggregate.get("total_pnl_delta_sum", 0.0),
        "gate4": payload["gate4"],
        "calibration": payload.get("calibration"),
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload.get("implementation_mode", "private_replay_scout"),
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": payload.get("causal_components"),
        "prior_trial_count": payload.get("prior_trial_count", 5),
        "nearby_prior_experiments": payload.get("nearby_prior_experiments", []),
        "multiple_testing_risk_bucket": payload.get("multiple_testing_risk_bucket", "moderate"),
        "new_evidence_type": payload.get(
            "new_evidence_type",
            "raw_sec13f_active_manager_flow_historical_pit_coverage",
        ),
        "new_evidence_axis": payload.get("new_evidence_axis", NEW_EVIDENCE_AXIS),
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
        "gate1": payload.get("gate1"),
        "gate2": payload.get("gate2"),
        "gate3": payload.get("gate3"),
        "gate4": payload.get("gate4"),
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "related_files": payload.get("related_files"),
        "changed_files": payload.get("changed_files"),
        "lean_quality_passed": payload.get("lean_quality_passed", True),
        "hub_identity": ticket_before.get("hub_identity"),
        "novelty": ticket_before.get("novelty"),
        "claimed_at": ticket_before.get("claimed_at"),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(path): framework._sha256(path)
            for path in [Path(__file__), OUT_JSON, LOG_JSON, TICKET_JSON, CARD_MD]
            if path.exists()
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
