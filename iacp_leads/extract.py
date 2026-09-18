"""Pull name, contact details and outbound links out of a profile page."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .classify import Link, classify_link
from .config import Config

# Elements that are page furniture rather than profile content.
_CHROME_TAGS = ("header", "footer", "nav", "script", "style", "noscript",
                "form", "aside", "svg")
_CHROME_ATTR_RE = re.compile(
    r"(^|[-_ ])(nav|navbar|menu|header|footer|masthead|breadcrumb|sidebar|"
    r"side-bar|cookie|consent|banner|skip|social|share|newsletter|subscribe|"
    r"site-info|site-header|site-footer|utility|topbar|megamenu|search)"
    r"([-_ ]|$)", re.I)
# Containers most likely to hold the actual profile.
_MAIN_SELECTORS = ("main", "[role=main]", "article", "#content", "#main",
                   ".entry-content", ".profile", ".therapist", ".member-profile",
                   ".listing-detail", ".single-therapist")

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# name (at) domain (dot) ie  -- common anti-scrape obfuscation.
# Both separators must carry an explicit marker (brackets, or the word spelled
# out), otherwise ordinary prose like "available at www.example.ie" matches.
_AT_SEP = r"(?:[\(\[\{]\s*(?:at|@)\s*[\)\]\}]|\s+@\s+)"
_DOT_SEP = r"(?:[\(\[\{]\s*(?:dot|\.)\s*[\)\]\}]|\s+dot\s+)"
_OBFUSCATED_EMAIL_RE = re.compile(
    r"([A-Za-z0-9._%+-]+)\s*" + _AT_SEP + r"\s*"
    r"([A-Za-z0-9.-]+?)\s*" + _DOT_SEP + r"\s*([A-Za-z]{2,})", re.I)
_PHONE_RE = re.compile(
    r"(?:\+353|00353|0)[\s.\-/()]*\d{1,2}[\s.\-/()]*\d{3}[\s.\-/()]*\d{3,4}"
    r"(?:[\s.\-/()]*\d{0,3})")
_TLD = (r"(?:ie|com|net|org|eu|info|me|co\.uk|org\.uk|online|life|health|care|"
        r"therapy|counselling|clinic|solutions|website|site|blog|co)")
_BARE_DOMAIN_RE = re.compile(
    r"\b(?:https?://)?(?:www\.)[A-Za-z0-9][A-Za-z0-9-]*"
    r"(?:\.[A-Za-z0-9-]+)*\." + _TLD + r"\b(?:/[^\s,;)\]<>\"']*)?", re.I)
_BARE_DOMAIN_NO_WWW_RE = re.compile(
    r"\b[A-Za-z0-9][A-Za-z0-9-]{2,}(?:\.[A-Za-z0-9-]+)*\.(?:ie|com)"
    r"\b(?:/[^\s,;)\]<>\"']*)?", re.I)

_COUNTIES = [
    "Antrim", "Armagh", "Carlow", "Cavan", "Clare", "Cork", "Derry", "Donegal",
    "Down", "Dublin", "Fermanagh", "Galway", "Kerry", "Kildare", "Kilkenny",
    "Laois", "Leitrim", "Limerick", "Longford", "Louth", "Mayo", "Meath",
    "Monaghan", "Offaly", "Roscommon", "Sligo", "Tipperary", "Tyrone",
    "Waterford", "Westmeath", "Wexford", "Wicklow",
]
_COUNTY_RE = re.compile(
    r"\b(?:Co\.?|County)\s+(" + "|".join(_COUNTIES) + r")\b", re.I)


@dataclass
class Profile:
    url: str
    name: str = ""
    county: str = ""
    location: str = ""
    email: str = ""
    phone: str = ""
    links: list[Link] = field(default_factory=list)
    raw_text_chars: int = 0

    @property
    def link_urls(self) -> set[str]:
        return {l.url for l in self.links}


def _strip_chrome(soup: BeautifulSoup) -> BeautifulSoup:
    for tag in soup.find_all(_CHROME_TAGS):
        tag.decompose()
    for tag in soup.find_all(attrs={"role": ["banner", "navigation", "contentinfo",
                                             "search", "complementary"]}):
        tag.decompose()
    for tag in soup.find_all(attrs={"class": True}):
        if _CHROME_ATTR_RE.search(" ".join(tag.get("class", []))):
            tag.decompose()
    for tag in soup.find_all(attrs={"id": True}):
        if _CHROME_ATTR_RE.search(str(tag.get("id", ""))):
            tag.decompose()
    return soup


def _content_root(soup: BeautifulSoup):
    for selector in _MAIN_SELECTORS:
        try:
            found = soup.select_one(selector)
        except Exception:
            continue
        if found and len(found.get_text(strip=True)) > 120:
            return found
    return soup.body or soup


def _clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00353"):
        digits = "0" + digits[5:]
    elif digits.startswith("353"):
        digits = "0" + digits[3:]
    if not (9 <= len(digits) <= 11):
        return ""
    if not digits.startswith("0"):
        return ""
    return digits


def _name_from(soup: BeautifulSoup, root) -> str:
    for candidate in (root.find("h1") if root else None, soup.find("h1")):
        if candidate:
            text = candidate.get_text(" ", strip=True)
            if 2 < len(text) < 90:
                return text
    meta = soup.find("meta", attrs={"property": "og:title"})
    if meta and meta.get("content"):
        return meta["content"].strip()[:90]
    if soup.title and soup.title.string:
        # "Jane Smith | IACP" -> "Jane Smith"
        return re.split(r"\s[|\-–]\s", soup.title.string.strip())[0][:90]
    return ""


def extract_profile(html: str, url: str, cfg: Config) -> Profile:
    soup = BeautifulSoup(html, "lxml")
    full = BeautifulSoup(html, "lxml")  # keep an unstripped copy for the name
    _strip_chrome(soup)
    root = _content_root(soup)
    profile = Profile(url=url)
    profile.name = _name_from(full, _content_root(BeautifulSoup(html, "lxml")))

    text = root.get_text(" ", strip=True) if root else ""
    profile.raw_text_chars = len(text)

    county = _COUNTY_RE.search(text)
    if county:
        profile.county = county.group(1).title()

    seen: set[str] = set()
    for anchor in (root.find_all("a", href=True) if root else []):
        href = anchor["href"].strip()
        label = anchor.get_text(" ", strip=True)[:120]
        low = href.lower()
        if low.startswith("mailto:"):
            found = _EMAIL_RE.search(href[7:])
            if found and not profile.email:
                profile.email = found.group(0).lower()
            continue
        if low.startswith("tel:"):
            cleaned = _clean_phone(href[4:])
            if cleaned and not profile.phone:
                profile.phone = cleaned
            continue
        if low.startswith(("javascript:", "#", "data:", "sms:", "fax:", "skype:")):
            continue
        absolute = urljoin(url, href)
        if not absolute.lower().startswith(("http://", "https://")):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        profile.links.append(classify_link(absolute, cfg, label))

    # Contact details written as plain text rather than linked.
    if not profile.email:
        found = _EMAIL_RE.search(text)
        if found:
            profile.email = found.group(0).lower()
    if not profile.email:
        found = _OBFUSCATED_EMAIL_RE.search(text)
        if found:
            profile.email = f"{found.group(1)}@{found.group(2)}.{found.group(3)}".lower()
    if not profile.phone:
        for match in _PHONE_RE.finditer(text):
            cleaned = _clean_phone(match.group(0))
            if cleaned:
                profile.phone = cleaned
                break

    # A site named in prose ("see www.janesmith.ie") counts just as much as a
    # hyperlink, and plenty of directory listings are typed that way.
    textual = text
    if profile.email:
        textual = textual.replace(profile.email, " ")
    textual = _EMAIL_RE.sub(" ", textual)
    for pattern in (_BARE_DOMAIN_RE, _BARE_DOMAIN_NO_WWW_RE):
        for match in pattern.finditer(textual):
            raw = match.group(0).rstrip(".,;:)")
            absolute = raw if raw.lower().startswith("http") else "https://" + raw
            host = urlparse(absolute).netloc.lower()
            if not host or "." not in host:
                continue
            if absolute in seen:
                continue
            link = classify_link(absolute, cfg, "(mentioned in text)")
            # Only prose-mined links that look like a real site are worth
            # trusting; the regex is too loose for anything else.
            if link.kind in ("website", "builder_site"):
                seen.add(absolute)
                profile.links.append(link)

    return profile
