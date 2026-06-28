from __future__ import annotations

import json

import pytest

import backtester


def test_atomic_write_json_retries_transient_replace_lock(tmp_path, monkeypatch):
    target = tmp_path / "result.json"
    real_replace = backtester.os.replace
    calls = {"replace": 0, "sleep": []}

    def flaky_replace(src, dst):
        calls["replace"] += 1
        if calls["replace"] < 3:
            raise PermissionError("transient lock")
        return real_replace(src, dst)

    def fake_sleep(seconds):
        calls["sleep"].append(seconds)

    monkeypatch.setattr(backtester.os, "replace", flaky_replace)
    monkeypatch.setattr(backtester.time, "sleep", fake_sleep)

    backtester._atomic_write_json(target, {"ok": True}, trailing_newline=True)

    assert calls["replace"] == 3
    assert calls["sleep"] == [0.25, 0.5]
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}
    assert not list(tmp_path.glob(".result.json.*.tmp"))


def test_atomic_write_json_cleans_temp_after_permanent_replace_lock(tmp_path, monkeypatch):
    target = tmp_path / "locked.json"
    calls = {"replace": 0}

    def locked_replace(src, dst):
        calls["replace"] += 1
        raise PermissionError("still locked")

    monkeypatch.setattr(backtester.os, "replace", locked_replace)
    monkeypatch.setattr(backtester.time, "sleep", lambda seconds: None)

    with pytest.raises(PermissionError, match="still locked"):
        backtester._atomic_write_json(target, {"ok": False})

    assert calls["replace"] == 6
    assert not target.exists()
    assert not list(tmp_path.glob(".locked.json.*.tmp"))
