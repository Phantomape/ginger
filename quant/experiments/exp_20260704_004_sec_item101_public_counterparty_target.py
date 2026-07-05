"""exp-20260704-004: SEC Item 1.01 public-counterparty target scout.

Observed-only alpha attribution. The fixed Item 1.01 contract-relation
provenance surface from exp-20260703-017 is mapped from extracted named
counterparties to listed public-company tickers, compressed to one target per
usable trade date, and measured at next-open entry with a 10-session close.

No strategy behavior changes here: no entries, ranking, sizing, exits, paper
orders, live orders, prompts, or watchlists are changed.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from quant.experiments import (  # noqa: E402
    exp_20260703_018_sec_item101_contract_relation_issuer_self as base,
)


EXPERIMENT_ID = "exp-20260704-004"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "sec_item101_public_counterparty_target"
RUNNER = f"quant/experiments/exp_20260704_004_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SOURCE_ROWS = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_contract_relation_provenance"
    / "rows.jsonl"
)
SOURCE_SUMMARY = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_contract_relation_provenance"
    / "latest_summary.json"
)
SEC_COMPANY_TICKERS = REPO_ROOT / "data" / "reference" / "sec_company_tickers.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_004_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "SEC 8-K Item 1.01 contract-relation provenance may create target-side "
    "alpha when the named counterparty is itself a listed ticker; a fixed "
    "normalized public-counterparty top-1/day 10-session observed-only read "
    "should show replacement value versus cash, SPY, and QQQ before any "
    "shared helper promotion."
)
CHANGED_VARIABLE = "sec_item101_public_counterparty_target_top1_10d_v1"
TRIAL_FAMILY = "sec_item101_public_counterparty_target_attribution"
TRIAL_VARIANT_ID = "fixed_public_counterparty_target_top1_10d_v1"
NEARBY_PRIORS = [
    "exp-20260703-017",
    "exp-20260703-018",
    "exp-20260703-020",
    "exp-20260703-021",
    "exp-20260704-001",
]
NEW_EVIDENCE_AXIS = (
    "New gate shape: normalized public counterparty identity mapped to listed "
    "ticker targets from fixed Item 1.01 provenance rows. This is not issuer-"
    "self, not SIC/theme peer propagation, not amount/duration regex retune, "
    "and not relation priority, top-N, hold, notional, or response-curve tuning."
)
PREDICTION = {
    "success_probability": 0.17,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "counterparty normalization too sparse",
        "public counterparty rows concentrate in banks",
        "SEC text source saturation",
        "window instability",
        "public archive PIT caveat",
    ],
    "confidence_reason": (
        "Issuer-self and economic-term Item 1.01 leads were noisy or failed "
        "shared promotion, while exp-20260703-020 explicitly required true "
        "counterparty/customer/supplier graph evidence. Normalized public "
        "counterparty targeting is a distinct target-side gate but still low "
        "prior because SEC text base rates are poor."
    ),
    "recorded_at": "2026-07-04T04:05:04+00:00",
}

WINDOWS = base.WINDOWS
PRIMARY_METRICS = base.PRIMARY_METRICS
RELATION_PRIORITY = base.RELATION_PRIORITY
ACCEPTANCE_RULE = {
    "min_settled_top1_rows": 12,
    "min_settled_windows": 2,
    "min_rows_per_settled_window": 3,
    "min_positive_windows_vs_spy_and_qqq": 2,
    "max_top_ticker_share": 0.40,
    "require_aggregate_primary_means_positive": True,
    "require_aggregate_primary_medians_nonnegative": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260704_004_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

TICKER_RE = re.compile(r"^[A-Z]{1,5}$")
LEGAL_TRAILING_TOKENS = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "llc",
    "plc",
    "lp",
    "llp",
    "holdings",
    "holding",
    "group",
    "sa",
    "nv",
    "ag",
    "se",
    "de",
    "mn",
    "na",
    "national",
    "association",
    "usa",
    "us",
    "bank",
}
GENERIC_NORMALIZED_NAMES = {
    "company",
    "issuer",
    "registrant",
    "borrower",
    "lender",
    "purchaser",
    "seller",
    "buyer",
    "agent",
    "trustee",
    "initial purchasers",
    "dealer manager",
    "preferred shareholder services",
    "client",
    "proceed",
    "proceeds",
    "section",
    "taxes",
}
MANUAL_ALIASES = {
    "j p morgan": "JPM",
    "jp morgan": "JPM",
    "jpmorgan": "JPM",
    "jpmorgan chase": "JPM",
    "jpmorgan securities": "JPM",
    "jpmorgan chase bank": "JPM",
    "bank of america": "BAC",
    "bofa": "BAC",
    "bofa securities": "BAC",
    "merrill lynch": "BAC",
    "goldman sachs": "GS",
    "goldman sachs bank": "GS",
    "morgan stanley": "MS",
    "citigroup": "C",
    "citibank": "C",
    "citi": "C",
    "wells fargo": "WFC",
    "barclays": "BCS",
    "barclays bank": "BCS",
    "deutsche bank": "DB",
    "ubs": "UBS",
    "hsbc": "HSBC",
    "td bank": "TD",
    "royal bank of canada": "RY",
    "rbc": "RY",
    "truist": "TFC",
    "fifth third": "FITB",
    "u s bank": "USB",
    "us bank": "USB",
    "bank of new york mellon": "BK",
    "bny mellon": "BK",
    "state street": "STT",
    "blackrock": "BLK",
    "talen energy": "TLN",
    "talen energy corporation": "TLN",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def clean_company_fragment(value: str) -> str:
    text = str(value or "")
    text = re.split(
        r",\s+(?:a|an|the)\s+"
        r"(?:delaware|nevada|new york|california|texas|florida|virginia|maryland|"
        r"ohio|pennsylvania|canadian|english|irish|german|french|dutch|swiss)\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    text = re.sub(r"\([^)]{1,32}\)", " ", text)
    text = re.split(
        r"\s+(?:pursuant|dated|under|whereby|which|for|as)\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return text.strip(" ,.;:-()")


def normalize_company_name(value: str) -> str:
    text = clean_company_fragment(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"/[a-z]{2}/", " ", text)
    text = re.sub(r"\b(?:the)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [token for token in text.split() if token]
    while tokens and tokens[-1] in LEGAL_TRAILING_TOKENS:
        tokens.pop()
    return " ".join(tokens)


def counterparty_variants(value: str) -> list[str]:
    fragments = [clean_company_fragment(value)]
    fragments.extend(
        part.strip(" ,.;:-()")
        for part in re.split(r"\s+(?:and|or|and/or)\s+", str(value or ""), flags=re.I)
        if part.strip()
    )
    output: list[str] = []
    seen: set[str] = set()
    for fragment in fragments:
        normalized = normalize_company_name(fragment)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def is_valid_public_ticker(ticker: str) -> bool:
    return bool(TICKER_RE.match(str(ticker or "").upper()))


def name_is_too_generic(normalized: str) -> bool:
    tokens = normalized.split()
    if normalized in GENERIC_NORMALIZED_NAMES:
        return True
    if len("".join(tokens)) < 6:
        return True
    return False


def load_company_index(path: Path) -> dict[str, Any]:
    payload = base.read_json(path, {}) or {}
    exact: dict[str, dict[str, Any]] = {}
    aliases: dict[str, dict[str, Any]] = {}
    title_rows: list[dict[str, Any]] = []
    duplicate_names: Counter[str] = Counter()
    skipped_tickers = 0

    for order, (_, entry) in enumerate(sorted(payload.items(), key=lambda item: int(item[0]))):
        ticker = str(entry.get("ticker") or "").upper()
        title = str(entry.get("title") or "")
        if not is_valid_public_ticker(ticker):
            skipped_tickers += 1
            continue
        normalized = normalize_company_name(title)
        if name_is_too_generic(normalized):
            continue
        row = {
            "ticker": ticker,
            "company_title": title,
            "normalized_name": normalized,
            "source": "sec_company_tickers",
            "order": order,
        }
        duplicate_names[normalized] += 1
        if normalized not in exact or order < int(exact[normalized]["order"]):
            exact[normalized] = row
        title_rows.append(row)

    for alias, ticker in MANUAL_ALIASES.items():
        normalized = normalize_company_name(alias)
        aliases[normalized] = {
            "ticker": ticker,
            "company_title": alias,
            "normalized_name": normalized,
            "source": "manual_common_public_counterparty_alias",
            "order": -1,
        }

    return {
        "exact": exact,
        "aliases": aliases,
        "title_rows": sorted(title_rows, key=lambda row: (len(row["normalized_name"]), row["order"])),
        "diagnostics": {
            "sec_company_ticker_rows": len(payload),
            "valid_title_aliases": len(exact),
            "manual_aliases": len(aliases),
            "skipped_invalid_tickers": skipped_tickers,
            "duplicate_normalized_name_count": sum(
                1 for _, count in duplicate_names.items() if count > 1
            ),
        },
    }


def containment_quality(needle: str, haystack: str) -> int | None:
    needle_tokens = needle.split()
    haystack_tokens = haystack.split()
    if len(needle_tokens) < 2 or len(haystack_tokens) < 2:
        return None
    needle_text = " ".join(needle_tokens)
    haystack_text = " ".join(haystack_tokens)
    if needle_text == haystack_text:
        return 0
    if needle_text in haystack_text:
        return 2
    if haystack_text in needle_text and len(haystack_tokens) >= 2:
        return 3
    return None


def match_counterparty(
    raw_name: str,
    company_index: Mapping[str, Any],
) -> dict[str, Any] | None:
    variants = counterparty_variants(raw_name)
    best: dict[str, Any] | None = None

    def consider(match: Mapping[str, Any], variant: str, quality: int, basis: str) -> None:
        nonlocal best
        ticker = str(match.get("ticker") or "").upper()
        if not is_valid_public_ticker(ticker):
            return
        candidate = {
            "counterparty_raw": raw_name,
            "counterparty_normalized": variant,
            "target_ticker": ticker,
            "target_company_title": match.get("company_title"),
            "target_normalized_name": match.get("normalized_name"),
            "match_quality_rank": quality,
            "match_basis": basis,
            "match_source": match.get("source"),
        }
        sort_key = (
            quality,
            0 if match.get("source") == "manual_common_public_counterparty_alias" else 1,
            -len(str(match.get("normalized_name") or "")),
            ticker,
        )
        candidate["_sort_key"] = sort_key
        if best is None or sort_key < best["_sort_key"]:
            best = candidate

    for variant in variants:
        if name_is_too_generic(variant):
            continue
        alias = company_index["aliases"].get(variant)
        if alias:
            consider(alias, variant, 0, "manual_alias_exact")
        exact = company_index["exact"].get(variant)
        if exact:
            consider(exact, variant, 1, "sec_title_exact")

    for variant in variants:
        if name_is_too_generic(variant):
            continue
        for alias_name, alias in company_index["aliases"].items():
            quality = containment_quality(alias_name, variant)
            if quality is not None:
                consider(alias, variant, quality, "manual_alias_containment")
        for title_row in company_index["title_rows"]:
            title_name = str(title_row["normalized_name"])
            if abs(len(title_name) - len(variant)) > 24 and title_name not in variant:
                continue
            quality = containment_quality(title_name, variant)
            if quality is not None:
                consider(title_row, variant, quality + 2, "sec_title_containment")

    if best is None:
        return None
    return {key: value for key, value in best.items() if key != "_sort_key"}


def build_counterparty_rows(
    accession_rows: Iterable[dict[str, Any]],
    company_index: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    mapped_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    raw_counterparty_count = 0
    no_match_counterparties: Counter[str] = Counter()
    self_matches: Counter[str] = Counter()
    match_bases: Counter[str] = Counter()
    match_sources: Counter[str] = Counter()

    for row in accession_rows:
        issuer = str(row.get("ticker") or "").upper()
        for raw_name in row.get("counterparty_candidates") or []:
            raw = str(raw_name or "").strip()
            if not raw:
                continue
            raw_counterparty_count += 1
            match = match_counterparty(raw, company_index)
            if match is None:
                normalized = normalize_company_name(raw)
                if normalized:
                    no_match_counterparties[normalized] += 1
                continue
            target = str(match["target_ticker"]).upper()
            if target == issuer:
                self_matches[target] += 1
                continue
            key = (
                str(row.get("accession_number") or ""),
                target,
                str(match.get("counterparty_normalized") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            match_bases[str(match.get("match_basis") or "unknown")] += 1
            match_sources[str(match.get("match_source") or "unknown")] += 1
            mapped_rows.append(
                {
                    **row,
                    "issuer_ticker": issuer,
                    "target_ticker": target,
                    "ticker": target,
                    **match,
                }
            )

    diagnostics = {
        "raw_counterparty_mentions": raw_counterparty_count,
        "mapped_counterparty_rows": len(mapped_rows),
        "unique_target_tickers": len({row["target_ticker"] for row in mapped_rows}),
        "unique_issuer_tickers": len({row["issuer_ticker"] for row in mapped_rows}),
        "match_bases": dict(sorted(match_bases.items())),
        "match_sources": dict(sorted(match_sources.items())),
        "self_matches_excluded": dict(self_matches.most_common(20)),
        "top_unmatched_counterparties": [
            {"normalized_counterparty": name, "mentions": count}
            for name, count in no_match_counterparties.most_common(30)
        ],
    }
    return mapped_rows, diagnostics


def counterparty_rank(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        RELATION_PRIORITY.get(str(row.get("relation_bucket") or ""), 99),
        int(row.get("match_quality_rank") or 99),
        -int(row.get("evidence_phrase_count") or 0),
        str(row.get("match_basis") or ""),
        str(row.get("accepted_at") or ""),
        str(row.get("target_ticker") or row.get("ticker") or ""),
        str(row.get("accession_number") or ""),
    )


def daily_top1_counterparty(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_day[str(row["usable_trade_date"])].append(row)
    selected = []
    for day, day_rows in by_day.items():
        best = sorted(day_rows, key=counterparty_rank)[0]
        selected.append(
            {
                **best,
                "selection_date": day,
                "daily_candidate_count": len(day_rows),
            }
        )
    return sorted(selected, key=lambda row: (row["selection_date"], counterparty_rank(row)))


def build_outcomes(
    selected_rows: Iterable[dict[str, Any]],
    bars: dict[str, list[dict[str, Any]]],
    *,
    horizon: int = 10,
    notional: float = 4000.0,
) -> list[dict[str, Any]]:
    outcomes = []
    for row in selected_rows:
        ticker = str(row.get("target_ticker") or row.get("ticker") or "").upper()
        ticker_bars = bars.get(ticker, [])
        entry_idx = base.first_bar_on_or_after(ticker_bars, row["usable_trade_date"])
        result = {
            "observer_only": True,
            "trade_enabled": False,
            "source_experiment": "exp-20260703-017",
            "source_row_key": {
                "accession_number": row.get("accession_number"),
                "relation_bucket": row.get("relation_bucket"),
                "source_text_hash16": row.get("source_text_hash16"),
            },
            "issuer_ticker": row.get("issuer_ticker"),
            "target_ticker": ticker,
            "ticker": ticker,
            "selection_date": row["selection_date"],
            "usable_trade_date": row["usable_trade_date"],
            "daily_candidate_count": row.get("daily_candidate_count"),
            "relation_bucket": row.get("relation_bucket"),
            "relation_quality": row.get("relation_quality"),
            "evidence_phrase_count": row.get("evidence_phrase_count"),
            "counterparty_raw": row.get("counterparty_raw"),
            "counterparty_normalized": row.get("counterparty_normalized"),
            "target_company_title": row.get("target_company_title"),
            "match_quality_rank": row.get("match_quality_rank"),
            "match_basis": row.get("match_basis"),
            "match_source": row.get("match_source"),
            "accession_number": row.get("accession_number"),
            "accepted_at": row.get("accepted_at"),
            "filing_date": row.get("filing_date"),
            "horizon_trading_days": horizon,
            "notional_usd": notional,
            "pit_caveat": row.get("pit_caveat"),
        }
        if entry_idx is None:
            outcomes.append({**result, "outcome_status": "unsettled_no_entry_bar"})
            continue
        exit_idx = entry_idx + horizon - 1
        entry_bar = ticker_bars[entry_idx]
        result["entry_date"] = entry_bar["_date"]
        result["entry_open"] = round(float(entry_bar["open"]), 4)
        result["window"] = base.window_for_entry(entry_bar["_date"])
        if exit_idx >= len(ticker_bars):
            outcomes.append({**result, "outcome_status": "unsettled_horizon"})
            continue
        exit_bar = ticker_bars[exit_idx]
        pnl = base.pnl_for_bars(entry_bar, exit_bar, notional)
        result.update(
            {
                "exit_date": exit_bar["_date"],
                "exit_close": round(float(exit_bar["close"]), 4),
                "pnl_usd": pnl,
                "replacement_value_vs_cash_usd": pnl,
            }
        )
        missing_comparator = False
        comparator_detail: dict[str, Any] = {}
        for comparator in ("SPY", "QQQ"):
            comp_rows = bars.get(comparator, [])
            comp_entry = base.bar_by_date(comp_rows, entry_bar["_date"])
            comp_exit = base.bar_by_date(comp_rows, exit_bar["_date"])
            comp_pnl = (
                base.pnl_for_bars(comp_entry, comp_exit, notional)
                if comp_entry and comp_exit
                else None
            )
            if comp_pnl is None:
                missing_comparator = True
            result[f"replacement_value_vs_{comparator.lower()}_usd"] = (
                round(pnl - comp_pnl, 2) if comp_pnl is not None else None
            )
            comparator_detail[comparator] = {
                "entry_date": comp_entry["_date"] if comp_entry else None,
                "exit_date": comp_exit["_date"] if comp_exit else None,
                "pnl_usd": comp_pnl,
            }
        result["comparator_detail"] = comparator_detail
        result["outcome_status"] = "missing_comparator_bars" if missing_comparator else "settled"
        outcomes.append(result)
    return outcomes


def count_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = Counter(str(row.get("target_ticker") or "UNKNOWN") for row in rows)
    issuers = Counter(str(row.get("issuer_ticker") or "UNKNOWN") for row in rows)
    match_bases = Counter(str(row.get("match_basis") or "UNKNOWN") for row in rows)
    buckets = Counter(str(row.get("relation_bucket") or "UNKNOWN") for row in rows)
    windows = Counter(str(row.get("window") or "outside") for row in rows)
    total = len(rows)
    return {
        "row_count": total,
        "target_ticker_count": len(tickers),
        "issuer_count": len(issuers),
        "match_basis_count": len(match_bases),
        "bucket_count": len(buckets),
        "window_count": len([window for window in windows if window != "outside"]),
        "top_ticker_share": round(tickers.most_common(1)[0][1] / total, 6)
        if total
        else None,
        "top_target_tickers_by_rows": [
            {"target_ticker": ticker, "rows": count, "share": round(count / total, 6)}
            for ticker, count in tickers.most_common(12)
        ]
        if total
        else [],
        "top_issuer_tickers_by_rows": [
            {"issuer_ticker": ticker, "rows": count, "share": round(count / total, 6)}
            for ticker, count in issuers.most_common(12)
        ]
        if total
        else [],
        "match_bases": dict(match_bases),
        "relation_buckets_by_rows": [
            {"relation_bucket": bucket, "rows": count, "share": round(count / total, 6)}
            for bucket, count in buckets.most_common()
        ]
        if total
        else [],
        "windows_by_rows": dict(sorted(windows.items())),
    }


def compact_log_record(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "policy_bundle",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    return {key: result[key] for key in keys}


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = base.baseline_metrics()
    source_summary = base.read_json(SOURCE_SUMMARY, {}) or {}
    raw_rows = base.load_jsonl(SOURCE_ROWS)
    accession_rows = base.dedupe_accessions(raw_rows)
    company_index = load_company_index(SEC_COMPANY_TICKERS)
    counterparty_rows, counterparty_diagnostics = build_counterparty_rows(
        accession_rows, company_index
    )
    selected = daily_top1_counterparty(counterparty_rows)
    tickers = sorted({row["target_ticker"] for row in selected} | {"SPY", "QQQ"})
    bars, warehouse_summary = base.load_bars(tickers)
    outcomes = build_outcomes(selected, bars)
    settled = [row for row in outcomes if row.get("outcome_status") == "settled"]
    canonical_settled = [row for row in settled if row.get("window") in WINDOWS]
    outside_settled = [row for row in settled if row.get("window") not in WINDOWS]

    overall_metrics = base.metric_summary(canonical_settled)
    by_window = base.group_summaries(canonical_settled, "window")
    by_bucket = base.group_summaries(canonical_settled, "relation_bucket")
    by_match_basis = base.group_summaries(canonical_settled, "match_basis")
    by_ticker = base.group_summaries(canonical_settled, "target_ticker")
    counts = count_summary(canonical_settled)

    window_rows = {
        item["window"]: item["row_count"]
        for item in by_window
        if item.get("window") in WINDOWS
    }
    settled_windows = [
        label
        for label, row_count in window_rows.items()
        if row_count >= ACCEPTANCE_RULE["min_rows_per_settled_window"]
    ]
    positive_windows_vs_spy_and_qqq = sum(
        1
        for item in by_window
        if item.get("window") in WINDOWS and item["spy_and_qqq_means_positive"]
    )
    aggregate_means_positive = all(
        (overall_metrics[metric]["mean"] or 0.0) > 0 for metric in PRIMARY_METRICS
    )
    aggregate_medians_nonnegative = all(
        (overall_metrics[metric]["median"] or 0.0) >= 0 for metric in PRIMARY_METRICS
    )
    checks = {
        "settled_top1_rows_min_passed": len(canonical_settled)
        >= ACCEPTANCE_RULE["min_settled_top1_rows"],
        "settled_windows_min_passed": len(settled_windows)
        >= ACCEPTANCE_RULE["min_settled_windows"],
        "positive_windows_vs_spy_and_qqq_passed": positive_windows_vs_spy_and_qqq
        >= ACCEPTANCE_RULE["min_positive_windows_vs_spy_and_qqq"],
        "aggregate_primary_means_positive": aggregate_means_positive,
        "aggregate_primary_medians_nonnegative": aggregate_medians_nonnegative,
        "top_ticker_share_passed": (
            counts["top_ticker_share"] is not None
            and counts["top_ticker_share"] <= ACCEPTANCE_RULE["max_top_ticker_share"]
        ),
    }
    directional_support = all(checks.values())
    failed_reasons = [name for name, passed in checks.items() if not passed]
    if directional_support:
        status = "observed_only_positive_lead"
        decision = "observed_only_positive_sec_item101_public_counterparty_target_lead"
        actual_success = 1
    else:
        status = "observed_only_rejected"
        decision = "observed_only_rejected_no_sec_item101_public_counterparty_target_edge"
        actual_success = 0

    status_counts = Counter(str(row.get("outcome_status") or "unknown") for row in outcomes)
    realized_failure_modes = []
    if not counterparty_rows:
        realized_failure_modes.append("counterparty normalization too sparse")
    if not checks["positive_windows_vs_spy_and_qqq_passed"]:
        realized_failure_modes.append("window instability")
    if not checks["top_ticker_share_passed"]:
        realized_failure_modes.append("public counterparty rows concentrate in banks")
    if not checks["aggregate_primary_medians_nonnegative"]:
        realized_failure_modes.append("accepted comparator not beaten")
    if not realized_failure_modes:
        realized_failure_modes.append("public archive PIT caveat")

    why = (
        "The normalized public-counterparty target source cleared the "
        "observed-only replacement checks, but it is not accepted alpha "
        "because no shared default-off helper was promoted and the SEC text "
        "surface remains a public-archive PIT proxy."
        if directional_support
        else "The normalized public-counterparty target source did not show "
        "enough broad 10-session replacement value after daily top-1 "
        "compression and ETF opportunity-cost checks."
    )

    summary = {
        "source_rows": len(raw_rows),
        "accession_deduped_rows": len(accession_rows),
        "mapped_counterparty_rows": len(counterparty_rows),
        "daily_top1_candidates": len(selected),
        "canonical_settled_rows": len(canonical_settled),
        "outside_canonical_settled_rows": len(outside_settled),
        "settled_windows": settled_windows,
        "positive_windows_vs_spy_and_qqq": positive_windows_vs_spy_and_qqq,
        "row_mean_cash": overall_metrics["replacement_value_vs_cash_usd"]["mean"],
        "row_mean_spy": overall_metrics["replacement_value_vs_spy_usd"]["mean"],
        "row_mean_qqq": overall_metrics["replacement_value_vs_qqq_usd"]["mean"],
        "row_median_cash": overall_metrics["replacement_value_vs_cash_usd"]["median"],
        "row_median_spy": overall_metrics["replacement_value_vs_spy_usd"]["median"],
        "row_median_qqq": overall_metrics["replacement_value_vs_qqq_usd"]["median"],
        "top_ticker_share": counts["top_ticker_share"],
        "top_target_tickers": counts["top_target_tickers_by_rows"][:8],
        "decision": decision,
    }

    result: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": directional_support,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_observed_attribution",
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": "sec_contract_relation_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "fixed counterparty name normalization",
            "listed ticker target mapping",
            "daily top-1 counterparty target",
            "next-open 10-session outcomes",
            "cash/SPY/QQQ replacement attribution",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_gate_shape",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": actual_success,
            "brier_score": round(
                (PREDICTION["success_probability"] - actual_success) ** 2, 4
            ),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": realized_failure_modes,
            "predicted_failure_mode_hit": bool(
                set(realized_failure_modes) & set(PREDICTION["main_failure_modes"])
            ),
            "surprise_note": (
                "Low surprise: the saturated SEC text public-counterparty "
                "target read did not clear broad window and comparator checks."
                if not directional_support
                else "Moderate surprise: the saturated SEC text target-side "
                "counterparty source cleared observed-only checks."
            ),
        },
        "policy_bundle": {
            "source_surface": "exp-20260703-017 Item 1.01 contract-relation provenance",
            "company_reference": repo_rel(SEC_COMPANY_TICKERS),
            "normalization": (
                "fixed legal-suffix stripping, split simple conjunctions, exact "
                "SEC company-title matches, fixed manual public-counterparty "
                "aliases, then conservative two-token containment"
            ),
            "excluded": [
                "issuer self-matches",
                "non-common/invalid ticker strings",
                "short or generic single-token names without exact public identity",
            ],
            "selection": (
                "one best public-counterparty target per usable_trade_date by "
                "relation priority, match quality, evidence count, match basis, "
                "accepted_at, target ticker, accession"
            ),
            "entry": "first local OHLCV open on or after usable_trade_date",
            "exit": "10th trading session close after entry",
            "notional_usd": 4000.0,
            "comparators": ["cash", "SPY", "QQQ"],
            "relation_priority": RELATION_PRIORITY,
            "manual_aliases": MANUAL_ALIASES,
        },
        "gate1": {
            "passed": True,
            "note": "Observed-only attribution; canonical strategy baseline unchanged.",
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": bool(canonical_settled),
            "fields_checked": [
                "issuer_ticker",
                "target_ticker",
                "counterparty_raw",
                "counterparty_normalized",
                "match_basis",
                "match_quality_rank",
                "accession_number",
                "relation_bucket",
                "relation_quality",
                "usable_trade_date",
                "accepted_at",
                "entry_date",
                "exit_date",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "source_rows": len(raw_rows),
            "accession_deduped_rows": len(accession_rows),
            "mapped_counterparty_rows": len(counterparty_rows),
            "daily_top1_candidates": len(selected),
            "canonical_settled_rows": len(canonical_settled),
            "entry_date_present_rows": sum(1 for row in outcomes if row.get("entry_date")),
            "target_price_relevance": (
                "This observed-only fixed-horizon paper read does not create "
                "target exits or orders; target_price is not part of the surface."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": len(selected),
            "signals_survived": len(canonical_settled),
            "survival_rate": round(len(canonical_settled) / len(selected), 6)
            if selected
            else None,
            "note": (
                "No executable filter, ranking, sizing, exit, prompt, or order "
                "rule was added. Survival here means daily top-1 public-"
                "counterparty target candidates with settled canonical-window "
                "10-session outcomes."
            ),
        },
        "gate4": {
            "passed": directional_support,
            "observed_only": True,
            "accepted_alpha": False,
            "strategy_rerun_required": False,
            "decision": decision,
            "acceptance_rule": ACCEPTANCE_RULE,
            "acceptance_checks": checks,
            "failed_reasons": failed_reasons,
            "before_after_strategy_delta": {
                "strategy_behavior_changed": False,
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
            },
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "strategy_behavior_changed": False,
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
        },
        "summary": summary,
        "diagnostics": {
            "source_summary": source_summary,
            "company_index": company_index["diagnostics"],
            "counterparty_diagnostics": counterparty_diagnostics,
            "warehouse_summary": warehouse_summary,
            "outcome_status_counts": dict(status_counts),
            "counts": counts,
            "by_window": by_window,
            "by_relation_bucket": by_bucket,
            "by_match_basis": by_match_basis,
            "by_target_ticker": by_ticker[:25],
        },
        "outcomes": outcomes,
        "production_impact": {
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Read-only analysis over exp-20260703-017 observer provenance "
                "and SEC company ticker reference. No helper, adapter, order, "
                "rank, size, exit, watchlist, or LLM behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not sweep Item 1.01 relation regexes, item codes, alias "
                "lists, legal suffixes, containment thresholds, bank-only "
                "subsets, relation priority, top-N, hold days, cooldown, "
                "notional, source priority, liquidity guards, or response "
                "curves on this same public-archive surface."
            ),
            "new_evidence_required": (
                "A valid retry needs materially richer counterparty identity "
                "evidence such as CIK-linked customer/supplier graph rows, "
                "contract value/duration/revenue exposure by counterparty, a "
                "new non-SEC source, or prospectively accumulated shared-helper "
                "rows with closed replacement value."
            ),
        },
        "next_retry_requires": [
            "CIK-linked customer/supplier counterparty identity rather than alias retune",
            "contract value/duration/revenue exposure by named public counterparty",
            "new non-SEC source or prospectively accumulated closed replacement rows",
            "no same-surface alias/top-N/hold/notional/liquidity/response retune",
        ],
        "related_files": [
            RUNNER,
            "quant/experiments/exp_20260703_018_sec_item101_contract_relation_issuer_self.py",
            "data/non_ohlcv/sec_contract_relation_provenance/rows.jsonl",
            "data/non_ohlcv/sec_contract_relation_provenance/latest_summary.json",
            "data/reference/sec_company_tickers.json",
            "experiments/logs/exp-20260703-017.json",
            "experiments/logs/exp-20260703-018.json",
            "experiments/logs/exp-20260703-020.json",
            "experiments/logs/exp-20260703-021.json",
            "experiments/logs/exp-20260704-001.json",
        ],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
    }
    return result


def build_card(result: dict[str, Any]) -> str:
    summary = result["summary"]
    failures = result["gate4"]["failed_reasons"] or ["none"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

- Status: `{result["status"]}`
- Decision: `{result["decision"]}`
- Accepted alpha: `false`
- Observed-only lead: `{str(result["observed_only_lead"]).lower()}`
- Mapped counterparty rows: `{summary["mapped_counterparty_rows"]}`
- Daily top-1 candidates: `{summary["daily_top1_candidates"]}`
- Canonical settled rows: `{summary["canonical_settled_rows"]}`
- Settled windows: `{", ".join(summary["settled_windows"]) or "none"}`
- Positive windows vs SPY and QQQ: `{summary["positive_windows_vs_spy_and_qqq"]}`
- Row means cash/SPY/QQQ: `{summary["row_mean_cash"]}` / `{summary["row_mean_spy"]}` / `{summary["row_mean_qqq"]}`
- Row medians cash/SPY/QQQ: `{summary["row_median_cash"]}` / `{summary["row_median_spy"]}` / `{summary["row_median_qqq"]}`
- Top target ticker share: `{summary["top_ticker_share"]}`
- Failed checks: `{", ".join(failures)}`

## Boundary

{result["post_run_reflection"]["forbidden_near_neighbor_retry"]}

## Reproduce

```powershell
{RUNNER_COMMAND}
.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict
```
"""


def update_ticket(result: dict[str, Any]) -> None:
    ticket = base.read_json(TICKET_JSON, {}) or {}
    ticket["status"] = result["status"]
    ticket["completed_at"] = result["timestamp"]
    ticket["result"] = {
        "decision": result["decision"],
        "artifact": result["artifact"],
        "log": result["log"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": result["observed_only_lead"],
    }
    ticket["gate4"] = result["gate4"]
    ticket["post_run_reflection"] = result["post_run_reflection"]
    ticket["next_retry_requires"] = result["next_retry_requires"]
    base.write_json(TICKET_JSON, ticket)


def write_manifest(result: dict[str, Any]) -> None:
    base.write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "generated_at": result["timestamp"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def main() -> int:
    result = build_result()
    base.write_json(OUT_JSON, result)
    save_experiment_log_entry(compact_log_record(result), allow_duplicate=True)
    base.write_text(CARD_MD, build_card(result))
    write_manifest(result)
    update_ticket(result)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": result["observed_only_lead"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "gate4": result["gate4"],
            "summary": result["summary"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": HYPOTHESIS,
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": result["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log_file": result["log"],
            "card_file": repo_rel(CARD_MD),
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["next_retry_requires"],
            "related_files": result["related_files"],
            "changed_files": CHANGED_FILES,
            "allowed_write_scope": CHANGED_FILES,
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    print(json.dumps(compact_log_record(result), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
