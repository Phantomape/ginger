"""
News T1-negative replay for backtester.

Reads data/clean_trade_news_YYYYMMDD.json (written by run.py / run_pipeline.py)
and identifies tickers with T1-negative news on a given date.  Used by the
backtester's --replay-news path to partially close the news-veto parity gap:
in production, signals for tickers with T1 negative news on the signal date are
rejected by the LLM or by explicit rule; in backtest those signals were always
accepted (optimistic bias).

T1-negative events are a subset of filter.py's _T1_TITLE_KEYWORDS:
    earnings miss, guidance cut, profit warning, bankruptcy, CEO fired, recall, etc.

T1-positive events (earnings beat, guidance raise, acquisition premium, FDA
approval, buyback) do NOT trigger a veto — they support the trade.

Conservative assumption: any T1-negative item in clean_trade_news on the signal
date vetoes that ticker's new-entry signal.  (In production, the LLM might still
approve despite negative news if it judges the move "already priced in" — so
this is a slight over-veto, erring on the pessimistic side.)
"""
import json
import os


_T1_NEGATIVE_KEYWORDS = [
    # Earnings misses
    "earnings miss", "misses estimates", "miss estimates",
    # Guidance cuts
    "guidance cut", "guidance lowered", "cuts guidance", "lowers guidance",
    "cuts forecast", "lowers forecast", "lowers full-year",
    # Distress events
    "bankruptcy", "chapter 11", "chapter 7", "profit warning",
    # Dividend cuts
    "dividend cut",
    # Executive bad-news events
    "ceo resign", "ceo fired", "ceo replaced", "executive departure",
    # Regulatory / safety / legal negatives
    "product recall", "safety recall", "sec charges", "doj charges",
]


def _archive_path(date_str, data_dir):
    return os.path.join(data_dir, f"clean_trade_news_{date_str}.json")


def _is_t1_negative(item):
    title = (item.get("title") or "").lower()
    for kw in _T1_NEGATIVE_KEYWORDS:
        if kw in title:
            return True
    return False


def get_news_for_date(date_obj, data_dir="data"):
    """
    Args:
        date_obj: datetime.date / datetime.datetime / pandas Timestamp / str
        data_dir: directory holding clean_trade_news_YYYYMMDD.json files

    Returns:
        {
          "file_present":         bool,
          "date_str":             "YYYYMMDD",
          "t1_negative_tickers":  set[str],   # tickers with T1-negative headlines
          "all_t1_tickers":       set[str],   # all tickers with any T1 news
        }
    """
    if hasattr(date_obj, "strftime"):
        date_str = date_obj.strftime("%Y%m%d")
    else:
        date_str = str(date_obj).replace("-", "")[:8]

    path = _archive_path(date_str, data_dir)
    if not os.path.exists(path):
        return {
            "file_present":        False,
            "date_str":            date_str,
            "t1_negative_tickers": set(),
            "all_t1_tickers":      set(),
        }

    try:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        return {
            "file_present":        False,
            "date_str":            date_str,
            "t1_negative_tickers": set(),
            "all_t1_tickers":      set(),
        }

    t1_negative = set()
    all_t1 = set()
    for item in items:
        if item.get("tier") != "T1":
            continue
        tickers = item.get("tickers") or []
        if isinstance(tickers, str):
            tickers = [tickers]
        for tkr in tickers:
            tkr = str(tkr).strip().upper()
            if not tkr:
                continue
            all_t1.add(tkr)
            if _is_t1_negative(item):
                t1_negative.add(tkr)

    return {
        "file_present":        True,
        "date_str":            date_str,
        "t1_negative_tickers": t1_negative,
        "all_t1_tickers":      all_t1,
    }


def apply_news_gate(signals, news_decision):
    """
    Veto new-entry signals for tickers with T1-negative news on the signal date.

    Args:
        signals:       list of signal dicts, each with "ticker" key
        news_decision: return value of get_news_for_date

    Returns:
        (filtered_signals, presented_n, vetoed_n)

        presented_n = len(signals) at entry
        vetoed_n    = presented_n - len(filtered_signals)
                      (0 if file_present is False — replay missing => no veto)
    """
    presented_n = len(signals)
    if not news_decision["file_present"]:
        return list(signals), presented_n, 0
    veto_set = news_decision["t1_negative_tickers"]
    kept = [s for s in signals if (s.get("ticker") or "").upper() not in veto_set]
    return kept, presented_n, presented_n - len(kept)
