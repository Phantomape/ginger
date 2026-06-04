from pathlib import Path
import sys


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from portfolio_accounting import compute_equity_market_value  # noqa: E402
from portfolio_engine import compute_portfolio_heat  # noqa: E402


def test_accounting_and_heat_read_all_operator_position_groups():
    open_positions = {
        "positions": [
            {"ticker": "SNXX", "shares": 10, "avg_cost": 20, "stop_price": 18},
        ],
        "core_positions": [
            {"ticker": "MRVL", "shares": 5, "avg_cost": 100, "stop_price": 90},
        ],
        "observations": [
            {"ticker": "APP", "shares": 2, "avg_cost": 300, "stop_price": 250},
        ],
    }
    current_prices = {"SNXX": 22, "MRVL": 110, "APP": 330}

    assert compute_equity_market_value(open_positions, current_prices) == 1430

    heat = compute_portfolio_heat(
        open_positions,
        current_prices,
        portfolio_value=10_000,
        features_dict={},
    )

    assert [row["ticker"] for row in heat["position_breakdown"]] == ["SNXX", "MRVL", "APP"]
    assert heat["total_at_risk_usd"] > 0
