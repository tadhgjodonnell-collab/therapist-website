"""Draft one email per prospect.

The point of this module is NOT to mail-merge a template. A therapist can spot
a merged email instantly, and a bad one costs you the person permanently.

So: every draft is built only from things that are actually true about that
person, the opening line differs by what is genuinely missing from their
listing, and each draft carries one [[ ]] slot that you must write yourself.
A draft that still has its slot filled in is not finished.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import classify as C

SLOT_RE = re.compile(r"\[\[.*?\]\]", re.S)

SLOT = ("[[Your own line here. Something you actually noticed on their "
        "listing - the thing they specialise in, how long they have been at "
        "it, where they practise. One sentence. If you cannot write one "
        "truthfully, do not email this person.]]")


@dataclass
class Sender:
    name: str = "[your name]"
    email: str = "[your email]"
    phone: str = ""
    price: str = "[your price]"
    demo_base_url: str = ""
    what_you_do: str = "I build websites for counsellors and psychotherapists in Ireland"

    @classmethod
    def load(cls, path: str | None) -> "Sender":
        if not path:
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise SystemExit(f"Unknown sender key(s): {', '.join(sorted(unknown))}")
        return cls(**data)


@dataclass
class Draft:
    name: str
    email: str
    phone: str
    subject: str
    body: str
    channel: str = "email"          # or "phone" when there is no address
    notes: list[str] = field(default_factory=list)

    @property
    def unfinished(self) -> bool:
        return bool(SLOT_RE.search(self.body))


def _first_name(name: str) -> str:
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if p]
    if not parts:
        return "there"
    first = parts[0]
    if first.lower().rstrip(".") in ("dr", "mr", "mrs", "ms", "miss", "prof"):
        first = parts[1] if len(parts) > 1 else first
    return first


def _host(url: str) -> str:
    return (urlparse(url).netloc or url).replace("www.", "")


def _observation(row: dict[str, str], where: str) -> tuple[str, str]:
    """The true, specific opening. Returns (subject, sentence)."""
    verdict = row.get("verdict", "")
    site = _host(row.get("website", ""))
    socials = [_host(u) for u in (row.get("social") or "").split(" | ") if u]
    dirs = [_host(u) for u in (row.get("directories") or "").split(" | ") if u]

    if verdict == C.DEAD_WEBSITE:
        return (f"{site} isn't loading",
                f"The website listed on your IACP profile, {site}, isn't "
                f"loading for me — I tried it a few times today. That's "
                f"worth knowing on its own, because anyone clicking it from "
                f"the directory is getting an error page.")
    if verdict == C.SOCIAL_ONLY:
        platform = "Facebook page" if any("facebook" in s for s in socials) else \
                   ("Instagram" if any("instagram" in s for s in socials) else "social page")
        return (f"Your IACP listing",
                f"Your {platform} is the only thing linked from it, which "
                f"works grand until someone searches your name and Facebook "
                f"decides what they see first — and it never shows your "
                f"fees or how to book.")
    if verdict == C.DIRECTORY_ONLY:
        other = dirs[0] if dirs else "another directory"
        return ("Your IACP listing",
                f"You're on {other} as well, which is fine, but on both of "
                f"them you're one of a long list on a page that isn't yours, "
                f"and neither lets you say much in your own words.")
    if verdict == C.BOOKING_ONLY:
        return ("Your IACP listing",
                "There's a booking link on it, but nothing that tells someone "
                "who you are or what a session costs before they're asked to "
                "pick a time — which is the bit most people stall on.")
    if verdict == C.BUILDER_WEBSITE:
        return ("Your website",
                f"You've a site already, at {site}. It's on a free builder "
                f"address rather than your own domain, so it reads as "
                f"temporary and it's working against you in search results "
                f"for {where}.")
    return ("Your IACP listing",
            f"There's no website on it, so that listing is the only way "
            f"someone searching for a therapist in {where} is going to find "
            f"you at all.")


def draft_for(row: dict[str, str], sender: Sender,
              demo_url: str = "") -> Draft:
    name = row.get("name", "").strip()
    where = row.get("town") or row.get("county") or "your area"
    subject, observation = _observation(row, where)
    first = _first_name(name)
    email = (row.get("email") or "").strip()
    phone = (row.get("phone") or "").strip()

    if not email:
        # No address on the listing, so this one is a phone call, not an email.
        body = (
            f"Calling {name}{' in ' + where if where else ''} — {phone}\n\n"
            f"Opening (say it in your own words, don't read it):\n"
            f"  My name's {sender.name}, {sender.what_you_do}. I came across "
            f"your listing on the IACP directory. {observation}\n\n"
            f"{SLOT}\n\n"
            f"  I've put together a draft page for you so you can see what I "
            f"mean rather than me describing it. Can I text or email you the "
            f"link and you can look at it whenever suits?\n\n"
            f"If they say yes, get the address and send the draft the same day.\n"
            f"If they say no, thank them and mark them closed. Don't ring twice."
        )
        return Draft(name, "", phone, f"Call: {name}", body, channel="phone")

    link_line = (
        f"I put a draft page together for you so you can see what I mean "
        f"instead of me describing it: {demo_url}\n\nIt's built from what's on "
        f"your public listing, so the fees and a few other bits are "
        f"placeholders. It isn't published or indexed — only you have "
        f"the link."
    ) if demo_url else (
        "If it'd help, I can put a draft page together from your listing so "
        "you can see what I mean instead of me describing it — no charge "
        "and no obligation either way."
    )

    body = (
        f"Hi {first},\n\n"
        f"My name's {sender.name}. {sender.what_you_do}, and I came across "
        f"your listing on the IACP directory. {observation}\n\n"
        f"{SLOT}\n\n"
        f"{link_line}\n\n"
        f"If it's useful, I charge {sender.price} once-off to finish it and "
        f"put it live on your own domain, and that's the end of it — no "
        f"monthly anything. If it's not for you, no bother at all: reply "
        f"\"no thanks\" and I won't contact you again.\n\n"
        f"{sender.name}\n"
        f"{sender.phone}\n"
        f"{sender.email}\n\n"
        f"(I got your details from your public listing on iacp.ie. Reply to "
        f"this and I'll delete them.)"
    )
    return Draft(name, email, phone, subject, body)


def _context_block(row: dict[str, str]) -> str:
    """What their listing actually says, so writing the personal line is quick."""
    lines = ["**Their listing says**", ""]
    for label, key in (("Town", "town"), ("County", "county"),
                       ("Accreditation", "accreditation"),
                       ("Specialisms", "specialisms")):
        if row.get(key):
            lines.append(f"- {label}: {row[key]}")
    if row.get("blurb"):
        lines.append(f"- In their own words: “{row['blurb'].strip()}”")
    if row.get("profile_url"):
        lines.append(f"- Profile: {row['profile_url']}")
    return "\n".join(lines)


def write_drafts(rows: list[dict[str, str]], sender: Sender, out_dir: str | Path,
                 demo_urls: dict[str, str] | None = None) -> list[Draft]:
    demo_urls = demo_urls or {}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    drafts: list[Draft] = []
    index = ["# Outreach drafts",
             f"\nGenerated {_dt.date.today():%d %B %Y}. "
             f"Every draft below has a `[[ ]]` line you need to replace with "
             f"something of your own before it goes anywhere.\n"]

    for i, row in enumerate(rows, 1):
        draft = draft_for(row, sender, demo_urls.get(row.get("profile_url", ""), ""))
        drafts.append(draft)
        slug = re.sub(r"[^a-z0-9]+", "-", draft.name.lower()).strip("-") or f"lead-{i}"
        text = (f"# {draft.name}\n\n"
                f"**To:** {draft.email or draft.phone or '(no contact)'}  \n"
                f"**Channel:** {draft.channel}  \n"
                f"**Subject:** {draft.subject}\n\n---\n\n"
                f"{draft.body}\n\n---\n\n{_context_block(row)}\n")
        (out / f"{i:03d}-{slug}.md").write_text(text, encoding="utf-8")
        index.append(f"- [{draft.name}]({i:03d}-{slug}.md) "
                     f"— {draft.channel}, {row.get('verdict', '')}")

    (out / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return drafts
