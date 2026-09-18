"""Find therapist profile URLs on the directory's listing pages."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from .config import Config
from .http_client import Fetcher, canonical_url, registrable_host

_ID_SEGMENT_RE = re.compile(r"^[0-9]+$")
_SKIP_PATH_RE = re.compile(
    r"\.(?:pdf|jpe?g|png|gif|svg|webp|ico|css|js|zip|docx?|xlsx?|mp4|mp3)$", re.I)
# Section pages that will never be a therapist profile.
_OBVIOUS_NON_PROFILE_RE = re.compile(
    r"^/(?:about|contact|news|events|blog|training|courses|cpd|shop|cart|"
    r"account|login|register|privacy|cookie|terms|sitemap|search|faq|press|"
    r"membership|complaints|ethics|governance|jobs|donate|media)\b", re.I)


@dataclass
class Discovery:
    profile_urls: list[str]
    listing_pages_seen: int
    shape_used: str
    js_rendered_warning: bool


def _same_site(url: str, cfg: Config) -> bool:
    reg = registrable_host(url)
    return any(reg == h or reg.endswith("." + h) for h in cfg.allowed_hosts)


def _page_links(html: str, base_url: str, cfg: Config) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    out: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.lower().startswith(("mailto:", "tel:", "javascript:", "#", "data:")):
            continue
        absolute = urljoin(base_url, href)
        if not absolute.lower().startswith(("http://", "https://")):
            continue
        if not _same_site(absolute, cfg):
            continue
        if _SKIP_PATH_RE.search(urlparse(absolute).path):
            continue
        out.append(canonical_url(absolute))
    return out


def _matches_any(url: str, patterns: list[str]) -> bool:
    target = urlparse(url).path + (("?" + urlparse(url).query) if urlparse(url).query else "")
    return any(re.search(p, target, re.I) for p in patterns)


def _shape_of(url: str) -> str | None:
    """A grouping key for URLs that look like sibling detail pages."""
    parts = urlparse(url)
    segments = [s for s in parts.path.split("/") if s]
    query = parse_qs(parts.query)
    id_keys = sorted(k for k in query
                     if re.fullmatch(r"(?:id|uid|mid|memberid|member_id|tid|"
                                     r"therapist|profile|ref)", k, re.I))
    if id_keys:
        return f"{parts.path}?{'&'.join(id_keys)}=*"
    if len(segments) < 2:
        return None
    last = segments[-1]
    # A slug or a numeric id; a one-word segment is more likely a section page.
    if not (_ID_SEGMENT_RE.match(last) or "-" in last or "_" in last or len(last) > 12):
        return None
    return "/" + "/".join(segments[:-1]) + "/*"


def autodetect_shape(urls: list[str], min_group: int = 5) -> tuple[str | None, list[str]]:
    """Guess the profile URL shape as the biggest family of sibling detail pages."""
    groups: dict[str, set[str]] = defaultdict(set)
    for url in urls:
        path = urlparse(url).path
        if _OBVIOUS_NON_PROFILE_RE.match(path):
            continue
        shape = _shape_of(url)
        if shape:
            groups[shape].add(url)
    if not groups:
        return None, []
    shape, members = max(groups.items(), key=lambda kv: len(kv[1]))
    if len(members) < min_group:
        return None, []
    return shape, sorted(members)


def discover(fetcher: Fetcher, cfg: Config, verbose: bool = True) -> Discovery:
    queue: list[str] = [canonical_url(u) for u in cfg.seeds]
    seen_pages: set[str] = set()
    all_links: list[str] = []
    matched: set[str] = set()
    pages_fetched = 0
    thin_pages = 0

    while queue and pages_fetched < cfg.max_pages:
        url = queue.pop(0)
        if url in seen_pages:
            continue
        seen_pages.add(url)
        html = fetcher.get(url)
        if html is None:
            continue
        pages_fetched += 1
        links = _page_links(html, url, cfg)
        if len(links) < 5:
            thin_pages += 1
        all_links.extend(links)
        if verbose:
            print(f"  [{pages_fetched}] {url} -> {len(links)} links", flush=True)

        for link in links:
            if _matches_any(link, cfg.profile_url_patterns):
                matched.add(link)
            elif (_matches_any(link, cfg.pagination_url_patterns)
                  and link not in seen_pages and link not in queue):
                queue.append(link)
        if cfg.max_profiles and len(matched) >= cfg.max_profiles:
            break

    shape_used = "configured profile_url_patterns"
    if not matched:
        shape, members = autodetect_shape(all_links)
        if shape:
            matched = set(members)
            shape_used = f"auto-detected shape {shape}"
            if verbose:
                print(f"  no configured pattern matched; {shape_used} "
                      f"({len(members)} URLs)", flush=True)

    # If every page we pulled was almost link-free, the directory is very
    # likely rendered client-side and plain HTTP will never see the listings.
    js_warning = pages_fetched > 0 and thin_pages == pages_fetched and not matched

    profiles = sorted(matched)
    if cfg.max_profiles:
        profiles = profiles[:cfg.max_profiles]
    return Discovery(profiles, pages_fetched, shape_used, js_warning)
