"""Command line entry point."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from . import discover as D
from . import export as E
from .config import Config
from .extract import extract_profile
from .http_client import Fetcher, canonical_url
from .pipeline import build_leads

BANNER = "iacp-leads - find IACP-listed therapists with no website"


def _fetcher(args, cfg: Config) -> Fetcher:
    if args.delay is not None:
        cfg.delay_seconds = args.delay
    if args.no_robots:
        cfg.respect_robots = False
    return Fetcher(cfg, cache_dir=args.cache, force=args.force,
                   verbose=not args.quiet)


def _load_config(args) -> Config:
    cfg = Config.load(args.config)
    if getattr(args, "seed", None):
        cfg.seeds = args.seed
    if getattr(args, "limit", None):
        cfg.max_profiles = args.limit
    if getattr(args, "max_pages", None):
        cfg.max_pages = args.max_pages
    return cfg


# --- run ---------------------------------------------------------------
def cmd_run(args) -> int:
    cfg = _load_config(args)
    fetcher = _fetcher(args, cfg)
    say = (lambda *a: None) if args.quiet else print

    if args.urls:
        urls = [canonical_url(u) for u in
                Path(args.urls).read_text(encoding="utf-8").split()
                if u.strip()]
        say(f"{BANNER}\n\nUsing {len(urls)} profile URL(s) from {args.urls}")
        if cfg.max_profiles:
            urls = urls[:cfg.max_profiles]
    else:
        say(f"{BANNER}\n\nStep 1/3  Crawling listing pages")
        found = D.discover(fetcher, cfg, verbose=not args.quiet)
        urls = found.profile_urls
        say(f"  {found.listing_pages_seen} listing page(s), "
            f"{len(urls)} profile URL(s) via {found.shape_used}")
        if found.js_rendered_warning:
            print(
                "\n  The listing pages came back with almost no links. The IACP\n"
                "  directory is most likely rendered in the browser, so plain\n"
                "  HTTP will never see the results. Options:\n"
                "    - save the result pages from your browser and use:\n"
                "        iacp-leads parse-dir ./saved-pages\n"
                "    - or collect the profile URLs yourself and use:\n"
                "        iacp-leads run --urls urls.txt\n"
                "  Run 'iacp-leads inspect <url>' to see what the server returns.",
                file=sys.stderr)
        if not urls:
            print("\nNo profile URLs found. Run 'iacp-leads inspect <listing-url>' "
                  "to see the page structure, then set profile_url_patterns in a "
                  "--config file.", file=sys.stderr)
            return 2

    say(f"\nStep 2/3  Reading {len(urls)} profile(s)")
    profiles = []
    for i, url in enumerate(urls, 1):
        html = fetcher.get(url)
        if html is None:
            continue
        profiles.append(extract_profile(html, url, cfg))
        if not args.quiet and (i % 25 == 0 or i == len(urls)):
            say(f"  {i}/{len(urls)} read")

    if not profiles:
        print("\nNo profiles could be read.", file=sys.stderr)
        return 2

    say("\nStep 3/3  Scoring")
    leads = build_leads(profiles, cfg, fetcher, check_live=args.check_live,
                        verbose=not args.quiet)
    if args.prospects_only:
        leads = [l for l in leads if l.is_prospect]

    written = E.write_csv(leads, args.out)
    say(E.summarise(leads))
    say(f"\nWrote {written} row(s) to {args.out}")
    say(f"Cache: {fetcher.stats['cache_hits']} hit(s), "
        f"{fetcher.stats['network']} fetched, {fetcher.stats['errors']} error(s), "
        f"{fetcher.stats['blocked']} blocked by robots.txt")
    return 0


# --- parse-dir ---------------------------------------------------------
def cmd_parse_dir(args) -> int:
    cfg = _load_config(args)
    files = sorted(p for p in Path(args.directory).rglob("*")
                   if p.suffix.lower() in (".html", ".htm"))
    if not files:
        print(f"No .html files under {args.directory}", file=sys.stderr)
        return 2
    print(f"{BANNER}\n\nParsing {len(files)} saved page(s) from {args.directory}")
    profiles = []
    for path in files:
        html = path.read_text(encoding="utf-8", errors="replace")
        url = args.base_url.rstrip("/") + "/" + path.name if args.base_url else path.as_uri()
        profiles.append(extract_profile(html, url, cfg))
    leads = build_leads(profiles, cfg, verbose=True)
    if args.prospects_only:
        leads = [l for l in leads if l.is_prospect]
    written = E.write_csv(leads, args.out)
    print(E.summarise(leads))
    print(f"\nWrote {written} row(s) to {args.out}")
    return 0


# --- inspect -----------------------------------------------------------
def cmd_inspect(args) -> int:
    cfg = _load_config(args)
    fetcher = _fetcher(args, cfg)
    html = fetcher.get(args.url)
    if html is None:
        print(f"Could not fetch {args.url}", file=sys.stderr)
        return 2

    soup = BeautifulSoup(html, "lxml")
    print(f"{BANNER}\n\nInspecting {args.url}")
    print(f"  bytes:            {len(html)}")
    print(f"  <title>:          {(soup.title.string or '').strip() if soup.title else '-'}")
    heads = [h.get_text(' ', strip=True)[:70] for h in soup.find_all('h1')][:5]
    print(f"  <h1>:             {heads or '-'}")
    for selector in ("main", "[role=main]", "article", "#content", ".profile"):
        try:
            hit = soup.select_one(selector)
        except Exception:
            hit = None
        if hit:
            print(f"  content container: {selector} "
                  f"({len(hit.get_text(strip=True))} chars of text)")
            break
    else:
        print("  content container: none of the usual ones matched")

    links = D._page_links(html, args.url, cfg)
    print(f"\n  same-site links:  {len(links)}")
    shapes = Counter()
    for link in links:
        shapes[D._shape_of(link) or urlparse(link).path] += 1
    print("  most common URL shapes (a profile listing shows up as a big group):")
    for shape, n in shapes.most_common(12):
        print(f"    {n:5}  {shape}")

    matched = [l for l in links if D._matches_any(l, cfg.profile_url_patterns)]
    print(f"\n  matched by configured profile_url_patterns: {len(matched)}")
    for link in matched[:5]:
        print(f"    {link}")
    shape, members = D.autodetect_shape(links)
    print(f"  auto-detected shape: {shape or 'none'} ({len(members)} URLs)")
    for link in members[:5]:
        print(f"    {link}")

    if args.as_profile:
        profile = extract_profile(html, args.url, cfg)
        print("\n  parsed as a profile page:")
        print(f"    name:   {profile.name or '-'}")
        print(f"    county: {profile.county or '-'}")
        print(f"    email:  {profile.email or '-'}")
        print(f"    phone:  {profile.phone or '-'}")
        print(f"    text:   {profile.raw_text_chars} chars")
        print(f"    links:  {len(profile.links)}")
        for link in profile.links[:20]:
            print(f"      {link.kind:12} {link.url}")
    else:
        print("\n  (add --as-profile to see how a therapist page would be parsed)")
    return 0


def cmd_config(args) -> int:
    print(Config().dump())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="iacp-leads", description=BANNER)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p, with_out=True):
        p.add_argument("--config", help="JSON file overriding any config key")
        p.add_argument("--cache", default=".cache", help="cache directory")
        p.add_argument("--force", action="store_true", help="ignore the cache")
        p.add_argument("--quiet", action="store_true")
        p.add_argument("--delay", type=float, help="seconds between requests")
        p.add_argument("--no-robots", action="store_true",
                       help="do not read robots.txt (use only with permission)")
        if with_out:
            p.add_argument("--out", default="out/leads.csv", help="CSV output path")
            p.add_argument("--prospects-only", action="store_true",
                           help="drop therapists who already have a website")

    run = sub.add_parser("run", help="crawl the directory and write a lead CSV")
    common(run)
    run.add_argument("--seed", action="append", help="listing URL (repeatable)")
    run.add_argument("--urls", help="file of profile URLs, one per line")
    run.add_argument("--limit", type=int, help="stop after N profiles")
    run.add_argument("--max-pages", type=int, help="max listing pages to crawl")
    run.add_argument("--check-live", action="store_true",
                     help="check listed websites actually load (finds dead sites)")
    run.set_defaults(func=cmd_run)

    parse = sub.add_parser("parse-dir", help="score profile pages saved from a browser")
    common(parse)
    parse.add_argument("directory")
    parse.add_argument("--base-url", help="prefix to rebuild original URLs")
    parse.set_defaults(func=cmd_parse_dir)

    inspect = sub.add_parser("inspect", help="show a page's structure, to adapt the config")
    common(inspect, with_out=False)
    inspect.add_argument("url")
    inspect.add_argument("--as-profile", action="store_true")
    inspect.set_defaults(func=cmd_inspect)

    conf = sub.add_parser("config", help="print the default config as JSON")
    conf.set_defaults(func=cmd_config)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted. The cache is kept, so re-running resumes.",
              file=sys.stderr)
        return 130
