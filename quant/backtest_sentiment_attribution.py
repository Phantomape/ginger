"""Read-only sentiment attribution for canonical backtest results.

This module does not change trade generation, ranking, or sizing. It labels
closed trades with a coarse sentiment surface and summarizes historical
performance by sentiment bucket.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentiment_surface import (
    SENTIMENT_BASELINE,
    build_sentiment_trade_attribution,
    classify_sentiment_surface,
)


def _float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def infer_trade_sentiment(trade):
    """Infer sentiment from replay-visible trade metadata.

    Current canonical backtests do not persist full daily market context per
    trade, so we infer a conservative sentiment approximation from replayed
    regime fields already stored in trade artifacts.
    """
    regime_bucket = str(trade.get("regime_exit_bucket") or "").lower()
    strategy = str(trade.get("strategy") or "").lower()

    breakout_count = 1 if "breakout" in strategy else 0
    ai_count = 1 if trade.get("sector") == "Technology" else 0

    if regime_bucket in {"aggressive", "risk_on", "strong_trend"}:
        ctx = {
            "spy_pct_from_ma": 0.03,
            "qqq_pct_from_ma": 0.05,
            "spy_20d_return": 0.05,
            "qqq_20d_return": 0.08,
            "vix": 16,
            "qqq_minus_spy_ret20": 0.04,
            "breakout_signal_count": breakout_count + 3,
            "ai_signal_count": ai_count + 2,
        }
    elif regime_bucket in {"defensive", "risk_off", "weak"}:
        ctx = {
            "spy_pct_from_ma": -0.03,
            "qqq_pct_from_ma": -0.05,
            "spy_20d_return": -0.06,
            "qqq_20d_return": -0.09,
            "vix": 31,
        }
    elif regime_bucket in {"balanced", "neutral"}:
        ctx = {
            "spy_20d_return": 0.01,
            "qqq_20d_return": 0.00,
            "vix": 20,
        }
    else:
        return {
            "sentiment": SENTIMENT_BASELINE,
            "confidence": 0.25,
            "why": ["no_regime_bucket_mapping"],
        }

    return classify_sentiment_surface(ctx)


def annotate_trades_with_sentiment(result):
    trades = []
    for trade in result.get("trades", []):
        out = dict(trade)
        sentiment = infer_trade_sentiment(trade)
        out["sentiment_surface"] = sentiment["sentiment"]
        out["sentiment_confidence"] = sentiment["confidence"]
        out["sentiment_why"] = sentiment["why"]
        trades.append(out)
    return trades


def build_sentiment_report(result):
    trades = annotate_trades_with_sentiment(result)
    attribution = build_sentiment_trade_attribution(trades)

    return {
        "schema_version": 1,
        "read_only": True,
        "source_period": result.get("period"),
        "source_expected_value_score": result.get("expected_value_score"),
        "trade_count": len(trades),
        "sentiment_trade_attribution": attribution,
        "notes": [
            "This is a replay-side sentiment attribution layer only.",
            "Current canonical backtest artifacts do not persist full daily market context per trade.",
            "Sentiment buckets are inferred conservatively from replay-visible regime metadata.",
            "Use this for exploratory attribution before introducing any sentiment-conditioned sizing overlays.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result_json")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    path = Path(args.result_json)
    result = json.loads(path.read_text(encoding="utf-8-sig"))
    report = build_sentiment_report(result)

    output = Path(args.output) if args.output else path.with_name(path.stem + "_sentiment.json")
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(str(output))


if __name__ == "__main__":
    main()
