"""Polite image fetching: honours 429/503 Retry-After with exponential backoff, and spaces out
requests to hosts that throttle bots (Wikimedia)."""
import threading
import time

import httpx

from services.ingestion.sources import USER_AGENT

THROTTLED_HOSTS = ("wikimedia.org",)
_last: dict[str, float] = {}
_lock = threading.Lock()


def _space(url: str, min_interval: float, sleep) -> None:
    host = next((h for h in THROTTLED_HOSTS if h in url), None)
    if not host or min_interval <= 0:
        return
    with _lock:
        wait = _last.get(host, 0) + min_interval - time.monotonic()
        if wait > 0:
            sleep(wait)
        _last[host] = time.monotonic()


def get_with_backoff(client: httpx.Client, url: str, attempts: int = 6, min_interval: float = 0.3,
                     sleep=time.sleep, timeout: float = 60) -> httpx.Response | None:
    for attempt in range(attempts):
        _space(url, min_interval, sleep)
        try:
            r = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        except httpx.HTTPError:
            sleep(min(60, 2 ** attempt))
            continue
        if r.status_code in (429, 503):
            sleep(min(120, float(r.headers.get("retry-after") or 2 ** (attempt + 1))))
            continue
        return r
    return None
