"""Build a one-page practice site for a therapist.

Two jobs: a tiny template renderer, and the default content used when we are
building a draft preview from nothing but a scraped IACP listing.
"""
from __future__ import annotations

import datetime as _dt
import html
import json
import re
import shutil
from pathlib import Path
from typing import Any

SITE_DIR = Path(__file__).resolve().parent.parent / "site"

# --- renderer -----------------------------------------------------------
# A deliberately small subset of mustache: {{var}}, {{&var}} (unescaped),
# {{#key}}...{{/key}} (list or truthy) and {{^key}}...{{/key}} (falsy).
#
# Parsed into a tree rather than matched with a regex, because the template
# legitimately nests a section inside a section of the SAME name (a list used
# both as a guard and as the thing iterated), and no regex can tell that
# closing tag from the outer one.
_TOKEN_RE = re.compile(r"\{\{([#^/&]?)([\w.]+)\}\}")

_TEXT, _VAR, _SECTION = "text", "var", "section"


def parse(template: str) -> list:
    stack: list[list] = [[]]
    open_keys: list[tuple[str, bool]] = []
    pos = 0
    for match in _TOKEN_RE.finditer(template):
        if match.start() > pos:
            stack[-1].append((_TEXT, template[pos:match.start()]))
        sigil, key = match.group(1), match.group(2)
        if sigil in ("#", "^"):
            stack.append([])
            open_keys.append((key, sigil == "^"))
        elif sigil == "/":
            if not open_keys or open_keys[-1][0] != key:
                expected = open_keys[-1][0] if open_keys else "nothing"
                raise ValueError(
                    f"template error: {{{{/{key}}}}} closes {expected}")
            children = stack.pop()
            name, inverted = open_keys.pop()
            stack[-1].append((_SECTION, name, inverted, children))
        else:
            stack[-1].append((_VAR, key, sigil != "&"))
        pos = match.end()
    if pos < len(template):
        stack[-1].append((_TEXT, template[pos:]))
    if open_keys:
        raise ValueError(f"template error: unclosed {{{{#{open_keys[-1][0]}}}}}")
    return stack[0]


def _lookup(ctx: dict[str, Any], key: str) -> Any:
    if key == ".":
        return ctx.get(".", "")
    node: Any = ctx
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return ""
    return node


def _render_nodes(nodes: list, ctx: dict[str, Any]) -> str:
    out: list[str] = []
    for node in nodes:
        kind = node[0]
        if kind is _TEXT or kind == _TEXT:
            out.append(node[1])
        elif kind == _VAR:
            value = _lookup(ctx, node[1])
            if value in (None, "", False):
                continue
            text = str(value)
            out.append(html.escape(text, quote=True) if node[2] else text)
        else:
            _, key, inverted, children = node
            value = _lookup(ctx, key)
            truthy = bool(value)
            if inverted:
                if not truthy:
                    out.append(_render_nodes(children, ctx))
                continue
            if not truthy:
                continue
            if isinstance(value, list):
                for item in value:
                    child = dict(ctx)
                    if isinstance(item, dict):
                        child.update(item)
                    else:
                        child["."] = item
                    out.append(_render_nodes(children, child))
            elif isinstance(value, dict):
                child = dict(ctx)
                child.update(value)
                out.append(_render_nodes(children, child))
            else:
                out.append(_render_nodes(children, ctx))
    return "".join(out)


def render(template: str, ctx: dict[str, Any]) -> str:
    return _render_nodes(parse(template), ctx)


# --- default content ----------------------------------------------------
# Written to sound like a person who has sat in the chair. The words that give
# a generated therapy site away are "journey", "safe space", "empower",
# "holistic", "thrive" and "reach out" - none of them appear below.

DEFAULT_HELPS_WITH = [
    "Anxiety and panic", "Depression and low mood", "Bereavement and loss",
    "Relationship difficulties", "Work stress and burnout",
    "Confidence and self-esteem", "Anger", "Trauma and its aftermath",
    "Separation and divorce", "Life not going the way you expected",
]

DEFAULTS: dict[str, Any] = {
    "role": "Counsellor and Psychotherapist",
    "credentials": "MIACP",
    "how_i_work_title": "There's no script to it",
    "how_i_work": [
        "The first session is mostly you talking and me listening. I'll ask "
        "what brought you here and what you'd like to be different. You don't "
        "need to have it worked out beforehand — most people don't, and "
        "saying it out loud for the first time is usually the hardest part.",
        "After that we go at whatever pace suits you. I won't hand you "
        "homework or a programme to work through. Some weeks we'll talk about "
        "what happened that week; other weeks we'll go further back. "
        "[Two or three lines here about how you actually work — "
        "person-centred, CBT, integrative, whatever it is. This is the part "
        "people read twice before they ring.]",
        "If after a few sessions you don't think I'm the right fit for you, "
        "say so and I'll help you find someone who is. That happens, and it "
        "isn't a failure on anyone's part.",
    ],
    "helps_with": DEFAULT_HELPS_WITH,
    "helps_with_note": "This isn't a checklist. Plenty of people arrive "
                       "without a word for what's wrong, and that is a "
                       "perfectly good place to start.",
    "session_length": "50 minutes, at the same time each week.",
    "fee": "€[00] per session. [If you hold a few lower-cost places for "
           "students or people out of work, say so here — it is one of "
           "the most-read lines on any therapist's site.]",
    "online_sessions": "[Yes or no — and if yes, say whether that's video "
                       "or phone, and whether the fee is the same.]",
    "availability": "[Are you taking new clients at the moment? Say it plainly, "
                    "and give a rough idea of the wait if there is one.]",
    "cancellation": "[Most practices ask for 24 or 48 hours' notice. Putting "
                    "your policy here means it never becomes an awkward "
                    "conversation later.]",
    "contact_paragraphs": [
        "Ringing is the quickest way. If phoning a stranger feels like more "
        "than you can do today, email is completely fine — a lot of "
        "people start that way.",
        "I'll normally come back to you within [one working day]. If I don't "
        "pick up I'm most likely in a session, so leave a message and I'll "
        "ring you back.",
        "There's nothing you need to prepare, and getting in touch doesn't "
        "commit you to anything.",
    ],
    "accreditation": "Member of the Irish Association for Counselling and "
                     "Psychotherapy (MIACP). I work in accordance with the "
                     "IACP Code of Ethics and Practice and attend regular "
                     "supervision. [Add your accreditation number.]",
    "confidentiality": "What you say in the room stays between us. The "
                       "exceptions are the ones the law requires — a risk "
                       "of serious harm to you or someone else — and "
                       "wherever possible I would talk to you about it first.",
    "privacy_note": "This site sets no cookies and collects no analytics.",
    "photo": "",
    "photo_caption": "",
    "eircode": "",
    "canonical": "",
    "draft": False,
    "robots": "index, follow",
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or "therapist"


def content_for(name: str, town: str = "", county: str = "", email: str = "",
                phone: str = "", helps_with: list[str] | None = None,
                draft: bool = True, **overrides: Any) -> dict[str, Any]:
    """Build page content, filling only what we actually know about them."""
    town = town or county or "[your town]"
    county = county or "[county]"
    first = (name or "").split()[0] if name else "your"

    ctx: dict[str, Any] = dict(DEFAULTS)
    ctx.update({
        "name": name,
        "town": town,
        "county": county,
        "email": email,
        "phone": phone,
        "phone_tel": _tel_href(phone),
        "phone_display": format_phone(phone),
        "year": _dt.date.today().year,
        "address_lines": ["[Street address]"],
        "where": f"{town}, County {county}. [Add the street address and "
                 f"Eircode, and say whether there's parking or how far it is "
                 f"from the bus.]",
        "lead": f"I'm a counsellor and psychotherapist working in {town}. "
                f"I see adults one to one, usually weekly, for as long as it "
                f"stays useful.",
        "intro_paragraphs": [
            "Most people get in touch after putting it off for a good while. "
            "That's normal, and however long it's taken doesn't matter now.",
            f"[A short paragraph in your own words about who you are and how "
            f"you came to this work. Two or three sentences is plenty — "
            f"people are deciding whether they'd feel alright sitting in a "
            f"room with you, not reading a CV.]",
        ],
        "draft": draft,
        "robots": "noindex, nofollow" if draft else "index, follow",
    })
    if helps_with:
        ctx["helps_with"] = helps_with
    ctx["has_helps_with"] = bool(ctx.get("helps_with"))
    ctx["meta_description"] = (
        f"{name}{', ' + ctx['credentials'] if ctx.get('credentials') else ''} "
        f"— counsellor and psychotherapist in {town}, County {county}. "
        f"Weekly one-to-one sessions for adults."
    )
    ctx.update(overrides)
    return ctx


def format_phone(phone: str) -> str:
    """0871234567 -> 087 123 4567, the way it is written in Ireland."""
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return ""
    if digits.startswith("08") and len(digits) == 10:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    if digits.startswith("01") and len(digits) == 9:
        return f"{digits[:2]} {digits[2:5]} {digits[5:]}"
    if len(digits) == 10:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    if len(digits) == 9:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    return phone


def _tel_href(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return ""
    return "+353" + digits[1:] if digits.startswith("0") else digits


def content_for_row(row: dict[str, str], draft: bool = True) -> dict[str, Any]:
    """Build page content from one row of the leads CSV."""
    specialisms = [x.strip() for x in (row.get("specialisms") or "").split(";")
                   if x.strip()]
    overrides: dict[str, Any] = {}
    if row.get("accreditation"):
        overrides["credentials"] = row["accreditation"]
    return content_for(
        name=row.get("name", ""),
        town=row.get("town", ""),
        county=row.get("county", ""),
        email=row.get("email", ""),
        phone=row.get("phone", ""),
        helps_with=specialisms or None,
        draft=draft,
        **overrides,
    )


def build(ctx: dict[str, Any], out_dir: str | Path,
          template_dir: str | Path = SITE_DIR) -> Path:
    template_dir = Path(template_dir)
    out = Path(out_dir)
    ctx = dict(ctx)
    ctx.setdefault("has_helps_with", bool(ctx.get("helps_with")))
    out.mkdir(parents=True, exist_ok=True)
    html_out = render((template_dir / "template.html").read_text(encoding="utf-8"), ctx)
    (out / "index.html").write_text(html_out, encoding="utf-8")
    shutil.copy(template_dir / "styles.css", out / "styles.css")
    (out / "content.json").write_text(
        json.dumps(ctx, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return out / "index.html"
