"""Replacing identifiers with placeholders, and putting them back.

A placeholder looks like `[PERSON_K3J9QX]`. It is derived from the value with a key only the server
holds, so the same value is the same placeholder in every message of every conversation, and nothing
about order or count shows. A conversation remembers what each placeholder it gave out stands for,
which is all restoring needs: a model can only repeat a placeholder it was given. One it invents or
mangles beyond recognition is shown as unknown rather than guessed.

The steps run in a fixed order on the text outside placeholders already made: secrets are removed,
then contact details and numbers are replaced, then host names, then names the app knows (customers,
staff, suppliers), then organisations by their legal form, then people found by the shape of the
text, and at the strict level every run of capitalised words.
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

from pseudonym_nl import names, patterns
from pseudonym_nl.known import KnownName, Matcher, surname, surname_forms
from pseudonym_nl.patterns import Found, Kind

LEVELS = ("off", "identifiers", "strict")
KINDS = "|".join(Kind.ALL)
CODE_LENGTH = 6
PLACEHOLDER = re.compile(rf"\[(?:{KINDS})_[A-Z2-7]{{{CODE_LENGTH}}}\]|\[REDACTED\]")
WRITTEN_BACK = re.compile(rf"\[?\b(?P<kind>{KINDS})[_ ](?P<code>[A-Z2-7]{{{CODE_LENGTH}}})\b\]?", re.IGNORECASE)
UNKNOWN = "[onbekend]"


def normalise(kind: str, value: str) -> str:
    v = " ".join(value.split()).casefold()
    if kind in (Kind.PHONE, Kind.IBAN, Kind.BSN, Kind.KVK, Kind.BTW, Kind.POSTCODE):
        v = re.sub(r"[\s\-.()]", "", v)
        if kind == Kind.PHONE:
            v = re.sub(r"^(?:\+|00)31", "0", v)
    return v


def placeholder(key: bytes, kind: str, value: str) -> str:
    digest = hmac.new(key, f"{kind}|{normalise(kind, value)}".encode(), hashlib.sha256).digest()
    return f"[{kind}_{base64.b32encode(digest).decode()[:CODE_LENGTH]}]"


Finder = Callable[[str], Iterable[Found]]


@dataclass
class Pseudonymiser:
    key: bytes
    level: str = "identifiers"
    matcher: Matcher | None = None
    own_hosts: frozenset[str] = frozenset()
    # Names that are never replaced, however they are found: your own company, the assistant.
    never: frozenset[str] = frozenset()
    # What each placeholder stands for: placeholder -> [kind, value]. Kept per conversation.
    mapping: dict[str, list[str]] = field(default_factory=dict)
    replaced: Counter[str] = field(default_factory=Counter)
    _recognised: dict[str, KnownName] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.never = frozenset(" ".join(n.split()).casefold() for n in self.never)

    def text(self, value: str) -> str:
        """The text as the provider may see it."""
        if self.level == "off" or not value:
            return value
        result, removed = patterns.redact_secrets(value)
        if removed:
            self.replaced["REDACTED"] += removed
        result = self._replace(result, patterns.identifiers)
        result = self._replace(result, lambda t: patterns.hosts(t, self.own_hosts))
        # known names, organisations by legal form and people by shape in one pass, so at one spot the
        # longest match wins: "Karin van Dijk" as one unknown person, not a known Karin plus a known van Dijk
        strict = self.level == "strict"
        result = self._replace(result, lambda t: chain(self.matcher.find(t) if self.matcher else (), patterns.organisations(t), names.people(t, strict=strict, never=self.never)), remember=True)
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
            ph = f"[{m.group('kind').upper()}_{m.group('code').upper()}]"
            entry = self.mapping.get(ph)
            return entry[1] if entry else UNKNOWN

        return WRITTEN_BACK.sub(back, value)

    def summary(self) -> dict[str, int]:
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
            ph = placeholder(self.key, f.kind, f.value)
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
        if f.kind == Kind.PERSON:
            words = re.findall(r"[^\W\d_]+", f.value)
            last = surname(words[1:]) if len(words) > 1 else None
            if last:
                for form in surname_forms(last, f.value):
                    self._recognised.setdefault(form.text + "|s", form)
            if len(words) > 1 and words[0] in names.first_names():
                self._recognised.setdefault(words[0] + "|s", KnownName(words[0], Kind.PERSON, f.value, any_case=False))


class StreamRestorer:
    """Restores placeholders in a stream of text chunks. A placeholder may arrive split over chunks, so
    the tail that could still be the start of one is held back until the next chunk decides."""

    KIND_PREFIX = re.compile(r"\[?(?P<word>[A-Za-z]+)(?:[_ ](?P<code>[A-Za-z2-7]{0,6}))?$")

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
        cut = len(buf)
        bracket = buf.rfind("[")
        if bracket != -1 and "]" not in buf[bracket:] and len(buf) - bracket <= 2 * CODE_LENGTH + 12:
            cut = bracket
        head = buf[:cut]
        m = cls.KIND_PREFIX.search(head)
        while m:  # the trailing token, and the shorter tails inside it ("en p": "p" opens PERSON)
            if (m.start() == 0 or not head[m.start() - 1].isalnum()) and cls._may_be_placeholder(m.group("word"), m.group("code")):
                return m.start()
            m = cls.KIND_PREFIX.search(head, m.start() + 1)
        return cut

    @staticmethod
    def _may_be_placeholder(word: str, code: str | None) -> bool:
        word = word.upper()
        if code is None:
            return any(k.startswith(word) for k in Kind.ALL)
        return word in Kind.ALL
