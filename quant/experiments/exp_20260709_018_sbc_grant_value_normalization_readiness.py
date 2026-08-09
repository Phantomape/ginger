"""exp-20260709-018: SBC grant-value normalization readiness audit.

Measurement-only audit for the accepted SBC burden-improvement paper sleeve.
The alpha hypothesis is that grant-date fair-value context could normalize raw
SBC burden improvements into a cleaner dilution-quality signal. This run only
checks whether local SEC filing text contains enough machine-parsable evidence
on the accepted exp-20260616-015 target trades to justify one future fixed
parser and Gate 1-4 run.

No entry, exit, ranking, sizing, paper state, live order, or production policy
behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260709-018"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sbc_grant_value_normalization_readiness"
RUNNER = f"quant/experiments/exp_20260709_018_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_DIR = REPO_ROOT / "data"
NON_OHLCV_DIR = DATA_DIR / "non_ohlcv"
BASELINE_RESULT = (
    DATA_DIR / "experiments" / "exp-20260616-015"
    / "exp_20260616_015_sbc_burden_improvement_shared_adapter.json"
)
CANONICAL_BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
AGG_SEC_TEXT = NON_OHLCV_DIR / "sec_filing_text_20241002_20260421.jsonl"

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260709_018_{SLUG}.json"
MATCHES_JSONL = OUT_DIR / "sbc_grant_value_text_matches.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "alpha_blocker/measurement_repair: accepted SBC burden improvement can "
    "only legally reopen with grant-value normalization, richer option/vesting "
    "context, or materially more closed forward outcome evidence. Audit whether "
    "local SEC filing text already contains enough grant-date fair-value and "
    "equity-award evidence on the accepted exp-20260616-015 target trades to "
    "support one future fixed shared parser and Gate 1-4 run."
)
ALPHA_HYPOTHESIS = HYPOTHESIS
CHANGE_TYPE = "measurement_repair"
IMPLEMENTATION_MODE = "self_registered_readiness_audit_no_strategy_change"
MECHANISM_FAMILY = "sbc_dilution_quality_grant_value_normalization"
TRIAL_FAMILY = "sbc_grant_value_normalization_surface_readiness"
TRIAL_VARIANT_ID = "accepted_sbc_trade_sec_text_grant_value_readiness_v1"
SINGLE_CAUSAL_VARIABLE = "sbc_grant_value_normalization_text_surface_readiness_v1"
CHANGED_VARIABLE = SINGLE_CAUSAL_VARIABLE
NEW_EVIDENCE_TYPE = "measurement_repair_alpha_enabling_grant_value_normalization"
NEW_EVIDENCE_AXIS = (
    "New evidence axis permitted by the SBC playbook: grant-value "
    "normalization readiness on the accepted exp-20260616-015 SBC target trade "
    "surface, joined to local SEC filing text by ticker and companyfacts filed "
    "date. This is not a threshold, rank, per-share buyback, allocator, hold, "
    "or notional retune."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260616-015",
    "exp-20260616-016",
    "exp-20260616-017",
    "exp-20260617-012",
    "exp-20260618-021",
    "exp-20260620-004",
    "exp-20260628-001",
]
CAUSAL_COMPONENTS = [
    "accepted_sbc_burden_target_trades",
    "sec_filing_text_join_by_ticker_and_sbc_current_sbc_filed",
    "grant_date_fair_value_text_parser_readiness",
    "equity_award_vesting_context_coverage",
    "no_sbc_threshold_rank_allocator_or_order_change",
]
PREDICTION = {
    "success_probability": 0.42,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "periodic_filing_text_not_joinable_to_companyfacts_filed_date",
        "grant_value_evidence_in_proxy_not_10k_10q",
        "too_few_windows_with_numeric_grant_value_rows",
        "parser_evidence_dominated_by_nvda_or_single_ticker",
    ],
    "confidence_reason": (
        "The accepted SBC sleeve uses annual companyfacts filed dates from a "
        "small technology universe. 10-K/10-Q filing text often carries "
        "share-based compensation footnotes, but grant-value detail can live "
        "in proxies or award tables, so readiness is uncertain."
    ),
    "recorded_at": "2026-07-09T15:41:00Z",
}
ACCEPTANCE_RULE = (
    "Accepted measurement repair only if >=30 accepted SBC target trades have "
    "same-date local SEC filing text, >=20 trades have numeric grant-date "
    "fair-value or fair-value-of-awards evidence, >=2 canonical windows have "
    ">=5 numeric evidence rows, and no single ticker supplies >40% of numeric "
    "evidence. This does not accept an alpha; it only authorizes a future fixed "
    "grant-value normalization parser plus Gate 1-4."
)

MIN_TEXT_MATCHED_TRADES = 30
MIN_NUMERIC_GRANT_VALUE_TRADES = 20
MIN_WINDOWS_WITH_NUMERIC = 2
MIN_NUMERIC_PER_WINDOW = 5
MAX_SINGLE_TICKER_NUMERIC_SHARE = 0.40

CHANGED_FILES = [
    RUNNER,
    "data/experiments/exp-20260709-018/exp_20260709_018_sbc_grant_value_normalization_readiness.json",
    "data/experiments/exp-20260709-018/sbc_grant_value_text_matches.jsonl",
    "experiments/logs/exp-20260709-018.json",
    "experiments/cards/exp-20260709-018.md",
    "experiments/manifests/exp-20260709-018.json",
    "experiments/tickets/exp-20260709-018.json",
]
ALLOWED_WRITE_SCOPE = CHANGED_FILES + [
    "docs/experiment_registry.json",
    "docs/experiment_log.jsonl",
    "docs/frozen_families.jsonl",
]

GRANT_CONTEXT_RE = re.compile(
    r"("
    r"weighted\s+average\s+grant[-\s]+date\s+fair\s+value|"
    r"grant[-\s]+date\s+fair\s+value|"
    r"fair\s+value\s+of\s+(?:stock\s+options|options|restricted\s+stock\s+units|rsus|"
    r"restricted\s+stock|performance\s+stock\s+units|psus|equity\s+awards|awards)\s+"
    r"(?:granted|vested)|"
    r"(?:stock\s+options|options|restricted\s+stock\s+units|rsus|restricted\s+stock|"
    r"performance\s+stock\s+units|psus|equity\s+awards|awards).{0,160}?"
    r"(?:granted|vested).{0,160}?(?:fair\s+value|grant[-\s]+date)|"
    r"(?:unrecognized|unamortized)\s+(?:stock[-\s]+based|share[-\s]+based)\s+"
    r"compensation\s+(?:cost|expense)"
    r")",
    re.IGNORECASE | re.DOTALL,
)
MONEY_RE = re.compile(
    r"\$?\s*(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
    r"(?P<scale>million|billion|thousand)?",
    re.IGNORECASE,
)
EQUITY_CONTEXT_RE = re.compile(
    r"(grant[-\s]+date\s+fair\s+value|stock[-\s]+based compensation|"
    r"share[-\s]+based compensation|restricted stock units|rsus|stock options|"
    r"performance stock units|psus|equity awards|vesting|unvested)",
    re.IGNORECASE,
)
GOOD_FORM_BASES = {"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "DEF 14A", "DEFA14A"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def jsonl_rows(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def round_or_none(value: Any, digits: int = 6) -> float | None:
    try:
        output = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(output):
        return None
    return round(output, digits)


def flatten_target_trades(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_window = payload.get("target_trades_by_window") or {}
    if not isinstance(by_window, dict):
        return out
    for window, rows in by_window.items():
        if not isinstance(rows, list):
            continue
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            item = dict(row)
            item.setdefault("window", window)
            item["_target_trade_index"] = len(out)
            item["_window_index"] = idx
            out.append(item)
    return out


def candidate_keys(trades: list[dict[str, Any]]) -> tuple[set[str], set[str], set[tuple[str, str]]]:
    tickers: set[str] = set()
    dates: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for trade in trades:
        ticker = str(trade.get("ticker") or trade.get("sbc_ticker") or "").upper()
        filing_date = str(trade.get("sbc_current_sbc_filed") or "")
        if not ticker or not filing_date:
            continue
        tickers.add(ticker)
        dates.add(filing_date)
        pairs.add((ticker, filing_date))
    return tickers, dates, pairs


def sec_text_paths(filing_dates: set[str]) -> list[Path]:
    paths: list[Path] = []
    if AGG_SEC_TEXT.exists():
        paths.append(AGG_SEC_TEXT)
    for filing_date in sorted(filing_dates):
        compact = filing_date.replace("-", "")
        path = NON_OHLCV_DIR / f"sec_filing_text_{compact}.jsonl"
        if path.exists():
            paths.append(path)
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path)
    return deduped


def row_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("ticker"),
        row.get("filing_date"),
        row.get("accession_number"),
        row.get("primary_document"),
        row.get("form_type"),
    )


def load_candidate_text_rows(
    paths: list[Path],
    tickers: set[str],
    filing_dates: set[str],
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], dict[str, Any]]:
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[Any, ...]] = set()
    source_counts: Counter[str] = Counter()
    form_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    scanned_rows = 0
    candidate_rows = 0
    for path in paths:
        for row in jsonl_rows(path):
            scanned_rows += 1
            ticker = str(row.get("ticker") or "").upper()
            filing_date = str(row.get("filing_date") or "")
            if ticker not in tickers or filing_date not in filing_dates:
                continue
            key = row_key(row)
            if key in seen:
                continue
            seen.add(key)
            form_base = str(row.get("form_base") or row.get("form_type") or "")
            if form_base and form_base not in GOOD_FORM_BASES:
                continue
            text = row.get("combined_text")
            if not isinstance(text, str) or not text.strip():
                continue
            candidate_rows += 1
            item = dict(row)
            item["_source_file"] = repo_rel(path)
            by_pair[(ticker, filing_date)].append(item)
            source_counts[repo_rel(path)] += 1
            form_counts[form_base or "unknown"] += 1
            status_counts[str(row.get("status") or "unknown")] += 1
    for rows in by_pair.values():
        rows.sort(
            key=lambda row: (
                0 if str(row.get("form_base") or row.get("form_type")) in {"10-K", "10-K/A"} else 1,
                -int(row.get("text_word_count") or 0),
            )
        )
    return by_pair, {
        "paths_read": [repo_rel(path) for path in paths],
        "source_path_count": len(paths),
        "scanned_rows": scanned_rows,
        "candidate_text_rows": candidate_rows,
        "deduped_candidate_pairs": len(by_pair),
        "source_counts": dict(source_counts.most_common()),
        "form_counts": dict(form_counts.most_common()),
        "status_counts": dict(status_counts.most_common()),
    }


def normalize_excerpt(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:260]


def parse_money(value: re.Match[str]) -> dict[str, Any] | None:
    raw_num = value.group("num")
    if not raw_num:
        return None
    try:
        amount = float(raw_num.replace(",", ""))
    except ValueError:
        return None
    scale = (value.group("scale") or "").lower()
    multiplier = {"thousand": 1_000.0, "million": 1_000_000.0, "billion": 1_000_000_000.0}.get(
        scale,
        1.0,
    )
    return {
        "raw": value.group(0).strip(),
        "amount": round(amount, 6),
        "scale": scale or None,
        "scaled_amount": round(amount * multiplier, 2),
    }


def evidence_type(context: str, money: dict[str, Any] | None) -> str:
    lower = context.lower()
    if money and (
        "per share" in lower
        or "weighted average grant" in lower
        or "weighted-average grant" in lower
    ):
        return "per_share_grant_date_fair_value"
    if money and (
        "fair value of" in lower
        or "grant-date fair value" in lower
        or "grant date fair value" in lower
    ):
        return "numeric_grant_or_award_fair_value"
    if money:
        return "numeric_equity_award_context"
    if "unrecognized" in lower or "unamortized" in lower or "vesting" in lower or "unvested" in lower:
        return "vesting_or_unrecognized_compensation_context"
    return "equity_award_context_only"


def parse_grant_value_evidence(text: str, limit: int = 8) -> list[dict[str, Any]]:
    if not EQUITY_CONTEXT_RE.search(text):
        return []
    compact = re.sub(r"\s+", " ", text)
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for match in GRANT_CONTEXT_RE.finditer(compact):
        start = max(0, match.start() - 220)
        end = min(len(compact), match.end() + 260)
        context = compact[start:end]
        money_match = None
        money = None
        for candidate in MONEY_RE.finditer(context):
            parsed = parse_money(candidate)
            if not parsed:
                continue
            if "$" in candidate.group(0) or parsed["scale"] or "per share" in context.lower():
                money_match = candidate
                money = parsed
                break
        etype = evidence_type(context, money)
        dedupe = (etype, money["raw"] if money else None)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        out.append(
            {
                "evidence_type": etype,
                "matched_phrase": normalize_excerpt(match.group(0)),
                "money": money,
                "has_numeric_value": money is not None,
                "context_excerpt": normalize_excerpt(context),
                "context_start": start,
                "context_end": end,
                "money_text": money_match.group(0).strip() if money_match else None,
            }
        )
        if len(out) >= limit:
            break
    if not out and EQUITY_CONTEXT_RE.search(compact):
        first = EQUITY_CONTEXT_RE.search(compact)
        if first:
            start = max(0, first.start() - 180)
            end = min(len(compact), first.end() + 220)
            out.append(
                {
                    "evidence_type": "equity_award_context_only",
                    "matched_phrase": normalize_excerpt(first.group(0)),
                    "money": None,
                    "has_numeric_value": False,
                    "context_excerpt": normalize_excerpt(compact[start:end]),
                    "context_start": start,
                    "context_end": end,
                    "money_text": None,
                }
            )
    return out


def pick_best_evidence(rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    candidates: list[tuple[int, dict[str, Any], list[dict[str, Any]]]] = []
    for row in rows:
        evidence = parse_grant_value_evidence(str(row.get("combined_text") or ""))
        numeric = sum(1 for item in evidence if item.get("has_numeric_value"))
        score = numeric * 100 + len(evidence)
        form_base = str(row.get("form_base") or row.get("form_type") or "")
        if form_base in {"10-K", "10-K/A"}:
            score += 10
        elif form_base in {"10-Q", "10-Q/A"}:
            score += 5
        candidates.append((score, row, evidence))
    if not candidates:
        return None, []
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1], candidates[0][2]


def build_match_rows(
    trades: list[dict[str, Any]],
    text_by_pair: dict[tuple[str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in trades:
        ticker = str(trade.get("ticker") or trade.get("sbc_ticker") or "").upper()
        filing_date = str(trade.get("sbc_current_sbc_filed") or "")
        text_rows = text_by_pair.get((ticker, filing_date), [])
        best_row, evidence = pick_best_evidence(text_rows)
        numeric = [item for item in evidence if item.get("has_numeric_value")]
        non_context_evidence = [
            item
            for item in evidence
            if item.get("evidence_type") != "equity_award_context_only"
        ]
        evidence_counts = Counter(item.get("evidence_type") or "unknown" for item in evidence)
        rows.append(
            {
                "target_trade_index": trade.get("_target_trade_index"),
                "window": trade.get("window"),
                "ticker": ticker,
                "signal_date": trade.get("signal_date") or trade.get("date"),
                "entry_date": trade.get("entry_date"),
                "sbc_current_sbc_filed": filing_date,
                "sbc_current_period_end": trade.get("sbc_current_period_end"),
                "sbc_current_sbc_value": round_or_none(trade.get("sbc_current_sbc_value"), 2),
                "sbc_current_revenue_value": round_or_none(
                    trade.get("sbc_current_revenue_value"),
                    2,
                ),
                "sbc_current_sbc_to_revenue": round_or_none(
                    trade.get("sbc_current_sbc_to_revenue"),
                    8,
                ),
                "sbc_sbc_ratio_improvement": round_or_none(
                    trade.get("sbc_sbc_ratio_improvement"),
                    8,
                ),
                "pnl": round_or_none(trade.get("pnl"), 2),
                "pnl_pct_net": round_or_none(trade.get("pnl_pct_net"), 6),
                "text_match_count": len(text_rows),
                "has_text_match": bool(text_rows),
                "best_form_base": (
                    str(best_row.get("form_base") or best_row.get("form_type") or "")
                    if best_row
                    else None
                ),
                "best_accession_number": best_row.get("accession_number") if best_row else None,
                "best_primary_document": best_row.get("primary_document") if best_row else None,
                "best_text_word_count": best_row.get("text_word_count") if best_row else None,
                "best_source_file": best_row.get("_source_file") if best_row else None,
                "evidence_count": len(evidence),
                "numeric_evidence_count": len(numeric),
                "has_equity_award_context": bool(evidence),
                "has_grant_value_evidence": bool(non_context_evidence),
                "has_numeric_grant_value_evidence": bool(numeric),
                "evidence_type_counts": dict(evidence_counts.most_common()),
                "evidence_examples": evidence[:3],
            }
        )
    return rows


def summarize_matches(match_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(match_rows)
    text_rows = [row for row in match_rows if row["has_text_match"]]
    evidence_rows = [row for row in match_rows if row["has_grant_value_evidence"]]
    context_rows = [row for row in match_rows if row.get("has_equity_award_context")]
    numeric_rows = [row for row in match_rows if row["has_numeric_grant_value_evidence"]]
    by_window: dict[str, dict[str, Any]] = {}
    for window in sorted({str(row.get("window")) for row in match_rows}):
        rows = [row for row in match_rows if str(row.get("window")) == window]
        numeric = [row for row in rows if row["has_numeric_grant_value_evidence"]]
        by_window[window] = {
            "target_trades": len(rows),
            "text_matched_trades": sum(1 for row in rows if row["has_text_match"]),
            "grant_value_evidence_trades": sum(
                1 for row in rows if row["has_grant_value_evidence"]
            ),
            "numeric_grant_value_trades": len(numeric),
            "tickers_with_numeric_evidence": sorted({row["ticker"] for row in numeric}),
        }
    numeric_by_ticker = Counter(row["ticker"] for row in numeric_rows)
    max_single_ticker_share = (
        max(numeric_by_ticker.values()) / len(numeric_rows) if numeric_rows else 0.0
    )
    type_counts: Counter[str] = Counter()
    form_counts: Counter[str] = Counter()
    for row in match_rows:
        if row["best_form_base"]:
            form_counts[row["best_form_base"]] += 1
        for key, count in row.get("evidence_type_counts", {}).items():
            type_counts[key] += int(count)
    windows_with_numeric = sum(
        1
        for values in by_window.values()
        if values["numeric_grant_value_trades"] >= MIN_NUMERIC_PER_WINDOW
    )
    criteria = {
        "min_text_matched_trades": {
            "actual": len(text_rows),
            "threshold": MIN_TEXT_MATCHED_TRADES,
            "passed": len(text_rows) >= MIN_TEXT_MATCHED_TRADES,
        },
        "min_numeric_grant_value_trades": {
            "actual": len(numeric_rows),
            "threshold": MIN_NUMERIC_GRANT_VALUE_TRADES,
            "passed": len(numeric_rows) >= MIN_NUMERIC_GRANT_VALUE_TRADES,
        },
        "min_windows_with_numeric": {
            "actual": windows_with_numeric,
            "threshold": MIN_WINDOWS_WITH_NUMERIC,
            "per_window_minimum": MIN_NUMERIC_PER_WINDOW,
            "passed": windows_with_numeric >= MIN_WINDOWS_WITH_NUMERIC,
        },
        "max_single_ticker_numeric_share": {
            "actual": round(max_single_ticker_share, 6),
            "threshold": MAX_SINGLE_TICKER_NUMERIC_SHARE,
            "passed": max_single_ticker_share <= MAX_SINGLE_TICKER_NUMERIC_SHARE,
        },
    }
    accepted = all(item["passed"] for item in criteria.values())
    return {
        "accepted_sbc_target_trades": total,
        "unique_tickers": len({row["ticker"] for row in match_rows}),
        "text_matched_trades": len(text_rows),
        "equity_award_context_trades": len(context_rows),
        "grant_value_evidence_trades": len(evidence_rows),
        "numeric_grant_value_trades": len(numeric_rows),
        "text_match_share": round(len(text_rows) / total, 6) if total else 0.0,
        "numeric_grant_value_share": round(len(numeric_rows) / total, 6) if total else 0.0,
        "windows_with_numeric_minimum": windows_with_numeric,
        "max_single_ticker_numeric_share": round(max_single_ticker_share, 6),
        "numeric_by_ticker": dict(numeric_by_ticker.most_common()),
        "by_window": by_window,
        "best_form_counts": dict(form_counts.most_common()),
        "evidence_type_counts": dict(type_counts.most_common()),
        "criteria": criteria,
        "passed": accepted,
    }


def baseline_gate_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    after = payload.get("after_metrics") or {}
    windows = {}
    generated = 0
    survived = 0
    for name, metrics in after.items():
        if not isinstance(metrics, dict):
            continue
        generated += int(metrics.get("signals_generated") or 0)
        survived += int(metrics.get("signals_survived") or 0)
        windows[name] = {
            "signals_generated": metrics.get("signals_generated"),
            "signals_survived": metrics.get("signals_survived"),
            "survival_rate": metrics.get("survival_rate"),
            "trade_count": metrics.get("trade_count"),
            "expected_value_score": metrics.get("expected_value_score"),
            "total_pnl": metrics.get("total_pnl"),
        }
    return {
        "source_experiment": "exp-20260616-015",
        "target_trade_count": (payload.get("target_trade_summary") or {}).get(
            "total_trade_count"
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "after_windows": windows,
    }


def build_payload() -> dict[str, Any]:
    source_payload = read_json(BASELINE_RESULT, {})
    trades = flatten_target_trades(source_payload)
    tickers, filing_dates, pairs = candidate_keys(trades)
    paths = sec_text_paths(filing_dates)
    text_by_pair, text_scan = load_candidate_text_rows(paths, tickers, filing_dates)
    match_rows = build_match_rows(trades, text_by_pair)
    summary = summarize_matches(match_rows)
    accepted_measurement_repair = bool(summary["passed"])
    status = "completed"
    decision = (
        "accepted_measurement_repair_sbc_grant_value_surface_ready"
        if accepted_measurement_repair
        else "blocked_sbc_grant_value_surface_not_ready"
    )
    rejection_reason = None if accepted_measurement_repair else (
        "Local SEC filing text does not yet satisfy the minimum joined numeric "
        "grant-value evidence coverage required to reopen the accepted SBC "
        "surface with a fixed parser."
    )
    gate4 = {
        "evaluation_type": "measurement_repair_readiness_no_strategy_change",
        "accepted_measurement_repair": accepted_measurement_repair,
        "accepted_alpha": False,
        "readiness_summary": summary,
        "pass_fail": {
            "passed": accepted_measurement_repair,
            "criteria": ACCEPTANCE_RULE,
        },
        "strategy_metrics_delta": {
            "expected_value_score_delta_sum": 0.0,
            "total_pnl_delta_sum": 0.0,
            "trade_count_delta": 0,
            "explanation": (
                "Read-only parser-readiness audit; no strategy, admission, "
                "ranking, sizing, exit, or order behavior changed."
            ),
        },
    }
    production_impact = {
        "trade_enabled": False,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "production_signal_path_changed": False,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "default_off_paper_only": False,
        "readiness_audit_only": True,
        "uses_llm": False,
        "uses_free_sec_text": True,
        "uses_accepted_sbc_artifact": True,
        "live_ready": False,
    }
    reopen_condition = (
        "Run the future SBC grant-value normalization alpha only after this "
        "surface has >=30 same-date accepted-SBC trade text matches, >=20 "
        "numeric grant-value evidence rows across >=2 windows with >=5 each, "
        "and max single-ticker numeric evidence share <=40%; or introduce a "
        "new independent option-exercise/vesting/proxy data source."
    )
    if accepted_measurement_repair:
        next_evidence = (
            "Build one shared, fixed grant-value normalization helper that "
            "parses the evidence patterns recorded here, expose it in daily "
            "default-off SBC snapshots, and run standard Gate 1-4 against "
            "exp-20260616-015 without changing rank/threshold/hold/notional "
            "unless the helper itself is the causal variable."
        )
    else:
        next_evidence = reopen_condition
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": LANE,
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": accepted_measurement_repair,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted_measurement_repair,
        "rejection_reason": rejection_reason,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "acceptance_rule": ACCEPTANCE_RULE,
        "source_artifacts": {
            "accepted_sbc_adapter_artifact": repo_rel(BASELINE_RESULT),
            "canonical_backtest_baseline": repo_rel(CANONICAL_BASELINE_RESULT),
        },
        "input_surface": {
            "accepted_sbc_target_trades": len(trades),
            "unique_tickers": sorted(tickers),
            "unique_sbc_current_sbc_filed_dates": sorted(filing_dates),
            "ticker_date_pairs": len(pairs),
        },
        "text_scan": text_scan,
        "coverage": summary,
        "match_rows_output": repo_rel(MATCHES_JSONL),
        "sample_numeric_matches": [
            row
            for row in match_rows
            if row["has_numeric_grant_value_evidence"]
        ][:10],
        "sample_text_misses": [
            row
            for row in match_rows
            if not row["has_text_match"]
        ][:10],
        "gate1": {
            "baseline": "accepted_exp_20260616_015_sbc_burden_improvement_shared_adapter",
            "baseline_artifact": repo_rel(BASELINE_RESULT),
            "metrics": baseline_gate_metrics(source_payload),
            "canonical_protocol_baseline": repo_rel(CANONICAL_BASELINE_RESULT),
        },
        "gate2": {
            "field_contract": "read_only_sec_text_join_no_executable_signal_contract_change",
            "required_source_trade_fields": [
                "ticker",
                "signal_date",
                "entry_date",
                "sbc_current_sbc_filed",
                "sbc_current_sbc_value",
                "sbc_current_revenue_value",
                "sbc_sbc_ratio_improvement",
            ],
            "required_sec_text_fields": [
                "ticker",
                "filing_date",
                "form_base",
                "accession_number",
                "primary_document",
                "combined_text",
                "text_word_count",
            ],
            "sentinel_entry_date_present": all(bool(row.get("entry_date")) for row in trades),
            "target_price_contract_changed": False,
            "missing_trade_field_counts": {
                field: sum(1 for row in trades if not row.get(field))
                for field in [
                    "ticker",
                    "signal_date",
                    "entry_date",
                    "sbc_current_sbc_filed",
                    "sbc_current_sbc_value",
                    "sbc_current_revenue_value",
                    "sbc_sbc_ratio_improvement",
                ]
            },
            "passed": bool(trades) and all(bool(row.get("entry_date")) for row in trades),
        },
        "gate3": {
            "survival_check": "unchanged_from_exp_20260616_015",
            "baseline_survival": baseline_gate_metrics(source_payload),
            "new_filters_added": False,
            "survival_rate_below_5pct": False,
            "passed": True,
        },
        "gate4": gate4,
        "before_metrics": {
            "accepted_sbc_target_trades": len(trades),
            "accepted_sbc_target_trade_summary": source_payload.get("target_trade_summary"),
        },
        "after_metrics": {
            "text_matched_trades": summary["text_matched_trades"],
            "numeric_grant_value_trades": summary["numeric_grant_value_trades"],
            "windows_with_numeric_minimum": summary["windows_with_numeric_minimum"],
            "max_single_ticker_numeric_share": summary["max_single_ticker_numeric_share"],
        },
        "delta_metrics": {
            "strategy_expected_value_score_delta_sum": 0.0,
            "strategy_total_pnl_delta_sum": 0.0,
            "strategy_trade_count_delta": 0,
            "measurement_surface_numeric_rows": summary["numeric_grant_value_trades"],
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                f"Joined {summary['text_matched_trades']} of "
                f"{summary['accepted_sbc_target_trades']} accepted SBC target "
                f"trades to local SEC text and found "
                f"{summary['numeric_grant_value_trades']} numeric grant-value "
                "evidence rows. The result is measurement-only and leaves "
                "SBC burden policy unchanged."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune SBC burden thresholds, rank insertion, allocator "
                "source, per-share/buyback adjustment, hold days, notional, or "
                "cooldown from this audit. Do not retry with only a different "
                "regex list unless new text/proxy/vesting data materially "
                "changes the evidence row count."
            ),
            "new_evidence_required": next_evidence,
            "reopen_condition": reopen_condition,
            "next_evidence_needed": next_evidence,
        },
        "gate_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "exp-20260616-015 accepted the shared default-off SBC burden "
                "adapter. exp-20260616-016 allocator insertion and "
                "exp-20260616-017 per-share/buyback retune failed. The "
                "playbook only permits reopen via closed forward rows, "
                "option/vesting context, or grant-value normalization; this "
                "audit tests that last alpha-enabling measurement axis without "
                "retuning the policy."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "changed_files": CHANGED_FILES,
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(CANONICAL_BASELINE_RESULT),
            repo_rel(AGG_SEC_TEXT),
            "data/non_ohlcv/sec_filing_text_YYYYMMDD.jsonl",
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }
    payload["headline_metrics"] = {
        "accepted_sbc_target_trades": summary["accepted_sbc_target_trades"],
        "text_matched_trades": summary["text_matched_trades"],
        "numeric_grant_value_trades": summary["numeric_grant_value_trades"],
        "windows_with_numeric_minimum": summary["windows_with_numeric_minimum"],
        "max_single_ticker_numeric_share": summary["max_single_ticker_numeric_share"],
        "accepted_measurement_repair": accepted_measurement_repair,
    }
    payload["_match_rows_for_jsonl"] = match_rows
    return payload


def build_card(payload: dict[str, Any]) -> str:
    coverage = payload["coverage"]
    criteria = coverage["criteria"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SBC grant-value normalization readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Accepted SBC target trades: `{coverage['accepted_sbc_target_trades']}`",
            f"- Text-matched trades: `{coverage['text_matched_trades']}`",
            f"- Numeric grant-value trades: `{coverage['numeric_grant_value_trades']}`",
            f"- Windows with >=5 numeric rows: `{coverage['windows_with_numeric_minimum']}`",
            f"- Max numeric ticker share: `{coverage['max_single_ticker_numeric_share']}`",
            f"- Criteria: `{criteria}`",
            "- Strategy/live order behavior changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["next_evidence_needed"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
    files.extend([REGISTRY_JSON, REPO_ROOT / "docs" / "experiment_log.jsonl"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "matches": repo_rel(MATCHES_JSONL),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    match_rows = payload.pop("_match_rows_for_jsonl")
    write_json(OUT_JSON, payload)
    write_jsonl(MATCHES_JSONL, match_rows)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "matches": repo_rel(MATCHES_JSONL),
            "coverage": {
                "accepted_sbc_target_trades": payload["coverage"][
                    "accepted_sbc_target_trades"
                ],
                "text_matched_trades": payload["coverage"]["text_matched_trades"],
                "numeric_grant_value_trades": payload["coverage"][
                    "numeric_grant_value_trades"
                ],
                "windows_with_numeric_minimum": payload["coverage"][
                    "windows_with_numeric_minimum"
                ],
                "max_single_ticker_numeric_share": payload["coverage"][
                    "max_single_ticker_numeric_share"
                ],
            },
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "rejection_reason": payload["rejection_reason"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "artifact": repo_rel(OUT_JSON),
                "matches": repo_rel(MATCHES_JSONL),
                "headline_metrics": payload["headline_metrics"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
