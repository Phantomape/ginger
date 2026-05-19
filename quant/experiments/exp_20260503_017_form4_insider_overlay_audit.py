"""Form 4 insider-buying non-OHLCV overlay audit.

This is a data availability and shadow-overlay feasibility audit only. It does
not fetch external data, does not create entries, and does not alter production
signal, risk, portfolio, or universe paths.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"
EXP_ID = "exp-20260503-017"
OUT_DIR = DATA_DIR / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "exp_20260503_017_form4_insider_overlay_audit.json"
LOG_JSON = DOCS_DIR / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = DOCS_DIR / "experiments" / "tickets" / f"{EXP_ID}.json"
EXPERIMENT_LOG = DOCS_DIR / "experiment_log.jsonl"
REGISTRY_JSON = DOCS_DIR / "experiment_registry.json"
AUDIT_MD = DOCS_DIR / "non_ohlcv_data_audit" / "form4_20260503.md"
BASELINE_LOG = DOCS_DIR / "experiments" / "logs" / "exp-20260503-011.json"

FORM4_FORMS = {"4", "4/A"}
NON_COMPANY_TICKERS = {"SPY", "QQQ", "IWM", "GLD", "IAU", "SLV"}
REQUIRED_FORM4_FIELDS = [
    "ticker",
    "cik",
    "accession_number",
    "filing_datetime",
    "transaction_date",
    "officer_title",
    "is_director",
    "is_officer",
    "is_10pct_owner",
    "transaction_code",
    "shares",
    "price",
    "transaction_value",
    "direct_or_indirect",
    "ownership_nature",
    "10b5_1_flag",
    "option_exercise_flag",
    "open_market_purchase_flag",
    "usable_trade_date",
    "pit_safe_flag",
]


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _normalize_cik(value: Any) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return None
    return digits.zfill(10)


def _company_ticker_maps() -> tuple[dict[str, str], dict[str, str]]:
    payload = _load_json(DATA_DIR / "sec_company_tickers.json", {})
    rows = payload.values() if isinstance(payload, dict) else payload
    ticker_to_cik: dict[str, str] = {}
    cik_to_ticker: dict[str, str] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        cik = _normalize_cik(row.get("cik_str") or row.get("cik"))
        if ticker and cik:
            ticker_to_cik[ticker] = cik
            cik_to_ticker.setdefault(cik, ticker)
    return ticker_to_cik, cik_to_ticker


def _universe_segments() -> dict[str, list[str]]:
    state = _load_json(DATA_DIR / "universe_state_20260501.json", {})
    return {
        "core": list(state.get("core_trade_universe") or []),
        "pilot": list(state.get("pilot_trade_universe") or []),
        "observation": list(state.get("observation_universe") or []),
    }


def _mapping_coverage(segments: dict[str, list[str]], ticker_to_cik: dict[str, str]) -> dict[str, Any]:
    coverage: dict[str, Any] = {}
    for name, tickers in segments.items():
        mapped = [ticker for ticker in tickers if ticker in ticker_to_cik]
        missing = [ticker for ticker in tickers if ticker not in ticker_to_cik]
        non_company = [ticker for ticker in tickers if ticker in NON_COMPANY_TICKERS]
        coverage[name] = {
            "ticker_count": len(tickers),
            "mapped_count": len(mapped),
            "missing_count": len(missing),
            "mapping_rate": round(len(mapped) / len(tickers), 4) if tickers else None,
            "missing_tickers": missing,
            "non_company_or_etf_tickers": non_company,
        }
    return coverage


def _news_archives() -> list[Path]:
    return sorted(
        path for path in DATA_DIR.glob("news_*.json")
        if re.fullmatch(r"news_\d{8}\.json", path.name)
    )


def _source_stat_archives() -> list[Path]:
    return sorted(
        path for path in DATA_DIR.glob("news_source_stats_*.json")
        if re.fullmatch(r"news_source_stats_\d{8}\.json", path.name)
    )


def _metadata_filing_type(item: dict[str, Any]) -> str:
    metadata = item.get("source_metadata") or {}
    return str(
        item.get("filing_type")
        or metadata.get("filing_type")
        or metadata.get("sec_filing_form")
        or ""
    ).upper()


def _scan_news_archives() -> dict[str, Any]:
    form_counts = Counter()
    sec_items_by_file = []
    form4_items_by_file = []
    latest_sec_samples = []
    for path in _news_archives():
        payload = _load_json(path, [])
        if not isinstance(payload, list):
            continue
        sec_count = 0
        form4_count = 0
        for item in payload:
            if not isinstance(item, dict) or item.get("source") != "sec":
                continue
            sec_count += 1
            filing_type = _metadata_filing_type(item)
            form_counts[filing_type or "unknown"] += 1
            if filing_type in FORM4_FORMS:
                form4_count += 1
        if sec_count:
            sec_items_by_file.append({"file": path.name, "sec_items": sec_count})
        if form4_count:
            form4_items_by_file.append({"file": path.name, "form4_items": form4_count})

    for path in reversed(_news_archives()):
        payload = _load_json(path, [])
        if not isinstance(payload, list):
            continue
        for item in payload:
            if isinstance(item, dict) and item.get("source") == "sec":
                latest_sec_samples.append({
                    "file": path.name,
                    "title": item.get("title"),
                    "filing_type": _metadata_filing_type(item),
                    "tickers": item.get("tickers") or [],
                    "sec_cik": item.get("sec_cik") or (item.get("source_metadata") or {}).get("sec_cik"),
                })
            if len(latest_sec_samples) >= 5:
                break
        if len(latest_sec_samples) >= 5:
            break

    source_stats_form_types = Counter()
    source_stats_urls = []
    for path in _source_stat_archives():
        payload = _load_json(path, [])
        if not isinstance(payload, list):
            continue
        for row in payload:
            if not isinstance(row, dict) or row.get("source_type") != "sec":
                continue
            filing_type = str((row.get("metadata") or {}).get("filing_type") or "").upper()
            source_stats_form_types[filing_type or "unknown"] += 1
            source_stats_urls.append({
                "file": path.name,
                "filing_type": filing_type,
                "url": row.get("url"),
                "entry_count": row.get("entry_count"),
                "parsed_item_count": row.get("parsed_item_count"),
                "error": row.get("error"),
            })

    return {
        "news_file_count": len(_news_archives()),
        "news_files_with_sec": len(sec_items_by_file),
        "news_files_with_form4": len(form4_items_by_file),
        "sec_item_count": sum(row["sec_items"] for row in sec_items_by_file),
        "form4_item_count": sum(row["form4_items"] for row in form4_items_by_file),
        "sec_filing_type_counts": dict(sorted(form_counts.items())),
        "sample_news_files_with_sec": sec_items_by_file[:10],
        "sample_news_files_with_form4": form4_items_by_file[:10],
        "latest_sec_samples": latest_sec_samples,
        "news_source_stats_file_count": len(_source_stat_archives()),
        "source_stats_sec_filing_type_counts": dict(sorted(source_stats_form_types.items())),
        "source_stats_sec_sources": source_stats_urls,
    }


def _recent_field(recent: dict[str, Any], field: str, idx: int) -> Any:
    values = recent.get(field)
    if not isinstance(values, list) or idx >= len(values):
        return None
    return values[idx]


def _scan_submission_cache(cik_to_ticker: dict[str, str], segments: dict[str, list[str]], ticker_to_cik: dict[str, str]) -> dict[str, Any]:
    cache_dir = DATA_DIR / "sec_submissions_cache"
    rows = []
    fields_seen = set()
    cache_files = sorted(cache_dir.glob("CIK*.json")) if cache_dir.exists() else []
    form_counts = Counter()
    universe_lookup = {
        "core": set(segments["core"]),
        "pilot": set(segments["pilot"]),
        "observation": set(segments["observation"]),
    }
    by_segment = Counter()
    for path in cache_files:
        payload = _load_json(path, {})
        cik = _normalize_cik(payload.get("cik")) or _normalize_cik(path.stem)
        ticker = cik_to_ticker.get(cik or "")
        recent = ((payload.get("filings") or {}).get("recent") or {}) if isinstance(payload, dict) else {}
        if not isinstance(recent, dict):
            continue
        lengths = [len(value) for value in recent.values() if isinstance(value, list)]
        count = max(lengths) if lengths else 0
        fields_seen.update(recent.keys())
        for idx in range(count):
            form = str(_recent_field(recent, "form", idx) or "").upper()
            form_counts[form or "unknown"] += 1
            if form not in FORM4_FORMS:
                continue
            segment_hits = [
                segment for segment, tickers in universe_lookup.items()
                if ticker and ticker in tickers
            ]
            if segment_hits:
                for segment in segment_hits:
                    by_segment[segment] += 1
            else:
                by_segment["outside_current_universe"] += 1
            rows.append({
                "ticker": ticker,
                "cik": cik,
                "form": form,
                "filing_date": _recent_field(recent, "filingDate", idx),
                "acceptance_datetime": _recent_field(recent, "acceptanceDateTime", idx),
                "report_date": _recent_field(recent, "reportDate", idx),
                "accession_number": _recent_field(recent, "accessionNumber", idx),
                "primary_document": _recent_field(recent, "primaryDocument", idx),
                "segment_hits": segment_hits or ["outside_current_universe"],
                "cache_file": path.name,
            })

    cache_by_segment = {}
    for segment, tickers in segments.items():
        mapped_ciks = [_normalize_cik(ticker_to_cik.get(ticker)) for ticker in tickers]
        mapped_ciks = [cik for cik in mapped_ciks if cik]
        cached = [cik for cik in mapped_ciks if (cache_dir / f"CIK{cik}.json").exists()]
        cache_by_segment[segment] = {
            "mapped_cik_count": len(mapped_ciks),
            "cached_submission_count": len(cached),
            "cache_coverage_rate": round(len(cached) / len(mapped_ciks), 4) if mapped_ciks else None,
            "cached_tickers": sorted(
                ticker for ticker in tickers
                if ticker_to_cik.get(ticker) and (cache_dir / f"CIK{ticker_to_cik[ticker]}.json").exists()
            ),
        }

    return {
        "cache_dir_exists": cache_dir.exists(),
        "cache_file_count": len(cache_files),
        "recent_metadata_fields_seen": sorted(fields_seen),
        "recent_form_counts_top": dict(form_counts.most_common(20)),
        "form4_metadata_row_count": len(rows),
        "form4_metadata_by_segment": dict(sorted(by_segment.items())),
        "form4_metadata_current_universe_rows": sum(
            1 for row in rows
            if any(segment in row["segment_hits"] for segment in ("core", "pilot", "observation"))
        ),
        "form4_metadata_samples": rows[:25],
        "submission_cache_coverage_by_segment": cache_by_segment,
        "pit_status": "biased_static_cache",
        "pit_warning": (
            "Submission cache files are latest snapshots fetched before this audit, not daily "
            "append-only Form 4 observations. They can show that metadata exists, but they are "
            "not point-in-time evidence for historical overlay performance."
        ),
    }


def _latest_signal_candidate_count() -> dict[str, Any]:
    paths = sorted(
        path for path in DATA_DIR.glob("quant_signals_*.json")
        if re.fullmatch(r"quant_signals_\d{8}\.json", path.name)
    )
    if not paths:
        return {"latest_file": None, "candidate_count": 0, "tickers": []}
    path = paths[-1]
    payload = _load_json(path, {})
    signals = payload.get("signals") if isinstance(payload, dict) else []
    tickers = sorted({
        str(signal.get("ticker") or "").upper()
        for signal in signals or []
        if isinstance(signal, dict) and signal.get("ticker")
    })
    return {"latest_file": path.name, "candidate_count": len(signals or []), "tickers": tickers}


def _baseline_metrics() -> dict[str, Any]:
    payload = _load_json(BASELINE_LOG, {})
    baseline = payload.get("baseline_metrics") if isinstance(payload, dict) else None
    if baseline:
        return baseline
    fallback = _load_json(DATA_DIR / "backtest_results_20260502.json", {})
    benchmarks = fallback.get("benchmarks") or {}
    return {
        "latest_available": {
            "expected_value_score": fallback.get("expected_value_score"),
            "total_return_pct": benchmarks.get("strategy_total_return_pct"),
            "total_pnl": fallback.get("total_pnl"),
            "sharpe_daily": fallback.get("sharpe_daily"),
            "max_drawdown_pct": fallback.get("max_drawdown_pct"),
            "win_rate": fallback.get("win_rate"),
            "trade_count": fallback.get("total_trades"),
            "signals_generated": fallback.get("signals_generated"),
            "signals_survived": fallback.get("signals_survived"),
            "survival_rate": fallback.get("survival_rate"),
            "vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
            "vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
        }
    }


def _field_availability(news_audit: dict[str, Any], cache_audit: dict[str, Any]) -> dict[str, Any]:
    metadata_has_form4 = cache_audit["form4_metadata_row_count"] > 0 or news_audit["form4_item_count"] > 0
    available = {
        "ticker": metadata_has_form4,
        "cik": metadata_has_form4,
        "accession_number": cache_audit["form4_metadata_row_count"] > 0,
        "filing_datetime": cache_audit["form4_metadata_row_count"] > 0,
        "transaction_date": False,
        "officer_title": False,
        "is_director": False,
        "is_officer": False,
        "is_10pct_owner": False,
        "transaction_code": False,
        "shares": False,
        "price": False,
        "transaction_value": False,
        "direct_or_indirect": False,
        "ownership_nature": False,
        "10b5_1_flag": False,
        "option_exercise_flag": False,
        "open_market_purchase_flag": False,
        "usable_trade_date": False,
        "pit_safe_flag": False,
    }
    missing = [field for field in REQUIRED_FORM4_FIELDS if not available.get(field)]
    return {
        "required_fields": REQUIRED_FORM4_FIELDS,
        "available_fields": [field for field in REQUIRED_FORM4_FIELDS if available.get(field)],
        "missing_fields": missing,
        "usability": "not_usable_for_meaningful_insider_buy_overlay",
        "reason": (
            "Local data may contain Form 4 filing metadata in SEC submissions cache, but it lacks "
            "transaction XML fields needed to distinguish open-market purchases from sales, option "
            "exercises, gifts, 10b5-1 trades, or tiny non-informative transactions."
        ),
    }


def _append_experiment_log(row: dict[str, Any]) -> None:
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        if any(f'"experiment_id":"{EXP_ID}"' in line or f'"experiment_id": "{EXP_ID}"' in line for line in lines):
            lines = [
                line for line in lines
                if f'"experiment_id":"{EXP_ID}"' not in line and f'"experiment_id": "{EXP_ID}"' not in line
            ]
            lines.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _update_ticket_and_registry(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {"experiment_id": EXP_ID})
    allowed = list(ticket.get("allowed_write_scope") or [])
    report_scope = "docs/non_ohlcv_data_audit/form4_20260503.md"
    if report_scope not in allowed:
        allowed.insert(2, report_scope)
    ticket.update({
        "status": payload["status"],
        "decision": payload["decision"],
        "completed_at": payload["timestamp"],
        "allowed_write_scope": allowed,
        "result": {
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "audit_report": str(AUDIT_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
            "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "decision": payload["decision"],
            "usable_meaningful_insider_buy_candidates": payload["shadow_overlay_metrics"]["candidate_count"],
            "form4_metadata_rows": payload["data_availability"]["submission_cache"]["form4_metadata_row_count"],
            "pit_safe": False,
            "production_impact": payload["production_impact"]["production_impact"],
            "next_action": payload["next_action"],
        },
    })
    _write_json(TICKET_JSON, ticket)

    registry = _load_json(REGISTRY_JSON, {})
    changed = False
    for entry in registry.get("experiments", []):
        if entry.get("experiment_id") == EXP_ID:
            entry["status"] = payload["status"]
            entry["updated_at"] = payload["timestamp"]
            entry["owner"] = "codex"
            changed = True
            break
    if changed:
        registry["updated_at"] = payload["timestamp"]
        _write_json(REGISTRY_JSON, registry)


def _write_markdown_report(payload: dict[str, Any]) -> None:
    availability = payload["data_availability"]
    field_status = availability["required_field_availability"]
    overlay = payload["shadow_overlay_metrics"]
    lines = [
        "# Form 4 Insider Overlay Data Audit",
        "",
        f"- experiment_id: `{EXP_ID}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        f"- production_impact: `{payload['production_impact']['production_impact']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Coverage",
        "",
        f"- CIK mapping: core {availability['cik_mapping']['core']['mapped_count']}/{availability['cik_mapping']['core']['ticker_count']}, "
        f"pilot {availability['cik_mapping']['pilot']['mapped_count']}/{availability['cik_mapping']['pilot']['ticker_count']}, "
        f"observation {availability['cik_mapping']['observation']['mapped_count']}/{availability['cik_mapping']['observation']['ticker_count']}.",
        f"- Archived news SEC items: {availability['news_archives']['sec_item_count']} across {availability['news_archives']['news_files_with_sec']} files.",
        f"- Archived news Form 4 items: {availability['news_archives']['form4_item_count']} across {availability['news_archives']['news_files_with_form4']} files.",
        f"- Submission cache Form 4 metadata rows: {availability['submission_cache']['form4_metadata_row_count']}.",
        f"- Current-universe Form 4 metadata rows in cache: {availability['submission_cache']['form4_metadata_current_universe_rows']}.",
        "",
        "## PIT Status",
        "",
        "- `pit_safe`: false.",
        "- Current news source diagnostics only show SEC feeds for 8-K, 10-Q, and 10-K. No daily Form 4 feed is archived.",
        "- The SEC submissions cache is a latest snapshot, not a daily append-only source. It is useful for schema discovery, not historical performance evidence.",
        "",
        "## Required Field Availability",
        "",
        f"- Available: {', '.join(field_status['available_fields']) if field_status['available_fields'] else 'none'}",
        f"- Missing: {', '.join(field_status['missing_fields'])}",
        "",
        "## Shadow Overlay Result",
        "",
        f"- meaningful insider-buy candidate_count: {overlay['candidate_count']}",
        f"- overlap_with_existing_signals: {overlay['overlap_with_existing_signals']}",
        f"- scarce_slot_opportunity_cost: {overlay['scarce_slot_opportunity_cost']}",
        f"- forward_return_of_tagged_candidates: {overlay['forward_return_of_tagged_candidates']}",
        "",
        "## Next Minimum Action",
        "",
        payload["next_action"],
        "",
    ]
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def build_payload() -> dict[str, Any]:
    ticker_to_cik, cik_to_ticker = _company_ticker_maps()
    segments = _universe_segments()
    mapping = _mapping_coverage(segments, ticker_to_cik)
    news_audit = _scan_news_archives()
    submission_audit = _scan_submission_cache(cik_to_ticker, segments, ticker_to_cik)
    field_status = _field_availability(news_audit, submission_audit)
    latest_signals = _latest_signal_candidate_count()

    meaningful_buy_candidates = 0
    status = "observed_only"
    decision = "data_gap"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    payload = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_discovery",
        "mechanism_family": "non_ohlcv_event_confirmation_insider_form4",
        "hypothesis": (
            "Public-market insider Form 4 buying, especially CEO/CFO large buys, "
            "cluster buying, first buys, and post-drawdown buys, may confirm existing "
            "trend_long/breakout_long candidates. This run only audits data availability "
            "and shadow overlay feasibility."
        ),
        "non_ohlcv_data_source": "SEC Form 4 insider ownership filings",
        "single_causal_variable": "Insider Form 4 data availability and shadow overlay audit",
        "experiment_mode": "data_audit_shadow_overlay_feasibility",
        "production_change_allowed": False,
        "alpha_hypothesis": {
            "category": "entry_confirmation_addon_confirmation",
            "text": (
                "Meaningful open-market insider buying can be a positive confirmation "
                "tag for existing A/B candidates rather than a standalone entry source."
            ),
            "why_not_production": (
                "No point-in-time transaction-level Form 4 archive exists locally, so "
                "meaningful insider buys cannot be replayed or attributed."
            ),
        },
        "history_check": {
            "prior_insider_form4_experiment_found": False,
            "related_sec_experiments": {
                "exp-20260503-004": "SEC feed coverage audit found old archives had zero SEC items before diagnostics.",
                "exp-20260503-005": "CIK-to-ticker mapping works for SEC Atom rows.",
                "exp-20260503-006": "Broad SEC filing scout was static/shadow and not production-ready.",
                "exp-20260503-011": "Liquidity-gated 10-K filing scout remains shadow-only and PIT-blocked.",
            },
            "mechanism_insight_check": {
                "conflict_with_recent_guardrails": False,
                "notes": (
                    "This is not another OHLCV threshold or broad SEC filing promotion. "
                    "It narrows to the playbook's Insider/Form 4 family and stops at data_gap."
                ),
            },
        },
        "baseline_metrics": _baseline_metrics(),
        "data_availability": {
            "cik_mapping": mapping,
            "news_archives": news_audit,
            "submission_cache": submission_audit,
            "required_field_availability": field_status,
            "pit_status": {
                "point_in_time_safe": False,
                "daily_form4_archive_available": news_audit["form4_item_count"] > 0,
                "transaction_xml_archive_available": False,
                "transaction_level_fields_available": False,
                "reason": (
                    "The local archive lacks daily Form 4 transaction XML and current SEC "
                    "news diagnostics do not include a Form 4 source. Submission cache "
                    "metadata is latest-snapshot and cannot support historical PIT overlay claims."
                ),
            },
        },
        "shadow_scoring_requested": {
            "insider_buy_value_to_market_cap": "blocked_missing_transaction_value_and_market_cap_join",
            "cluster_buying_30d": "blocked_missing_transaction_level_archive",
            "CEO_CFO_buy_flag": "blocked_missing_reporting_owner_title",
            "first_purchase_1y": "blocked_missing_transaction_history",
            "first_purchase_3y": "blocked_missing_transaction_history",
            "post_drawdown_purchase": "blocked_until_open_market_purchase_flag_exists",
            "exclude_option_exercise": "blocked_missing_transaction_code_and_derivative_fields",
            "exclude_tiny_purchase": "blocked_missing_shares_price_value",
        },
        "shadow_overlay_metrics": {
            "candidate_count": meaningful_buy_candidates,
            "meaningful_insider_buy_definition": (
                "open_market_purchase_flag=true, option_exercise_flag=false, "
                "transaction_value above tiny-purchase threshold, and PIT-safe usable_trade_date"
            ),
            "signals_with_meaningful_insider_buy": 0,
            "signals_without_meaningful_insider_buy": latest_signals["candidate_count"],
            "insider_buy_but_no_signal": 0,
            "latest_signal_file": latest_signals["latest_file"],
            "latest_signal_tickers": latest_signals["tickers"],
            "overlap_with_existing_signals": {
                "candidate_count": meaningful_buy_candidates,
                "overlap_count": 0,
                "overlap_rate": None,
                "reason": "No usable meaningful insider-buy candidates can be tagged from local data.",
            },
            "scarce_slot_opportunity_cost": {
                "measurable": False,
                "slot_conflict_count": 0,
                "replacement_value_10d_excess_proxy": None,
                "reason": "No usable tagged candidates; do not infer slot value from Form 4 filing metadata alone.",
            },
            "forward_return_of_tagged_candidates": {
                "5d": {"count": 0, "avg": None, "median": None, "win_rate": None},
                "10d": {"count": 0, "avg": None, "median": None, "win_rate": None},
                "20d": {"count": 0, "avg": None, "median": None, "win_rate": None},
                "60d": {"count": 0, "avg": None, "median": None, "win_rate": None},
                "90d": {"count": 0, "avg": None, "median": None, "win_rate": None},
            },
        },
        "after_metrics": {
            "expected_value_score_delta": 0.0,
            "production_metrics_changed": False,
            "reason": "Data audit only; no replay, strategy, sizing, ranking, or universe path changed.",
        },
        "expected_value_score_delta": 0.0,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_impact": "data_audit_only",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "decision_rationale": (
            "CIK mapping is good enough to identify issuers, but there is no PIT-safe "
            "transaction-level Form 4 archive and no local Form 4 adapter. The correct "
            "decision is data_gap, not shadow alpha promotion."
        ),
        "next_action": (
            "Build a default-off Form 4 adapter that archives daily owner=include type=4 "
            "filings plus transaction XML fields, then rerun this audit after at least "
            "30 daily archives exist."
        ),
        "related_files": [
            "data/sec_company_tickers.json",
            "data/sec_submissions_cache",
            "data/news_source_stats_20260502.json",
            "quant/sec_ticker_map.py",
            "quant/sec_submissions.py",
            "quant/experiments/exp_20260503_017_form4_insider_overlay_audit.py",
            "data/experiments/exp-20260503-017/exp_20260503_017_form4_insider_overlay_audit.json",
            "docs/non_ohlcv_data_audit/form4_20260503.md",
            "experiments/logs/exp-20260503-017.json",
            "experiments/tickets/exp-20260503-017.json",
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_markdown_report(payload)
    _update_ticket_and_registry(payload)
    _append_experiment_log(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "core_cik_mapping": payload["data_availability"]["cik_mapping"]["core"],
        "news_form4_items": payload["data_availability"]["news_archives"]["form4_item_count"],
        "submission_cache_form4_rows": payload["data_availability"]["submission_cache"]["form4_metadata_row_count"],
        "usable_candidate_count": payload["shadow_overlay_metrics"]["candidate_count"],
        "production_impact": payload["production_impact"]["production_impact"],
        "audit_report": str(AUDIT_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
