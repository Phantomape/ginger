"""Focused tests for the research digest builder (exp-20260721-006)."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from build_research_digest import (  # noqa: E402
    DIGEST_BYTE_CAP,
    DIGEST_JSON_PATH,
    DIGEST_MD_PATH,
    LEDGER_PATH,
    MAP_PATH,
    _extract_fields,
    backfill,
    build_digest,
    latest_status,
    parse_map_sections,
    read_mechanism_scan_manifest,
    read_ledger,
)
from quant.alpha_mechanism_generator import build_mechanism_lead_batch  # noqa: E402
import build_research_digest as digest_builder  # noqa: E402


def test_mechanism_generator_provenance_markers_are_preserved():
    fields = _extract_fields(
        """generator_id: ai_berkshire_bottleneck
generator_version: bottleneck-hunter-v1
mechanism_id: grid-transformer-constraint
evidence_grade: LEAD
market_prior_status: UNIDENTIFIED
pit_feasibility: source timestamps must be archived
source_authorization: verified for two primary sources
scan_run_id: mechanism-scan-20260727-001
scan_completed_at: 2026-07-27T06:30:00Z
"""
    )
    assert fields["generator_id"] == "ai_berkshire_bottleneck"
    assert fields["generator_version"] == "bottleneck-hunter-v1"
    assert fields["mechanism_id"] == "grid-transformer-constraint"
    assert fields["evidence_grade"] == "lead"
    assert fields["market_prior_status"] == "unidentified"
    assert fields["pit_feasibility"] == "source timestamps must be archived"
    assert fields["source_authorization"] == "verified for two primary sources"
    assert fields["scan_run_id"] == "mechanism-scan-20260727-001"
    assert fields["scan_completed_at"] == "2026-07-27T06:30:00Z"


def test_generator_markdown_round_trips_through_digest_parser():
    with open(
        os.path.join(REPO_ROOT, "data", "reference", "alpha_mechanism_scan_template.json"),
        encoding="utf-8",
    ) as fh:
        scan = json.load(fh)
    with open(
        os.path.join(REPO_ROOT, "data", "reference", "alpha_mechanism_generators.json"),
        encoding="utf-8",
    ) as fh:
        registry = json.load(fh)
    batch = build_mechanism_lead_batch(scan, registry)
    markdown = batch["research_map_sections"][0]["research_map_markdown"]
    parsed = parse_map_sections(markdown)
    assert len(parsed) == 1
    assert parsed[0]["entry_id"] == batch["research_map_sections"][0]["entry_id"]
    fields = _extract_fields(parsed[0]["body"])
    assert fields["generator_id"] == "ai_berkshire_bottleneck"
    assert fields["market_prior_status"] == "unidentified"
    assert fields["evidence_grade"] == "lead"


def _mechanism_batch(include_lead):
    with open(
        os.path.join(REPO_ROOT, "data", "reference", "alpha_mechanism_scan_template.json"),
        encoding="utf-8",
    ) as fh:
        scan = json.load(fh)
    with open(
        os.path.join(REPO_ROOT, "data", "reference", "alpha_mechanism_generators.json"),
        encoding="utf-8",
    ) as fh:
        registry = json.load(fh)
    if not include_lead:
        scan["leads"] = []
        scan["history_vetoes"] = []
    return build_mechanism_lead_batch(scan, registry)


def test_zero_lead_scan_has_verifiable_freshness(tmp_path):
    path = tmp_path / "latest_mechanism_scan.json"
    path.write_text(json.dumps(_mechanism_batch(False)), encoding="utf-8")
    manifest = read_mechanism_scan_manifest(path, known_entry_ids=set())
    assert manifest["status"] == "no_new_lead"
    assert manifest["lead_count"] == 0
    assert manifest["scan_completed_at"] == "2026-07-27T01:05:00Z"


def test_nonempty_scan_must_be_published_to_map(tmp_path):
    path = tmp_path / "latest_mechanism_scan.json"
    batch = _mechanism_batch(True)
    path.write_text(json.dumps(batch), encoding="utf-8")
    try:
        read_mechanism_scan_manifest(path, known_entry_ids=set())
    except ValueError as exc:
        assert "unpublished map entries" in str(exc)
    else:
        raise AssertionError("unpublished lead batch was accepted")


def test_scan_sidecar_rejects_tampered_batch(tmp_path):
    path = tmp_path / "latest_mechanism_scan.json"
    batch = _mechanism_batch(False)
    batch["scan_manifest"]["status"] = "leads_generated"
    path.write_text(json.dumps(batch), encoding="utf-8")
    try:
        read_mechanism_scan_manifest(path, known_entry_ids=set())
    except ValueError as exc:
        assert "batch_hash mismatch" in str(exc)
    else:
        raise AssertionError("tampered mechanism scan sidecar was accepted")


def test_digest_binds_published_mechanism_batch_without_live_writes(
    tmp_path, monkeypatch
):
    with open(
        os.path.join(REPO_ROOT, "data", "reference", "alpha_mechanism_scan_template.json"),
        encoding="utf-8",
    ) as fh:
        scan = json.load(fh)
    with open(
        os.path.join(REPO_ROOT, "data", "reference", "alpha_mechanism_generators.json"),
        encoding="utf-8",
    ) as fh:
        registry = json.load(fh)
    batch = build_mechanism_lead_batch(scan, registry)

    map_path = tmp_path / "alpha_external_research_map.md"
    ledger_path = tmp_path / "ledger.jsonl"
    digest_md_path = tmp_path / "latest_digest.md"
    digest_json_path = tmp_path / "latest_digest.json"
    scan_path = tmp_path / "latest_mechanism_scan.json"
    map_path.write_text(
        "# Test map\n\n" + batch["research_map_sections"][0]["research_map_markdown"],
        encoding="utf-8",
    )
    scan_path.write_text(json.dumps(batch), encoding="utf-8")
    monkeypatch.setattr(digest_builder, "MAP_PATH", str(map_path))
    monkeypatch.setattr(digest_builder, "LEDGER_PATH", str(ledger_path))
    monkeypatch.setattr(digest_builder, "DIGEST_DIR", str(tmp_path))
    monkeypatch.setattr(digest_builder, "DIGEST_MD_PATH", str(digest_md_path))
    monkeypatch.setattr(digest_builder, "DIGEST_JSON_PATH", str(digest_json_path))
    monkeypatch.setattr(digest_builder, "MECHANISM_SCAN_PATH", str(scan_path))

    stats = digest_builder.build_digest()
    assert stats["entries"] == 1
    payload = json.loads(digest_json_path.read_text(encoding="utf-8"))
    freshness = payload["latest_mechanism_scan"]
    assert freshness["research_date"] == "2026-07-26"
    assert freshness["timezone"] == "America/Los_Angeles"
    assert freshness["scan_run_id"] == scan["run_id"]
    assert freshness["batch_hash"] == batch["batch_hash"]


def test_all_sections_have_unique_entry_ids():
    sections = parse_map_sections(open(MAP_PATH, encoding="utf-8").read())
    assert len(sections) >= 133
    ids = [s["entry_id"] for s in sections]
    assert all(ids), "sections missing entry_id"
    assert len(set(ids)) == len(ids), "duplicate entry_ids"


def test_backfill_idempotent():
    result = backfill()
    assert result["ids_assigned"] == 0
    assert result["ledger_seeded"] == 0


def test_ledger_valid_and_latest_wins():
    events = read_ledger()
    assert events, "ledger empty"
    research_statuses = {
        "fresh", "proposed", "rejected", "accepted",
        "parked", "lane_blocked", "declined",
    }
    for e in events:
        if e["entry_id"].startswith("res-"):
            assert e["status"] in research_statuses
        else:
            assert e["entry_id"].startswith("digest-scan-")
            assert e["status"] == "no_fresh_entries"
    state = latest_status(events)
    assert len(state) <= len(events)


def test_digest_build_caps_and_idempotence():
    first = build_digest()
    ledger_after_first = open(LEDGER_PATH, "rb").read()
    second = build_digest()
    assert second["new_lane_blocked_events"] == 0, "rerun appended events (not idempotent)"
    assert open(LEDGER_PATH, "rb").read() == ledger_after_first
    for key in ("md_bytes", "json_bytes"):
        assert first[key] < DIGEST_BYTE_CAP
    assert os.path.getsize(DIGEST_MD_PATH) < DIGEST_BYTE_CAP
    assert os.path.getsize(DIGEST_JSON_PATH) < DIGEST_BYTE_CAP

    md_ids = [
        line.split()[1]
        for line in open(DIGEST_MD_PATH, encoding="utf-8")
        if line.startswith("## res-")
    ]
    payload = json.load(open(DIGEST_JSON_PATH, encoding="utf-8"))
    json_ids = [entry["entry_id"] for entry in payload["shown"]]
    assert md_ids == json_ids, "Markdown and JSON published different ranked subsets"
    assert second["shown"] == len(md_ids) == len(json_ids)


def test_lane_precheck_flags_at_least_one_entry():
    stats = build_digest()
    assert stats["lane_blocked"] >= 1, (
        "zero lane_blocked entries: precheck wiring broken per acceptance rule"
    )
    payload = json.load(open(DIGEST_JSON_PATH, encoding="utf-8"))
    shown_ids = {e["entry_id"] for e in payload["shown"]}
    state = latest_status(read_ledger())
    blocked = {k for k, v in state.items() if v["status"] == "lane_blocked"}
    assert not (shown_ids & blocked), "lane_blocked entry leaked into digest"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
