from __future__ import annotations

import json
from pathlib import Path

import pytest

import data_paths
import stale_artifact_sweep as sweep


# ── atomic_write_text: transient-lock retry (matches backtester._atomic_write_json) ──

def test_atomic_write_text_retries_transient_replace_lock(tmp_path, monkeypatch):
    target = tmp_path / "quant_signals_20260627.json"
    real_replace = data_paths.os.replace
    calls = {"replace": 0, "sleep": []}

    def flaky_replace(src, dst):
        calls["replace"] += 1
        if calls["replace"] < 3:
            raise PermissionError("transient lock")
        return real_replace(src, dst)

    monkeypatch.setattr(data_paths.os, "replace", flaky_replace)
    monkeypatch.setattr(data_paths.time, "sleep", lambda s: calls["sleep"].append(s))

    data_paths.atomic_write_json({"signals": {"AAPL": 1}}, target)

    assert calls["replace"] == 3
    assert calls["sleep"] == [0.05, 0.1]
    assert json.loads(target.read_text(encoding="utf-8")) == {"signals": {"AAPL": 1}}
    assert not list(tmp_path.glob(".quant_signals_20260627.json.*.tmp"))


def test_atomic_write_text_reraises_permanent_lock_and_cleans_temp(tmp_path, monkeypatch):
    target = tmp_path / "locked.json"

    def locked_replace(src, dst):
        raise PermissionError("still locked")

    monkeypatch.setattr(data_paths.os, "replace", locked_replace)
    monkeypatch.setattr(data_paths.time, "sleep", lambda s: None)

    with pytest.raises(PermissionError, match="still locked"):
        data_paths.atomic_write_json({"ok": False}, target)

    assert not target.exists()
    assert not list(tmp_path.glob(".locked.json.*.tmp"))


# ── recover_orphan_atomic_writes: promote / clean / skip semantics ──

FUTURE = 10**12  # now far in the future so every temp is "old enough"


def _make_orphan_temp(directory, final_name, content):
    temp = directory / f".{final_name}.deadbeef.tmp"
    temp.write_text(content, encoding="utf-8")
    return temp


def test_recover_promotes_orphan_when_final_missing(tmp_path):
    temp = _make_orphan_temp(tmp_path, "quant_signals_20260627.json", '{"signals": {"AAPL": 1}}')
    final = tmp_path / "quant_signals_20260627.json"

    result = sweep.recover_orphan_atomic_writes(tmp_path, now=FUTURE)

    assert str(final) in result["recovered"]
    assert final.exists()
    assert json.loads(final.read_text(encoding="utf-8")) == {"signals": {"AAPL": 1}}
    assert not temp.exists()


def test_recover_promotes_with_copy_fallback_when_replace_denied(tmp_path, monkeypatch):
    temp = _make_orphan_temp(tmp_path, "quant_signals_20260627.json", '{"signals": {"AAPL": 1}}')
    final = tmp_path / "quant_signals_20260627.json"

    def denied_replace(src, dst):
        raise PermissionError("replace denied")

    monkeypatch.setattr(sweep.os, "replace", denied_replace)
    monkeypatch.setattr(sweep.time, "sleep", lambda s: None)

    result = sweep.recover_orphan_atomic_writes(tmp_path, now=FUTURE)

    assert str(final) in result["recovered"]
    assert final.exists()
    assert json.loads(final.read_text(encoding="utf-8")) == {"signals": {"AAPL": 1}}
    assert not temp.exists()


def test_recoverable_dirs_cover_all_daily_artifact_dirs():
    expected_dirs = {
        f"data/{subdir}" for subdir, _pattern in data_paths.DAILY_ARTIFACTS.values()
    }

    assert expected_dirs <= set(sweep._RECOVERABLE_DIRS)


def test_recover_jsonl_temp_requires_valid_json_lines(tmp_path):
    temp = _make_orphan_temp(
        tmp_path,
        "daily_news_structured_event_observations_20260627.jsonl",
        '{"ticker": "AAPL"}\n{"ticker": "MSFT"}\n',
    )
    final = tmp_path / "daily_news_structured_event_observations_20260627.jsonl"

    result = sweep.recover_orphan_atomic_writes(tmp_path, now=FUTURE)

    assert str(final) in result["recovered"]
    assert final.exists()
    assert not temp.exists()


def test_recover_skips_invalid_jsonl_temp_without_data_loss(tmp_path):
    temp = _make_orphan_temp(
        tmp_path,
        "daily_news_structured_event_observations_20260627.jsonl",
        '{"ticker": "AAPL"}\n{bad line}\n',
    )

    result = sweep.recover_orphan_atomic_writes(tmp_path, now=FUTURE)

    assert not (
        tmp_path / "daily_news_structured_event_observations_20260627.jsonl"
    ).exists()
    assert temp.exists()
    assert any("invalid" in s["reason"] for s in result["skipped"])


def test_recover_cleans_stale_temp_when_final_exists(tmp_path):
    final = tmp_path / "quant_signals_20260627.json"
    final.write_text('{"signals": {"final": true}}', encoding="utf-8")
    temp = _make_orphan_temp(tmp_path, "quant_signals_20260627.json", '{"signals": {"stale": true}}')

    result = sweep.recover_orphan_atomic_writes(tmp_path, now=FUTURE)

    assert str(temp) in result["cleaned"]
    assert not temp.exists()
    # existing final is never overwritten by a stale temp
    assert json.loads(final.read_text(encoding="utf-8")) == {"signals": {"final": True}}


def test_recover_cleans_stale_temp_after_permission_retry(tmp_path, monkeypatch):
    final = tmp_path / "quant_signals_20260627.json"
    final.write_text('{"signals": {"final": true}}', encoding="utf-8")
    temp = _make_orphan_temp(tmp_path, "quant_signals_20260627.json", '{"signals": {"stale": true}}')
    real_unlink = Path.unlink
    calls = {"unlink": 0, "chmod": [], "sleep": []}

    def flaky_unlink(self, *args, **kwargs):
        if self == temp:
            calls["unlink"] += 1
            if calls["unlink"] == 1:
                raise PermissionError("[WinError 5] access denied")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    monkeypatch.setattr(sweep, "_make_user_writable", lambda path: calls["chmod"].append(path))
    monkeypatch.setattr(sweep.time, "sleep", lambda s: calls["sleep"].append(s))

    result = sweep.recover_orphan_atomic_writes(tmp_path, now=FUTURE)

    assert str(temp) in result["cleaned"]
    assert not temp.exists()
    assert calls["unlink"] == 2
    assert calls["chmod"] == [temp]
    assert calls["sleep"] == [0.05]
    assert json.loads(final.read_text(encoding="utf-8")) == {"signals": {"final": True}}


def test_recover_reports_unlink_failure_without_data_loss(tmp_path, monkeypatch):
    final = tmp_path / "quant_signals_20260627.json"
    final.write_text('{"signals": {"final": true}}', encoding="utf-8")
    temp = _make_orphan_temp(tmp_path, "quant_signals_20260627.json", '{"signals": {"stale": true}}')
    real_unlink = Path.unlink

    def locked_unlink(self, *args, **kwargs):
        if self == temp:
            raise PermissionError("[WinError 5] access denied")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked_unlink)
    monkeypatch.setattr(sweep.time, "sleep", lambda s: None)

    result = sweep.recover_orphan_atomic_writes(tmp_path, now=FUTURE)

    assert result["cleaned"] == []
    assert temp.exists()
    assert json.loads(final.read_text(encoding="utf-8")) == {"signals": {"final": True}}
    assert any("unlink_failed" in s["reason"] for s in result["skipped"])


def test_recover_skips_invalid_temp_without_data_loss(tmp_path):
    temp = _make_orphan_temp(tmp_path, "quant_signals_20260627.json", "{ truncated half-writ")

    result = sweep.recover_orphan_atomic_writes(tmp_path, now=FUTURE)

    assert not (tmp_path / "quant_signals_20260627.json").exists()
    assert temp.exists()  # invalid temp left in place, never deleted
    assert any("invalid" in s["reason"] for s in result["skipped"])


def test_recover_ignores_young_temp_possibly_mid_write(tmp_path):
    temp = _make_orphan_temp(tmp_path, "quant_signals_20260627.json", '{"signals": {}}')

    # now == temp mtime -> age ~0 < min_age, so it must be left untouched
    result = sweep.recover_orphan_atomic_writes(tmp_path)

    assert temp.exists()
    assert not (tmp_path / "quant_signals_20260627.json").exists()
    assert result["recovered"] == [] and result["cleaned"] == []
