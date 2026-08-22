import builtins
import os
from types import SimpleNamespace

import pytest

import intraday_moomoo as M


def _fake_moomoo_module():
    return SimpleNamespace(
        AuType=object(),
        KLType=object(),
        OpenQuoteContext=object(),
        RET_OK=0,
        Session=object(),
    )


def test_moomoo_sdk_import_uses_repo_local_appdata_and_restores_env(tmp_path, monkeypatch):
    target = tmp_path / "sdk_appdata"
    observed_appdata = []
    real_import = builtins.__import__

    def recording_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "moomoo":
            observed_appdata.append(os.environ.get("APPDATA"))
            return _fake_moomoo_module()
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setenv("GINGER_MOOMOO_SDK_APPDATA", str(target))
    monkeypatch.delenv("GINGER_MOOMOO_USE_SYSTEM_APPDATA", raising=False)
    monkeypatch.setenv("APPDATA", "caller-appdata")
    monkeypatch.setattr(builtins, "__import__", recording_import)

    imported = M._import_moomoo_quote_sdk()

    assert observed_appdata == [str(target)]
    assert target.is_dir()
    assert os.environ["APPDATA"] == "caller-appdata"
    assert imported[3] == 0


def test_moomoo_sdk_import_restores_appdata_when_import_fails(tmp_path, monkeypatch):
    target = tmp_path / "sdk_appdata"
    real_import = builtins.__import__

    def failing_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "moomoo":
            assert os.environ["APPDATA"] == str(target)
            raise PermissionError("synthetic SDK import failure")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setenv("GINGER_MOOMOO_SDK_APPDATA", str(target))
    monkeypatch.delenv("GINGER_MOOMOO_USE_SYSTEM_APPDATA", raising=False)
    monkeypatch.setenv("APPDATA", "caller-appdata")
    monkeypatch.setattr(builtins, "__import__", failing_import)

    with pytest.raises(PermissionError, match="synthetic SDK import failure"):
        M._import_moomoo_quote_sdk()

    assert os.environ["APPDATA"] == "caller-appdata"


def test_moomoo_sdk_import_honors_system_appdata_override(monkeypatch):
    real_import = builtins.__import__

    def recording_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "moomoo":
            assert os.environ["APPDATA"] == "system-appdata"
            return _fake_moomoo_module()
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setenv("GINGER_MOOMOO_USE_SYSTEM_APPDATA", "1")
    monkeypatch.setenv("APPDATA", "system-appdata")
    monkeypatch.setattr(builtins, "__import__", recording_import)
    monkeypatch.setattr(
        M,
        "_redirect_moomoo_sdk_appdata",
        lambda: pytest.fail("redirect must be bypassed for explicit system APPDATA"),
    )
    monkeypatch.setattr(
        M,
        "_restore_moomoo_sdk_appdata",
        lambda previous: pytest.fail("restore must be bypassed without redirect"),
    )

    M._import_moomoo_quote_sdk()

    assert os.environ["APPDATA"] == "system-appdata"
