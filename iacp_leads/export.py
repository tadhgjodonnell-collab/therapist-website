"""Write the lead list out as CSV, and print a summary you can act on."""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from . import classify as C
from .pipeline import Lead

COLUMNS = [
    "score", "verdict", "pitch", "name", "county", "email", "phone",
    "website", "social", "directories", "other_links", "profile_url", "why",
]


def _links_of(lead: Lead, kind: str) -> str:
    return " | ".join(sorted({l.url for l in lead.profile.links if l.kind == kind}))


def row_for(lead: Lead) -> dict[str, str]:
    p, v = lead.profile, lead.verdict
    other = " | ".join(sorted({
        l.url for l in p.links
        if l.kind in (C.BOOKING, C.WEBSITE, C.BUILDER) and l.url != v.website
    }))
    return {
        "score": str(v.score),
        "verdict": v.verdict,
        "pitch": C.VERDICT_PITCH.get(v.verdict, ""),
        "name": p.name,
        "county": p.county,
        "email": p.email,
        "phone": p.phone,
        "website": v.website,
        "social": _links_of(lead, C.SOCIAL),
        "directories": _links_of(lead, C.DIRECTORY),
        "other_links": other,
        "profile_url": p.url,
        "why": "; ".join(v.reasons),
    }


def write_csv(leads: list[Lead], path: str) -> int:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for lead in leads:
            writer.writerow(row_for(lead))
    return len(leads)


def summarise(leads: list[Lead]) -> str:
    if not leads:
        return "No profiles were parsed - nothing to summarise."
    counts = Counter(l.verdict.verdict for l in leads)
    prospects = [l for l in leads if l.is_prospect]
    contactable = [l for l in prospects if l.profile.email or l.profile.phone]
    lines = [
        "",
        f"Profiles parsed:      {len(leads)}",
        f"Prospects (no site):  {len(prospects)}",
        f"  ...contactable:     {len(contactable)}",
        "",
        "Breakdown:",
    ]
    order = [C.NO_WEB_PRESENCE, C.DEAD_WEBSITE, C.BOOKING_ONLY, C.SOCIAL_ONLY,
             C.DIRECTORY_ONLY, C.BUILDER_WEBSITE, C.HAS_WEBSITE]
    for verdict in order:
        if counts.get(verdict):
            lines.append(f"  {verdict:18} {counts[verdict]:5}   "
                         f"{C.VERDICT_PITCH.get(verdict, '')}")
    by_county = Counter(l.profile.county or "(unknown)" for l in contactable)
    if by_county:
        lines += ["", "Top counties among contactable prospects:"]
        for county, n in by_county.most_common(8):
            lines.append(f"  {county:18} {n:5}")
    if contactable:
        lines += ["", "Best 10 to call first:"]
        for lead in contactable[:10]:
            p = lead.profile
            contact = p.email or p.phone or "-"
            lines.append(f"  {lead.verdict.score:3}  {p.name[:32]:32} "
                         f"{(p.county or '-')[:10]:10} {contact}")
    return "\n".join(lines)
