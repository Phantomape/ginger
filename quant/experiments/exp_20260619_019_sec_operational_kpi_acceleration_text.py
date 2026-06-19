"""exp-20260619-019: SEC operational KPI acceleration text scout.

Replay-only alpha search. The single decision hypothesis is a free PIT SEC
8-K/exhibit text candidate source: issuer filings with concrete operational
KPI acceleration language (production, deliveries, deployments, orders,
bookings, subscribers/users, mined units, or capacity) plus numeric evidence,
paired with liquid SPY-relative confirmation, may surface post-disclosure
underreaction candidates before a next-open 10-trading-day continuation leg.

This is private replay first because deterministic text extraction can be
noisy and has no shared daily/backtest contract yet. A positive replay is only
a lead until a shared default-off helper reproduces the same PIT filing-text
semantics in historical replay and daily production. No production code, run
adapter, backtester adapter, ranking, sizing, exits, orders, LLM/news path, or
watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base
import exp_20260617_011_sec_text_contract_economics as template
import exp_20260617_021_intraindustry_liquidity_leader_lead_lag_scout as broad_static


EXPERIMENT_ID = "exp-20260619-019"
STEM = "sec_operational_kpi_acceleration_text"
TRIAL_FAMILY = "sec_operational_kpi_acceleration_text_candidate_pool"
TRIAL_VARIANT_ID = "sec_operational_kpi_acceleration_text_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_operational_kpi_acceleration_text_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
TEXT_DIR = REPO_ROOT / "data" / "non_ohlcv"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260619_019_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

MIN_TEXT_WORDS = 120
MAX_TEXT_CHARS_SCANNED = 80_000
MATCH_CONTEXT_CHARS = 360

KPI_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    (
        "production_delivery",
        re.compile(
            r"\b(PRODUCTION|PRODUCED|DELIVERIES|DELIVERED|SHIPMENTS?|VEHICLES?|"
            r"CUSTOMER DELIVERIES|DELIVERY VOLUME)\b",
            re.IGNORECASE,
        ),
        1.45,
    ),
    (
        "deployment_capacity",
        re.compile(
            r"\b(DEPLOYMENTS?|DEPLOYED|INSTALLED|INSTALLATIONS?|LAUNCHED|"
            r"GIGAWATTS?|MEGAWATTS?|GWH|MWH|ENERGY STORAGE|CAPACITY ADDED|"
            r"DATA CENTER CAPACITY)\b",
            re.IGNORECASE,
        ),
        1.35,
    ),
    (
        "orders_bookings_backlog",
        re.compile(
            r"\b(BOOKINGS?|BACKLOG|PURCHASE ORDERS?|CUSTOMER ORDERS?|"
            r"NET ORDERS?|ORDER INTAKE|BOOK[-\s]?TO[-\s]?BILL)\b",
            re.IGNORECASE,
        ),
        1.30,
    ),
    (
        "subscribers_users",
        re.compile(
            r"\b(SUBSCRIBERS?|PAID SUBSCRIBERS?|MEMBERS?|ACTIVE USERS?|"
            r"MONTHLY ACTIVE USERS?|DAU|MAU|NET ADDS?|CUSTOMER COUNT)\b",
            re.IGNORECASE,
        ),
        1.25,
    ),
    (
        "mined_compute",
        re.compile(
            r"\b(MINED|BITCOIN PRODUCED|BTC PRODUCED|HASH RATE|HASHRATE|"
            r"EXAHASH|EH/S|COMPUTE CAPACITY|GPU CLUSTER)\b",
            re.IGNORECASE,
        ),
        1.20,
    ),
)
ACCEL_RE = re.compile(
    r"\b(RECORD|INCREASED|INCREASE|GREW|GROWTH|UP|ROSE|HIGHER|EXPANDED|"
    r"SURPASSED|EXCEEDED|ACCELERATED|YEAR[-\s]?OVER[-\s]?YEAR|YOY|"
    r"QUARTER[-\s]?OVER[-\s]?QUARTER|QOQ|SEQUENTIAL|SEQUENTIALLY)\b",
    re.IGNORECASE,
)
NEGATIVE_RE = re.compile(
    r"\b(DECREASED|DECLINED|DOWN|LOWER|REDUCED|DROP|DROPPED|FELL|WEAKER|"
    r"WEAKNESS|LOSS OF|ADVERSE|HEADWIND|SHORTFALL)\b",
    re.IGNORECASE,
)
NUMERIC_EVIDENCE_RE = re.compile(
    r"(?:\b\d[\d,]*(?:\.\d+)?\s?(?:%|PERCENT|BILLION|MILLION|THOUSAND|BN|MM|"
    r"M|K|MW|GW|GWH|MWH|EH/S|EXAHASH|HASH|BITCOIN|BTC|VEHICLES?|UNITS?|"
    r"ORDERS?|BOOKINGS?|SUBSCRIBERS?|MEMBERS?|USERS?|DEPLOYMENTS?|CUSTOMERS?|"
    r"BARRELS?|TONS?)\b)",
    re.IGNORECASE,
)
EXCLUDE_RE = re.compile(
    r"\b(CREDIT AGREEMENT|LOAN AGREEMENT|INDENTURE|NOTES DUE|SENIOR NOTES|"
    r"CONVERTIBLE NOTES|WARRANT|UNDERWRITING AGREEMENT|AT THE MARKET|"
    r"ATM OFFERING|SECURITIES PURCHASE AGREEMENT|EQUITY INCENTIVE|"
    r"RESTRICTED STOCK UNITS?|PERFORMANCE UNITS?|SHARE UNITS?|COURT ORDER|"
    r"ORDER OF THE COURT|EMPLOYMENT AGREEMENT|LEASE AGREEMENT)\b",
    re.IGNORECASE,
)
NORMALIZE_RE = re.compile(r"[^A-Z0-9%]+")

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "text_false_positive",
        "earnings_press_release_noise",
        "single_ticker_or_theme_concentration",
        "window_regression",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Generic SEC item/text and Companyfacts threshold families have failed, "
        "but operational KPI acceleration is a distinct free evidence axis: it "
        "requires concrete non-financial operating metrics plus numeric "
        "acceleration language from issuer 8-K/exhibit text and a same-day "
        "liquid SPY-relative tape confirmation. Failure risk remains high "
        "because earnings-release language can be noisy or concentrated in "
        "crypto/AI infrastructure themes."
    ),
    "recorded_at": "2026-06-19T21:05:00Z",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_free_sec_filing_text": True,
    "uses_free_sec_companyfacts": False,
    "uses_free_ohlcv": True,
    "uses_llm": False,
    "trade_enabled": False,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "candidate_universe": "broad liquid warehouse names with PIT issuer SEC 8-K/exhibit text",
        "failure_handling": (
            "missing SEC filing text, missing usable_trade_date, missing "
            "operational KPI term, missing acceleration language, missing "
            "numeric evidence, financing/stock-unit false-positive context, "
            "missing OHLCV, missing next open, or missing 10d exit rejects the "
            "paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same PIT "
        "SEC 8-K/exhibit text fields, KPI category rules, numeric/negative/"
        "exclusion evidence, same-day OHLCV confirmation, cooldown, next-open "
        "paper entry, 10-day exit, costs, and concentration controls in both "
        "historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: issuer 8-K or exhibit text with concrete operational "
        "KPI acceleration such as production, deliveries, deployments, orders, "
        "bookings, subscribers/users, mined units, or capacity, paired with "
        "liquid SPY-relative confirmation, may surface post-disclosure "
        "underreaction candidates before a 10-trading-day continuation leg."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Reservation warned near broad post-news/SEC-text families; "
            "override was used because the new evidence axis is structured "
            "operational KPI acceleration phrases and numeric exhibit text, "
            "not SEC item/form metadata, Companyfacts ratios, governance/"
            "counterparty text, or generic quantified backlog phrases."
        ),
        "exp-20260615-013": (
            "Rejected quantified backlog/RPO/bookings text as sparse/noisy. "
            "This run broadens to concrete operational KPIs beyond financial "
            "backlog while still requiring acceleration plus numeric evidence."
        ),
        "exp-20260617-011": (
            "Rejected issuer SEC text contract-economics. This run is not "
            "contract value/duration; it is operating KPI acceleration."
        ),
        "exp-20260619-017": (
            "Rejected public-counterparty relation text. This run trades the "
            "filing issuer on its own operating KPI disclosure, not a named "
            "counterparty."
        ),
        "exp-20260619-018": (
            "Rejected acquisition pro-forma revenue integration because sample "
            "was sparse and old_thin regressed. This run uses 8-K/exhibit "
            "operating KPI text, not Companyfacts acquisition tags."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260619_019_sec_operational_kpi_acceleration_text.py"
    ),
}

_TEXT_KPI_CACHE: tuple[list[dict[str, Any]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _normalized_excerpt(text: str, limit: int = 360) -> str:
    return NORMALIZE_RE.sub(" ", str(text or "").upper()).strip()[:limit]


def _context_features(context: str, category: str, category_weight: float) -> dict[str, Any] | None:
    if EXCLUDE_RE.search(context):
        return None
    accel_terms = sorted({match.group(0).upper() for match in ACCEL_RE.finditer(context)})
    if not accel_terms:
        return None
    numeric_terms = sorted({match.group(0).upper() for match in NUMERIC_EVIDENCE_RE.finditer(context)})
    if not numeric_terms:
        return None
    negative_terms = sorted({match.group(0).upper() for match in NEGATIVE_RE.finditer(context)})
    if len(negative_terms) >= len(accel_terms) and "RECORD" not in accel_terms:
        return None
    strength = (
        category_weight
        + 0.075 * min(len(numeric_terms), 8)
        + 0.060 * min(len(accel_terms), 8)
        - 0.100 * min(len(negative_terms), 5)
    )
    if any(term in {"RECORD", "SURPASSED", "EXCEEDED"} for term in accel_terms):
        strength += 0.12
    if any("YEAR" in term or term == "YOY" for term in accel_terms):
        strength += 0.08
    if category in {"production_delivery", "orders_bookings_backlog"}:
        strength += 0.05
    return {
        "kpi_category": category,
        "kpi_strength": _round(strength, 6),
        "acceleration_terms": accel_terms[:10],
        "numeric_evidence_terms": numeric_terms[:10],
        "negative_terms": negative_terms[:10],
        "context_excerpt_normalized": _normalized_excerpt(context),
    }


def _extract_kpi_row(raw: dict[str, Any]) -> dict[str, Any] | None:
    ticker = str(raw.get("ticker") or "").upper()
    if str(raw.get("form_base") or raw.get("form_type") or "").upper() != "8-K":
        return None
    usable_date = str(raw.get("usable_trade_date") or "")[:10]
    if not ticker or not usable_date:
        return None
    text = str(raw.get("combined_text") or "")
    if len(text.split()) < MIN_TEXT_WORDS:
        return None
    scanned = text[:MAX_TEXT_CHARS_SCANNED]
    best: dict[str, Any] | None = None
    for category, regex, weight in KPI_PATTERNS:
        for match in regex.finditer(scanned):
            left = max(0, match.start() - MATCH_CONTEXT_CHARS)
            right = min(len(scanned), match.end() + MATCH_CONTEXT_CHARS)
            context = scanned[left:right]
            features = _context_features(context, category, weight)
            if features is None:
                continue
            row = {
                "ticker": ticker,
                "date": usable_date,
                "filing_date": str(raw.get("filing_date") or "")[:10],
                "accepted_at": str(raw.get("accepted_at") or "")[:19],
                "accession_number": str(raw.get("accession_number") or ""),
                "form_type": raw.get("form_type"),
                "eight_k_item_codes": raw.get("eight_k_item_codes") or [],
                "primary_document": raw.get("primary_document"),
                "text_char_count": raw.get("text_char_count"),
                "text_word_count": raw.get("text_word_count"),
                "pit_source": raw.get("pit_source"),
                "pit_caveat": raw.get("pit_caveat"),
                "matched_kpi_term": match.group(0).upper(),
                **features,
            }
            if best is None or float(row["kpi_strength"] or 0.0) > float(best["kpi_strength"] or 0.0):
                best = row
    return best


def _load_sec_text_rows(*, max_filed: str, tickers: list[str] | None = None, **_: Any) -> list[dict[str, Any]]:
    del tickers
    global _TEXT_KPI_CACHE
    if _TEXT_KPI_CACHE is None:
        rows: list[dict[str, Any]] = []
        scan: Counter[str] = Counter()
        seen: set[str] = set()
        for path in sorted(TEXT_DIR.glob("sec_filing_text_*.jsonl")):
            with path.open(encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        scan["json_decode_errors"] += 1
                        continue
                    scan["raw_text_rows"] += 1
                    if str(raw.get("form_base") or raw.get("form_type") or "").upper() != "8-K":
                        scan["non_8k_rows"] += 1
                        continue
                    accession = str(raw.get("accession_number") or "")
                    key = accession or f"{raw.get('ticker')}:{raw.get('usable_trade_date')}:{raw.get('primary_document')}"
                    if key in seen:
                        scan["duplicate_accession"] += 1
                        continue
                    seen.add(key)
                    row = _extract_kpi_row(raw)
                    if row is None:
                        scan["8k_rows_without_operational_kpi_acceleration"] += 1
                        continue
                    rows.append(row)
                    scan[f"category_{row['kpi_category']}"] += 1
        rows.sort(
            key=lambda row: (
                row["date"],
                row["ticker"],
                -(float(row.get("kpi_strength") or 0.0)),
                row.get("accession_number") or "",
            )
        )
        _TEXT_KPI_CACHE = (rows, dict(scan))
    rows, _scan = _TEXT_KPI_CACHE
    return [row for row in rows if str(row.get("date") or "")[:10] <= max_filed]


def _build_quality_index(
    text_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stats: Counter[str] = Counter()
    for row in text_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            stats["missing_ticker"] += 1
            continue
        by_ticker[ticker].append(row)
        stats[f"category_{row.get('kpi_category') or 'unknown'}"] += 1
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row["date"],
                -(float(row.get("kpi_strength") or 0.0)),
                row.get("accession_number") or "",
            )
        )
    _all_rows, raw_scan = _TEXT_KPI_CACHE or ([], {})
    return dict(by_ticker), {
        "sec_text_rows_loaded": len(text_rows),
        "tickers_with_operational_kpi_acceleration": len(by_ticker),
        "text_source": _repo_rel(TEXT_DIR),
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "match_context_chars": MATCH_CONTEXT_CHARS,
        "raw_text_scan": raw_scan,
        **dict(stats),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    scan: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[ticker]:
            signal_date = str(event.get("date") or "")[:10]
            if not (str(cfg["start"]) <= signal_date <= str(cfg["end"])):
                continue
            scan["event_rows_in_window"] += 1
            confirm = base._price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            meta = sector_entries.get(ticker, {})
            kpi_strength = float(event.get("kpi_strength") or 0.0)
            score = (
                kpi_strength
                + 0.45 * float(confirm["candidate_ret20_excess_spy"])
                + 0.14 * float(confirm["candidate_ret60_excess_spy"])
                + 0.12 * float(confirm["candidate_close_location"])
                + 0.025
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            scan["qualified_candidate_rows"] += 1
            scan[f"qualified_{event.get('kpi_category') or 'unknown'}"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_OPERATIONAL_KPI_ACCELERATION_TEXT_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "sec_8k_text_usable_trade_date_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_filing_text": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"text_{key}": value for key, value in event.items() if key not in {"ticker", "date"}},
                    **confirm,
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(existing["candidate_score"]):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row.get("text_kpi_strength") or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    scan["eligible_quality_tickers"] = len(quality_index)
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "match_context_chars": MATCH_CONTEXT_CHARS,
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_operational_kpi_acceleration_text"
        if gate["passed"]
        else "rejected_sec_operational_kpi_acceleration_text_candidate_pool"
    )
    return gate


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | KPI Events | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=scan.get("event_rows_in_window", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC Operational KPI Acceleration Text",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _configure_base() -> None:
    template.EXPERIMENT_ID = EXPERIMENT_ID
    template.STEM = STEM
    template.TRIAL_FAMILY = TRIAL_FAMILY
    template.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    template.CHANGED_VARIABLE = CHANGED_VARIABLE
    template.RULE_VERSION = RULE_VERSION
    template.OWNER = OWNER
    template.OUT_DIR = OUT_DIR
    template.OUT_JSON = OUT_JSON
    template.LOG_JSON = LOG_JSON
    template.TICKET_JSON = TICKET_JSON
    template.CARD_MD = CARD_MD
    template.MANIFEST_JSON = MANIFEST_JSON
    template.EXPERIMENT_LOG = EXPERIMENT_LOG
    template.REGISTRY_JSON = REGISTRY_JSON
    template.PREDICTION = PREDICTION
    template.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    template.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    template._load_sec_text_rows = _load_sec_text_rows
    template._build_quality_index = _build_quality_index
    template._candidate_rows_for_window = _candidate_rows_for_window
    template._gate4 = _gate4
    template._build_card = _build_card
    template._configure_base()
    base._load_window_snapshot = broad_static._broad_load_window_snapshot


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    total_events = sum(
        int(scan.get("event_rows_in_window") or 0)
        for scan in payload["context_scan_by_window"].values()
    )
    total_trades = int(payload["target_trade_summary"]["total_trade_count"] or 0)
    if gate4["passed"]:
        interpretation = (
            "SEC operational KPI acceleration text cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest parser was promoted."
        )
    elif total_trades == 0:
        interpretation = (
            "SEC operational KPI acceleration text did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). The "
            f"parser found {total_events} in-window KPI events, but none "
            "survived liquidity/price confirmation and next-open/10d execution."
        )
    else:
        interpretation = (
            "SEC operational KPI acceleration text did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). The "
            f"source produced {total_trades} paper trades from {total_events} "
            "in-window KPI events, but the bundle did not beat the canonical "
            "three-window EV/PnL/risk/comparator screen."
        )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected",
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_text_operational_kpi_acceleration_candidate_pool",
            "new_evidence_type": "sec_8k_exhibit_operational_kpi_acceleration_numeric_text_tuple",
            "nearby_prior_experiments": [
                "exp-20260615-013",
                "exp-20260617-011",
                "exp-20260619-017",
                "exp-20260619-018",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "match_context_chars": MATCH_CONTEXT_CHARS,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "max_signal_return": base.MAX_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "kpi_categories": [label for label, _regex, _weight in KPI_PATTERNS],
        "acceleration_terms": ACCEL_RE.pattern,
        "numeric_evidence": NUMERIC_EVIDENCE_RE.pattern,
        "negative_terms": NEGATIVE_RE.pattern,
        "exclude_terms": EXCLUDE_RE.pattern,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["companyfacts_source"] = None
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(TEXT_DIR)
    payload["backtest_protocol"]["candidate_ohlcv_source"] = _repo_rel(base.framework.WAREHOUSE)
    payload["backtest_protocol"]["execution_model"] = (
        "Issuer SEC 8-K/exhibit filing text is keyed by accepted_at and "
        "usable_trade_date. The parser requires an operational KPI category "
        "term, acceleration language, and numeric evidence inside a local "
        "context, while negative and financing/stock-unit/legal false-positive "
        "contexts are rejected. The candidate is the filing issuer. Price "
        "confirmation uses only signal-date OHLCV and SPY relative strength. "
        "Paper entry is the next available open with existing entry slippage; "
        "exit is the close 10 trading days after the signal with target-side "
        "sell slippage and ROUND_TRIP_COST_PCT. The core baseline remains the "
        "canonical core replay; only the default-off paper candidate snapshot "
        "uses the broad liquid universe."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "extracted KPI category, acceleration terms, numeric evidence terms, and negative terms",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume for issuer ticker",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially cleaner structured operating metrics, such as "
        "CIK-level KPI tables, standardized production/delivery history, parsed "
        "unit economics, closed forward replacement rows, or a shared daily "
        "helper. Do not sweep KPI phrase lists, item codes, RS/close/volume "
        "guards, top-N, hold, cooldown, or notional on these frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                total_trades,
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping operational KPI phrase lists, acceleration "
            "terms, numeric evidence terms, item codes, RS/close/volume/vol "
            "guards, top-N, hold days, cooldown, or notional on these frozen "
            "windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _persist(payload: dict[str, Any]) -> None:
    log_record = base._build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


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
            _repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
