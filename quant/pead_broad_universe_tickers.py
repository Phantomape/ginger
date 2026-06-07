"""Canonical ~500-ticker universe for PEAD broad universe paper sleeve.

exp-20260607-003: PEAD_BROAD_500_TICKER_EARNINGS_EXPANSION

Selection criteria:
- S&P 500 constituent or closely adjacent large/mid-cap
- Market cap typically > $5B (good analyst EPS estimate coverage)
- Standard earnings reporting (excludes ETFs, REITs with non-standard EPS)
- Available on yfinance (for earnings data fetching)

This list is intentionally static and conservative. Add tickers via appending
to PEAD_BROAD_SUPPLEMENTAL; remove via PEAD_BROAD_EXCLUDED. The combined set
drives both the earnings snapshot fetch and OHLCV warehouse lookups.
"""

from __future__ import annotations

# Core S&P 500-adjacent universe for PEAD observation.
# Organized by GICS sector for auditing. ~500 tickers total.
PEAD_BROAD_UNIVERSE_500: list[str] = [
    # Information Technology
    "AAPL", "MSFT", "NVDA", "AVGO", "AMD", "INTC", "TXN", "QCOM", "MU",
    "AMAT", "LRCX", "KLAC", "ADI", "MCHP", "MRVL", "MPWR", "CDNS", "SNPS",
    "ANSS", "CRM", "NOW", "ADBE", "ORCL", "SAP", "IBM", "ACN", "CTSH",
    "INTU", "FTNT", "PANW", "CRWD", "CHKP", "AKAM", "EPAM", "FFIV",
    "NTAP", "STX", "WDC", "HPQ", "HPE", "CSCO", "JNPR", "COMM",
    "KEYS", "LDOS", "SAIC", "VRSN", "GDDY", "WEX", "IT", "GARTNER",
    "GIB", "DBX", "BOX", "DOCN", "DDOG", "SNOW", "ZS", "OKTA",
    "APP", "PLTR", "RBLX", "U", "NET", "TEAM", "HUBS", "TWLO",
    "MDB", "ESTC", "TTD", "MGNI", "S", "TOST", "BILL", "GLBE",
    # Communication Services
    "META", "GOOG", "GOOGL", "NFLX", "DIS", "CMCSA", "T", "VZ",
    "TMUS", "CHTR", "FOXA", "FOX", "OMC", "IPG", "WBD", "PARA",
    "SIRI", "DISH", "LUMN", "AMX", "SPOT", "PINS", "SNAP", "MTCH",
    "ZM", "BMBL", "IAC", "LYFT", "UBER", "LYFT",
    # Consumer Discretionary
    "AMZN", "TSLA", "MCD", "NKE", "SBUX", "TGT", "HD", "LOW",
    "BKNG", "MAR", "HLT", "ABNB", "EXPE", "TRIP",
    "GM", "F", "STLA", "TM", "HMC",
    "DHI", "LEN", "PHM", "NVR", "TOL", "MTH", "MDC",
    "LVS", "WYNN", "MGM", "CZR", "RCL", "CCL", "NCLH",
    "RH", "WSM", "BBY", "ETSY", "EBAY", "W", "CVNA",
    "ANF", "AEO", "URBN", "PVH", "HBI", "RL", "TPR",
    "YUM", "QSR", "DPZ", "WEN", "JACK", "DRI", "EAT",
    "DKNG", "PENN", "FDX",
    # Consumer Staples
    "WMT", "COST", "KO", "PEP", "PG", "PM", "MO", "MDLZ",
    "STZ", "BUD", "KHC", "GIS", "K", "SJM", "HRL", "CAG",
    "CL", "KMB", "CHD", "CLX", "EL", "KVUE", "COTY",
    "NVO",  # Novo Nordisk (consumer/pharma overlap, widely covered)
    # Energy
    "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "VLO",
    "OXY", "HAL", "BKR", "DVN", "APA", "EQT", "CTRA", "HES",
    "FANG", "MRO", "PXD", "PDCE", "SM", "MTDR", "CRC",
    "WHR", "LPX",  # adjacent industrial/energy
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "C", "USB", "PNC",
    "TFC", "COF", "AXP", "DFS", "SYF", "ALLY", "CACC",
    "BLK", "SCHW", "IBKR", "SF", "EVR", "LPL", "RJF",
    "CB", "MMC", "AIG", "PRU", "MET", "AFL", "ALL", "PGR",
    "TRV", "CNA", "GL", "HIG", "UNM", "SFG", "VOYA", "WR",
    "BX", "KKR", "APO", "CG", "ARES", "BAM", "BN",
    "SPGI", "MCO", "MSCI", "ICE", "CME", "NDAQ", "CBOE",
    "FIS", "FISV", "GPN", "ADP", "PAYX", "JKHY",
    "V", "MA", "PYPL", "SQ",
    "COIN", "HOOD",
    "FNF", "FAF", "STC",
    "MTB", "HBAN", "RF", "CFG", "KEY", "FITB", "ZION", "BOK", "WTFC",
    "OZRK", "IBCP",
    # Healthcare
    "JNJ", "UNH", "LLY", "PFE", "MRK", "ABBV", "AMGN", "BMY",
    "GILD", "REGN", "VRTX", "BIIB", "MRNA", "BNTX", "SGEN",
    "ABT", "TMO", "DHR", "MDT", "SYK", "BSX", "ISRG", "EW",
    "ZBH", "BAX", "BDX", "HOLX", "IQV", "IDXX", "DXCM",
    "RMD", "INSP", "TMDX", "AXNX", "NVCR",
    "HCA", "CNC", "HUM", "ELV", "MOH", "CVS",
    "MCK", "CAH", "ABC", "PDCO", "HSIC",
    "CI", "ANTM",  # (now ELV) legacy
    "CORT", "JAZZ", "INCY", "EXEL", "ALNY", "IONS",
    # Industrials
    "HON", "GE", "CAT", "DE", "RTX", "LMT", "GD", "NOC", "BA",
    "UPS", "CSX", "UNP", "NSC", "CNI", "CP",
    "EMR", "ETN", "ITW", "PH", "ROK", "DOV", "GNRC",
    "AME", "CARR", "OTIS", "XYL", "XYLEM",
    "FAST", "SWK", "IR", "TT", "TRANE",
    "AOS", "ALLE", "CREE", "ROP", "IEX",
    "WM", "RSG", "CWST", "CLH",
    "EXPD", "CHRW", "GXO", "XPO", "JBHT", "KNX",
    "DAL", "UAL", "AAL", "LUV", "ALK",
    "GHM", "TDY", "LDOS", "BAH", "CACI",
    "MAN", "RHI", "KFRC",
    # Materials
    "LIN", "APD", "ECL", "SHW", "PPG", "NEM", "FCX",
    "NUE", "STLD", "X", "CLF", "RS",
    "CF", "MOS", "FMC", "ALB", "BALL", "IP", "PKG",
    "SEE", "AMCR", "SLVM", "SILG",
    "MLM", "VMC", "CRH", "EXP", "SUM", "USCR",
    # Real Estate (earnings-reporting REITs only)
    # Note: REIT EPS is non-standard (FFO vs EPS); yfinance may not have estimates.
    # Including only REITs where yfinance typically provides EPS estimates.
    "AMT", "PLD", "CCI", "EQIX", "DLR",
    "SPG", "O", "PSA", "EXR", "VICI",
    # Utilities
    # Utilities report EPS; included for completeness even if surprise rates are lower.
    "NEE", "DUK", "SO", "AEP", "EXC", "XEL", "WEC", "ED",
    "DTE", "ES", "EIX", "PPL", "AEE", "CMS", "CNP",
    # Additional large/mid-cap with strong analyst coverage
    "TSM", "ASML", "ARM", "SMCI", "DELL", "FSLR", "ENPH",
    "CELH", "ON", "SWKS", "QRVO", "WOLF",
    "ZI", "GTLB", "CFLT", "AFRM", "SOFI", "LC", "UPST",
    "CRVL", "CSGP", "CBRE", "JLL",
    "LPLA", "NUAN", "VRNT", "NICE", "SABA",
    "NXPI", "STM", "IFNNY", "ERIC",
    "CRDO",  # already in core watchlist; included here for completeness
    "SPY",   # will be filtered out by EXCLUDED_TICKERS in sleeve
]

# Additional supplemental tickers beyond the base 500 (optional expansion).
PEAD_BROAD_SUPPLEMENTAL: list[str] = []

# Tickers to never include in the broad universe (ETFs, non-earnings, etc.)
PEAD_BROAD_EXCLUDED: set[str] = {
    "SPY", "QQQ", "IWM", "GLD", "IAU", "SLV", "TLT", "IEF",
    "XLE", "XLP", "XLU", "XLV", "XLF", "XLI", "XLB", "XLK",
    "ARKX", "UFO", "UUP", "USO", "SNXX",
}


def get_pead_broad_universe_tickers(
    *,
    include_supplemental: bool = True,
    exclude: set[str] | None = None,
) -> list[str]:
    """Return deduplicated, sorted PEAD broad universe ticker list.

    Args:
        include_supplemental: Whether to add PEAD_BROAD_SUPPLEMENTAL tickers.
        exclude: Additional tickers to exclude (stacked on PEAD_BROAD_EXCLUDED).
    """
    excluded = PEAD_BROAD_EXCLUDED | (exclude or set())
    tickers: set[str] = set()
    for raw in PEAD_BROAD_UNIVERSE_500:
        t = str(raw).upper().strip()
        if t and t not in excluded:
            tickers.add(t)
    if include_supplemental:
        for raw in PEAD_BROAD_SUPPLEMENTAL:
            t = str(raw).upper().strip()
            if t and t not in excluded:
                tickers.add(t)
    return sorted(tickers)
