"""ORTEX short-interest / borrow-economics sidecar (default-off data fetcher).

ORTEX is the keystone PIT borrow-fee / utilization / short-interest source that the
repo has lacked (see alpha-saturation notes). This module is a *data fetcher only* --
it pulls ORTEX series and persists them under ``data/non_ohlcv/ortex/``. It does NOT
touch any buy/sell/rank/sizing logic, so it ships as a default-off sidecar.

Security
--------
The API key is read from the ``ORTEX_API_KEY`` environment variable (preferred), or,
as a fallback, from a gitignored ``.env`` file at the repo root. The key is NEVER
hardcoded and NEVER committed -- ``.env`` is in ``.gitignore``; only ``.env.example``
(no real value) is tracked. Set the key portably with, on Windows:

    setx ORTEX_API_KEY "your-real-key"      # persists for the user across reboots

Endpoint paths
--------------
ORTEX's exact REST path layout is not published in a scrapable form. Rather than
hardcode a guess, ``--discover`` probes a list of candidate path templates with your
key (or the public ``TEST`` key) and reports which returns HTTP 200. Once you know the
working template, pass it via ``--path`` or set ``ORTEX_SI_PATH`` to skip discovery.

Confirmed facts (docs.ortex.com): auth header is ``Ortex-Api-Key``; the public trial
key is the literal string ``TEST``; endpoint families are short interest (daily),
cost-to-borrow (all / new), and days-to-cover.

Examples
--------
    # 1) Find the working short-interest path using the public trial key (no real key needed):
    python quant/ortex_data_sidecar.py --discover --exchange NASDAQ --ticker AAPL --key TEST

    # 2) Fetch short interest for a ticker once you know the path (key from env):
    python quant/ortex_data_sidecar.py --exchange NASDAQ --ticker AAPL \
        --path "/api/v1/{exchange}/{ticker}/short_interest"

    # 3) Arbitrary endpoint + query params, saved to data/non_ohlcv/ortex/:
    python quant/ortex_data_sidecar.py --path "/api/v1/{exchange}/{ticker}/ctb/all" \
        --exchange NASDAQ --ticker AAPL --param from_date=2026-01-01 --param to_date=2026-06-27
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "non_ohlcv" / "ortex"

AUTH_HEADER = "Ortex-Api-Key"
DEFAULT_BASE_URL = os.environ.get("ORTEX_BASE_URL", "https://api.ortex.com")
TRIAL_KEY = "TEST"

# Candidate path templates probed by --discover. The first that returns HTTP 200 wins.
# Add/trim these as ORTEX's published layout is confirmed; supersede entirely with --path.
SHORT_INTEREST_PATH_CANDIDATES = (
    "/api/v1/{exchange}/{ticker}/short_interest",
    "/api/v1/stock/{exchange}/{ticker}/short_interest",
    "/api/v1/short_interest/{exchange}/{ticker}",
    "/v1/{exchange}/{ticker}/short_interest",
    "/api/v1/{exchange}/{ticker}/si",
)


def load_api_key(explicit: str | None = None) -> str | None:
    """Resolve the key: explicit arg > env var > gitignored .env file. Never hardcoded."""
    if explicit:
        return explicit.strip()
    env = os.environ.get("ORTEX_API_KEY")
    if env:
        return env.strip()
    # Fallback: minimal .env parse (no python-dotenv dependency). .env is gitignored.
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "ORTEX_API_KEY":
                return value.strip().strip('"').strip("'")
    return None


def _mask(key: str) -> str:
    """Render a key for logs without leaking it (e.g. 'ab..yz')."""
    if not key or key == TRIAL_KEY:
        return key or "<none>"
    return f"{key[:2]}..{key[-2:]}" if len(key) > 4 else "****"


def fetch(
    path_template: str,
    *,
    exchange: str,
    ticker: str,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    params: dict | None = None,
    timeout: float = 30.0,
    retries: int = 3,
) -> requests.Response:
    """GET a single ORTEX endpoint with auth header, retry/backoff on 429/5xx."""
    path = path_template.format(exchange=exchange, ticker=ticker)
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    headers = {AUTH_HEADER: api_key, "Accept": "application/json"}
    last: requests.Response | None = None
    for attempt in range(retries):
        resp = requests.get(url, headers=headers, params=params or {}, timeout=timeout)
        last = resp
        if resp.status_code < 500 and resp.status_code != 429:
            return resp
        # Transient (rate-limit / server error) -> exponential backoff.
        time.sleep(min(2 ** attempt, 8))
    return last  # type: ignore[return-value]


def discover_path(
    *,
    exchange: str,
    ticker: str,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    candidates=SHORT_INTEREST_PATH_CANDIDATES,
) -> str | None:
    """Probe candidate short-interest path templates; return the first that returns 200."""
    for template in candidates:
        try:
            resp = fetch(
                template, exchange=exchange, ticker=ticker, api_key=api_key,
                base_url=base_url, retries=1, timeout=15.0,
            )
        except requests.RequestException as exc:
            print(f"  {template:50s} -> request error: {exc}")
            continue
        marker = "OK" if resp.status_code == 200 else ""
        print(f"  {template:50s} -> HTTP {resp.status_code} {marker}")
        if resp.status_code == 200:
            return template
    return None


def save_json(payload, *, exchange: str, ticker: str, label: str, output_dir: Path) -> Path:
    """Persist a fetched payload as pretty JSON under data/non_ohlcv/ortex/."""
    output_dir.mkdir(parents=True, exist_ok=True)
    safe = f"{exchange}_{ticker}_{label}".replace("/", "_").upper()
    out = output_dir / f"ortex_{safe}.json"
    tmp = out.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.replace(tmp, out)
    except OSError:
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.unlink(missing_ok=True)
    return out


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Fetch ORTEX short-interest / borrow data.")
    p.add_argument("--exchange", required=True, help="e.g. NASDAQ, NYSE")
    p.add_argument("--ticker", required=True, help="e.g. AAPL")
    p.add_argument("--path", default=os.environ.get("ORTEX_SI_PATH"),
                   help="Endpoint path template with {exchange}/{ticker}. Skips discovery.")
    p.add_argument("--param", action="append", default=[], metavar="k=v",
                   help="Query parameter (repeatable), e.g. --param from_date=2026-01-01")
    p.add_argument("--key", default=None,
                   help="API key override (else ORTEX_API_KEY env / .env). Use TEST to trial.")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    p.add_argument("--label", default="short_interest", help="Filename label for the saved JSON.")
    p.add_argument("--discover", action="store_true",
                   help="Probe candidate path templates and print which returns 200.")
    return p


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    api_key = load_api_key(args.key)
    if not api_key:
        print("ERROR: no API key. Set ORTEX_API_KEY (env or .env), or pass --key TEST.",
              file=sys.stderr)
        return 2
    print(f"Using key {_mask(api_key)} against {args.base_url}")

    if args.discover or not args.path:
        print("Discovering working short-interest path:")
        found = discover_path(
            exchange=args.exchange, ticker=args.ticker, api_key=api_key, base_url=args.base_url,
        )
        if not found:
            print("No candidate returned 200. Confirm the path from app.ortex.com/apis "
                  "(the docs 'API' tab shows a curl example) and pass it via --path.",
                  file=sys.stderr)
            return 1
        print(f"Working path: {found}")
        if args.discover:
            return 0
        args.path = found

    params = {}
    for item in args.param:
        k, _, v = item.partition("=")
        params[k.strip()] = v.strip()

    resp = fetch(args.path, exchange=args.exchange, ticker=args.ticker, api_key=api_key,
                 base_url=args.base_url, params=params)
    if resp.status_code != 200:
        print(f"ERROR: HTTP {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
        return 1
    try:
        payload = resp.json()
    except ValueError:
        print("ERROR: response was not JSON.", file=sys.stderr)
        return 1
    out = save_json(payload, exchange=args.exchange, ticker=args.ticker,
                    label=args.label, output_dir=Path(args.output_dir))
    print(f"Saved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
