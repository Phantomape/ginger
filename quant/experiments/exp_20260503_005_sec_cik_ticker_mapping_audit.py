from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"
EXP_ID = "exp-20260503-005"
ARTIFACT_DIR = DATA_DIR / "experiments" / EXP_ID
ARTIFACT_PATH = ARTIFACT_DIR / "sec_cik_ticker_mapping_audit.json"
LOG_PATH = DOCS_DIR / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_PATH = DOCS_DIR / "experiments" / "tickets" / f"{EXP_ID}.json"


def _get_universe() -> set[str]:
    from data_layer import get_universe

    return set(get_universe())


def run() -> dict:
    from parser import parse_feed_with_diagnostics
    from sources import SEC_FEEDS

    universe = _get_universe()
    feed_results = []
    all_items = []

    for feed in SEC_FEEDS:
        items, diagnostics = parse_feed_with_diagnostics(
            feed["url"],
            "sec",
            {
                "filing_type": feed.get("filing_type", ""),
                "user_agent": "ginger-research/1.0 contact: research@example.com",
            },
        )
        mapped_to_universe = sum(1 for item in items if universe.intersection(item.get("tickers") or []))
        feed_results.append({
            "filing_type": feed.get("filing_type"),
            "status": diagnostics.get("status"),
            "entry_count": diagnostics.get("entry_count"),
            "parsed_item_count": diagnostics.get("parsed_item_count"),
            "sec_items_with_cik": diagnostics.get("sec_items_with_cik"),
            "sec_items_with_ticker": diagnostics.get("sec_items_with_ticker"),
            "sec_items_without_ticker": diagnostics.get("sec_items_without_ticker"),
            "mapped_to_current_universe": mapped_to_universe,
            "sample_mapped": [
                {
                    "title": item.get("title"),
                    "tickers": item.get("tickers"),
                    "cik": item.get("sec_cik"),
                }
                for item in items
                if item.get("tickers")
            ][:5],
        })
        all_items.extend(items)

    total_items = len(all_items)
    total_with_cik = sum(1 for item in all_items if item.get("sec_cik"))
    total_with_ticker = sum(1 for item in all_items if item.get("tickers"))
    total_in_universe = sum(1 for item in all_items if universe.intersection(item.get("tickers") or []))
    mapping_rate = round(total_with_ticker / total_items, 4) if total_items else None

    artifact = {
        "experiment_id": EXP_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "observed_only",
        "lane": "measurement_repair",
        "change_type": "sec_cik_ticker_mapping_audit",
        "hypothesis": (
            "A local SEC company_tickers cache plus SEC title CIK parsing can turn live "
            "SEC Atom filings into ticker-tagged event rows, releasing the filing-context "
            "shadow alpha branch from the prior zero-join blocker."
        ),
        "mapping_summary": {
            "total_items": total_items,
            "total_with_cik": total_with_cik,
            "total_with_ticker": total_with_ticker,
            "total_without_ticker": total_items - total_with_ticker,
            "total_in_current_universe": total_in_universe,
            "mapping_rate": mapping_rate,
            "feed_results": feed_results,
        },
        "decision": "observed_only",
        "rejection_reason": None,
        "next_action": (
            "Rerun the earnings/SEC round-1 shadow join after at least one forward news "
            "archive contains ticker-tagged SEC rows. If current-universe overlap remains "
            "too small, test a filing-driven shadow universe scout rather than changing "
            "production entries."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "parity_test_added": True,
        },
        "related_files": [
            "quant/sec_ticker_map.py",
            "quant/refresh_sec_company_tickers.py",
            "quant/parser.py",
            "quant/experiments/exp_20260503_005_sec_cik_ticker_mapping_audit.py",
            "data/sec_company_tickers.json",
        ],
    }
    return artifact


def persist(payload: dict) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    TICKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    for path in (ARTIFACT_PATH, LOG_PATH):
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ticket = {
        "experiment_id": EXP_ID,
        "status": payload["status"],
        "title": "SEC CIK-to-ticker mapping audit",
        "summary": payload["hypothesis"],
        "best_variant": "observed_only",
        "best_variant_gate4": False,
        "delta_metrics": payload["mapping_summary"],
        "next_action": payload["next_action"],
    }
    TICKET_PATH.write_text(json.dumps(ticket, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    payload = run()
    persist(payload)
    print(json.dumps(payload["mapping_summary"], indent=2, ensure_ascii=False))
    print(f"wrote: {ARTIFACT_PATH}")
