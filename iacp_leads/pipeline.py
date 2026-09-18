"""Turn extracted profiles into scored leads."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from . import classify as C
from .config import Config
from .extract import Profile
from .http_client import Fetcher

# Below this many profiles there isn't enough signal to tell a shared nav link
# from a genuine coincidence, so boilerplate subtraction stays off.
MIN_PROFILES_FOR_BOILERPLATE = 10
BOILERPLATE_SHARE = 0.30


@dataclass
class Lead:
    profile: Profile
    verdict: C.Verdict
    dropped_boilerplate: list[str] = field(default_factory=list)

    @property
    def is_prospect(self) -> bool:
        return self.verdict.verdict in C.PROSPECT_VERDICTS


def find_boilerplate_hosts(profiles: list[Profile]) -> set[str]:
    """Hosts linked from a large share of profiles are site chrome, not theirs.

    This is what stops IACP's own Facebook link in the page furniture from
    making every therapist look like they have a social presence.
    """
    if len(profiles) < MIN_PROFILES_FOR_BOILERPLATE:
        return set()
    counts: Counter[str] = Counter()
    for profile in profiles:
        for host in {l.host for l in profile.links}:
            counts[host] += 1
    cutoff = max(2, int(len(profiles) * BOILERPLATE_SHARE))
    return {host for host, n in counts.items() if n >= cutoff}


def build_leads(profiles: list[Profile], cfg: Config,
                fetcher: Fetcher | None = None,
                check_live: bool = False,
                verbose: bool = True) -> list[Lead]:
    boilerplate = find_boilerplate_hosts(profiles)
    if boilerplate and verbose:
        print(f"  ignoring {len(boilerplate)} shared/chrome host(s): "
              f"{', '.join(sorted(boilerplate)[:8])}"
              f"{' ...' if len(boilerplate) > 8 else ''}", flush=True)

    cleaned: list[tuple[Profile, list[C.Link], list[str]]] = []
    for profile in profiles:
        kept, dropped = [], []
        for link in profile.links:
            if link.host in boilerplate:
                dropped.append(link.url)
            else:
                kept.append(link)
        cleaned.append((profile, kept, dropped))

    dead: set[str] = set()
    if check_live and fetcher is not None:
        candidates = {l.url for _, links, _ in cleaned for l in links
                      if l.kind in (C.WEBSITE, C.BUILDER)}
        if verbose and candidates:
            print(f"  checking {len(candidates)} website(s) for signs of life...",
                  flush=True)
        for url in sorted(candidates):
            if fetcher.head_ok(url) is False:
                dead.add(url)
        if verbose and dead:
            print(f"  {len(dead)} listed website(s) did not respond", flush=True)

    leads: list[Lead] = []
    for profile, links, dropped in cleaned:
        verdict = C.verdict_for(links, profile.email, profile.phone, dead)
        profile.links = links
        leads.append(Lead(profile, verdict, dropped))

    leads.sort(key=lambda l: (-l.verdict.score, l.profile.county, l.profile.name))
    return leads
