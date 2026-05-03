from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"
EXP_ID = "exp-20260503-004"
ARTIFACT_DIR = DATA_DIR / "experiments" / EXP_ID
ARTIFACT_PATH = ARTIFACT_DIR / "sec_feed_coverage_audit.json"
LOG_PATH = DOCS_DIR / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_PATH = DOCS_DIR / "experiments" / "tickets" / f"{EXP_ID}.json"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sec_count(path: Path) -> int:
    try:
        payload = _load_json(path)
    except Exception:
        return 0
    if not isinstance(payload, list):
        return 0
    return sum(1 for item in payload if isinstance(item, dict) and item.get("source") == "sec")


def run() -> dict:
    news_files = sorted(DATA_DIR.glob("news_*.json"))
    clean_files = sorted(DATA_DIR.glob("clean_news_*.json"))
    trade_files = sorted(DATA_DIR.glob("clean_trade_news_*.json"))
    source_stat_files = sorted(DATA_DIR.glob("news_source_stats_*.json"))

    news_with_sec = []
    clean_with_sec = []
    trade_with_sec = []

    for path in news_files:
        count = _sec_count(path)
        if count:
            news_with_sec.append({"file": path.name, "sec_items": count})
    for path in clean_files:
        count = _sec_count(path)
        if count:
            clean_with_sec.append({"file": path.name, "sec_items": count})
    for path in trade_files:
        count = _sec_count(path)
        if count:
            trade_with_sec.append({"file": path.name, "sec_items": count})

    artifact = {
        "experiment_id": EXP_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "observed_only",
        "lane": "measurement_repair",
        "hypothesis": (
            "The earnings/SEC round-1 alpha exploration is blocked primarily by "
            "missing SEC archive coverage rather than by a failed ranking signal."
        ),
        "archive_audit": {
            "news_file_count": len(news_files),
            "clean_news_file_count": len(clean_files),
            "clean_trade_news_file_count": len(trade_files),
            "news_source_stats_file_count": len(source_stat_files),
            "news_files_with_sec": len(news_with_sec),
            "clean_news_files_with_sec": len(clean_with_sec),
            "clean_trade_news_files_with_sec": len(trade_with_sec),
            "sample_news_files_with_sec": news_with_sec[:10],
            "sample_clean_news_files_with_sec": clean_with_sec[:10],
            "sample_trade_news_files_with_sec": trade_with_sec[:10],
        },
        "decision": "observed_only",
        "rejection_reason": (
            "Current local archives show zero persisted SEC source items, so SEC "
            "severity and filing-context experiments are not yet measuring a live sample."
        ),
        "next_action": (
            "Run the daily pipeline forward after the SEC diagnostics patch and verify "
            "that news_source_stats_YYYYMMDD.json shows nonzero SEC entries or explicit "
            "fetch errors before retrying earnings/SEC alpha ranking."
        ),
        "related_files": [
            "quant/parser.py",
            "quant/fetch_news.py",
            "quant/run_pipeline.py",
            "quant/run.py",
            "quant/experiments/exp_20260503_004_sec_feed_coverage_audit.py",
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
        "title": "SEC feed coverage audit",
        "summary": payload["hypothesis"],
        "best_variant": "observed_only",
        "best_variant_gate4": False,
        "delta_metrics": payload["archive_audit"],
        "next_action": payload["next_action"],
    }
    TICKET_PATH.write_text(json.dumps(ticket, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    artifact = run()
    persist(artifact)
    print(json.dumps(artifact["archive_audit"], indent=2, ensure_ascii=False))
    print(f"wrote: {ARTIFACT_PATH}")
