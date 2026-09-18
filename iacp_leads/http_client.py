"""Polite HTTP fetching: on-disk cache, rate limiting, robots.txt, retries."""
from __future__ import annotations

import hashlib
import random
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests

from .config import Config


def canonical_url(url: str) -> str:
    """Normalise a URL so the cache and the seen-set don't hold duplicates."""
    parts = urlparse(url)
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", parts.query, ""))


def registrable_host(url_or_host: str) -> str:
    """Best-effort eTLD+1. Handles the two-label suffixes that matter here."""
    host = url_or_host
    if "://" in host:
        host = urlparse(host).netloc
    host = host.lower().split("@")[-1].split(":")[0].strip(".")
    if not host:
        return ""
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    two_label_suffixes = {
        "co.uk", "org.uk", "me.uk", "ac.uk", "gov.uk", "net.uk", "sch.uk",
        "co.ie", "org.ie", "gov.ie", "ac.ie", "ie.eu",
        "com.au", "net.au", "org.au", "co.nz", "org.nz",
        "co.za", "com.br", "co.in", "com.mx", "co.jp",
    }
    if ".".join(labels[-2:]) in two_label_suffixes and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


class Fetcher:
    """Fetches pages, caching every response body under cache_dir.

    The cache makes re-runs free and means an interrupted crawl resumes without
    re-hitting the site, which is the single most important courtesy here.
    """

    def __init__(self, cfg: Config, cache_dir: str = ".cache", force: bool = False,
                 verbose: bool = True):
        self.cfg = cfg
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.force = force
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": cfg.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IE,en;q=0.9",
        })
        self._last_request_at = 0.0
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.stats = {"cache_hits": 0, "network": 0, "errors": 0, "blocked": 0}

    # -- cache ----------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        host = registrable_host(url).replace(".", "_") or "unknown"
        return self.cache_dir / host / f"{digest}.html"

    def cached(self, url: str) -> str | None:
        path = self._cache_path(canonical_url(url))
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
        return None

    def _store(self, url: str, body: str) -> None:
        path = self._cache_path(canonical_url(url))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", errors="replace")

    # -- robots ---------------------------------------------------------
    def _robots_for(self, url: str):
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in self._robots:
            return self._robots[origin]
        parser = urllib.robotparser.RobotFileParser()
        try:
            resp = self.session.get(f"{origin}/robots.txt",
                                    timeout=self.cfg.timeout_seconds)
            if resp.status_code == 200:
                parser.parse(resp.text.splitlines())
            else:
                parser = None  # no robots.txt served -> nothing disallowed
        except requests.RequestException:
            parser = None
        self._robots[origin] = parser
        return parser

    def allowed(self, url: str) -> bool:
        if not self.cfg.respect_robots:
            return True
        parser = self._robots_for(url)
        if parser is None:
            return True
        return parser.can_fetch(self.cfg.user_agent, url)

    def crawl_delay(self, url: str) -> float:
        """robots.txt Crawl-delay wins if it asks for more than we planned."""
        if not self.cfg.respect_robots:
            return self.cfg.delay_seconds
        parser = self._robots_for(url)
        if parser is None:
            return self.cfg.delay_seconds
        try:
            declared = parser.crawl_delay(self.cfg.user_agent)
        except Exception:
            declared = None
        if declared:
            return max(self.cfg.delay_seconds, float(declared))
        return self.cfg.delay_seconds

    # -- fetching -------------------------------------------------------
    def _throttle(self, url: str) -> None:
        wait = self.crawl_delay(url) + random.uniform(0, self.cfg.jitter_seconds)
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < wait:
            time.sleep(wait - elapsed)
        self._last_request_at = time.monotonic()

    def get(self, url: str) -> str | None:
        """Return page HTML, or None if it could not be fetched."""
        url = canonical_url(url)
        if not self.force:
            hit = self.cached(url)
            if hit is not None:
                self.stats["cache_hits"] += 1
                return hit

        if not self.allowed(url):
            self.stats["blocked"] += 1
            self._log(f"  robots.txt disallows {url} - skipped")
            return None

        backoff = 2.0
        for attempt in range(1, self.cfg.max_retries + 1):
            self._throttle(url)
            try:
                resp = self.session.get(url, timeout=self.cfg.timeout_seconds,
                                        allow_redirects=True)
            except requests.RequestException as exc:
                self._log(f"  attempt {attempt} failed for {url}: {exc}")
                if attempt == self.cfg.max_retries:
                    self.stats["errors"] += 1
                    return None
                time.sleep(backoff)
                backoff *= 2
                continue

            if resp.status_code == 200:
                self.stats["network"] += 1
                body = resp.text
                self._store(url, body)
                return body
            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("Retry-After")
                pause = float(retry_after) if (retry_after or "").isdigit() else backoff
                self._log(f"  {resp.status_code} from {url}, waiting {pause:.0f}s")
                time.sleep(pause)
                backoff *= 2
                continue
            self._log(f"  {resp.status_code} for {url} - giving up")
            self.stats["errors"] += 1
            return None

        self.stats["errors"] += 1
        return None

    def head_ok(self, url: str) -> bool | None:
        """Is this URL live? None when we genuinely could not tell."""
        try:
            resp = self.session.head(url, timeout=self.cfg.timeout_seconds,
                                     allow_redirects=True)
            if resp.status_code >= 400:
                # Some hosts reject HEAD outright; confirm with a ranged GET.
                resp = self.session.get(url, timeout=self.cfg.timeout_seconds,
                                        allow_redirects=True,
                                        headers={"Range": "bytes=0-2048"})
            return resp.status_code < 400
        except requests.RequestException:
            return False

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)
