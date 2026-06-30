import json
from pathlib import Path

from run_intraday import _persist_intraday_structured_news_observation


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_run_intraday_structured_news_wiring_is_default_off(tmp_path):
    date_tag = "20260629"
    time_label = "1300ET"
    _write_json(
        tmp_path
        / "daily"
        / "intraday"
        / "news"
        / f"intraday_trade_news_{date_tag}_{time_label}.json",
        [
            {
                "title": "AMD raises guidance",
                "summary": "AMD raises guidance by 12% after strong earnings",
                "published_at": "2026-06-29T17:00:00Z",
                "tickers": ["AMD"],
                "source": "unit",
            }
        ],
    )
    _write_json(
        tmp_path
        / "daily"
        / "intraday"
        / "snapshots"
        / f"intraday_review_{date_tag}_{time_label}.json",
        {
            "date": date_tag,
            "time_label": time_label,
            "capture_time_et": "2026-06-29 13:00 ET",
        },
    )

    snapshot = _persist_intraday_structured_news_observation(
        date_tag,
        time_label,
        tmp_path,
    )

    assert snapshot["trade_enabled"] is False
    assert snapshot["strategy_behavior_changed"] is False
    event_path = Path(snapshot["event_artifact_path"])
    observation_path = Path(snapshot["forward_observation_artifact_path"])
    assert event_path.exists()
    assert observation_path.exists()
    event_payload = json.loads(event_path.read_text(encoding="utf-8"))
    observations = _read_jsonl(observation_path)
    assert event_payload["event_contract_audit"]["selected_ledger_rows"] >= 1
    assert len(observations) == event_payload["event_contract_audit"]["selected_ledger_rows"]
    assert {row["outcome_status"] for row in observations} == {"pending_forward_close"}
    assert any(row["target_relation_quality"] is True for row in observations)
