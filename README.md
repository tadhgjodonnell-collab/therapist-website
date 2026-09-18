# iacp-leads

Tools for selling websites to Irish counsellors and psychotherapists. Three
steps, three commands:

```bash
python -m iacp_leads run                                    # 1. find prospects
python -m iacp_leads site  --from-csv out/leads.csv         # 2. build each one a draft site
python -m iacp_leads email --from-csv out/leads.csv \
       --sender sender.json --demos demos \
       --base-url https://drafts.yourdomain.ie              # 3. draft the outreach
```

You end up with a scored CSV, one private draft website per prospect, and one
email per prospect that links to *their* draft rather than a generic sample.

---

## 1. Finding prospects

Crawls the IACP directory, reads each profile, works out whether the person
links to a site they actually own, and writes a scored CSV, best prospects
first.

```
score  verdict          name              county  email                    phone
110    no_web_presence  Aoife Brennan     Clare                            0871234567
105    social_only      Declan Moore      Kerry   declan.moore@example.ie  0667123456
85     directory_only   Marie Dunne       Meath                            0469021234
60     builder_website  Tom Fitzgerald    Cork    tom@fitzcounselling.com
0      has_website      Niamh Kelly       Galway  hello@niamhkellytherapy.ie
```

### Install

```bash
pip install -r requirements.txt
```

### Use

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

### Verdicts

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

### How it avoids the obvious ways this goes wrong

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

### If the crawl comes back empty

The directory may be rendered in the browser, in which case plain HTTP sees an
empty shell. The tool detects this and says so. Two ways around it:

```bash
# save the result pages from your browser (Ctrl+S), then:
python -m iacp_leads parse-dir ./saved-pages

# or collect profile URLs yourself into a text file, one per line:
python -m iacp_leads run --urls urls.txt
```

Both paths run the same extraction and scoring.

### Tuning it

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

### Being a good citizen about it

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

## 2. The site

One page, no JavaScript, no build step. `site/template.html` plus
`site/styles.css`, filled from a JSON file.

```bash
# a private draft for every prospect in the CSV
python -m iacp_leads site --from-csv out/leads.csv --out demos --limit 25

# a paying client's real site: no draft banner, indexable
python -m iacp_leads site --content clients/aoife.json --out build/aoife --live
```

Each build writes `index.html`, `styles.css` and the `content.json` it was built
from — edit that and rebuild.

### Why it doesn't read as generated

The brief was that it must not look AI-made, so the tells are dealt with
deliberately:

- **No card grids, no icon rows, no gradients, no drop shadows, no hero
  banner, no animation, no JavaScript.** One warm paper background, one ink
  colour, one muted green accent.
- **One serif throughout** (Newsreader, with Georgia as the fallback). Mixed
  serif/sans reads corporate; the default sans stack reads like a dashboard.
- **Asymmetric.** The portrait sits off the text column and drops below the
  first line rather than aligning to it; on wide screens the section labels
  move out into the left margin. Perfect symmetry is what makes a page look
  auto-laid-out.
- **No dark mode.** A one-person practice does not ship a theme toggle.
- **The copy avoids the giveaway words** — no journey, safe space, empower,
  holistic, thrive, unlock or reach out. There's a test that fails the build
  if any of them come back.
- **Plain practical detail instead of marketing.** Fee in euro, session length,
  cancellation policy, whether there's parking, whether they're taking new
  clients. This is what people actually read, and templates never include it.

Two things in there come from how the profession actually works rather than
from design:

- **There is no testimonials section, and there never will be.** IACP's Code of
  Ethics restricts soliciting client endorsements. A "What clients say" block
  marks a site as built by someone who has never worked with a therapist — it's
  the single clearest tell. A test enforces its absence.
- **Crisis signposting is built in** — Samaritans, Text About It, Pieta,
  emergency services — with a line saying the therapist isn't an emergency
  service. Every real Irish practice site carries this and its absence is
  conspicuous.

### Draft builds are safe to send

A draft build is marked `noindex, nofollow`, and carries a banner saying it's a
draft made from their public listing, that fees and anything in square brackets
are placeholders, and that nothing is published. Nothing about them is invented:
only the name, town, county, accreditation and specialisms actually scraped from
their listing are filled in. Everything else is an obvious, bracketed prompt.

That banner isn't an apology — inviting someone to correct their own fees is the
thing that gets a reply.

## 3. The emails

```bash
python -m iacp_leads email --from-csv out/leads.csv --sender sender.json \
       --demos demos --base-url https://drafts.yourdomain.ie --out outreach
```

`sender.json` is your half:

```json
{
  "name": "Your Name",
  "email": "you@example.ie",
  "phone": "087 000 0000",
  "price": "€450",
  "what_you_do": "I build websites for counsellors and psychotherapists in Ireland"
}
```

You get one markdown file per prospect, plus an index.

**This is not a mail merge, on purpose.** A therapist spots a merged email
instantly and you only get one go at each person. So:

- **The opening line is different for each prospect**, and it's true of them
  specifically. Someone with a dead website gets told their site isn't loading —
  which is a favour before it's a pitch. Someone with only a Facebook page gets
  a different sentence from someone with nothing at all.
- **Every draft has a `[[ ]]` slot you must write yourself**, and the tool tells
  you how many are still unwritten. Underneath each draft it prints what their
  listing actually says — their town, specialisms, accreditation and their own
  words — so writing that line takes about twenty seconds. If you can't write
  one truthfully, that's a signal not to email that person.
- **Prospects with no email address become a phone script instead**, because a
  listing with only a phone number is a call, not a send.
- Each email says where you got their details and how to opt out, in one line
  at the bottom.

## Development

```bash
python -m unittest discover -s tests -t .
```

56 tests, no network needed — they run against HTML fixtures in `tests/fixtures/`
that deliberately include IACP-style page furniture. Several of them exist to
protect decisions rather than code: that the site copy stays free of the
giveaway words, that no testimonials section creeps in, that crisis signposting
is present, and that every email draft still demands a line of your own.

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
| `sitegen.py` | template renderer and the site's default content |
| `outreach.py` | per-prospect email and phone-call drafts |
| `site/` | `template.html` and `styles.css` — the product you're selling |

### One thing to know about how this was built

`www.iacp.ie` is blocked by this development environment's network policy, so
the live HTML was never seen while writing it. That's why the extraction is
heuristic-first — content-shape detection and frequency analysis rather than
hardcoded CSS selectors — and why `inspect` exists. Expect to run `inspect`
once against the real site and possibly adjust `profile_url_patterns`; the rest
is designed not to need it.
