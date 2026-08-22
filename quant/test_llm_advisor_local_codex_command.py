from pathlib import Path


def test_local_codex_command_uses_ephemeral_read_only_by_default(
    tmp_path: Path, monkeypatch
) -> None:
    import data_paths
    import llm_advisor

    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(data_paths, "DATA_ROOT", data_root)
    monkeypatch.setattr(llm_advisor, "DATA_ROOT", data_root)
    monkeypatch.setattr(
        llm_advisor,
        "_discover_codex_executable",
        lambda: r"C:\fake\codex.exe",
    )

    calls = {}

    class _Completed:
        returncode = 1
        stdout = ""
        stderr = "startup failed"

    def _fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return _Completed()

    monkeypatch.setattr(llm_advisor.subprocess, "run", _fake_run)

    result = llm_advisor._call_local_codex(
        "prompt-file.txt",
        "system body",
        "user body",
        "20260525",
        data_root,
    )

    assert result["success"] is False
    assert calls["cmd"][:3] == [r"C:\fake\codex.exe", "exec", "--ephemeral"]
    assert calls["cmd"][calls["cmd"].index("--sandbox") + 1] == "read-only"
