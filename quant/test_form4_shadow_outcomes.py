from __future__ import annotations

from form4_shadow_outcomes import _owner_is_issuer, _window_name


def test_window_name_uses_canonical_ranges():
    assert _window_name("2024-10-02") == "old_thin"
    assert _window_name("2025-04-23") == "mid_weak"
    assert _window_name("2025-10-23") == "late_strong"
    assert _window_name("2026-05-01") is None


def test_owner_is_issuer_detects_self_rows():
    assert _owner_is_issuer({
        "owner_name": "Palantir Technologies Inc.",
        "issuer_name": "Palantir Technologies Inc.",
        "ticker": "PLTR",
    })
    assert not _owner_is_issuer({
        "owner_name": "Example CEO",
        "issuer_name": "Example Corp",
        "ticker": "EX",
    })
