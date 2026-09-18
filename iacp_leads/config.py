"""Configuration: domain classification lists and tunable crawl settings.

Everything here can be overridden from a JSON file passed with --config, so the
tool can be adapted to the live site without editing code.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

# The directory itself, plus the professional bodies and public services a
# therapist routinely links to. A link to one of these is never "their website".
SELF_DOMAINS = {
    "iacp.ie",
}

# Social profiles. Having only these means no website -> a strong lead.
SOCIAL_DOMAINS = {
    "facebook.com", "fb.com", "fb.me", "messenger.com",
    "instagram.com", "instagr.am",
    "twitter.com", "x.com",
    "linkedin.com", "lnkd.in",
    "tiktok.com", "youtube.com", "youtu.be",
    "pinterest.com", "pinterest.ie", "threads.net", "threads.com",
    "snapchat.com", "bsky.app", "mastodon.social",
    "whatsapp.com", "wa.me", "t.me", "telegram.me",
}

# Other directories / listing sites. A therapist who is only findable on these
# is renting an audience, not owning one -> also a strong lead.
DIRECTORY_DOMAINS = {
    "psychologytoday.com",
    "counsellingdirectory.org.uk", "counselling-directory.org.uk",
    "welldoing.org", "bacp.co.uk", "ukcp.org.uk",
    "iahip.org", "apcp.ie", "icp.ie", "fti.ie",
    "psychotherapycouncil.ie", "irish-counselling.ie",
    "addictioncounsellors.ie", "nappe.ie",
    "psychologicalsociety.ie", "psihq.ie", "coru.ie",
    "therapy.ie", "mytherapy.ie", "findatherapist.ie", "therapistdirectory.ie",
    "goodtherapy.org", "harleytherapy.com", "bark.com", "yelp.ie", "yelp.com",
    "goldenpages.ie", "hotfrog.ie", "cylex.ie", "yell.com",
    # public / charity services, never a personal site
    "hse.ie", "tusla.ie", "citizensinformation.ie", "gov.ie",
    "mentalhealthireland.ie", "aware.ie", "pieta.ie", "samaritans.org",
    "yourmentalhealth.ie", "turn2me.ie", "spunout.ie", "jigsaw.ie",
    "barnardos.ie", "childline.ie", "womensaid.ie", "mabs.ie",
}

# Booking / practice-management tools. A Calendly link is not a website.
BOOKING_DOMAINS = {
    "calendly.com", "bookwhen.com", "acuityscheduling.com", "squarespace-scheduling.com",
    "janeapp.com", "simplepractice.com", "powerdiary.com", "cliniko.com",
    "setmore.com", "youcanbook.me", "10to8.com", "appointedd.com",
    "zoom.us", "meet.google.com", "teams.microsoft.com", "doxy.me",
    "eventbrite.ie", "eventbrite.com", "ticketsolve.com",
    "paypal.com", "paypal.me", "stripe.com", "revolut.me", "buymeacoffee.com",
    "gofundme.com", "patreon.com",
}

# Infrastructure, assets, share widgets, maps, cookie banners. Pure noise.
NOISE_DOMAINS = {
    "w3.org", "schema.org", "ogp.me", "gmpg.org",
    "google.com", "goo.gl", "google.ie", "gstatic.com", "googleapis.com",
    "googletagmanager.com", "google-analytics.com", "doubleclick.net",
    "maps.app.goo.gl", "maps.google.com",
    "gravatar.com", "cloudflare.com", "cloudfront.net", "jsdelivr.net",
    "unpkg.com", "bootstrapcdn.com", "jquery.com", "fontawesome.com",
    "addthis.com", "sharethis.com", "cookiebot.com", "cookieyes.com",
    "wordpress.org", "wix.com", "squarespace.com", "weebly.com", "godaddy.com",
    "adobe.com", "apple.com", "microsoft.com", "mozilla.org",
    "mailchimp.com", "us1.list-manage.com", "list-manage.com",
    "sentry.io", "hotjar.com", "recaptcha.net",
}

# Site builders that host real sites on a shared subdomain. These DO count as a
# website, but a free builder subdomain is a good upgrade pitch, so flag them.
BUILDER_HOST_SUFFIXES = (
    "wixsite.com", "wix.com", "squarespace.com", "weebly.com",
    "wordpress.com", "blogspot.com", "blogspot.ie",
    "sites.google.com", "godaddysites.com", "myshopify.com",
    "webnode.ie", "webnode.com", "jimdosite.com", "strikingly.com",
    "carrd.co", "notion.site", "webflow.io", "github.io", "netlify.app",
    "vercel.app", "wordpress.site", "business.site",
)


@dataclass
class Config:
    # --- crawling -------------------------------------------------------
    seeds: list[str] = field(default_factory=lambda: [
        "https://www.iacp.ie/therapists",
        "https://www.iacp.ie/iacp-find-a-therapist",
    ])
    # Regexes matched against a URL's path to recognise a profile page. If none
    # match anything, the crawler falls back to shape auto-detection.
    profile_url_patterns: list[str] = field(default_factory=lambda: [
        r"/therapist[s]?/[^/]+/?$",
        r"/counsellor[s]?/[^/]+/?$",
        r"/member[s]?/[^/]+/?$",
        r"/profile/[^/]+/?$",
        r"/find-a-therapist/[^/]+/?$",
    ])
    # Regexes for "next page" links.
    pagination_url_patterns: list[str] = field(default_factory=lambda: [
        r"[?&]page=\d+",
        r"[?&]p=\d+",
        r"/page/\d+",
        r"[?&]offset=\d+",
        r"[?&]start=\d+",
    ])
    allowed_hosts: list[str] = field(default_factory=lambda: ["iacp.ie"])
    max_pages: int = 200
    max_profiles: int = 0  # 0 = unlimited

    # --- politeness -----------------------------------------------------
    delay_seconds: float = 1.5
    jitter_seconds: float = 0.5
    timeout_seconds: float = 30.0
    max_retries: int = 3
    respect_robots: bool = True
    user_agent: str = (
        "iacp-leads/1.0 (prospect research for web design services; "
        "contact via site owner)"
    )

    # --- classification -------------------------------------------------
    self_domains: list[str] = field(default_factory=lambda: sorted(SELF_DOMAINS))
    social_domains: list[str] = field(default_factory=lambda: sorted(SOCIAL_DOMAINS))
    directory_domains: list[str] = field(default_factory=lambda: sorted(DIRECTORY_DOMAINS))
    booking_domains: list[str] = field(default_factory=lambda: sorted(BOOKING_DOMAINS))
    noise_domains: list[str] = field(default_factory=lambda: sorted(NOISE_DOMAINS))
    builder_host_suffixes: list[str] = field(default_factory=lambda: list(BUILDER_HOST_SUFFIXES))

    @classmethod
    def load(cls, path: str | None) -> "Config":
        cfg = cls()
        if not path:
            return cfg
        with open(path, "r", encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
        unknown = set(data) - {f for f in cls.__dataclass_fields__}
        if unknown:
            raise SystemExit(
                f"Unknown config key(s) in {path}: {', '.join(sorted(unknown))}"
            )
        for key, value in data.items():
            setattr(cfg, key, value)
        return cfg

    def dump(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)
