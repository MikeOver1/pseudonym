"""People and organisations the app does not know, recognised by the shape of the text: a first name
from the list followed by a surname, a name after a title, a speaker at the start of a line. At the
strict level any run of capitalised words counts, a person when it opens with a first name and an
organisation otherwise. No model and no network: this runs in the process."""

from __future__ import annotations

import re
from collections.abc import Iterator
from functools import cache
from pathlib import Path

from pseudonym_nl.patterns import Found, Kind

CAP = r"[A-ZÀ-Þ][a-zà-ÿ]+(?:-[A-ZÀ-Þ]?[a-zà-ÿ]+)*"
PARTICLE = r"(?:van|de|der|den|te|ter|ten|'t|v\.|d\.|le|la|di|da|del|von|el|al|bin|ibn)"
INITIALS = r"(?:[A-Z]\.\s*)+"
SURNAME = rf"(?:{PARTICLE}\s+)*{CAP}(?:\s+{CAP})?"
TITLE = r"(?i:dhr|mevr|mw|mr|mrs|ms|drs|ir|ing|dr)\.?|(?i:de heer|mevrouw|meneer|familie|fam\.|t\.a\.v\.)"
AFTER_TITLE = re.compile(rf"(?:^|(?<![\w.]))(?:{TITLE})\s+((?:{INITIALS})?{SURNAME})")
FIRST = re.compile(rf"\b{CAP}\b")
# What may follow a first name: initials, particles, one or two surname words.
REST_OF_NAME = re.compile(rf"(?:\s+{INITIALS})?(?:\s+{PARTICLE})*\s+{CAP}(?:\s+{CAP})?")
SPEAKER = re.compile(rf"(?m)^\s*({CAP}(?:\s+{PARTICLE})*(?:\s+{CAP}){{0,2}}):\s")
RUN = re.compile(rf"\b{CAP}(?:\s+(?:{CAP}|{PARTICLE}|&))*\s+{CAP}\b")
# Capitalised words that end no name: time words, places, generic nouns in headings.
NOT_SURNAME = frozenset(
    [
        "Januari",
        "Februari",
        "Maart",
        "April",
        "Mei",
        "Juni",
        "Juli",
        "Augustus",
        "September",
        "Oktober",
        "November",
        "December",
        "Maandag",
        "Dinsdag",
        "Woensdag",
        "Donderdag",
        "Vrijdag",
        "Zaterdag",
        "Zondag",
        "Claude",
        "Keuken",
        "Catering",
        "Event",
        "Events",
        "Offerte",
        "Voorstel",
        "Menu",
        "Diner",
        "Lunch",
        "Borrel",
        "Bruiloft",
        "Receptie",
        "Nederland",
        "Amsterdam",
        "Rotterdam",
        "Utrecht",
        "Groningen",
        "Arnhem",
        "Nijmegen",
        "Eindhoven",
        "Zwolle",
        "Excel",
        "Word",
        "Teams",
        "Outlook",
        "Google",
        "Drive",
        "Dashboard",
        "Sales",
        "Marketing",
        "Finance",
        "Office",
    ]
)


@cache
def first_names() -> frozenset[str]:
    text = (Path(__file__).parent / "first_names.txt").read_text(encoding="utf-8")
    return frozenset(w for line in text.splitlines() if not line.startswith("#") for w in line.split())


def people(text: str, strict: bool = False, never: frozenset[str] = frozenset()) -> Iterator[Found]:
    """People found by shape. Each match covers the whole name as written. A word of a `never` name
    (casefolded) ends no name, so "Anna Bakkerij Zoet" does not take the company along."""
    names = first_names()
    stop = NOT_SURNAME | {w.capitalize() for n in never for w in n.split()}

    def _ends_well(name: str) -> bool:
        words = [w for w in re.findall(r"[^\W\d_]+", name) if w[:1].isupper()]
        return bool(words) and words[-1] not in stop

    for m in AFTER_TITLE.finditer(text):
        if _ends_well(m.group(1)):
            yield Found(m.start(1), m.end(1), Kind.PERSON, m.group(1))
    for m in FIRST.finditer(text):
        # every capitalised word is tried as a first name, so "Zie Pieter Bakker" still finds Pieter Bakker
        if m.group() not in names:
            continue
        rest = REST_OF_NAME.match(text, m.end())
        if rest and _ends_well(text[m.start() : rest.end()]):
            yield Found(m.start(), rest.end(), Kind.PERSON, text[m.start() : rest.end()])
    for m in SPEAKER.finditer(text):
        first = m.group(1).split()[0]
        if first in names:
            yield Found(m.start(1), m.end(1), Kind.PERSON, m.group(1))
    if strict:
        for m in RUN.finditer(text):
            if not _ends_well(m.group()):
                continue
            first = m.group().split()[0]
            kind = Kind.PERSON if first in names else Kind.ORG
            yield Found(m.start(), m.end(), kind, m.group())
