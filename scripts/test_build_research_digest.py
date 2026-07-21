"""Focused tests for the research digest builder (exp-20260721-006)."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_research_digest import (  # noqa: E402
    DIGEST_BYTE_CAP,
    DIGEST_JSON_PATH,
    DIGEST_MD_PATH,
    LEDGER_PATH,
    MAP_PATH,
    backfill,
    build_digest,
    latest_status,
    parse_map_sections,
    read_ledger,
)


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
    for e in events:
        assert e["entry_id"].startswith("res-")
        assert e["status"] in {
            "fresh", "proposed", "rejected", "accepted",
            "parked", "lane_blocked", "declined",
        }
    state = latest_status(events)
    assert len(state) <= len(events)


def test_digest_build_caps_and_idempotence():
    first = build_digest()
    second = build_digest()
    assert second["new_lane_blocked_events"] == 0, "rerun appended events (not idempotent)"
    for key in ("md_bytes", "json_bytes"):
        assert first[key] < DIGEST_BYTE_CAP
    assert os.path.getsize(DIGEST_MD_PATH) < DIGEST_BYTE_CAP
    assert os.path.getsize(DIGEST_JSON_PATH) < DIGEST_BYTE_CAP


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
