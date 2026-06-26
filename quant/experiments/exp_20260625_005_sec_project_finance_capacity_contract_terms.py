"""exp-20260625-005: SEC project-finance capacity contract terms.

Alpha-search replay scout with one fixed decision bundle. Generic SEC text,
offering, customer-concentration, and debt-ratio scans are frozen or weak. This
run tests a materially narrower machine-checkable field: primary-document and
exhibit text that combines project-finance/covenant economics with capacity or
customer-contract evidence.

This runner is experiment-owned and replay-only. It changes no production
strategy code, shared helper, daily snapshot, live/default orders, ranking,
sizing, exits, watchlist, LLM, or news path. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
EXPERIMENTS_ROOT = QUANT_ROOT / "experiments"
for entry in (REPO_ROOT, QUANT_ROOT, EXPERIMENTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import exp_20260624_022_sec_offering_richer_terms_constructive_financing as template  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_live_readiness,
    full_stack_verdict,
)


base = template.prior.base
TEXT_DIR = template.richer.TEXT_DIR

EXPERIMENT_ID = "exp-20260625-005"
OWNER = "alpha-explore"
STEM = "sec_project_finance_capacity_contract_terms"
TRIAL_FAMILY = "sec_project_finance_capacity_contract_terms_candidate_pool"
TRIAL_VARIANT_ID = "top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_project_finance_capacity_contract_terms_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260625_005_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = template.BASE_NOTIONAL_USD
HOLD_DAYS = template.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = template.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = template.SAME_TICKER_COOLDOWN_DAYS

MIN_FINANCING_AMOUNT_USD = 50_000_000.0
MAX_FINANCING_AMOUNT_USD = 80_000_000_000.0
MIN_TEXT_WORDS = 220
MAX_TEXT_CHARS_SCANNED = 180_000
EVIDENCE_SPAN_CHARS = 1400

ELIGIBLE_FORMS = {"8-K", "8-K/A", "6-K", "6-K/A"}

PROJECT_RE = re.compile(
    r"\b(data\s*center|datacenter|high performance computing|HPC|AI infrastructure|"
    r"cloud services?|compute facility|facility|project|campus|site|power|"
    r"interconnection|megawatts?|MW\b|capacity)\b",
    re.IGNORECASE,
)
CONTRACT_RE = re.compile(
    r"\b(non[- ]?cancelable|take[- ]or[- ]pay|minimum (?:revenue )?commitment|"
    r"customer contract|customer agreement|lease agreement|datacenter lease|"
    r"anchor customer|reserved capacity|contracted capacity|long[- ]term (?:lease|contract)|"
    r"term of (?:the )?(?:lease|agreement)|service agreement)\b",
    re.IGNORECASE,
)
FINANCE_RE = re.compile(
    r"\b(project financ(?:e|ing)|senior secured notes?|secured notes?|credit facility|"
    r"loan agreement|term loan|indenture|collateral|debt service reserve|"
    r"debt service coverage|cash waterfall|completion guarantee|guaranteed completion|"
    r"construction financing|net proceeds|fund(?:s|ing) (?:the|remaining|construction))\b",
    re.IGNORECASE,
)
QUALITY_RE = re.compile(
    r"\b(completion guarantee|debt service reserve|debt service coverage|cash waterfall|"
    r"collateral|senior secured|first lien|restricted payments|mandatory redemption|"
    r"non[- ]?cancelable|take[- ]or[- ]pay|minimum (?:revenue )?commitment|"
    r"contracted capacity|reserved capacity)\b",
    re.IGNORECASE,
)
FALSE_POSITIVE_RE = re.compile(
    r"\b(risk factors?|may not|could fail|we may|we could|unrelated to|"
    r"not yet entered into|subject to negotiation|historical|for the year ended|"
    r"litigation|stock option|employee benefit|tax withholding)\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(
    r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s?"
    r"(billion|bn|million|mm|m)?",
    re.IGNORECASE,
)
MW_RE = re.compile(r"\b([0-9]{1,4}(?:\.[0-9]+)?)\s?(?:MW|megawatts?)\b", re.IGNORECASE)

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "sec_text_saturation",
        "accepted_distribution_comparator_not_beaten",
        "target_concentration_failed",
        "project_finance_debt_not_equity_alpha",
    ],
    "confidence_reason": (
        "Playbook freezes generic SEC text and offering scans, but explicitly "
        "allows richer structured customer/supplier/contract/covenant economics. "
        "This tests a machine-checkable exhibit-level project-finance capacity-"
        "contract axis rather than phrase-list or amount-threshold retunes; main "
        "risk is sparse rows and SEC text saturation."
    ),
    "recorded_at": "2026-06-25T04:04:15+00:00",
}

PRODUCTION_IMPACT = {
    **template.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "implementation_mode": "candidate_pool_full_stack_private_replay_scout",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "daily_snapshot_exposed": False,
    "trade_enabled": False,
    "live_ready": False,
    "uses_free_sec_filing_text": True,
    "uses_free_sec_companyfacts": False,
    "uses_raw_companyfacts_cache": False,
    "uses_project_finance_capacity_contract_terms": True,
    "execution_envelope": {
        "base_notional": BASE_NOTIONAL_USD,
        "capital_cap": "8% paper sleeve cap; no live capital enabled",
        "liquidity_slippage_model": "ADV20 >= $50M; existing next-open/slippage/cost model",
        "portfolio_displacement": "default-off additive paper overlay; no core displacement",
        "max_concurrent": HOLD_DAYS * MAX_PAPER_TRADES_PER_DAY,
        "order_semantics": "next available open paper entry, close after 10 trading days",
        "kill_switch": "paper-only; proposed 5% sleeve drawdown review before live consideration",
        "failure_handling": (
            "missing SEC text, missing project/capacity term, missing financing/"
            "covenant term, missing quality-contract term, missing local dollar "
            "amount, missing OHLCV/next-open/10d exit, or failed price "
            "confirmation rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same SEC "
        "primary-document and exhibit fields in both historical replay and daily "
        "production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC primary-document project-finance and capacity-"
        "contract economics, such as completion guarantees, debt-service "
        "reserves, data-center lease/MW capacity and non-cancelable customer "
        "commitments, may identify funded expansion demand that generic SEC "
        "text/offering scans missed."
    ),
    "2_history_check": {
        "exp-20260621-012": (
            "Rejected SEC no-covenant credit-facility text; retry requires "
            "normalized lender/customer identity, duration/funding certainty, "
            "covenant/refinancing economics, or closed forward rows."
        ),
        "exp-20260621-014": (
            "Rejected customer prepayment/capacity-commitment text; retry "
            "requires richer customer/lender identity and non-cancelable exposure."
        ),
        "exp-20260624-021": (
            "Accepted richer offering-term measurement repair, but it did not "
            "test project/capacity contract economics."
        ),
        "exp-20260624-022": (
            "Rejected constructive offering terms due thin sample and comparator "
            "failure. This run is not an offering amount/security/use retune."
        ),
        "novelty_gate": (
            "Reservation warned on customer/debt Companyfacts-ratio neighbors and "
            "dry-source saturation; override axis is SEC primary-document and "
            "exhibit-level project-finance/capacity-contract economics."
        ),
    },
    "3_single_policy_bundle": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical windows. Aggregate EV/PnL must be "
        "positive, no window EV/PnL regression, at least two EV-improved windows, "
        "sufficient target trades across all three windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260625_005_sec_project_finance_capacity_contract_terms.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return template._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return template._round(value, digits)


def _float_or_none(value: Any) -> float | None:
    return template._float_or_none(value)


def _clean_excerpt(text: str, limit: int = 520) -> str:
    return " ".join(str(text or "").split())[:limit]


def _money_value(match: re.Match[str]) -> float | None:
    try:
        raw = float(match.group(1).replace(",", ""))
    except (TypeError, ValueError):
        return None
    unit = str(match.group(2) or "").lower()
    if unit in {"billion", "bn"}:
        value = raw * 1_000_000_000.0
    elif unit in {"million", "mm", "m"}:
        value = raw * 1_000_000.0
    else:
        value = raw
    if value < MIN_FINANCING_AMOUNT_USD or value > MAX_FINANCING_AMOUNT_USD:
        return None
    return value


def _span_metrics(span: str) -> dict[str, Any] | None:
    if FALSE_POSITIVE_RE.search(span):
        return None
    project_hits = PROJECT_RE.findall(span)
    contract_hits = CONTRACT_RE.findall(span)
    finance_hits = FINANCE_RE.findall(span)
    quality_hits = QUALITY_RE.findall(span)
    money_values = [
        value
        for value in (_money_value(match) for match in MONEY_RE.finditer(span))
        if value is not None
    ]
    mw_values = []
    for match in MW_RE.finditer(span):
        try:
            mw_values.append(float(match.group(1)))
        except (TypeError, ValueError):
            continue
    if not project_hits or not finance_hits or not quality_hits or not money_values:
        return None
    if not contract_hits and not mw_values:
        return None
    amount = max(money_values)
    max_mw = max(mw_values) if mw_values else None
    score = (
        1.0
        + 0.20 * min(len(set(project_hits)), 6)
        + 0.24 * min(len(set(finance_hits)), 6)
        + 0.28 * min(len(set(quality_hits)), 8)
        + 0.18 * min(len(set(contract_hits)), 5)
        + 0.16 * min(math.log10(amount / MIN_FINANCING_AMOUNT_USD), 4.0)
        + (0.35 if max_mw and max_mw >= 50.0 else 0.0)
    )
    return {
        "project_finance_amount_usd": _round(amount, 2),
        "project_finance_max_mw": _round(max_mw, 2) if max_mw is not None else None,
        "project_term_count": len(project_hits),
        "contract_term_count": len(contract_hits),
        "finance_term_count": len(finance_hits),
        "quality_term_count": len(quality_hits),
        "project_terms": sorted({str(x).lower() for x in project_hits})[:12],
        "contract_terms": sorted({str(x).lower() for x in contract_hits})[:12],
        "finance_terms": sorted({str(x).lower() for x in finance_hits})[:12],
        "quality_terms": sorted({str(x).lower() for x in quality_hits})[:12],
        "contract_economics_strength": _round(score, 6),
        "contract_economics_evidence_excerpt": _clean_excerpt(span),
    }


def _contract_event(text: str) -> dict[str, Any] | None:
    if not text or len(text.split()) < MIN_TEXT_WORDS:
        return None
    scanned = text[:MAX_TEXT_CHARS_SCANNED]
    anchors = list(PROJECT_RE.finditer(scanned)) + list(FINANCE_RE.finditer(scanned)) + list(CONTRACT_RE.finditer(scanned))
    best: dict[str, Any] | None = None
    for anchor in anchors:
        start = max(0, anchor.start() - EVIDENCE_SPAN_CHARS)
        end = min(len(scanned), anchor.end() + EVIDENCE_SPAN_CHARS)
        span = scanned[start:end]
        metrics = _span_metrics(span)
        if metrics is None:
            continue
        if best is None or float(metrics["contract_economics_strength"]) > float(best["contract_economics_strength"]):
            best = metrics
    if best is not None:
        best["text_word_count_scanned"] = len(scanned.split())
    return best


def _load_sec_text_rows(*, max_filed: str, tickers: list[str] | None = None, **_: Any) -> list[dict[str, Any]]:
    allowed = {ticker.upper() for ticker in tickers or []}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(TEXT_DIR.glob("sec_filing_text_*.jsonl")):
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ticker = str(raw.get("ticker") or "").upper()
                if allowed and ticker not in allowed:
                    continue
                form = str(raw.get("form_type") or raw.get("form_base") or "").upper()
                if form not in ELIGIBLE_FORMS:
                    continue
                usable_date = str(raw.get("usable_trade_date") or "")[:10]
                if not usable_date or usable_date > max_filed:
                    continue
                accession = str(raw.get("accession_number") or "")
                key = accession or f"{ticker}:{usable_date}:{raw.get('primary_document')}"
                if key in seen:
                    continue
                seen.add(key)
                event = _contract_event(str(raw.get("combined_text") or ""))
                if event is None:
                    continue
                rows.append(
                    {
                        "ticker": ticker,
                        "date": usable_date,
                        "filing_date": str(raw.get("filing_date") or "")[:10],
                        "accepted_at": str(raw.get("accepted_at") or "")[:19],
                        "accession_number": accession,
                        "form_type": raw.get("form_type"),
                        "form_base": raw.get("form_base"),
                        "eight_k_item_codes": raw.get("eight_k_item_codes") or [],
                        "primary_document": raw.get("primary_document"),
                        "text_char_count": raw.get("text_char_count"),
                        "text_word_count": raw.get("text_word_count"),
                        "pit_source": raw.get("pit_source"),
                        "pit_caveat": raw.get("pit_caveat"),
                        "source_file": _repo_rel(path),
                        **event,
                    }
                )
    return rows


def _build_quality_index(text_rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    form_counts: Counter[str] = Counter()
    term_counts: Counter[str] = Counter()
    for row in text_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        by_ticker[ticker].append(row)
        form_counts[str(row.get("form_type") or "unknown")] += 1
        for field in ("project_terms", "contract_terms", "finance_terms", "quality_terms"):
            for term in row.get(field) or []:
                term_counts[str(term)] += 1
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row["date"],
                -float(row.get("contract_economics_strength") or 0.0),
                -float(row.get("project_finance_amount_usd") or 0.0),
                -float(row.get("project_finance_max_mw") or 0.0),
                row.get("accession_number") or "",
            )
        )
    index = {ticker: {"events": rows} for ticker, rows in by_ticker.items()}
    return index, {
        "sec_contract_rows_loaded": len(text_rows),
        "tickers_with_contract_terms": len(by_ticker),
        "form_type_counts": dict(form_counts),
        "top_contract_terms": dict(term_counts.most_common(20)),
        "text_source": _repo_rel(TEXT_DIR),
        "eligible_forms": sorted(ELIGIBLE_FORMS),
        "rule_version": RULE_VERSION,
    }


def _quality_score(event: dict[str, Any], confirm: dict[str, Any]) -> float:
    amount = _float_or_none(event.get("project_finance_amount_usd")) or MIN_FINANCING_AMOUNT_USD
    max_mw = _float_or_none(event.get("project_finance_max_mw")) or 0.0
    evidence_strength = float(event.get("contract_economics_strength") or 0.0)
    amount_component = min(math.log10(max(amount, 1.0) / MIN_FINANCING_AMOUNT_USD), 4.0)
    mw_component = min(max_mw / 100.0, 5.0)
    return (
        1.15 * evidence_strength
        + 0.24 * amount_component
        + 0.18 * mw_component
        + 0.55 * float(confirm["candidate_ret20_excess_spy"])
        + 0.16 * float(confirm["candidate_ret60_excess_spy"])
        + 0.12 * float(confirm["candidate_close_location"])
        + 0.025 * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
    )


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    scan: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in list(quality_index[ticker].get("events") or []):
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
            score = _quality_score(event, confirm)
            scan["qualified_candidate_rows"] += 1
            scan[f"qualified_form_{event.get('form_type') or 'unknown'}"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_PROJECT_FINANCE_CAPACITY_CONTRACT_TERMS_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "sec_filing_text_usable_trade_date_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_filing_text": True,
                    "uses_free_sec_companyfacts": False,
                    "uses_raw_companyfacts_cache": False,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"contract_{key}": value for key, value in event.items() if key not in {"ticker", "date"}},
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
            -float(row.get("contract_contract_economics_strength") or 0.0),
            -float(row.get("contract_project_finance_amount_usd") or 0.0),
            -float(row.get("contract_project_finance_max_mw") or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "eligible_forms": sorted(ELIGIBLE_FORMS),
        "min_financing_amount_usd": MIN_FINANCING_AMOUNT_USD,
        "max_financing_amount_usd": MAX_FINANCING_AMOUNT_USD,
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "evidence_span_chars": EVIDENCE_SPAN_CHARS,
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
        "positive_replay_lead_not_promoted_sec_project_finance_capacity_contract_terms"
        if gate["passed"]
        else "rejected_sec_project_finance_capacity_contract_terms_candidate_pool"
    )
    return gate


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Text Events | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {trades} |".format(
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
            f"# {EXPERIMENT_ID} SEC Project-Finance Capacity Contract Terms",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- Gate 4 passed: `{payload['gate4']['passed']}`",
            "- Production impact: no live/default behavior changed.",
            "",
            "## Hypothesis",
            "",
            PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "",
            "## Three-window Gate 4",
            "",
            *rows,
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _execution_envelope() -> ExecutionEnvelope:
    return ExecutionEnvelope(
        base_notional=BASE_NOTIONAL_USD,
        max_capital_pct=0.08,
        min_dollar_volume=base.MIN_AVG_DOLLAR_VOLUME_20D,
        slippage_bps=85.0,
        max_displacement=0,
        max_concurrent=HOLD_DAYS * MAX_PAPER_TRADES_PER_DAY,
        order_semantics="next_open_paper_entry_close_after_10_trading_days",
        kill_switch_drawdown_pct=0.05,
        sleeve_drawdown_stop_pct=0.08,
        notes="Default-off paper only; no live orders or core displacement.",
    )


def _add_full_stack_block(payload: dict[str, Any]) -> None:
    gate4 = payload["gate4"]
    envelope = _execution_envelope()
    live_readiness = evaluate_live_readiness(
        envelope=envelope,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
    )
    helper_gate4 = {
        "passed": bool(gate4.get("passed")),
        "status": "passed" if gate4.get("passed") else "blocked",
        "hard_failures": list(gate4.get("failed_reasons") or []),
        "source_gate4": gate4,
    }
    verdict = full_stack_verdict(
        gate4=helper_gate4,
        live_readiness=live_readiness,
        envelope=envelope,
    )
    verdict["contract_completeness"] = {
        "shared_helper_promoted": False,
        "run_adapter_changed": False,
        "daily_snapshot_exposed": False,
        "parity_test_added": False,
        "note": (
            "This run records the full-stack envelope and replay verdict, but "
            "does not promote shared daily production code. Positive numeric "
            "results would remain a lead until shared helper/parity work exists."
        ),
    }
    payload["full_stack"] = verdict


def _configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OWNER = OWNER
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    base.HOLD_DAYS = HOLD_DAYS
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = _load_sec_text_rows
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._build_card = _build_card


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    if gate4["passed"]:
        interpretation = (
            "The project-finance capacity-contract terms bundle cleared the "
            "numeric three-window replay screen, but no shared daily adapter was "
            "promoted in this run, so it remains a replay lead."
        )
        status = "positive_replay_lead_not_promoted"
    else:
        interpretation = (
            "The project-finance capacity-contract terms bundle did not clear "
            f"Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "It is not retained or promoted."
        )
        status = "rejected"
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "candidate_pool_full_stack",
            "implementation_mode": "candidate_pool_full_stack_private_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_sec_project_finance_capacity_contract_candidate_pool",
            "new_evidence_type": "structured_project_finance_capacity_contract_terms_from_primary_sec_text",
            "new_evidence_axis": (
                "Structured project-finance/capacity-contract economics extracted "
                "from SEC primary-document and exhibit text: completion guarantee "
                "plus debt-service reserve or named facility/customer/MW/non-"
                "cancelable capacity terms."
            ),
            "nearby_prior_experiments": [
                "exp-20260621-012",
                "exp-20260621-014",
                "exp-20260624-021",
                "exp-20260624-022",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "high",
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
        "brier_score": round((PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2, 6),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "predicted_failure_mode_hit": bool(
            set(PREDICTION["main_failure_modes"]) & set(gate4.get("failed_reasons") or [])
        ),
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "eligible_forms": sorted(ELIGIBLE_FORMS),
        "min_financing_amount_usd": MIN_FINANCING_AMOUNT_USD,
        "max_financing_amount_usd": MAX_FINANCING_AMOUNT_USD,
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "evidence_span_chars": EVIDENCE_SPAN_CHARS,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "max_signal_return": base.MAX_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"].pop("companyfacts_source", None)
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(TEXT_DIR)
    payload["backtest_protocol"]["execution_model"] = (
        "SEC primary-document and exhibit text is keyed by accepted_at and "
        "usable_trade_date. The parser admits rows only when a local evidence "
        "span contains project/capacity terms, finance/covenant terms, a quality "
        "contract or secured financing term, and a local dollar amount. Price "
        "confirmation uses only signal-date OHLCV. Paper entry is next available "
        "open; exit is the close 10 trading days after signal with existing costs."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "local evidence-span project/capacity terms",
        "local evidence-span finance/covenant terms",
        "local evidence-span contract-quality terms",
        "local evidence-span extracted dollar value and optional MW capacity",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping project/contract phrase lists, dollar "
            "thresholds, MW thresholds, form lists, RS/close/volume guards, top-N, "
            "hold days, cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": (
            "A valid retry needs normalized named customer/lender identity, "
            "explicit contract duration/funding certainty, covenant headroom or "
            "project drawdown milestones, closed forward replacement-value rows, "
            "or a shared daily helper proving the same parser works out of sample."
        ),
    }
    _add_full_stack_block(payload)
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
        _repo_rel(TEXT_DIR),
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
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "full_stack": payload["full_stack"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
        "gate4": payload["gate4"],
        "full_stack": payload["full_stack"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
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
    runner = Path(__file__)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(runner),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(path): base.framework._sha256(path)
            for path in [runner, OUT_JSON, LOG_JSON, TICKET_JSON, CARD_MD]
            if path.exists()
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
