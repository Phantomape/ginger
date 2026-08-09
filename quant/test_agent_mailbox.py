"""Tests for the file-based agent mailbox (scripts/agent_mailbox.py).

Covers legacy sequence/receive compatibility plus structured launch receipts,
attachment hashing, path hardening, cross-runtime verification, and native
Codex/Claude dispatch through fakes. No test launches an external model CLI.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def _make_receipt(
    tmp_path,
    *,
    channel="debate",
    participant="challenger",
    role="challenger",
    runtime="claude",
    run_id="run-1",
    initiator_runtime="codex",
    acknowledged=True,
    requested_model="test-model",
):
    exe = tmp_path / f"{runtime}.exe"
    exe.write_bytes(f"fake-{runtime}-native-cli".encode())
    return mb.make_launch_receipt(
        channel=channel,
        participant=participant,
        role=role,
        runtime=runtime,
        run_id=run_id,
        executable=exe,
        executable_version=f"{runtime} 1.2.3",
        requested_model=requested_model,
        cross_provider_acknowledged=acknowledged,
        nonce=f"nonce-{run_id}",
        initiator_runtime=initiator_runtime,
    )


def _assert_cross_runtime_dispatch_channel(info, runtime, mailbox_root):
    channel = f"debate-{runtime}"
    mb.send_message(
        channel, "challenger", "reply",
        role="challenger", runtime=runtime,
        provider=mb.RUNTIME_PROVIDERS[runtime], run_id=f"run-{runtime}",
        identity_receipt=info["receipt"], root=mailbox_root,
    )
    report = mb.verify_channel(channel, root=mailbox_root, repo_root=mailbox_root)
    assert report["legacy_messages"] == 0
    assert report["structured_valid"] is True
    assert report["cross_model_verified"] is True
    peer_receipt = info["receipt"]
    verifier_receipt = mb.make_launch_receipt(
        channel=channel, participant="verifier", role="verifier",
        runtime=runtime, run_id=f"verify-{runtime}",
        executable=peer_receipt["executable"],
        executable_version=peer_receipt["executable_version"],
        cross_provider_acknowledged=True,
        initiator_runtime=info["initiator_receipt"]["runtime"],
    )
    mb.send_message(
        channel, "verifier", "verified", role="verifier", runtime=runtime,
        provider=mb.RUNTIME_PROVIDERS[runtime], run_id=f"verify-{runtime}",
        identity_receipt=verifier_receipt, root=mailbox_root,
    )
    final_report = mb.verify_channel(
        channel, root=mailbox_root, repo_root=mailbox_root,
    )
    assert final_report["structured_valid"] is True
    assert final_report["role_run_ids"]["verifier"] == [f"verify-{runtime}"]


def test_legacy_message_schema_is_unchanged(tmp_path):
    seq = mb.send_message("legacy", "A", "hello", root=tmp_path)
    row = json.loads((tmp_path / "legacy" / "0001-A.json").read_text())
    assert seq == 1
    assert set(row) == {"channel", "seq", "from", "text", "ts"}


def test_legacy_send_and_recv_cli_output_is_unchanged(tmp_path, capsys):
    mb.main([
        "--mailbox-root", str(tmp_path), "send", "--channel", "legacy",
        "--me", "A", "--text", "hello",
    ])
    assert capsys.readouterr().out.strip() == "[sent channel=legacy seq=1 from=A]"
    mb.main([
        "--mailbox-root", str(tmp_path), "recv", "--channel", "legacy",
        "--me", "B", "--timeout", "1",
    ])
    output = capsys.readouterr()
    assert output.out.strip() == "hello"
    assert output.err.strip() == "[from=A seq=1]"


def test_launch_receipt_is_canonical_bound_and_nonthrowing(tmp_path):
    receipt = _make_receipt(tmp_path)
    report = mb.validate_launch_receipt(
        receipt,
        expected_channel="debate",
        expected_participant="challenger",
        expected_role="challenger",
        expected_runtime="claude",
        expected_provider="anthropic",
        expected_run_id="run-1",
    )
    assert report["valid"] is True
    assert receipt["provider"] == mb.RUNTIME_PROVIDERS["claude"]
    assert receipt["receipt_hash"] == mb.canonical_hash(
        {key: value for key, value in receipt.items() if key != "receipt_hash"}
    )

    tampered = copy.deepcopy(receipt)
    tampered["provider"] = "openai"
    bad = mb.validate_launch_receipt(tampered)
    assert bad["valid"] is False
    assert "provider_runtime_mismatch" in bad["errors"]

    model_tampered = copy.deepcopy(receipt)
    model_tampered["requested_model"] = "different-model"
    model_bad = mb.validate_launch_receipt(model_tampered)
    assert model_bad["valid"] is False
    assert "receipt_hash_mismatch" in model_bad["errors"]
    assert mb.validate_launch_receipt(None)["valid"] is False


def _send_codex_model_debate(tmp_path, *, models):
    roles = ("initiator", "challenger", "verifier")
    for index, (role, model) in enumerate(zip(roles, models, strict=True), 1):
        receipt = _make_receipt(
            tmp_path,
            participant=f"{role}-person",
            role=role,
            runtime="codex",
            run_id=f"run-{index}",
            initiator_runtime="codex",
            acknowledged=False,
            requested_model=model,
        )
        mb.send_message(
            "debate", role, f"{role} message", role=role, runtime="codex",
            provider="openai", run_id=f"run-{index}",
            identity_receipt=receipt, root=tmp_path,
        )
    return mb.verify_channel("debate", root=tmp_path, repo_root=tmp_path)


def test_codex_model_diverse_debate_is_verified(tmp_path):
    report = _send_codex_model_debate(
        tmp_path, models=("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-sol"),
    )
    assert report["structured_valid"] is True
    assert report["cross_model_verified"] is False
    assert report["codex_model_diverse_verified"] is True
    assert report["verification_level"] == (
        "launcher_attested_codex_model_diverse"
    )
    assert report["requested_models_by_role"] == {
        "initiator": ["gpt-5.6-sol"],
        "challenger": ["gpt-5.6-terra"],
        "verifier": ["gpt-5.6-sol"],
    }


def test_codex_same_model_debate_is_not_model_diverse(tmp_path):
    report = _send_codex_model_debate(
        tmp_path, models=("gpt-5.6-sol", "gpt-5.6-sol", "gpt-5.6-sol"),
    )
    assert report["structured_valid"] is True
    assert report["codex_model_diverse_verified"] is False
    assert report["verification_level"] == "launcher_attested_single_runtime"


def test_codex_challenger_and_verifier_must_use_different_models(tmp_path):
    report = _send_codex_model_debate(
        tmp_path, models=("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-terra"),
    )
    assert report["structured_valid"] is True
    assert report["codex_model_diverse_verified"] is False
    assert report["verification_level"] == "launcher_attested_single_runtime"


@pytest.mark.parametrize("missing_model", [None, "", "   "])
def test_codex_missing_or_blank_model_is_not_model_diverse(
    tmp_path, missing_model,
):
    report = _send_codex_model_debate(
        tmp_path,
        models=("gpt-5.6-sol", "gpt-5.6-terra", missing_model),
    )
    assert report["structured_valid"] is True
    assert report["codex_model_diverse_verified"] is False
    assert report["verification_level"] == "launcher_attested_single_runtime"


def test_sender_string_is_not_receipt_identity(tmp_path):
    receipt = _make_receipt(tmp_path, participant="real-participant")
    mb.send_message(
        "debate", "display-name", "structured",
        role="challenger", runtime="claude", provider="anthropic",
        run_id="run-1", identity_receipt=receipt, root=tmp_path,
    )
    row = mb.read_transcript("debate", root=tmp_path)[0]
    assert row["from"] == "display-name"
    assert row["identity_receipt"]["participant"] == "real-participant"


def test_structured_attachments_are_hashed_and_cross_runtime_verified(tmp_path):
    cdir = tmp_path / "debate"
    attachments = cdir / "attachments"
    attachments.mkdir(parents=True)
    first = attachments / "proposal.json"
    second = attachments / "challenge.md"
    first.write_text('{"candidate":"x"}', encoding="utf-8")
    second.write_text("counter-evidence", encoding="utf-8")
    codex_receipt = _make_receipt(
        tmp_path, participant="proposer", role="proposer", runtime="codex",
        run_id="run-codex", initiator_runtime="claude",
    )
    claude_receipt = _make_receipt(
        tmp_path, participant="challenger", role="challenger", runtime="claude",
        run_id="run-claude", initiator_runtime="codex",
    )
    mb.send_message(
        "debate", "p", "proposal", role="proposer", runtime="codex",
        provider="openai", run_id="run-codex",
        identity_receipt=codex_receipt, attachment="attachments/proposal.json",
        root=tmp_path,
    )
    mb.send_message(
        "debate", "c", "challenge", role="challenger", runtime="claude",
        provider="anthropic", run_id="run-claude",
        identity_receipt=claude_receipt, attachment="attachments/challenge.md",
        root=tmp_path,
    )
    report = mb.verify_channel("debate", root=tmp_path, repo_root=tmp_path)
    assert report["errors"] == []
    assert report["structured_valid"] is True
    assert report["cross_model_verified"] is True
    assert set(report["attachment_sha256"]) == {
        "attachments/proposal.json", "attachments/challenge.md",
    }
    assert len(report["transcript_sha256"]) == 64


def test_attachment_tamper_fails_verification(tmp_path):
    cdir = tmp_path / "debate"
    attachments = cdir / "attachments"
    attachments.mkdir(parents=True)
    body = attachments / "body.md"
    body.write_text("original", encoding="utf-8")
    receipt = _make_receipt(tmp_path)
    mb.send_message(
        "debate", "speaker", "see attachment", role="challenger",
        runtime="claude", provider="anthropic", run_id="run-1",
        identity_receipt=receipt, attachment=body, root=tmp_path,
    )
    body.write_text("tampered", encoding="utf-8")
    report = mb.verify_channel("debate", root=tmp_path, repo_root=tmp_path)
    assert report["cross_model_verified"] is False
    assert report["attachment_errors"]
    assert "attachment_sha256_mismatch" in report["attachment_errors"][0]["error"]


def test_legacy_channel_is_never_cross_model_verified(tmp_path):
    mb.send_message("legacy", "codex", "I claim to be Claude", root=tmp_path)
    report = mb.verify_channel("legacy", root=tmp_path, repo_root=tmp_path)
    assert report["verification_level"] == "legacy_existence_only"
    assert report["cross_model_verified"] is False


def test_verifier_cannot_reuse_challenger_run_identity(tmp_path):
    challenger = _make_receipt(
        tmp_path, participant="challenger", role="challenger",
        run_id="review-run",
    )
    verifier = _make_receipt(
        tmp_path, participant="verifier", role="verifier",
        run_id="review-run",
    )
    for sender, role, receipt in (
        ("challenger", "challenger", challenger),
        ("verifier", "verifier", verifier),
    ):
        mb.send_message(
            "debate", sender, role, role=role, runtime="claude",
            provider="anthropic", run_id="review-run",
            identity_receipt=receipt, root=tmp_path,
        )
    report = mb.verify_channel("debate", root=tmp_path, repo_root=tmp_path)
    assert report["structured_valid"] is False
    assert any(
        item["error"].startswith("role_run_id_collision:challenger:verifier")
        for item in report["identity_errors"]
    )


@pytest.mark.parametrize(
    "bad_slug",
    ["..", "../x", r"..\x", "/abs", r"C:\abs", "a/b", r"a\b", " N"],
)
def test_path_component_slugs_reject_traversal(tmp_path, bad_slug):
    with pytest.raises(ValueError):
        mb.send_message(bad_slug, "A", "x", root=tmp_path)
    with pytest.raises(ValueError):
        mb.send_message("safe", bad_slug, "x", root=tmp_path)
    with pytest.raises(ValueError):
        mb.recv_message("safe", bad_slug, timeout=0, root=tmp_path)


def test_cross_provider_dispatch_without_ack_fails_before_launch(tmp_path, monkeypatch):
    exe = tmp_path / "claude.exe"
    exe.write_bytes(b"fake")
    monkeypatch.setattr(
        mb, "_find_runtime_info",
        lambda runtime, explicit=None: {"exe": str(exe), "version": "claude 1"},
    )
    monkeypatch.setattr(
        mb.subprocess, "Popen",
        lambda *args, **kwargs: pytest.fail("Popen must not run without ack"),
    )
    with pytest.raises(RuntimeError, match="acknowledge-cross-provider"):
        mb.dispatch_peer(
            "debate", "initiator", "task", peer="challenger",
            initiator_runtime="codex", runtime="claude", root=tmp_path,
            repo_root=tmp_path,
        )
    assert not (tmp_path / "debate").exists()


@pytest.mark.parametrize("runtime", ["codex", "claude"])
def test_dispatch_uses_native_runtime_command_without_real_launch(
    tmp_path, monkeypatch, runtime,
):
    exe = tmp_path / f"{runtime}.exe"
    exe.write_bytes(f"fake-{runtime}".encode())
    initiator = "claude" if runtime == "codex" else "codex"
    initiator_exe = tmp_path / f"{initiator}.exe"
    initiator_exe.write_bytes(f"fake-{initiator}".encode())
    captured = {}

    def fake_find(selected, explicit=None):
        selected_exe = exe if selected == runtime else initiator_exe
        return {"exe": str(selected_exe.resolve()), "version": f"{selected} 1"}

    class FakeProcess:
        pid = 4242

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(mb, "_find_runtime_info", fake_find)
    monkeypatch.setattr(mb.subprocess, "Popen", fake_popen)
    info = mb.dispatch_peer(
        f"debate-{runtime}", "initiator", "task", peer="challenger",
        initiator_runtime=initiator, runtime=runtime,
        initiator_model=f"{initiator}-initiator-model",
        acknowledge_cross_provider=True, runtime_exe=str(exe),
        initiator_runtime_exe=str(initiator_exe),
        model=f"{runtime}-peer-model", run_id=f"run-{runtime}",
        root=tmp_path, repo_root=tmp_path,
    )
    assert info["pid"] == 4242
    assert info["runtime"] == runtime
    assert info["provider"] == mb.RUNTIME_PROVIDERS[runtime]
    assert info["initiator_receipt"]["runtime"] == initiator
    assert info["receipt"]["requested_model"] == f"{runtime}-peer-model"
    assert info["initiator_receipt"]["requested_model"] == (
        f"{initiator}-initiator-model"
    )
    assert info["initiator_model"] == f"{initiator}-initiator-model"
    assert mb.validate_launch_receipt(
        info["receipt"], expected_channel=f"debate-{runtime}",
        expected_participant="challenger", expected_role="challenger",
        expected_runtime=runtime, expected_provider=info["provider"],
        expected_run_id=f"run-{runtime}",
    )["valid"]
    if runtime == "codex":
        assert captured["cmd"][1:4] == ["exec", "--sandbox", "workspace-write"]
    else:
        assert captured["cmd"][1:3] == ["--print", "--permission-mode"]
        assert "acceptEdits" in captured["cmd"]
    assert "--dangerously-skip-permissions" not in captured["cmd"]
    assert "--model" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--model") + 1] == (
        f"{runtime}-peer-model"
    )
    assert "--identity-receipt" in captured["cmd"][-1]
    _assert_cross_runtime_dispatch_channel(info, runtime, tmp_path)


def test_runtime_discovery_skips_broken_wrapper_with_fake_probe(tmp_path, monkeypatch):
    broken = tmp_path / "codex.CMD"
    native = tmp_path / "codex.exe"
    broken.write_text("broken")
    native.write_text("native")
    monkeypatch.setattr(
        mb, "_runtime_candidates", lambda runtime, explicit=None: [str(broken), str(native)],
    )

    def fake_run(cmd, **kwargs):
        if Path(cmd[0]) == broken:
            return SimpleNamespace(returncode=1, stdout="", stderr="broken")
        return SimpleNamespace(returncode=0, stdout="codex 9.9", stderr="")

    monkeypatch.setattr(mb.subprocess, "run", fake_run)
    monkeypatch.setattr(mb.shutil, "which", lambda value: None)
    info = mb._find_runtime_info("codex")
    assert info == {"exe": str(native.resolve()), "version": "codex 9.9"}


def test_legacy_dispatch_arguments_remain_supported(tmp_path, monkeypatch):
    exe = tmp_path / "codex.exe"
    exe.write_bytes(b"fake-codex")

    class FakeProcess:
        pid = 99

    info_row = {"exe": str(exe.resolve()), "version": "codex 1"}
    monkeypatch.setattr(
        mb, "_find_runtime_info", lambda runtime, explicit=None: info_row,
    )
    monkeypatch.setattr(
        mb.subprocess, "Popen", lambda *args, **kwargs: FakeProcess(),
    )
    info = mb.dispatch_peer(
        "legacy-dispatch", "A", "task", codex_exe=str(exe),
        root=tmp_path, repo_root=tmp_path,
    )
    assert {"seq", "pid", "exe", "log"}.issubset(info)
    assert info["runtime"] == "codex"
    opener = mb.read_transcript("legacy-dispatch", root=tmp_path)[0]
    assert set(opener) == {"channel", "seq", "from", "text", "ts"}


def test_dispatch_on_existing_channel_seeds_peer_cursor_at_current_opener(
    tmp_path, monkeypatch,
):
    exe = tmp_path / "codex.exe"
    exe.write_bytes(b"fake-codex")

    class FakeProcess:
        pid = 100

    monkeypatch.setattr(
        mb, "_find_runtime_info",
        lambda runtime, explicit=None: {
            "exe": str(exe.resolve()), "version": "codex 1",
        },
    )
    monkeypatch.setattr(
        mb.subprocess, "Popen", lambda *args, **kwargs: FakeProcess(),
    )
    mb.send_message("existing", "old-initiator", "stale opener", root=tmp_path)
    info = mb.dispatch_peer(
        "existing", "new-initiator", "current verifier opener",
        peer="verifier", codex_exe=str(exe), root=tmp_path,
        repo_root=tmp_path,
    )
    assert info["seq"] == 2
    received = mb.recv_message(
        "existing", "verifier", timeout=0, root=tmp_path,
    )
    assert received is not None
    assert received["seq"] == 2
    assert received["text"] == "current verifier opener"


def test_dispatch_cli_passes_initiator_model(tmp_path, monkeypatch, capsys):
    captured = {}

    def fake_dispatch(channel, me, task, **kwargs):
        captured.update({
            "channel": channel, "me": me, "task": task, **kwargs,
        })
        return {
            "seq": 1, "pid": 77, "exe": "codex.exe",
            "log": str(tmp_path / "log"),
        }

    monkeypatch.setattr(mb, "dispatch_peer", fake_dispatch)
    mb.main([
        "--mailbox-root", str(tmp_path), "dispatch",
        "--channel", "debate", "--me", "initiator", "--task", "task",
        "--initiator-runtime", "codex",
        "--initiator-model", "gpt-5.6-sol",
        "--runtime", "codex", "--model", "gpt-5.6-terra",
    ])
    capsys.readouterr()
    assert captured["initiator_model"] == "gpt-5.6-sol"
    assert captured["model"] == "gpt-5.6-terra"


def test_attachment_traversal_is_rejected(tmp_path):
    cdir = tmp_path / "safe"
    (cdir / "attachments").mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    with pytest.raises(ValueError):
        mb.send_message(
            "safe", "A", "bad", attachment="../outside.txt", root=tmp_path,
        )
