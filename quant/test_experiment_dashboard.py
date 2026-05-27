import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_experiment_dashboard import build_experiment_index, write_dashboard  # noqa: E402


def test_dashboard_index_splits_actionable_anomalies_from_archive_notes(tmp_path):
    root = tmp_path
    (root / "docs").mkdir()
    (root / "experiments" / "tickets").mkdir(parents=True)
    (root / "docs" / "experiments" / "tickets").mkdir(parents=True)
    (root / "experiments" / "logs").mkdir(parents=True)
    (root / "data" / "experiments" / "exp-20990102-002").mkdir(parents=True)

    registry_path = root / "docs" / "experiment_registry.json"
    registry_path.write_text(
        json.dumps({
            "schema_version": 1,
            "updated_at": None,
            "experiments": [
                {
                    "experiment_id": "exp-20990102-001",
                    "status": "proposed",
                    "lane": "measurement_repair",
                    "ticket_file": "experiments/tickets/exp-20990102-001.json",
                },
                {
                    "experiment_id": "exp-20990102-003",
                    "status": "proposed",
                    "lane": "measurement_repair",
                    "ticket_file": "experiments/tickets/exp-20990102-003.json",
                }
            ],
        }),
        encoding="utf-8",
    )
    ticket_payload = {
        "experiment_id": "exp-20990102-001",
        "status": "claimed",
        "lane": "measurement_repair",
    }
    for ticket_dir in (
        root / "experiments" / "tickets",
        root / "docs" / "experiments" / "tickets",
    ):
        (ticket_dir / "exp-20990102-001.json").write_text(
            json.dumps(ticket_payload),
            encoding="utf-8",
        )
    (root / "experiments" / "tickets" / "exp-20990102-003.json").write_text(
        json.dumps({
            "experiment_id": "exp-20990102-003",
            "status": "claimed",
            "lane": "measurement_repair",
        }),
        encoding="utf-8",
    )
    (root / "docs" / "experiments" / "tickets" / "exp-20990102-003.json").write_text(
        json.dumps({
            "experiment_id": "exp-20990102-003",
            "status": "proposed",
            "lane": "measurement_repair",
        }),
        encoding="utf-8",
    )
    (root / "docs" / "experiment_log.jsonl").write_text(
        json.dumps({
            "experiment_id": "exp-20990102-002",
            "status": "rejected",
            "hypothesis": "Log-only row should be indexed.",
            "trial_family": "log_only_family",
            "delta_metrics": {
                "expected_value_score_delta": -0.25,
                "total_pnl_delta": -1200.0,
            },
        }) + "\n",
        encoding="utf-8",
    )

    index = build_experiment_index(root, registry_path, today="20990102")
    by_id = {row["experiment_id"]: row for row in index["experiments"]}

    assert index["next_experiment_id"] == "exp-20990102-004"
    assert "split_brain_ticket_paths" not in by_id["exp-20990102-001"]["anomalies"]
    assert "docs_ticket" not in by_id["exp-20990102-001"]["sources"]
    assert "experiments/tickets/exp-20990102-001.json" in by_id["exp-20990102-001"]["files"]
    assert "docs/experiments/tickets/exp-20990102-001.json" not in by_id[
        "exp-20990102-001"
    ]["files"]
    assert "split_brain_ticket_paths" not in by_id["exp-20990102-003"]["anomalies"]
    assert "missing_from_registry" not in by_id["exp-20990102-002"]["anomalies"]
    assert "archive_missing_from_registry" in by_id["exp-20990102-002"]["identity_notes"]
    assert (
        "archive_jsonl_without_per_experiment_log"
        in by_id["exp-20990102-002"]["identity_notes"]
    )
    assert by_id["exp-20990102-002"]["card"]["metadata"]["trial_family"] == "log_only_family"
    assert by_id["exp-20990102-002"]["metrics"]["expected_value_score_delta"] == -0.25
    assert index["leaderboards"]["bottom_ev_delta"][0]["experiment_id"] == "exp-20990102-002"
    assert index["summary"]["anomaly_experiment_count"] == 0
    assert index["summary"]["identity_note_experiment_count"] >= 1
    assert any(
        column["field"] == "trial_family" and column["unique"] >= 1
        for column in index["dataset_view"]["columns"]
    )
    assert any(
        collection["slug"] == "archive_identity_notes" and collection["count"] >= 1
        for collection in index["collections"]
    )


def test_dashboard_writer_outputs_static_html_and_json(tmp_path):
    index = {
        "schema_version": 1,
        "generated_at": "2099-01-02T00:00:00+00:00",
        "root": str(tmp_path),
        "registry_path": "docs/experiment_registry.json",
        "next_experiment_id": "exp-20990102-003",
        "summary": {
            "experiment_count": 1,
            "registry_count": 1,
            "status_counts": {"proposed": 1},
            "anomaly_counts": {},
            "anomaly_experiment_count": 0,
        },
        "leaderboards": {
            "top_ev_delta": [],
            "bottom_ev_delta": [],
            "top_pnl_delta": [],
            "rejected_families": [],
        },
        "dataset_view": {"columns": []},
        "collections": [],
        "experiments": [
            {
                "experiment_id": "exp-20990102-001",
                "status_group": "proposed",
                "sources": ["registry"],
                "anomalies": [],
                "delta_metrics": {"return_factor": float("inf")},
            }
        ],
    }

    html_path, json_path = write_dashboard(index, tmp_path / "dashboard")

    assert html_path.exists()
    assert json_path.exists()
    html = html_path.read_text(encoding="utf-8")
    assert "Ginger Experiment Dashboard" in html
    assert "Leaderboards" in html
    assert "Dataset View" in html
    assert "Collections" in html
    json_text = json_path.read_text(encoding="utf-8")
    assert "Infinity" not in html
    assert "Infinity" not in json_text
    assert "NaN" not in json_text
    assert json.loads(json_text)["next_experiment_id"] == "exp-20990102-003"
