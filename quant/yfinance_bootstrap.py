import os
import tempfile

import yfinance.cache as yf_cache


PROXY_ENV_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "GIT_HTTP_PROXY",
    "GIT_HTTPS_PROXY",
)


def configure_yfinance_runtime():
    """Normalize yfinance runtime settings across all entrypoints."""
    for key in PROXY_ENV_VARS:
        value = os.environ.get(key)
        if value and "127.0.0.1:9" in value:
            os.environ.pop(key, None)

    cache_dir = os.path.join(tempfile.gettempdir(), "ginger_yfinance_cache")
    os.makedirs(cache_dir, exist_ok=True)
    try:
        yf_cache.set_cache_location(cache_dir)
    except Exception:
        pass

    return cache_dir
