"""Languages: everything detection needs to know about one language and the countries that write it.

A `Language` is plain data: first names, titles, surname particles, legal forms, the words around a
number that say what it is, and `Rule`s for the identifiers its countries use. The engine merges the
active languages with the language-neutral `CORE` into a `Profile`, compiled once per combination.

Identifiers are per country, names per language. A pack is named after a language and carries the
identifiers of the countries it is written for: `nl` holds Dutch numbers, `en` British and American
ones. A country that shares a language with another builds on its pack (see CONTRIBUTING.md), so
Flemish names come from `nl` while Belgian numbers live in an `nl-BE` pack.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from functools import cache
from importlib import resources

from pseudonym.kinds import LABELS


@dataclass(frozen=True)
class Found:
    start: int
    end: int
    kind: str
    value: str


@dataclass(frozen=True)
class Rule:
    """An identifier recognised by its shape. `check` verifies a check digit or range, so an arbitrary
    number is not taken for one; `context` must occur in the `reach` characters before the match, for
    numbers only recognisable by what the text calls them. Keep repetitions in `pattern` bounded
    (`{0,5}`, not `*`): a pattern that can backtrack over a whole text is quadratic."""

    kind: str
    pattern: re.Pattern[str]
    check: Callable[[str], bool] | None = None
    context: re.Pattern[str] | None = None
    reach: int = 60

    def find(self, text: str) -> Iterator[Found]:
        for m in self.pattern.finditer(text):
            if self.context is not None and not self.context.search(text, max(0, m.start() - self.reach), m.start()):
                continue
            if self.check is not None and not self.check(m.group()):
                continue
            yield Found(m.start(), m.end(), self.kind, m.group())


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    # names
    first_names: frozenset[str] = frozenset()  # capitalised, as written
    # ordinary capitalised words of this language that are first names elsewhere ("Will", "Mark"):
    # while this language is active they open no name found by shape
    not_first_names: frozenset[str] = frozenset()
    particles: frozenset[str] = frozenset()  # lower-case surname particles: "van", "de"
    titles: tuple[str, ...] = ()  # regex fragments, matched case-insensitively: r"mrs?\.?", "de heer"
    not_names: frozenset[str] = frozenset()  # capitalised words that end no name: months, weekdays, places
    empty_values: frozenset[str] = frozenset()  # lower-case values in name fields that name no one: "unknown"
    # organisations
    org_suffixes: tuple[str, ...] = ()  # regex fragments for legal forms after a name: r"B\.?V\.?"
    org_prefixes: tuple[str, ...] = ()  # words that open an organisation's name: "Stichting"
    org_joiners: tuple[str, ...] = ()  # lower-case words inside an organisation's name: "and", "of"
    # identifiers
    rules: tuple[Rule, ...] = ()
    phone_prefixes: tuple[tuple[str, str], ...] = ()  # (country code, trunk prefix): ("31", "0")
    tlds: frozenset[str] = frozenset()  # top-level domains a host name may end in
    public_hosts: frozenset[str] = frozenset()  # hosts that identify no one: government, public services
    # secrets
    password_labels: tuple[str, ...] = ()  # regex fragments: "wachtwoord"
    login_words: tuple[str, ...] = ()  # regex fragments that say a login follows: r"log (?:je|u) in"
    # presentation and tests
    labels: Mapping[str, str] = field(default_factory=dict, hash=False, compare=False)  # kind -> human label
    unknown: str = ""  # what a placeholder the model invented reads back as: "[unknown]"
    found: tuple[tuple[str, str], ...] = ()  # (text, kind): each text holds one identifier of that kind
    left_alone: tuple[str, ...] = ()  # texts that only look like they hold one


def first_names(package: str, filename: str = "first_names.txt") -> frozenset[str]:
    """A name list next to a language module: whitespace-separated, `#` starts a comment line."""
    text = resources.files(package).joinpath(filename).read_text(encoding="utf-8")
    return frozenset(w for line in text.splitlines() if not line.lstrip().startswith("#") for w in line.split())


# ---------------------------------------------------------------- registry

_registry: dict[str, Language] = {}


def register(language: Language) -> Language:
    """Make a language available by its code. Packs outside this package call this on import."""
    _registry[language.code] = language
    return language


def get(code: str) -> Language:
    try:
        return _registry[code]
    except KeyError:
        raise KeyError(f"No language {code!r}; available: {', '.join(sorted(_registry))}") from None


def available() -> tuple[str, ...]:
    return tuple(sorted(_registry))


def resolve(languages: Iterable[str | Language] | None) -> tuple[Language, ...]:
    """Language objects for codes or objects; None means every registered language."""
    if languages is None:
        return tuple(_registry[c] for c in available())
    out = tuple(get(x) if isinstance(x, str) else x for x in languages)
    if not out:
        raise ValueError("At least one language is needed.")
    return out


# ---------------------------------------------------------------- merged and compiled


def _alternation(fragments: Iterable[str]) -> str:
    return "|".join(sorted(set(fragments), key=len, reverse=True))


@dataclass(frozen=True, eq=False)
class Profile:
    """The active languages merged with CORE and compiled."""

    languages: tuple[Language, ...]
    first_names: frozenset[str]
    particles: frozenset[str]
    not_names: frozenset[str]
    empty_values: frozenset[str]
    rules: tuple[Rule, ...]
    phone_prefixes: tuple[tuple[str, str], ...]
    public_hosts: frozenset[str]
    labels: Mapping[str, str]
    unknown: str
    after_title: re.Pattern[str] | None
    rest_of_name: re.Pattern[str]
    speaker: re.Pattern[str]
    run: re.Pattern[str]
    org_suffix: re.Pattern[str] | None
    org_prefix: re.Pattern[str] | None
    legal_suffix: re.Pattern[str] | None
    host: re.Pattern[str]
    labelled_password: re.Pattern[str]
    quoted_password: re.Pattern[str]
    login_context: re.Pattern[str]

    @classmethod
    def of(cls, languages: Iterable[str | Language] | None = None) -> Profile:
        return _compiled(resolve(languages))


# A capitalised word as names write it: Anna, O'Brien, McDonald, Smith-Jones
SP = r"[^\S\n]+"  # the space between the words of a name, which never runs over a line break
CAP = r"[A-ZÀ-Þ](?:['’][A-ZÀ-Þ])?[a-zà-ÿ]+(?:[A-ZÀ-Þ][a-zà-ÿ]+)?(?:-[A-ZÀ-Þ]?[a-zà-ÿ]+)*"
INITIALS = r"(?:[A-Z]\.[^\S\n]*){1,4}"


@cache
def _compiled(languages: tuple[Language, ...]) -> Profile:
    from pseudonym.core import CORE  # the core module imports this one

    every = (CORE, *languages)
    union = lambda attr: frozenset().union(*(getattr(lang, attr) for lang in every))  # noqa: E731
    joined = lambda attr: tuple(x for lang in every for x in getattr(lang, attr))  # noqa: E731

    particle = rf"(?:{_alternation(re.escape(p) for p in union('particles'))})"
    surname = rf"(?:{particle}{SP}){{0,3}}{CAP}(?:{SP}{CAP})?"
    titles = joined("titles")
    suffixes, prefixes = joined("org_suffixes"), joined("org_prefixes")
    joiners = _alternation(re.escape(j) for j in joined("org_joiners"))
    org_word = r"[A-Z][\w&'’.-]*"
    labels = dict(LABELS)
    for lang in reversed(languages):  # the first language names things
        labels.update(lang.labels)
    return Profile(
        languages=languages,
        first_names=union("first_names") - union("not_first_names"),
        particles=union("particles"),
        not_names=union("not_names"),
        empty_values=union("empty_values"),
        rules=joined("rules"),
        phone_prefixes=joined("phone_prefixes"),
        public_hosts=union("public_hosts"),
        labels=labels,
        unknown=next((lang.unknown for lang in languages if lang.unknown), "[unknown]"),
        after_title=re.compile(rf"(?:^|(?<![\w.]))(?i:{_alternation(titles)}){SP}((?:{INITIALS})?{surname})") if titles else None,
        rest_of_name=re.compile(rf"(?:{SP}{INITIALS})?(?:{SP}{particle}){{0,3}}{SP}{CAP}(?:{SP}{CAP})?"),
        # a speaker opens a line, perhaps as a list item: "Anna de Vries: ...", "- Rachel: ..."
        speaker=re.compile(rf"(?m)^[ \t]*(?:[-*•][ \t]+)?({CAP}(?:{SP}{particle}){{0,3}}(?:{SP}{CAP}){{0,2}}):\s"),
        run=re.compile(rf"\b{CAP}(?:{SP}(?:{CAP}|{particle}|&)){{0,7}}{SP}{CAP}\b"),
        # at most eight words: a name is never longer, and the bound keeps long capitalised text linear
        org_suffix=re.compile(rf"\b{org_word}(?:{SP}(?:{org_word}|{joiners})){{0,7}}{SP}(?:{_alternation(suffixes)})(?![\w.])") if suffixes else None,
        org_prefix=re.compile(rf"\b(?:{_alternation(re.escape(p) for p in prefixes)}){SP}{org_word}(?:{SP}(?:{org_word}|{joiners})){{0,7}}") if prefixes else None,
        legal_suffix=re.compile(rf"\s*(?:,\s*)?\b(?:{_alternation(suffixes)})\s*$", re.IGNORECASE) if suffixes else None,
        host=re.compile(rf"(?i)(?<![\w@.-])(?:[a-z0-9](?:[a-z0-9-]{{0,61}}[a-z0-9])?\.){{1,10}}(?:{_alternation(union('tlds'))})(?![\w-])"),
        labelled_password=re.compile(rf"(?i)\b({_alternation(joined('password_labels'))})(\s*[:=]\s*)(?!\[REDACTED\])([^\s'\"]{{6,}})"),
        quoted_password=re.compile(rf"(?i)\b({_alternation(joined('password_labels'))})(\s*[:=]\s*)(['\"])(?!\[REDACTED\])([^'\"\n]+)\3"),
        login_context=re.compile(rf"(?i)\b(?:{_alternation(joined('login_words'))})\b"),
    )
