# iacp-leads

Finds therapists in the IACP directory who have **no website** — the people most
likely to buy one.

It crawls the directory, reads each profile, works out whether the person links
to a site they actually own, and writes a scored CSV with their name, county and
contact details, best prospects first.

```
score  verdict          name              county  email                    phone
110    no_web_presence  Aoife Brennan     Clare                            0871234567
105    social_only      Declan Moore      Kerry   declan.moore@example.ie  0667123456
85     directory_only   Marie Dunne       Meath                            0469021234
60     builder_website  Tom Fitzgerald    Cork    tom@fitzcounselling.com
0      has_website      Niamh Kelly       Galway  hello@niamhkellytherapy.ie
```

## Install

```bash
pip install -r requirements.txt
```

## Use

```bash
# the normal run: crawl, score, write out/leads.csv
python -m iacp_leads run

# try it on 20 profiles first
python -m iacp_leads run --limit 20

# drop everyone who already has a site, and check that listed sites still load
python -m iacp_leads run --prospects-only --check-live
```

Open `out/leads.csv` in a spreadsheet and sort by `score`.

### Before the first full run

Read one listing page and see what the server actually returns:

```bash
python -m iacp_leads inspect https://www.iacp.ie/therapists
python -m iacp_leads inspect https://www.iacp.ie/therapists/some-profile --as-profile
```

This prints the page's link shapes, which container holds the content, and how a
profile would be parsed. If the crawler finds nothing, this tells you why in one
command.

## Verdicts

| verdict | meaning | why they buy |
|---|---|---|
| `no_web_presence` | no website, no social, nothing | invisible outside the IACP listing |
| `dead_website` | lists a site that doesn't load | paying for a broken link (needs `--check-live`) |
| `booking_only` | a Calendly link and nothing else | no page explaining who they are or what they charge |
| `social_only` | Facebook/Instagram only | renting an audience, no search presence |
| `directory_only` | only on Psychology Today and similar | one of fifty on somebody else's page |
| `builder_website` | site on a free `*.wixsite.com`-style subdomain | no custom domain — an upgrade pitch, not a new build |
| `has_website` | their own domain, and it loads | not a prospect |

Scoring is `verdict base + 15 if there's an email + 10 if there's a phone − 30 if
there's neither`, so a lead you can't contact sinks. The `why` column in the CSV
says what drove each verdict.

## How it avoids the obvious ways this goes wrong

**Site chrome.** IACP's own footer links to IACP's Facebook page. Naively, that
makes *every* therapist look like they have a social presence and nobody looks
like a prospect. Two defences: header/nav/footer elements are stripped before
parsing, and then any host linked from more than 30% of profiles is treated as
furniture and subtracted (`pipeline.py`). The second one catches shared links
that sit inside the profile body, where no CSS selector would help. It stays off
below 10 profiles, where the signal isn't there.

**Websites written as plain text.** Plenty of listings type
`www.janesmith.ie` without linking it. Prose is scanned for bare domains too, and
for `name (at) domain (dot) ie` style emails — with markers required on both
separators, so ordinary prose like "available at www.example.ie" doesn't get read
as an email address.

**Builder domains.** `squarespace.com` is the vendor and means nothing;
`jane.squarespace.com` is a real site. These are told apart rather than lumped
together.

**A site redesign.** If the configured URL patterns match nothing, the crawler
falls back to auto-detecting the profile URL shape: it groups same-site links by
path shape and takes the biggest family of sibling detail pages. On a page of
therapist links it finds `/therapists/*` without being told.

## If the crawl comes back empty

The directory may be rendered in the browser, in which case plain HTTP sees an
empty shell. The tool detects this and says so. Two ways around it:

```bash
# save the result pages from your browser (Ctrl+S), then:
python -m iacp_leads parse-dir ./saved-pages

# or collect profile URLs yourself into a text file, one per line:
python -m iacp_leads run --urls urls.txt
```

Both paths run the same extraction and scoring.

## Tuning it

Every setting — seed URLs, URL patterns, delays, and all the domain
classification lists — lives in `iacp_leads/config.py` and can be overridden
without touching code:

```bash
python -m iacp_leads config > my-config.json   # dump the defaults
# edit my-config.json
python -m iacp_leads run --config my-config.json
```

The lists worth editing are `directory_domains` (other directories that aren't a
real website) and `booking_domains`.

## Being a good citizen about it

Defaults: reads and obeys `robots.txt`, one request at a time, 1.5s apart plus
jitter, honouring any longer `Crawl-delay` the site asks for. Every response is
cached to `.cache/`, so re-runs and interrupted crawls cost the site nothing —
this matters more than the delay does. `--no-robots` exists but don't use it
without permission.

A note worth having before you start sending: IACP-listed therapists are mostly
sole traders, so their details are personal data under GDPR, and Ireland's
ePrivacy regulations (SI 336/2011) treat unsolicited marketing **email** to an
individual as needing prior consent — a corporate-sounding address doesn't change
that if the business is one person. Phone contact to a business number is the
more defensible channel, as is post. Whatever you send, say where you got their
details and make opting out easy. Worth 20 minutes with someone who knows the
rules before a first campaign — the tool gives you the list either way.

## Development

```bash
python -m unittest discover -s tests -t .
```

33 tests, no network needed — they run against HTML fixtures in `tests/fixtures/`
that deliberately include IACP-style page furniture.

### Layout

| file | job |
|---|---|
| `config.py` | settings and the domain classification lists |
| `http_client.py` | cache, rate limiting, robots.txt, retries |
| `discover.py` | finds profile URLs, incl. URL-shape auto-detection |
| `extract.py` | name, county, email, phone, links out of one profile |
| `classify.py` | is this link their website? what's the verdict? |
| `pipeline.py` | boilerplate subtraction, liveness checks, scoring |
| `export.py` | CSV and the terminal summary |

### One thing to know about how this was built

`www.iacp.ie` is blocked by this development environment's network policy, so
the live HTML was never seen while writing it. That's why the extraction is
heuristic-first — content-shape detection and frequency analysis rather than
hardcoded CSS selectors — and why `inspect` exists. Expect to run `inspect`
once against the real site and possibly adjust `profile_url_patterns`; the rest
is designed not to need it.
