"""People and organisations nobody listed, recognised by the shape of the text: a first name followed by
a surname, a name after a title, a speaker at the start of a line, a name with a legal form. At the
strict level any run of capitalised words counts, a person when it opens with a first name and an
organisation otherwise. No model and no network: this runs in the process."""

from __future__ import annotations

import re
from collections.abc import Iterator

from pseudonym.kinds import Kind
from pseudonym.language import CAP, Found, Profile

FIRST = re.compile(rf"\b{CAP}\b")
WORDS = re.compile(r"[^\W\d_]+")


def people(text: str, profile: Profile, strict: bool = False, never: frozenset[str] = frozenset()) -> Iterator[Found]:
    """People found by shape. Each match covers the whole name as written. A word of a `never` name
    (casefolded) ends no name, so "Anna Bakkerij Zoet" does not take the company along."""
    names = profile.first_names
    stop = profile.not_names | {w.capitalize() for n in never for w in n.split()}

    def ends_well(name: str) -> bool:
        words = [w for w in WORDS.findall(name) if w[:1].isupper()]
        return bool(words) and words[-1] not in stop

    if profile.after_title is not None:
        for m in profile.after_title.finditer(text):
            if ends_well(m.group(1)):
                yield Found(m.start(1), m.end(1), Kind.PERSON, m.group(1))
    for m in FIRST.finditer(text):
        # every capitalised word is tried as a first name, so "See Pieter Bakker" still finds Pieter Bakker
        if m.group() not in names:
            continue
        rest = profile.rest_of_name.match(text, m.end())
        if rest and ends_well(text[m.start() : rest.end()]):
            yield Found(m.start(), rest.end(), Kind.PERSON, text[m.start() : rest.end()])
    for m in profile.speaker.finditer(text):
        if m.group(1).split()[0] in names:
            yield Found(m.start(1), m.end(1), Kind.PERSON, m.group(1))
    if strict:
        for m in profile.run.finditer(text):
            if ends_well(m.group()):
                kind = Kind.PERSON if m.group().split()[0] in names else Kind.ORG
                yield Found(m.start(), m.end(), kind, m.group())


def organisations(text: str, profile: Profile) -> Iterator[Found]:
    """Organisations recognisable by their legal form ("Jansen B.V.") or the word that opens their name
    ("Stichting Het Park")."""
    for pattern in (profile.org_suffix, profile.org_prefix):
        if pattern is not None:
            for m in pattern.finditer(text):
                yield Found(m.start(), m.end(), Kind.ORG, m.group())


def hosts(text: str, profile: Profile, own: frozenset[str] = frozenset()) -> Iterator[Found]:
    """Host names, except public infrastructure and your own."""
    for m in profile.host.finditer(text):
        host = m.group().lower()
        if not _listed(host, own) and not _listed(host, profile.public_hosts):
            yield Found(m.start(), m.end(), Kind.HOST, m.group())


def identifiers(text: str, profile: Profile) -> Iterator[Found]:
    for rule in profile.rules:
        yield from rule.find(text)


def _listed(host: str, known: frozenset[str]) -> bool:
    return any(host == k or host.endswith(f".{k}") for k in known)
