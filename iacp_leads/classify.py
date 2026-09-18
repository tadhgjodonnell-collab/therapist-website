"""Decide whether a link is the therapist's own website, and score the lead."""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from .config import Config
from .http_client import registrable_host

# Link kinds, roughly in order of how much they matter to the pitch.
WEBSITE = "website"          # their own site -> not a prospect
BUILDER = "builder_site"     # a real site, but on a free builder subdomain
SOCIAL = "social"            # Facebook/Instagram only -> prospect
DIRECTORY = "directory"      # only listed on other directories -> prospect
BOOKING = "booking"          # a Calendly link is not a website -> prospect
SELF = "self"                # back to iacp.ie
NOISE = "noise"              # assets, maps, share widgets


@dataclass
class Link:
    url: str
    host: str
    kind: str
    text: str = ""


def _host_of(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
    except ValueError:
        return ""
    return netloc.lower().split("@")[-1].split(":")[0].strip(".")


def _is_builder_site(host: str, cfg: Config) -> bool:
    """jane.wixsite.com is a site; wix.com itself is just the vendor."""
    for suffix in cfg.builder_host_suffixes:
        if host == suffix or host == f"www.{suffix}":
            return False
        if host.endswith("." + suffix):
            return True
    return False


def classify_link(url: str, cfg: Config, text: str = "") -> Link:
    host = _host_of(url)
    if not host:
        return Link(url, "", NOISE, text)
    reg = registrable_host(host)

    # Builder subdomains are checked first: squarespace.com is noise, but
    # jane.squarespace.com is the very site we are looking for.
    if _is_builder_site(host, cfg):
        return Link(url, host, BUILDER, text)

    for domains, kind in (
        (cfg.self_domains, SELF),
        (cfg.social_domains, SOCIAL),
        (cfg.directory_domains, DIRECTORY),
        (cfg.booking_domains, BOOKING),
        (cfg.noise_domains, NOISE),
    ):
        if reg in domains or host in domains:
            return Link(url, host, kind, text)

    return Link(url, host, WEBSITE, text)


# --- profile level ------------------------------------------------------

# Verdicts, best prospect first.
NO_WEB_PRESENCE = "no_web_presence"
BOOKING_ONLY = "booking_only"
DIRECTORY_ONLY = "directory_only"
SOCIAL_ONLY = "social_only"
DEAD_WEBSITE = "dead_website"
BUILDER_WEBSITE = "builder_website"
HAS_WEBSITE = "has_website"

PROSPECT_VERDICTS = {
    NO_WEB_PRESENCE, BOOKING_ONLY, DIRECTORY_ONLY, SOCIAL_ONLY,
    DEAD_WEBSITE, BUILDER_WEBSITE,
}

_BASE_SCORE = {
    NO_WEB_PRESENCE: 100,
    DEAD_WEBSITE: 95,
    BOOKING_ONLY: 85,
    SOCIAL_ONLY: 80,
    DIRECTORY_ONLY: 75,
    BUILDER_WEBSITE: 45,
    HAS_WEBSITE: 0,
}

VERDICT_PITCH = {
    NO_WEB_PRESENCE: "No website and no social presence at all - invisible outside the IACP listing.",
    DEAD_WEBSITE: "Lists a website, but the domain does not resolve or load - they are paying for a dead link.",
    BOOKING_ONLY: "Only a booking link - no page that explains who they are or what they charge.",
    SOCIAL_ONLY: "Facebook/Instagram only - renting an audience, nothing they own, no search presence.",
    DIRECTORY_ONLY: "Only findable on other directories - competing with every other therapist on one page.",
    BUILDER_WEBSITE: "Site on a free builder subdomain - no custom domain, weak credibility and SEO.",
    HAS_WEBSITE: "Already has their own website.",
}


@dataclass
class Verdict:
    verdict: str
    score: int
    website: str = ""
    reasons: list[str] = field(default_factory=list)


def verdict_for(links: list[Link], email: str, phone: str,
                dead_websites: set[str] | None = None) -> Verdict:
    """Classify one profile from its outbound links and contact details."""
    dead_websites = dead_websites or set()
    reasons: list[str] = []

    real = [l for l in links if l.kind == WEBSITE]
    builder = [l for l in links if l.kind == BUILDER]
    live_real = [l for l in real if l.url not in dead_websites]

    if live_real:
        v, site = HAS_WEBSITE, live_real[0].url
    elif real:
        # every own-domain link we found was unreachable
        v, site = DEAD_WEBSITE, real[0].url
        reasons.append(f"website {real[0].host} did not respond")
    elif builder:
        v, site = BUILDER_WEBSITE, builder[0].url
        reasons.append(f"hosted on {builder[0].host}")
    else:
        site = ""
        kinds = {l.kind for l in links}
        if SOCIAL in kinds:
            v = SOCIAL_ONLY
            hosts = sorted({l.host for l in links if l.kind == SOCIAL})
            reasons.append("social only: " + ", ".join(hosts))
        elif DIRECTORY in kinds:
            v = DIRECTORY_ONLY
            hosts = sorted({l.host for l in links if l.kind == DIRECTORY})
            reasons.append("other directories only: " + ", ".join(hosts))
        elif BOOKING in kinds:
            v = BOOKING_ONLY
            hosts = sorted({l.host for l in links if l.kind == BOOKING})
            reasons.append("booking link only: " + ", ".join(hosts))
        else:
            v = NO_WEB_PRESENCE
            reasons.append("no outbound links on the profile")

    score = _BASE_SCORE[v]
    if v != HAS_WEBSITE:
        # A prospect you cannot contact is not a prospect.
        if email:
            score += 15
            reasons.append("email on profile")
        if phone:
            score += 10
            reasons.append("phone on profile")
        if not email and not phone:
            score -= 30
            reasons.append("no contact details on profile")
    return Verdict(v, max(score, 0), site, reasons)
