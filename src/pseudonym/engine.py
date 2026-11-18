"""Replacing identifiers with placeholders, and putting them back.

A placeholder looks like `[PERSON_K3J9QX]`. It is derived from the value with a key only you hold, so
the same value is the same placeholder in every message of every conversation, and nothing about
order or count shows. A conversation remembers what each placeholder it gave out stands for, which is
all restoring needs: a model can only repeat a placeholder it was given. One it invents or mangles
beyond recognition is shown as unknown rather than guessed.

The steps run in a fixed order on the text outside placeholders already made: secrets are removed,
then contact details and numbers are replaced, then host names, then names you know, organisations by
their legal form and people found by the shape of the text, and at the strict level every run of
capitalised words.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from itertools import chain

from pseudonym import names
from pseudonym.kinds import KINDS, REDACTED, Kind
from pseudonym.known import KnownName, Matcher, surname, surname_forms
from pseudonym.language import Found, Language, Profile
from pseudonym.redact import redact_secrets

LEVELS = ("off", "identifiers", "strict")
CODE_LENGTH = 6
CODE = "[A-Z2-7]"
_KINDS = "|".join(sorted(KINDS, key=len, reverse=True))
# as the model may write a kind back: any case, a space for an underscore
_KINDS_WRITTEN = "|".join(k.replace("_", "[_ ]") for k in sorted(KINDS, key=len, reverse=True))
PLACEHOLDER = re.compile(rf"\[(?:{_KINDS})_{CODE}{{{CODE_LENGTH}}}\]|\[{REDACTED}\]")
WRITTEN_BACK = re.compile(rf"\[?\b(?P<kind>{_KINDS_WRITTEN})[_ ](?P<code>{CODE}{{{CODE_LENGTH}}})\b\]?", re.IGNORECASE)
SEPARATED = (Kind.PHONE, Kind.IBAN, Kind.CARD, Kind.NATIONAL_ID, Kind.COMPANY_ID, Kind.VAT_ID, Kind.POSTCODE)


def normalise(kind: str, value: str, profile: Profile | None = None) -> str:
    """The value as compared: "+31 6-1234 5678" and "0612345678" are the same number."""
    v = " ".join(value.split()).casefold()
    if kind in SEPARATED:
        v = re.sub(r"[\s\-.()/]", "", v)
    if kind == Kind.PHONE:
        for code, trunk in (profile or Profile.of()).phone_prefixes:
            for intl in (f"+{code}", f"00{code}"):
                if v.startswith(intl):
                    rest = v[len(intl) :]
                    return trunk + (rest[len(trunk) :] if trunk and rest.startswith(trunk) else rest)
    return v


def placeholder(key: bytes, kind: str, value: str, profile: Profile | None = None) -> str:
    digest = hmac.new(key, f"{kind}|{normalise(kind, value, profile)}".encode(), hashlib.sha256).digest()
    return f"[{kind}_{base64.b32encode(digest).decode()[:CODE_LENGTH]}]"


Finder = Callable[[str], Iterable[Found]]


@dataclass
class Pseudonymiser:
    key: bytes
    # The languages your text is written in, as codes or Language objects; `available()` lists them.
    # Each adds names and rules, and one language's ordinary words keep another's same-spelled first
    # names ("Mark", "Frank") from opening a name, so name only the languages you need.
    languages: Iterable[str | Language]
    level: str = "identifiers"
    matcher: Matcher | None = None
    own_hosts: frozenset[str] = frozenset()
    # Names that are never replaced, however they are found: your own company, the assistant.
    never: frozenset[str] = frozenset()
    # What each placeholder stands for: placeholder -> [kind, value]. Kept per conversation.
    mapping: dict[str, list[str]] = field(default_factory=dict)
    replaced: Counter[str] = field(default_factory=Counter)
    profile: Profile = field(init=False, repr=False)
    _recognised: dict[str, KnownName] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}, not {self.level!r}")
        self.profile = Profile.of(tuple(self.languages))
        self.never = frozenset(" ".join(n.split()).casefold() for n in self.never)

    def text(self, value: str) -> str:
        """The text as the provider may see it."""
        if self.level == "off" or not value:
            return value
        p = self.profile
        result, removed = redact_secrets(value)  # in every language: a secret is never worth missing
        if removed:
            self.replaced[REDACTED] += removed
        result = self._replace(result, lambda t: names.identifiers(t, p))
        result = self._replace(result, lambda t: names.hosts(t, p, self.own_hosts))
        # known names, organisations by legal form and people by shape in one pass, so at one spot the
        # longest match wins: "Karin van Dijk" as one unknown person, not a known Karin plus a known van Dijk
        strict = self.level == "strict"
        result = self._replace(
            result,
            lambda t: chain(self.matcher.find(t) if self.matcher else (), names.organisations(t, p), names.people(t, p, strict=strict, never=self.never)),
            remember=True,
        )
        if self._recognised:
            # the same names again, where the shape did not give them away (a surname alone, lower case)
            seen = Matcher.build(self._recognised.values())
            result = self._replace(result, lambda t: chain(seen.find(t), seen.find_single(t)))
        if self.matcher is not None:
            # a known first name or surname on its own, last: a name in the text comes first
            result = self._replace(result, self.matcher.find_single)
        return result

    def restore(self, value: str) -> str:
        """The model's text with the real values back, however it wrote the placeholders."""
        if not value:
            return value

        def back(m: re.Match[str]) -> str:
            kind = m.group("kind").upper().replace(" ", "_")
            entry = self.mapping.get(f"[{kind}_{m.group('code').upper()}]")
            return entry[1] if entry else self.profile.unknown

        return WRITTEN_BACK.sub(back, value)

    def summary(self) -> dict[str, int]:
        """How many of each kind were replaced. `profile.labels` names them for people."""
        return {k: v for k, v in sorted(self.replaced.items()) if v}

    # ------------------------------------------------------------------ internals
    def _replace(self, text: str, finder: Finder, remember: bool = False) -> str:
        out: list[str] = []
        pos = 0
        for protected in self._segments(text):
            out.append(self._replace_free(text[pos : protected[0]], finder, remember))
            out.append(text[protected[0] : protected[1]])
            pos = protected[1]
        out.append(self._replace_free(text[pos:], finder, remember))
        return "".join(out)

    @staticmethod
    def _segments(text: str) -> Iterator[tuple[int, int]]:
        for m in PLACEHOLDER.finditer(text):
            yield m.start(), m.end()

    def _replace_free(self, text: str, finder: Finder, remember: bool) -> str:
        if not text:
            return text
        found = sorted(finder(text), key=lambda f: (f.start, -(f.end - f.start)))
        out: list[str] = []
        pos = 0
        for f in found:
            if f.start < pos or " ".join(f.value.split()).casefold() in self.never:
                continue
            ph = placeholder(self.key, f.kind, f.value, self.profile)
            self.mapping.setdefault(ph, [f.kind, f.value])
            self.replaced[f.kind] += 1
            if remember:
                self._remember(f)
            out.append(text[pos : f.start])
            out.append(ph)
            pos = f.end
        out.append(text[pos:])
        return "".join(out)

    def _remember(self, f: Found) -> None:
        """A name found once is a name wherever else it appears, and so are its surname and first name."""
        key = f.value.casefold()
        if key in self._recognised:
            return
        self._recognised[key] = KnownName(f.value, f.kind, f.value, any_case=True)
        if f.kind == Kind.ORG and self.profile.legal_suffix is not None:
            short = self.profile.legal_suffix.sub("", f.value).strip(" ,")
            if short != f.value and len(short) >= 4:
                self._recognised.setdefault(short.casefold(), KnownName(short, Kind.ORG, f.value, any_case=True))
        if f.kind == Kind.PERSON:
            words = names.WORDS.findall(f.value)
            last = surname(words[1:], self.profile) if len(words) > 1 else None
            if last:
                for form in surname_forms(last, f.value):
                    self._recognised.setdefault(form.text + "|s", form)
            if len(words) > 1 and words[0] in self.profile.first_names:
                self._recognised.setdefault(words[0] + "|s", KnownName(words[0], Kind.PERSON, f.value, any_case=False))


class StreamRestorer:
    """Restores placeholders in a stream of text chunks. A placeholder may arrive split over chunks, so
    the tail that could still be the start of one is held back until the next chunk decides."""

    REACH = max(map(len, KINDS)) + CODE_LENGTH + 3  # "[", "_", "]"

    def __init__(self, pz: Pseudonymiser) -> None:
        self._pz = pz
        self._buf = ""

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        cut = self._safe_cut(self._buf)
        out, self._buf = self._buf[:cut], self._buf[cut:]
        return self._pz.restore(out)

    def finish(self) -> str:
        out, self._buf = self._buf, ""
        return self._pz.restore(out)

    @classmethod
    def _safe_cut(cls, buf: str) -> int:
        """Where the held-back tail starts: the earliest spot near the end that may open a placeholder."""
        for i in range(max(0, len(buf) - cls.REACH), len(buf)):
            if (buf[i] == "[" or (buf[i].isalpha() and (i == 0 or not buf[i - 1].isalnum()))) and cls._may_open(buf[i:]):
                return i
        return len(buf)

    @staticmethod
    def _may_open(tail: str) -> bool:
        s = tail.removeprefix("[").upper().replace(" ", "_")
        if not s:
            return True
        for kind in KINDS:
            if kind.startswith(s):
                return True
            if s.startswith(kind + "_"):
                code = s[len(kind) + 1 :]
                if len(code) <= CODE_LENGTH and re.fullmatch(f"{CODE}*", code):
                    return True
        return False
