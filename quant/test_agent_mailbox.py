"""Tests for the file-based agent mailbox (scripts/agent_mailbox.py).

Covers: sequence allocation + atomic no-overwrite, recv ordering/cursor
advance, recv skipping your own messages, --peer filtering, timeout, transcript
order, and a real cross-thread listen (recv blocks, then returns once a message
is written by another thread).
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import agent_mailbox as mb  # noqa: E402


def test_send_allocates_increasing_sequences(tmp_path):
    assert mb.send_message("c", "A", "one", root=tmp_path) == 1
    assert mb.send_message("c", "B", "two", root=tmp_path) == 2
    assert mb.send_message("c", "A", "three", root=tmp_path) == 3
    files = sorted((tmp_path / "c").glob("*.json"))
    assert [p.name for p in files] == ["0001-A.json", "0002-B.json", "0003-A.json"]


def test_send_never_overwrites_a_taken_sequence(tmp_path):
    mb.send_message("c", "A", "one", root=tmp_path)
    # Pre-create the file the next seq would use, as a different sender, to
    # simulate a concurrent winner; send must skip to the following seq.
    (tmp_path / "c" / "0002-X.json").write_text(
        '{"channel":"c","seq":2,"from":"X","text":"race","ts":"t"}',
        encoding="utf-8",
    )
    seq = mb.send_message("c", "A", "two", root=tmp_path)
    assert seq == 3
    assert (tmp_path / "c" / "0002-X.json").read_text(encoding="utf-8").startswith(
        '{"channel":"c","seq":2,"from":"X"'
    )  # untouched


def test_recv_returns_peer_message_and_advances_cursor(tmp_path):
    mb.send_message("c", "A", "hi from A", root=tmp_path)
    mb.send_message("c", "A", "second from A", root=tmp_path)
    first = mb.recv_message("c", "B", timeout=2, root=tmp_path)
    assert first["from"] == "A" and first["text"] == "hi from A"
    second = mb.recv_message("c", "B", timeout=2, root=tmp_path)
    assert second["text"] == "second from A"  # cursor advanced, not re-read


def test_recv_skips_own_messages(tmp_path):
    mb.send_message("c", "A", "A1", root=tmp_path)
    mb.send_message("c", "B", "B1", root=tmp_path)
    # A should skip its own A1 and read B1.
    got = mb.recv_message("c", "A", timeout=2, root=tmp_path)
    assert got["from"] == "B" and got["text"] == "B1"


def test_recv_peer_filter(tmp_path):
    mb.send_message("c", "B", "from B", root=tmp_path)
    mb.send_message("c", "C", "from C", root=tmp_path)
    got = mb.recv_message("c", "A", peer="C", timeout=2, root=tmp_path)
    assert got["from"] == "C"


def test_recv_timeout_returns_none(tmp_path):
    t0 = time.time()
    got = mb.recv_message("c", "A", timeout=1, root=tmp_path, poll=0.05)
    assert got is None
    assert time.time() - t0 >= 1


def test_recv_blocks_then_returns_when_message_arrives(tmp_path):
    def delayed_send():
        time.sleep(0.3)
        mb.send_message("c", "A", "late hello", root=tmp_path)

    th = threading.Thread(target=delayed_send)
    th.start()
    got = mb.recv_message("c", "B", timeout=5, root=tmp_path, poll=0.05)
    th.join()
    assert got is not None and got["text"] == "late hello"


def test_transcript_is_ordered(tmp_path):
    mb.send_message("c", "A", "1", root=tmp_path)
    mb.send_message("c", "B", "2", root=tmp_path)
    mb.send_message("c", "A", "3", root=tmp_path)
    rows = mb.read_transcript("c", root=tmp_path)
    assert [r["seq"] for r in rows] == [1, 2, 3]
    assert [r["from"] for r in rows] == ["A", "B", "A"]


def test_list_channels(tmp_path):
    mb.send_message("alpha", "A", "x", root=tmp_path)
    mb.send_message("beta", "A", "y", root=tmp_path)
    assert mb.list_channels(root=tmp_path) == ["alpha", "beta"]


def test_extract_references():
    exp_ids, paths = mb.extract_references(
        "see exp-20260628-014 and data/x/y.json, plus exp-20260101-001 "
        "(docs/agent_mailbox.md)."
    )
    assert exp_ids == {"exp-20260628-014", "exp-20260101-001"}
    assert "data/x/y.json" in paths
    assert "docs/agent_mailbox.md" in paths


def test_verify_flags_dangling_but_not_existing(tmp_path):
    repo = tmp_path / "repo"
    (repo / "experiments" / "tickets").mkdir(parents=True)
    (repo / "experiments" / "tickets" / "exp-20260628-014.json").write_text("{}")
    (repo / "docs").mkdir()
    (repo / "docs" / "real.md").write_text("x")
    mbox = tmp_path / "mbox"
    mb.send_message("c", "A", "grounded: exp-20260628-014 and docs/real.md",
                    root=mbox)
    mb.send_message("c", "B", "bad: exp-20260628-999 and docs/missing.md",
                    root=mbox)
    rep = mb.verify_channel("c", root=mbox, repo_root=repo)
    refs = {(f["kind"], f["ref"]) for f in rep["dangling"]}
    assert ("exp_id", "exp-20260628-999") in refs
    assert ("path", "docs/missing.md") in refs
    # existing references are NOT flagged
    assert ("exp_id", "exp-20260628-014") not in refs
    assert ("path", "docs/real.md") not in refs


def test_verify_cannot_catch_misattribution(tmp_path):
    """Documents the known limit: an existing-but-wrong id passes verify."""
    repo = tmp_path / "repo"
    (repo / "experiments" / "tickets").mkdir(parents=True)
    (repo / "experiments" / "tickets" / "exp-20260628-007.json").write_text("{}")
    mbox = tmp_path / "mbox"
    # Claim attributes a fact to a real id that is actually a different exp.
    mb.send_message("c", "A", "low_deployment_etf has 17 rows (exp-20260628-007)",
                    root=mbox)
    rep = mb.verify_channel("c", root=mbox, repo_root=repo)
    assert rep["dangling"] == []  # exists -> not flagged, even though mis-cited
