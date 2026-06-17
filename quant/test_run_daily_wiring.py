import ast
import inspect
from pathlib import Path
import sys
import textwrap


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from fundamental_growth_rs_paper_sleeve import (  # noqa: E402
    prep_and_build_fundamental_growth_rs_paper_sleeve_snapshot,
)
from run import _core_slot_ticker_set, main  # noqa: E402


def test_core_slot_ticker_set_only_includes_positive_core_slots():
    payload = {
        "core_positions": [
            {"ticker": "MRVL", "shares": 24},
            {"ticker": "ZERO", "shares": 0},
        ],
        "positions": [
            {
                "ticker": "AMZN",
                "shares": 4,
                "opened_by_strategy": "breakout_long",
            },
            {
                "ticker": "SNXX",
                "shares": 48,
                "opened_by_strategy": "fomo",
            },
            {
                "ticker": "META",
                "shares": 2,
                "slot_policy": "no_core_slot",
            },
        ],
        "observations": [
            {"ticker": "APP", "shares": 17},
        ],
    }

    assert _core_slot_ticker_set(payload) == {"AMZN", "MRVL"}


def test_fundamental_growth_rs_call_uses_core_slot_ticker_set():
    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    current_core_tickers_args = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", None) not in {
            "build_fundamental_growth_rs_paper_sleeve_snapshot",
            "prep_and_build_fundamental_growth_rs_paper_sleeve_snapshot",
        }:
            continue
        for keyword in node.keywords:
            if keyword.arg == "current_core_tickers":
                current_core_tickers_args.append(keyword.value)

    assert current_core_tickers_args
    assert any(
        isinstance(value, ast.Call)
        and getattr(value.func, "id", None) == "_core_slot_ticker_set"
        for value in current_core_tickers_args
    )


def test_fundamental_growth_rs_prep_forwards_core_tickers_to_builder():
    tree = ast.parse(
        textwrap.dedent(
            inspect.getsource(prep_and_build_fundamental_growth_rs_paper_sleeve_snapshot)
        )
    )
    current_core_tickers_args = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", None) != "build_fundamental_growth_rs_paper_sleeve_snapshot":
            continue
        for keyword in node.keywords:
            if keyword.arg == "current_core_tickers":
                current_core_tickers_args.append(keyword.value)

    assert current_core_tickers_args
    assert any(
        isinstance(value, ast.Name) and value.id == "current_core_tickers"
        for value in current_core_tickers_args
    )
