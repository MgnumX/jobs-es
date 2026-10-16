# src/jobs_es/httpclient.py

import hashlib
import json
import random
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from .source_meta import pause_for

UA = "jobs-es-scraper/0.1"
PAUSE = 0.45  # compat for sources still using hc.PAUSE

_client = httpx.Client(
    headers={"User-Agent": UA},
    timeout=25.0,
    follow_redirects=True,
)

RETRY_STATUS = {429, 500, 502, 503, 504}

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
FETCH_LOG = DATA_DIR / "fetch_log.jsonl"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

_last_by_source: dict[str, float] = {}


class HttpError(RuntimeError):
    pass


class CachedResponse:
    """
    Respuesta fake para cache local.
    Solo imita lo mínimo que usa el scraper:
      - .text
      - .status_code
      - .json()
      - .from_cache
    """

    def __init__(self, url: str, text: str):
        self.url = url
        self.text = text
        self.status_code = 200
        self.headers = {"content-type": "text/plain; charset=utf-8", "x-cache": "local"}
        self.from_cache = True

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        return None


def _wait(source: str | None) -> None:
    pause = pause_for(source)
    now = time.monotonic()
    last = _last_by_source.get(source or "", 0.0)
    delta = now - last
    if delta < pause:
        time.sleep(pause - delta)
    _last_by_source[source or ""] = time.monotonic()


def _rotate_fetch_log() -> None:
    try:
        if FETCH_LOG.exists() and FETCH_LOG.stat().st_size > 10_000_000:
            old = FETCH_LOG.with_name("fetch_log.jsonl.1")
            if old.exists():
                old.unlink()
            FETCH_LOG.rename(old)
    except Exception:
        pass


def _log_fetch(
    source: str | None,
    url: str,
    status: int | None = None,
    elapsed_ms: int | None = None,
    cache: bool = False,
    error: str | None = None,
) -> None:
    try:
        _rotate_fetch_log()
        with FETCH_LOG.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": datetime.now().isoformat(),
                        "source": source,
                        "url": url,
                        "status": status,
                        "elapsed_ms": elapsed_ms,
                        "cache": cache,
                        "error": error,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except Exception:
        pass


def _cache_paths(url: str):
    h = hashlib.sha256(url.encode()).hexdigest()
    return CACHE_DIR / f"{h}.body", CACHE_DIR / f"{h}.meta.json"


def cache_get(url: str, ttl_hours: int = 24 * 7) -> str | None:
    body_path, meta_path = _cache_paths(url)
    if not body_path.exists() or not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(meta["fetched_at"])
    except Exception:
        return None
    if datetime.now() - fetched_at > timedelta(hours=ttl_hours):
        return None
    try:
        return body_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def cache_put(url: str, body: str, status: int = 200, content_type: str = "") -> None:
    try:
        body_path, meta_path = _cache_paths(url)
        body_path.write_text(body, encoding="utf-8")
        meta_path.write_text(
            json.dumps(
                {
                    "url": url,
                    "fetched_at": datetime.now().isoformat(),
                    "status": status,
                    "content_type": content_type,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _backoff_delay(resp, attempt: int) -> float:
    retry_after = None
    if resp is not None:
        retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return min(30.0, float(retry_after))
        except Exception:
            pass
    return min(30.0, (0.8 * (2 ** attempt)) + random.uniform(0.0, 0.4))


def get(
    url: str,
    *,
    source: str | None = None,
    params=None,
    headers=None,
    retries: int = 3,
    cache: bool = False,
    cache_ttl_hours: int = 24 * 7,
):
    _wait(source)
    if cache:
        cached_body = cache_get(url, ttl_hours=cache_ttl_hours)
        if cached_body is not None:
            _log_fetch(source, url, 200, 0, True, None)
            return CachedResponse(url, cached_body)
    started = time.monotonic()
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = _client.get(url, params=params, headers=headers)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            if resp.status_code == 200:
                if cache:
                    cache_put(url, resp.text, resp.status_code, resp.headers.get("content-type", ""))
                _log_fetch(source, url, resp.status_code, elapsed_ms, False, None)
                return resp
            if resp.status_code in RETRY_STATUS and attempt < retries:
                _log_fetch(source, url, resp.status_code, elapsed_ms, False, f"retry_{attempt + 1}")
                time.sleep(_backoff_delay(resp, attempt))
                continue
            _log_fetch(source, url, resp.status_code, elapsed_ms, False, f"bad_status_{resp.status_code}")
            raise HttpError(f"HTTP {resp.status_code} for {url}")
        except httpx.HTTPError as e:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            last_error = e
            if attempt < retries:
                _log_fetch(source, url, None, elapsed_ms, False, f"network_retry_{attempt + 1}")
                time.sleep(_backoff_delay(None, attempt))
                continue
            _log_fetch(source, url, None, elapsed_ms, False, repr(e))
            raise HttpError(f"network error for {url}: {e}") from e
    _log_fetch(source, url, None, int((time.monotonic() - started) * 1000), False, "failed")
    raise HttpError(f"failed {url}: {last_error}")


def post_json(
    url: str,
    payload,
    *,
    source: str | None = None,
    headers=None,
    retries: int = 3,
):
    _wait(source)
    started = time.monotonic()
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = _client.post(url, json=payload, headers=headers)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            if resp.status_code in {200, 201}:
                _log_fetch(source, url, resp.status_code, elapsed_ms, False, None)
                return resp.json()
            if resp.status_code in RETRY_STATUS and attempt < retries:
                _log_fetch(source, url, resp.status_code, elapsed_ms, False, f"retry_{attempt + 1}")
                time.sleep(_backoff_delay(resp, attempt))
                continue
            _log_fetch(source, url, resp.status_code, elapsed_ms, False, f"bad_status_{resp.status_code}")
            raise HttpError(f"HTTP {resp.status_code} for {url}")
        except httpx.HTTPError as e:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            last_error = e
            if attempt < retries:
                _log_fetch(source, url, None, elapsed_ms, False, f"network_retry_{attempt + 1}")
                time.sleep(_backoff_delay(None, attempt))
                continue
            _log_fetch(source, url, None, elapsed_ms, False, repr(e))
            raise HttpError(f"network error for {url}: {e}") from e
    _log_fetch(source, url, None, int((time.monotonic() - started) * 1000), False, "failed")
    raise HttpError(f"failed {url}: {last_error}")


def get_json(url: str, **kw):
    return get(url, **kw).json()


def strip_tags(html: str) -> str:
    txt = re.sub(r"<(script|style).*?>.*?</\1>", " ", html, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", "\n", txt)
    txt = txt.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", txt).strip()
