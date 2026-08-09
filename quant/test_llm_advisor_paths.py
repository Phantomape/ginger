from __future__ import annotations

import json
from pathlib import Path
import importlib.util


def test_save_prompt_file_uses_organized_path_inside_repo(tmp_path: Path, monkeypatch) -> None:
    import data_paths
    import llm_advisor

    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    repo_root.mkdir()

    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(data_paths, "DATA_ROOT", data_root)
    monkeypatch.setattr(llm_advisor, "DATA_ROOT", data_root)

    prompt_path = llm_advisor._save_prompt_file(
        "20260525",
        "system body",
        "user body",
        trade_news=[],
        trend_signals={"quant_signals": []},
    )

    assert Path(prompt_path) == data_root / "daily" / "llm" / "prompts" / "llm_prompt_20260525.txt"
    assert Path(prompt_path).exists()
    assert not (data_root / "llm_prompt_20260525.txt").exists()


def test_fetch_news_writes_organized_daily_paths(tmp_path: Path, monkeypatch) -> None:
    import fetch_news

    class _FixedDateTime:
        @classmethod
        def now(cls):
            import datetime as _dt

            return _dt.datetime(2026, 5, 25, 12, 0, 0)

    data_root = tmp_path / "data"
    monkeypatch.setattr(fetch_news, "datetime", _FixedDateTime)

    news_path = Path(fetch_news.save_to_file([{"title": "item"}], output_dir=data_root))
    stats_path = Path(fetch_news.save_source_stats([{"source": "feed"}], output_dir=data_root))

    assert news_path == data_root / "daily" / "news" / "raw" / "news_20260525.json"
    assert stats_path == data_root / "daily" / "news" / "source_stats" / "news_source_stats_20260525.json"
    assert not (data_root / "news_20260525.json").exists()
    assert not (data_root / "news_source_stats_20260525.json").exists()


def test_options_forward_ledger_reads_organized_quant_signals(tmp_path: Path) -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_options_forward_ledger.py"
    spec = importlib.util.spec_from_file_location("run_options_forward_ledger_for_test", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    data_root = tmp_path / "data"
    organized = data_root / "daily" / "signals" / "quant" / "quant_signals_20260525.json"
    organized.parent.mkdir(parents=True)
    organized.write_text('{"signals": []}', encoding="utf-8")

    assert module._quant_signal_path(data_root, "20260525") == organized

    legacy_root = tmp_path / "legacy_data"
    legacy = legacy_root / "quant_signals_20260524.json"
    legacy_root.mkdir()
    legacy.write_text('{"signals": []}', encoding="utf-8")

    assert module._quant_signal_path(legacy_root, "20260524") == legacy


def test_import_advice_default_writes_organized_llm_archives(tmp_path: Path, monkeypatch) -> None:
    import data_paths
    import import_advice
    import llm_advisor

    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(data_paths, "DATA_ROOT", data_root)
    monkeypatch.setattr(llm_advisor, "DATA_ROOT", data_root)

    out_path = Path(import_advice.import_advice(
        "20260525",
        '{"new_trade": "NO NEW TRADE", "position_actions": []}',
    ))

    advice_path = data_root / "daily" / "llm" / "advice" / "investment_advice_20260525.json"
    replay_path = data_root / "daily" / "llm" / "responses" / "llm_prompt_resp_20260525.json"
    assert out_path == advice_path
    assert advice_path.exists()
    assert replay_path.exists()
    assert not (data_root / "investment_advice_20260525.json").exists()
    assert not (data_root / "llm_prompt_resp_20260525.json").exists()


def test_get_investment_advice_uses_local_codex_archive_path(
    tmp_path: Path, monkeypatch
) -> None:
    import data_paths
    import llm_advisor

    class _FixedDateTime:
        @classmethod
        def now(cls):
            import datetime as _dt

            return _dt.datetime(2026, 5, 25, 12, 0, 0)

    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(data_paths, "DATA_ROOT", data_root)
    monkeypatch.setattr(llm_advisor, "DATA_ROOT", data_root)
    monkeypatch.setattr(llm_advisor, "datetime", _FixedDateTime)
    monkeypatch.setattr(
        llm_advisor,
        "build_prompt",
        lambda trade_news, open_positions, trend_signals=None: (
            "system body",
            "user body",
        ),
    )

    def _fake_local_codex(prompt_file, system_message, user_message, date_str, data_dir, model=None):
        advice_path = data_paths.daily_artifact_path("investment_advice", date_str, data_dir)
        raw = json.dumps(
            {
                "new_trade": "NO NEW TRADE",
                "add_on_trades": [],
                "add_on_vetoes": [],
                "position_actions": [],
            }
        )
        assert llm_advisor.save_advice(
            raw,
            str(advice_path),
            token_usage={"provider": "local_codex", "model": model},
        )
        return {
            "success": True,
            "advice_path": str(advice_path),
            "replay_path": str(
                data_paths.daily_artifact_path("llm_prompt_resp", date_str, data_dir)
            ),
            "model": model,
            "provider": "local_codex",
            "token_usage": {"provider": "local_codex", "model": model},
        }

    monkeypatch.setattr(llm_advisor, "_call_local_codex", _fake_local_codex)

    result = llm_advisor.get_investment_advice(
        [],
        open_positions={"positions": []},
        trend_signals={"quant_signals": []},
    )

    advice_path = data_root / "daily" / "llm" / "advice" / "investment_advice_20260525.json"
    replay_path = data_root / "daily" / "llm" / "responses" / "llm_prompt_resp_20260525.json"
    prompt_path = data_root / "daily" / "llm" / "prompts" / "llm_prompt_20260525.txt"

    assert result["success"] is True
    assert "Local Codex" in result["advice"]
    assert advice_path.exists()
    assert replay_path.exists()
    assert prompt_path.exists()
    saved = json.loads(advice_path.read_text(encoding="utf-8"))
    assert saved["token_usage"]["provider"] == "local_codex"
    assert saved["token_usage"]["model"] == "gpt-5.6-sol"


def test_get_investment_advice_falls_back_when_local_codex_fails(
    tmp_path: Path, monkeypatch
) -> None:
    import data_paths
    import llm_advisor

    class _FixedDateTime:
        @classmethod
        def now(cls):
            import datetime as _dt

            return _dt.datetime(2026, 5, 25, 12, 0, 0)

    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(data_paths, "DATA_ROOT", data_root)
    monkeypatch.setattr(llm_advisor, "DATA_ROOT", data_root)
    monkeypatch.setattr(llm_advisor, "datetime", _FixedDateTime)
    monkeypatch.setattr(
        llm_advisor,
        "build_prompt",
        lambda trade_news, open_positions, trend_signals=None: (
            "system body",
            "user body",
        ),
    )
    monkeypatch.setattr(
        llm_advisor,
        "_call_local_codex",
        lambda *args, **kwargs: {
            "success": False,
            "error": "local_codex_executable_unavailable",
            "model": "gpt-5.6-sol",
        },
    )

    result = llm_advisor.get_investment_advice(
        [],
        open_positions={"positions": []},
        trend_signals={"quant_signals": []},
    )

    prompt_path = data_root / "daily" / "llm" / "prompts" / "llm_prompt_20260525.txt"
    replay_path = data_root / "daily" / "llm" / "responses" / "llm_prompt_resp_20260525.json"

    assert result["success"] is True
    assert "Local Codex auto-call failed" in result["advice"]
    assert prompt_path.exists()
    assert not replay_path.exists()


def test_call_local_codex_records_nonzero_exit_diagnostic(
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
    monkeypatch.setattr(llm_advisor, "_local_codex_timeout_seconds", lambda: 10)

    calls = {}

    class _Completed:
        returncode = 1
        stdout = "stdout diagnostic"
        stderr = "fatal: model startup failed"

    def _fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["input"] = kwargs.get("input")
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
    assert result["error"] == "local_codex_returncode_1"
    assert result["returncode"] == 1
    assert "fatal: model startup failed" in result["stderr"]
    assert calls["cmd"][:2] == [r"C:\fake\codex.exe", "exec"]
    assert "user body" in calls["input"]

    diagnostic_path = Path(result["diagnostic_path"])
    assert diagnostic_path == (
        data_root / "daily" / "llm" / "advice" / "local_codex_failure_20260525.json"
    )
    payload = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert payload["error"] == "local_codex_returncode_1"
    assert payload["returncode"] == 1
    assert payload["prompt_file"] == "prompt-file.txt"
    assert payload["response_path_status"]["exists"] is False
    assert "fatal: model startup failed" in payload["stderr"]
    assert "user body" not in diagnostic_path.read_text(encoding="utf-8")


def test_get_investment_advice_includes_local_codex_diagnostic_path(
    tmp_path: Path, monkeypatch
) -> None:
    import data_paths
    import llm_advisor

    class _FixedDateTime:
        @classmethod
        def now(cls):
            import datetime as _dt

            return _dt.datetime(2026, 5, 25, 12, 0, 0)

    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(data_paths, "DATA_ROOT", data_root)
    monkeypatch.setattr(llm_advisor, "DATA_ROOT", data_root)
    monkeypatch.setattr(llm_advisor, "datetime", _FixedDateTime)
    monkeypatch.setattr(
        llm_advisor,
        "build_prompt",
        lambda trade_news, open_positions, trend_signals=None: (
            "system body",
            "user body",
        ),
    )

    diagnostic_path = (
        data_root / "daily" / "llm" / "advice" / "local_codex_failure_20260525.json"
    )
    monkeypatch.setattr(
        llm_advisor,
        "_call_local_codex",
        lambda *args, **kwargs: {
            "success": False,
            "error": "local_codex_returncode_1",
            "model": "gpt-5.6-sol",
            "diagnostic_path": str(diagnostic_path),
            "stderr": "fatal: model startup failed",
        },
    )

    result = llm_advisor.get_investment_advice(
        [],
        open_positions={"positions": []},
        trend_signals={"quant_signals": []},
    )

    assert result["success"] is True
    assert f"Diagnostic artifact: {diagnostic_path}" in result["advice"]
    assert result["token_usage"]["diagnostic_path"] == str(diagnostic_path)
    assert result["token_usage"]["stderr_tail"] == "fatal: model startup failed"
