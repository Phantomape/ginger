"""Reproduce identity repair before/after in disposable repos; print JSON only."""

import hashlib
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EDGE = ROOT / ".codex/worktrees/edge-v2"
sys.path.insert(0, str(ROOT / "scripts"))

BASELINES = {
    "root": (ROOT, "f978e063a91b2621ac5c75341d868eca7eed5bf0"),
    "edge": (EDGE, "11ef9c48356faf8cf010ec47a448a1736e39f7a8"),
}
HISTORICAL = {
    "root": "55381cd696851950ca4eed11825e0fb7f0aa6098a2333e1d34828119dbdda82d",
    "edge": "a0f149aaa4874a56b01d29f30dd8fe6c7892ddfcb9bc29dcb08f66f58a4d89c4",
}


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Identity test",
         "-c", "user.email=identity@example.invalid", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True,
    ).stdout


def run():
    report = {"experiment_id": "exp-20260906-002", "historical_identities": {}, "lanes": {}}
    for name, (lane, revision) in BASELINES.items():
        source = git(lane, "show", f"{revision}:scripts/experiment_registry.py").decode("utf-8")
        old = types.ModuleType("baseline_registry")
        old.__file__ = str(lane / "scripts/experiment_registry.py")
        exec(compile(source, old.__file__, "exec"), old.__dict__)
        current = types.ModuleType("installed_registry")
        current.__file__ = old.__file__
        installed = Path(current.__file__).read_text(encoding="utf-8")
        exec(compile(installed, current.__file__, "exec"), current.__dict__)
        historical = lane / "experiments/tickets/exp-20260826-001.json"
        raw = historical.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        report["historical_identities"][name] = {
            "path": str(historical), "experiment_uid": json.loads(raw)["experiment_uid"],
            "sha256": actual, "pre_close_reference_sha256": HISTORICAL[name],
            "unchanged": actual == HISTORICAL[name],
        }
        assert actual == HISTORICAL[name]
        with tempfile.TemporaryDirectory(prefix="ginger-identity-proof-") as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            git(root, "init", "-b", "primary")
            git(root, "commit", "--allow-empty", "-m", "fixture")
            sibling = Path(temporary) / "sibling"
            git(root, "worktree", "add", "-b", "sibling", str(sibling))
            tickets = sibling / "experiments/tickets"
            tickets.mkdir(parents=True)
            (tickets / "exp-20990101-001.json").write_text("{}")
            before_live = old.next_experiment_id({}, today="20990101", root=root)
            after_live = current.next_experiment_id({}, today="20990101", root=root)
            git(root, "checkout", "-b", "history-only")
            history = root / "experiments/tickets"
            history.mkdir(parents=True)
            (history / "exp-20990101-002.json").write_text("{}")
            git(root, "add", "experiments")
            git(root, "commit", "-m", "ref-only identity")
            git(root, "checkout", "primary")
            before_ref = old.next_experiment_id({}, today="20990101", root=root)
            after_ref = current.next_experiment_id({}, today="20990101", root=root)
            assert before_live == before_ref == "exp-20990101-001"
            assert after_live == "exp-20990101-002"
            assert after_ref == "exp-20990101-003"
            report["lanes"][name] = {
                "baseline_commit": revision,
                "baseline_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "installed_source_sha256": hashlib.sha256(installed.encode()).hexdigest(),
                "live_sibling_before": before_live, "live_sibling_after": after_live,
                "ref_only_before": before_ref, "ref_only_after": after_ref,
                "before_collision_free": False, "after_collision_free": True,
            }
    report["trade_enabled"] = False
    report["economic_progress"] = False
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
