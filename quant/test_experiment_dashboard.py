import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_experiment_dashboard import (  # noqa: E402
    build_experiment_index,
    build_production_compare,
    write_dashboard,
)


def test_dashboard_index_splits_actionable_anomalies_from_archive_notes(tmp_path):
    root = tmp_path
    (root / "docs").mkdir()
    (root / "experiments" / "tickets").mkdir(parents=True)
    (root / "docs" / "experiments" / "tickets").mkdir(parents=True)
    (root / "experiments" / "logs").mkdir(parents=True)
    (root / "experiments" / "cards").mkdir(parents=True)
    (root / "experiments" / "manifests").mkdir(parents=True)
    (root / "data" / "experiments" / "exp-20990102-002").mkdir(parents=True)
    (root / "data" / "paper_sleeves" / "state_surface").mkdir(parents=True)

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
    (root / "experiments" / "cards" / "exp-20990102-001.md").write_text(
        "---\nexperiment_id: exp-20990102-001\n---\n# Experiment Card\n",
        encoding="utf-8",
    )
    (root / "experiments" / "manifests" / "exp-20990102-001.json").write_text(
        json.dumps({
            "experiment_id": "exp-20990102-001",
            "manifest_type": "ginger_experiment_revision_manifest",
        }),
        encoding="utf-8",
    )
    (root / "docs" / "experiment_log.jsonl").write_text(
        "\n".join([
            json.dumps({
                "experiment_id": "exp-20990102-002",
                "status": "rejected",
                "hypothesis": "Log-only row should be indexed.",
                "trial_family": "log_only_family",
                "delta_metrics": {
                    "expected_value_score_delta": -0.25,
                    "total_pnl_delta": -1200.0,
                },
            }),
            json.dumps({
                "experiment_id": "exp-20990102-004",
                "status": "rejected",
                "hypothesis": "Rejected but high-upside row should be easy to find.",
                "trial_family": "high_upside_reject_family",
                "delta_metrics": {
                    "expected_value_score_delta": 1.25,
                    "total_pnl_delta": 42000.0,
                },
            }),
        ]) + "\n",
        encoding="utf-8",
    )
    (root / "docs" / "current_state.md").write_text(
        "\n".join([
            "# State",
            "",
            "## Return Constraint / Activation Map",
            "",
            "| Surface | Default execution status | Current evidence | Limits | Activation lever | Risk |",
            "|---|---|---|---|---|---|",
            "| `STATE_SURFACE_SATELLITE` | Default-off paper only; live/default orders disabled | Accepted paper refinements | Needs closed forward replacement-value rows | Trade-enabled satellite sleeve | Concentration |",
        ]),
        encoding="utf-8",
    )
    (root / "data" / "paper_sleeves" / "state_surface" / "state.json").write_text(
        json.dumps({
            "sleeve": "STATE_SURFACE_SATELLITE_PAPER",
            "updated_at": "2099-01-02T00:00:00+00:00",
            "open_positions": [{"ticker": "AAA", "unrealized_pnl": 12.5}],
            "pending_entries": [{"ticker": "BBB"}],
            "closed_positions": [{"ticker": "CCC"}, {"ticker": "DDD"}, {"ticker": "EEE"}],
            "skipped_entries": [],
        }),
        encoding="utf-8",
    )

    index = build_experiment_index(root, registry_path, today="20990102")
    by_id = {row["experiment_id"]: row for row in index["experiments"]}

    assert index["next_experiment_id"] == "exp-20990102-005"
    assert "split_brain_ticket_paths" not in by_id["exp-20990102-001"]["anomalies"]
    assert "docs_ticket" not in by_id["exp-20990102-001"]["sources"]
    assert "card" in by_id["exp-20990102-001"]["sources"]
    assert "manifest" in by_id["exp-20990102-001"]["sources"]
    assert "experiments/tickets/exp-20990102-001.json" in by_id["exp-20990102-001"]["files"]
    assert "experiments/cards/exp-20990102-001.md" in by_id["exp-20990102-001"]["files"]
    assert (
        "experiments/manifests/exp-20990102-001.json"
        in by_id["exp-20990102-001"]["files"]
    )
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
    assert (
        index["leaderboards"]["rejected_high_upside"][0]["experiment_id"]
        == "exp-20990102-004"
    )
    assert index["leaderboards"]["high_after_ev"] == []
    assert index["leaderboards"]["rejected_high_after_ev"] == []
    assert index["leaderboards"]["unresolved_rejected_high_after_ev"] == []
    assert index["leaderboards"]["resolved_rejected_high_after_ev"] == []
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
    assert any(
        collection["slug"] == "rejected_high_upside" and collection["count"] == 1
        for collection in index["collections"]
    )
    compare = index["production_compare"]
    assert compare["summary"]["forward_accumulating_count"] == 1
    assert compare["summary"]["paper_closed_count"] == 3
    assert compare["surfaces"][0]["evidence_gap"] == 17


def test_production_compare_reads_activation_map_and_live_positions(tmp_path):
    root = tmp_path
    (root / "docs").mkdir()
    (root / "operator_inputs").mkdir()
    (root / "data" / "paper_sleeves" / "broad_market").mkdir(parents=True)
    (root / "data" / "paper_sleeves" / "low_deployment_etf").mkdir(parents=True)
    (root / "docs" / "current_state.md").write_text(
        "\n".join([
            "## Return Constraint / Activation Map",
            "| Surface | Default execution status | Current evidence | Limits | Activation lever | Risk |",
            "|---|---|---|---|---|---|",
            "| Core live stack | Trade-enabled default path | Accepted core stack | Conservative caps | Gate 1-4 | Drawdown |",
            "| `BROAD_MARKET_LEADERSHIP_PAPER` | Default-off paper only; live/default orders disabled | Paper adapter | Needs closed forward replacement-value outcomes | Small sleeve | Hidden beta |",
            "| Low-deployment ETF overlay | Paper-only overlay | Parity contract allows paper ETF overlay attribution only | Cash semantics, closed forward outcomes, and explicit trade adapter are not ready | Cash-deployment sleeve | Whipsaw |",
        ]),
        encoding="utf-8",
    )
    (root / "operator_inputs" / "open_positions.json").write_text(
        json.dumps({
            "as_of": "2099-01-02",
            "positions": [{"ticker": "AAA", "opened_by_strategy": "breakout_long"}],
            "observations": [{"ticker": "BBB", "opened_by_strategy": "legacy"}],
        }),
        encoding="utf-8",
    )
    (root / "data" / "paper_sleeves" / "broad_market" / "state.json").write_text(
        json.dumps({
            "sleeve": "BROAD_MARKET_LEADERSHIP_PAPER",
            "open_positions": [{"ticker": "RKLB"}],
            "pending_entries": [{"ticker": "PL"}],
            "closed_positions": [{"ticker": "IRDM"}],
        }),
        encoding="utf-8",
    )
    (root / "data" / "paper_sleeves" / "broad_market" / "snapshots.jsonl").write_text(
        "\n".join([
            json.dumps({
                "asof_date": "2099-01-01",
                "open_position_count": 1,
                "pending_count": 1,
                "closed_position_count": 0,
                "parameters": {"forward_gate_min_closed_trades": 4},
                "sleeve": "BROAD_MARKET_LEADERSHIP_PAPER",
            }),
            json.dumps({
                "asof_date": "2099-01-02",
                "open_position_count": 1,
                "pending_count": 0,
                "closed_position_count": 1,
                "parameters": {"forward_gate_min_closed_trades": 4},
                "sleeve": "BROAD_MARKET_LEADERSHIP_PAPER",
            }),
        ]) + "\n",
        encoding="utf-8",
    )
    (root / "data" / "paper_sleeves" / "low_deployment_etf" / "state.json").write_text(
        json.dumps({
            "sleeve": "LOW_DEPLOYMENT_DYNAMIC_ETF_OVERLAY_PAPER",
            "updated_at": "2099-01-02T00:00:00+00:00",
            "closed_positions": [{"ticker": "QQQ"} for _ in range(24)],
            "parameters": {"forward_gate_min_closed_trades": 60},
        }),
        encoding="utf-8",
    )
    (root / "data" / "paper_sleeves" / "low_deployment_etf" / "snapshots.jsonl").write_text(
        "\n".join([
            json.dumps({
                "asof_date": "2099-01-02",
                "closed_position_count": 24,
                "parameters": {"forward_gate_min_closed_trades": 60},
                "sleeve": "LOW_DEPLOYMENT_DYNAMIC_ETF_OVERLAY_PAPER",
            }),
        ]) + "\n",
        encoding="utf-8",
    )

    compare = build_production_compare(root)

    assert compare["summary"]["executing_count"] == 1
    assert compare["summary"]["forward_accumulating_count"] == 2
    assert compare["summary"]["paper_closed_count"] == 25
    assert compare["summary"]["paper_open_count"] == 1
    assert compare["live_positions"]["count"] == 2
    broad_curve = [
        curve
        for curve in compare["evidence_curves"]
        if curve["sleeve"] == "BROAD_MARKET_LEADERSHIP_PAPER"
    ][0]
    assert broad_curve["target_count"] == 4
    assert broad_curve["points"][-1]["pipeline_pct"] > 0
    broad = [row for row in compare["surfaces"] if "BROAD_MARKET" in row["surface"]][0]
    assert broad["paper_pending_count"] == 1
    assert broad["required_closed_forward"] == 4
    assert broad["target_basis"] == "paper_sleeve_forward_gate"
    assert broad["evidence_gap"] == 3
    low_deployment = [
        row for row in compare["surfaces"] if "Low-deployment" in row["surface"]
    ][0]
    assert low_deployment["paper_closed_count"] == 24
    assert low_deployment["required_closed_forward"] == 60
    assert low_deployment["target_basis"] == "paper_sleeve_forward_gate"
    assert low_deployment["evidence_gap"] == 36
    low_deployment_curve = [
        curve
        for curve in compare["evidence_curves"]
        if curve["sleeve"] == "LOW_DEPLOYMENT_DYNAMIC_ETF_OVERLAY_PAPER"
    ][0]
    assert low_deployment_curve["target_count"] == 60
    assert low_deployment_curve["closed_count"] == 24


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
            "high_after_ev": [],
            "rejected_high_after_ev": [],
            "unresolved_rejected_high_after_ev": [],
            "resolved_rejected_high_after_ev": [],
            "rejected_high_upside": [],
            "rejected_families": [],
        },
        "dataset_view": {"columns": []},
        "collections": [],
        "production_compare": {
            "summary": {},
            "surfaces": [],
            "paper_sleeves": [],
            "evidence_curves": [],
            "live_positions": {},
            "generated_from": [],
        },
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
    assert "Hub-style local browser" in html
    assert "Experiment Hub" in html
    assert "detail-panel" in html
    assert "repo-card" in html
    assert "color-scheme: dark" in html
    assert "--panel: #282c34" in html
    assert "overflow-wrap: anywhere" in html
    assert "-webkit-line-clamp: 2" in html
    assert "Reset filters" in html
    assert "data-density=\"compact\"" in html
    assert "filter-chip" in html
    assert "Pinned Compare" in html
    assert "data-action=\"copy-id\"" in html
    assert "score-pill" in html
    assert "Leaderboards" in html
    assert "Rejected Upside" in html
    assert "Rejected High-Upside" in html
    assert "High After EV" in html
    assert "Rejected After EV &gt; 10" in html
    assert "Still Open High EV Rejects" in html
    assert "Resolved High EV Rejects" in html
    assert "Accepted Follow-Ups" in html
    assert "After EV" in html
    assert "Dataset View" in html
    assert "Collections" in html
    assert "Prod Compare" in html
    assert "Production vs Backtest" in html
    assert "Forward Evidence Curves" in html
    assert "snapshot date from paper sleeve snapshots.jsonl" in html
    assert "Series indexed" in html
    assert "curve.closed_count" in html
    assert "curve.target_count" in html
    assert "curve-point" in html
    assert "curve-hit" in html
    assert "snapshot point" in html
    json_text = json_path.read_text(encoding="utf-8")
    assert "Infinity" not in html
    assert "Infinity" not in json_text
    assert "NaN" not in json_text
    assert json.loads(json_text)["next_experiment_id"] == "exp-20990102-003"
