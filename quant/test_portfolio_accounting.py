from portfolio_accounting import resolve_portfolio_accounting


def test_missing_cash_is_derived_from_portfolio_value():
    open_positions = {
        "portfolio_value_usd": 100_000,
        "positions": [
            {"ticker": "NVDA", "shares": 100, "avg_cost": 400.0},
            {"ticker": "MSFT", "shares": 50, "avg_cost": 300.0},
        ],
    }
    current_prices = {"NVDA": 500.0, "MSFT": 320.0}

    result = resolve_portfolio_accounting(open_positions, current_prices)

    assert result["equity_market_value_usd"] == 66_000
    assert result["cash_usd"] == 34_000
    assert result["portfolio_value_usd"] == 100_000
    assert result["cash_source"] == "derived_from_portfolio_value_usd"
    assert result["cash_is_inferred"] is True
    assert result["warnings"] == []


def test_explicit_cash_still_uses_equity_plus_cash():
    open_positions = {
        "portfolio_value_usd": 100_000,
        "cash_usd": 10_000,
        "positions": [
            {"ticker": "NVDA", "shares": 100, "avg_cost": 400.0},
        ],
    }
    current_prices = {"NVDA": 500.0}

    result = resolve_portfolio_accounting(open_positions, current_prices)

    assert result["equity_market_value_usd"] == 50_000
    assert result["cash_usd"] == 10_000
    assert result["portfolio_value_usd"] == 60_000
    assert result["cash_source"] == "explicit_cash_usd"
    assert result["cash_is_inferred"] is False
