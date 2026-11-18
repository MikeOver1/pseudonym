"""Names the app knows: customers, contact persons, staff and suppliers, and the forms a text writes
them in. The pseudonymiser replaces them wherever they appear, however they are capitalised."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from pseudonym_nl.patterns import Found, Kind

# Values that name no one: what the app's free-text customer fields hold besides customers.
STOP = frozenset(
    [
        "test",
        "onbekend",
        "nvt",
        "n.v.t.",
        "divers",
        "diversen",
        "intern",
        "particulier",
        "prive",
        "privé",
        "klant",
        "gast",
        "gasten",
        "relatie",
        "bedrijf",
        "bedrijven",
        "overig",
        "overige",
        "geen",
        "nog",
        "onbekend",
        "nader",
        "te",
        "bepalen",
        "ntb",
        "tbd",
        "familie",
        "fam",
        "bruiloft",
        "verjaardag",
        "feest",
        "diner",
        "lunch",
        "borrel",
        "receptie",
        "catering",
        "event",
        "evenement",
    ]
)
LEGAL_SUFFIX = re.compile(r"\s*(?:,\s*)?\b(?:B\.?V\.?|N\.?V\.?|V\.?O\.?F\.?|C\.?V\.?|Holding|Groep|Group|GmbH|Ltd\.?|Inc\.?)\s*$", re.IGNORECASE)
PARTICLES = frozenset(["van", "de", "der", "den", "te", "ter", "ten", "het", "'t", "v.", "d.", "in", "op", "aan", "bij", "tot", "le", "la", "di", "da", "del", "von", "el", "al", "bin", "ibn"])
WORD = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*")


@dataclass(frozen=True)
class KnownName:
    text: str  # as it may be written
    kind: str
    value: str  # the real value it stands for
    any_case: bool = True
    whole: bool = True  # the full name; False for a first name or surname on its own


def _letters(s: str) -> int:
    return sum(c.isalpha() for c in s)


def people(names: Iterable[str]) -> list[KnownName]:
    """Known people: full name; surname alone and first name alone when they point to one person."""
    full = sorted({" ".join(n.split()) for n in names if n and _letters(n) >= 4 and n.strip().casefold() not in STOP})
    firsts: Counter[str] = Counter()
    lasts: Counter[str] = Counter()
    parts: dict[str, tuple[str | None, str | None]] = {}
    for name in full:
        words = WORD.findall(name)
        if not words:
            continue
        first = words[0] if words[0][:1].isupper() and len(words) > 1 else None
        last = surname(words[1:] if first else words)
        parts[name] = (first, last)
        if first:
            firsts[first.casefold()] += 1
        if last:
            lasts[last.casefold()] += 1
    out: list[KnownName] = []
    for name in full:
        out.append(KnownName(name, Kind.PERSON, name, any_case=True))
        first, last = parts.get(name, (None, None))
        if first and firsts[first.casefold()] == 1 and len(first) >= 3 and first.casefold() not in STOP:
            out.append(KnownName(first, Kind.PERSON, name, any_case=False, whole=False))
        if last and lasts[last.casefold()] == 1 and last.casefold() not in STOP:
            out.extend(surname_forms(last, name))
    return out


def surname(words: list[str]) -> str | None:
    """The surname with its particles ("van Dijk"), when its last word is a real one of four letters."""
    rest = [w for w in words if w.casefold() not in PARTICLES]
    if not rest or len(rest[-1]) < 4 or not rest[-1][:1].isupper():
        return None
    particles = [w.lower() for w in words[: words.index(rest[-1])] if w.casefold() in PARTICLES]
    return " ".join([*particles, rest[-1]])


def surname_forms(last: str, value: str) -> list[KnownName]:
    """A surname as written mid-sentence ("van Dijk") and opening one ("Van Dijk")."""
    forms = {last, last[:1].upper() + last[1:]}
    return [KnownName(f, Kind.PERSON, value, any_case=False, whole=False) for f in sorted(forms)]


def organisations(names: Iterable[str], never: Iterable[str] = ()) -> list[KnownName]:
    """Known organisations: the name, the name without its legal form, and a slug form in addresses."""
    skip = {n.casefold() for n in never}
    out: list[KnownName] = []
    seen: set[str] = set()
    for raw in names:
        name = " ".join((raw or "").split())
        key = name.casefold()
        if not name or _letters(name) < 4 or key in STOP or key in skip or key in seen or name == name.lower():
            continue
        seen.add(key)
        out.append(KnownName(name, Kind.ORG, name, any_case=True))
        short = LEGAL_SUFFIX.sub("", name).strip(" ,")
        if short and short != name and _letters(short) >= 4 and short.casefold() not in STOP and short.casefold() not in skip:
            out.append(KnownName(short, Kind.ORG, name, any_case=True))
        slug = re.sub(r"[^a-z0-9]", "", short.casefold())
        if _letters(slug) >= 8:
            out.append(KnownName(slug, Kind.ORG, name, any_case=True))
    return out


class Matcher:
    """One compiled search over every known form, longest form first. Whole names are searched by
    `find`, a first name or surname on its own by `find_single`: those come last, after a full name in
    the text had its chance to claim the word."""

    def __init__(self, patterns: list[re.Pattern[str]], lookup: dict[str, KnownName], single: Matcher | None = None) -> None:
        self._patterns = patterns
        self._lookup = lookup
        self.single = single

    @classmethod
    def build(cls, entries: Iterable[KnownName], _whole: bool = True) -> Matcher:
        entries = list(entries)
        single = cls.build([e for e in entries if not e.whole], _whole=False) if _whole and any(not e.whole for e in entries) else None
        lookup: dict[str, KnownName] = {}
        groups: dict[bool, list[str]] = {True: [], False: []}
        for e in entries:
            if not e.text.strip() or e.whole != _whole:
                continue
            key = cls._key(e.text, e.any_case)
            if key in lookup:
                continue
            lookup[key] = e
            groups[e.any_case].append(e.text)
        patterns = []
        for any_case, texts in groups.items():
            if not texts:
                continue
            alts = "|".join(r"\s+".join(re.escape(w) for w in t.split()) for t in sorted(texts, key=len, reverse=True))
            flags = re.IGNORECASE if any_case else 0
            patterns.append(re.compile(rf"(?<![^\W\d_])(?:{alts})(?![^\W\d_])", flags))
        return cls(patterns, lookup, single)

    @staticmethod
    def _key(text: str, any_case: bool) -> str:
        t = " ".join(text.split())
        return (t.casefold() if any_case else t) + ("|i" if any_case else "|s")

    def find(self, text: str) -> Iterator[Found]:
        for pattern in self._patterns:
            any_case = bool(pattern.flags & re.IGNORECASE)
            for m in pattern.finditer(text):
                entry = self._lookup.get(self._key(m.group(), any_case))
                if entry is None and not any_case:
                    entry = self._lookup.get(self._key(m.group(), True))
                if entry is not None:
                    yield Found(m.start(), m.end(), entry.kind, entry.value)

    def find_single(self, text: str) -> Iterator[Found]:
        if self.single is not None:
            yield from self.single.find(text)

    @property
    def size(self) -> int:
        return len(self._lookup) + (self.single.size if self.single else 0)
