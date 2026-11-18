"""Identifiers found by their shape, and secrets removed for good.

Patterns catch what the app cannot know by name: an e-mail address in a pasted mail, a phone number
in a quote request, a bank account on an invoice. Where a format has a check digit it is verified, so
an arbitrary number is not taken for one. Numbers that are only recognisable by what the text calls
them (citizen service, chamber of commerce) count only with that context nearby. Secrets are not
replaced by a placeholder but removed, and never put back.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import ClassVar

REDACTED = "[REDACTED]"


@dataclass(frozen=True)
class Found:
    start: int
    end: int
    kind: str
    value: str


class Kind:
    PERSON = "PERSON"
    ORG = "ORG"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    IBAN = "IBAN"
    BSN = "BSN"
    KVK = "KVK"
    BTW = "BTW"
    BIRTHDATE = "GEBOREN"
    POSTCODE = "POSTCODE"
    ADDRESS = "ADRES"
    IP = "IP"
    HOST = "HOST"
    ALL = ("PERSON", "ORG", "EMAIL", "PHONE", "IBAN", "BSN", "KVK", "BTW", "GEBOREN", "POSTCODE", "ADRES", "IP", "HOST")
    LABELS: ClassVar[dict[str, str]] = {
        "PERSON": "namen",
        "ORG": "organisaties",
        "EMAIL": "e-mailadressen",
        "PHONE": "telefoonnummers",
        "IBAN": "bankrekeningen",
        "BSN": "burgerservicenummers",
        "KVK": "KvK-nummers",
        "BTW": "btw-nummers",
        "GEBOREN": "geboortedata",
        "POSTCODE": "postcodes",
        "ADRES": "adressen",
        "IP": "IP-adressen",
        "HOST": "hostnamen",
        "REDACTED": "geheimen",
    }


# Secrets: tokens with a recognisable prefix, private keys, credentials in addresses and in
# configuration. Each pattern's last group, or the whole match, is the secret.
SECRETS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+"),
    re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bsntry[su]_[A-Za-z0-9+/=_\-]{20,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
]
# The password runs to the last "@" before the host, so one holding an "@" goes as a whole.
URL_PASSWORD = re.compile(r"\b([a-z][a-z0-9+.\-]*://[^\s:/@]+:)([^\s/]+)(@)(?=[^\s@/]+(?:[/?#]|\s|$))")
QUOTED_SECRET = re.compile(
    r"(?i)\b(password|passwd|pwd|wachtwoord|secret|api[_-]?key|access[_-]?key|token|client[_-]?secret)\b"
    r"(\s*[:=]\s*)(['\"])([^'\"\s]{8,})\3"
)
ENV_SECRET = re.compile(r"(?m)^(\s*(?:export\s+)?[A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY|ACCESS_KEY)[A-Z0-9_]*\s*[:=]\s*)(?!\[REDACTED\])(\S{6,})\s*$")
# Credentials written out for colleagues in a work instruction: a labelled password, or a line that
# is nothing but a password-shaped word (lower and upper case, digit and symbol) just after a login.
LABELLED_PASSWORD = re.compile(r"(?i)\b(wachtwoord|password|passwd|pwd)(\s*[:=]\s*)(?!\[REDACTED\])([^\s'\"]{6,})")
# A quoted one, however short and with spaces: the quotes say where it ends.
QUOTED_PASSWORD = re.compile(r"(?i)\b(wachtwoord|password|passwd|pwd)(\s*[:=]\s*)(['\"])(?!\[REDACTED\])([^'\"\n]+)\3")
PASSWORD_LINE = re.compile(r"(?m)^([ \t]*)(?=\S*[a-z])(?=\S*[A-Z])(?=\S*\d)(?=\S*[^\w\s])(?!\S*(?:://|@))(\S{8,64})[ \t]*$")
LOGIN_CONTEXT = re.compile(r"(?i)\b(?:inlog\w*|ingelogd|log (?:je|u) in|login|gebruikersnaam|username|wachtwoord|password)\b")
LOGIN_REACH = 300


def redact_secrets(text: str) -> tuple[str, int]:
    """The text with every secret removed, and how many were."""
    count = 0

    def gone(_match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return REDACTED

    for pattern in SECRETS:
        text = pattern.sub(gone, text)

    def keep_prefix(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{match.group(1)}{REDACTED}{match.group(3)}"

    text = URL_PASSWORD.sub(keep_prefix, text)

    def quoted(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        quote = match.group(3)
        return f"{match.group(1)}{match.group(2)}{quote}{REDACTED}{quote}"

    text = QUOTED_SECRET.sub(quoted, text)

    def assigned(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{match.group(1)}{REDACTED}"

    text = ENV_SECRET.sub(assigned, text)

    def labelled(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{match.group(1)}{match.group(2)}{REDACTED}"

    text = QUOTED_PASSWORD.sub(quoted, text)
    text = LABELLED_PASSWORD.sub(labelled, text)

    def after_login(match: re.Match[str]) -> str:
        nonlocal count
        if not LOGIN_CONTEXT.search(text, max(0, match.start() - LOGIN_REACH), match.start()):
            return match.group()
        count += 1
        return f"{match.group(1)}{REDACTED}"

    text = PASSWORD_LINE.sub(after_login, text)
    return text, count


EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?![\w-])")
# Dutch numbers (06, 0xx, +31, 0031) and other international ones with a plus.
PHONE = re.compile(
    r"(?<![\w+])(?:(?:\+|00)31[\s\-.]?(?:\(0\)[\s\-.]?)?|0)(?:\d[\s\-.]?){8}\d(?!\d)"
    r"|(?<![\w+])\+(?!31)\d{1,3}(?:[\s\-.]?\d){6,12}(?!\d)"
)
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b")
BSN = re.compile(r"\b\d{9}\b|\b\d{4}\.\d{2}\.\d{3}\b")
BSN_CONTEXT = re.compile(r"(?i)\b(bsn|burgerservicenummer|sofi-?nummer)\b")
KVK = re.compile(r"\b\d{8}\b")
KVK_CONTEXT = re.compile(r"(?i)\b(kvk|kamer van koophandel|handelsregister)\b")
BTW = re.compile(r"\bNL\s?\d{9}\s?B\s?\d{2}\b")
BIRTHDATE = re.compile(r"\b(?:[0-3]?\d[-/.][01]?\d[-/.](?:19|20)\d{2}|[0-3]?\d \w+ (?:19|20)\d{2})\b")
BIRTHDATE_CONTEXT = re.compile(r"(?i)\b(geboren|geboortedatum|geb\.|date of birth|dob)\b")
POSTCODE = re.compile(r"\b[1-9]\d{3}[ ]?(?!SA|SD|SS)[A-Z]{2}\b")
STREET = re.compile(
    r"\b[A-Z][a-zà-ÿ]+(?:[- ][A-Za-zà-ÿ]+){0,4}"  # at most five words: keeps long capitalised runs linear
    r"(?:straat|laan|weg|plein|singel|gracht|kade|dijk|dreef|hof|pad|park|steeg|baan|markt|erf)"
    r"\s\d{1,4}(?:[ -]?[a-zA-Z]\b|-\d{1,3})?"
)
IPV4 = re.compile(r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}(?![\d.])")
NOT_ADDRESSES = {"0.0.0.0", "127.0.0.1", "255.255.255.255"}
HOST = re.compile(
    r"(?i)(?<![\w@.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:nl|com|org|net|io|eu|be|de|dev|app|cloud|co|uk|info|biz|online|shop|site|tech|ai|frl|amsterdam)(?![\w-])"
)
# Hosts that identify no one: public infrastructure, documentation and the tools everyone uses.
PUBLIC_HOSTS = frozenset(
    {
        "amazonaws.com",
        "anthropic.com",
        "claude.ai",
        "apple.com",
        "atlassian.com",
        "cloudflare.com",
        "docker.com",
        "example.com",
        "example.org",
        "example.net",
        "github.com",
        "gitlab.com",
        "google.com",
        "googleapis.com",
        "google.nl",
        "microsoft.com",
        "office.com",
        "mozilla.org",
        "npmjs.com",
        "openai.com",
        "pypi.org",
        "python.org",
        "sentry.io",
        "slack.com",
        "stackoverflow.com",
        "w3.org",
        "wikipedia.org",
        "youtube.com",
        "linkedin.com",
        "facebook.com",
        "instagram.com",
        "whatsapp.com",
        "supabase.co",
        "vercel.app",
        "rijksoverheid.nl",
        "belastingdienst.nl",
        "kvk.nl",
        "nvwa.nl",
    }
)
# A company name with its legal form: "Jansen Catering B.V.", "Stichting Het Park". At most eight
# words, which also keeps a long run of capitalised words from taking quadratic time.
ORG_SUFFIX = re.compile(
    r"\b(?:[A-Z][\w&'’.-]*(?:\s+(?:[A-Z][\w&'’.-]*|&|en|van|de|der|den|het|voor|'t)){0,7})"
    r"\s+(?:B\.?V\.?|N\.?V\.?|V\.?O\.?F\.?|C\.?V\.?|Holding|Groep|Group|GmbH|Ltd\.?|Inc\.?)(?![\w.])"
)
ORG_PREFIX = re.compile(r"\b(?:Stichting|Gemeente|Vereniging|Hotel|Restaurant|Brasserie|Landgoed|Kasteel)\s+(?:[A-Z][\w'’-]*(?:\s+(?:[A-Z][\w'’-]*|van|de|der|den|het|'t)){0,7})")


def identifiers(text: str) -> Iterator[Found]:
    """Contact details and numbers, in the order the checks run."""
    checks: list[tuple[re.Pattern[str], str, Callable[[re.Match[str]], bool]]] = [
        (EMAIL, Kind.EMAIL, _always),
        (IBAN, Kind.IBAN, lambda m: _valid_iban(m.group())),
        (BTW, Kind.BTW, _always),
        (BSN, Kind.BSN, lambda m: _in_context(text, m, BSN_CONTEXT) and _valid_bsn(m.group())),
        (KVK, Kind.KVK, lambda m: _in_context(text, m, KVK_CONTEXT)),
        (PHONE, Kind.PHONE, _always),
        (BIRTHDATE, Kind.BIRTHDATE, lambda m: _in_context(text, m, BIRTHDATE_CONTEXT)),
        (STREET, Kind.ADDRESS, _always),
        (POSTCODE, Kind.POSTCODE, _always),
        (IPV4, Kind.IP, lambda m: m.group() not in NOT_ADDRESSES),
    ]
    for pattern, kind, keep in checks:
        for match in pattern.finditer(text):
            if keep(match):
                yield Found(match.start(), match.end(), kind, match.group())


def organisations(text: str) -> Iterator[Found]:
    """Company names recognisable by their legal form or a generic first word."""
    for pattern in (ORG_SUFFIX, ORG_PREFIX):
        for match in pattern.finditer(text):
            yield Found(match.start(), match.end(), Kind.ORG, match.group())


def _always(_match: re.Match[str]) -> bool:
    return True


def _in_context(text: str, match: re.Match[str], context: re.Pattern[str]) -> bool:
    """A number counts only where the text, shortly before it, says what it is."""
    return bool(context.search(text[max(0, match.start() - 60) : match.start()]))


def hosts(text: str, own: frozenset[str]) -> Iterator[Found]:
    """Host names other than public infrastructure and the company's own addresses."""
    for match in HOST.finditer(text):
        host = match.group().lower()
        if not _listed(host, own) and not _listed(host, PUBLIC_HOSTS):
            yield Found(match.start(), match.end(), Kind.HOST, match.group())


def _listed(host: str, known: frozenset[str]) -> bool:
    return any(host == k or host.endswith(f".{k}") for k in known)


def _valid_iban(value: str) -> bool:
    compact = value.replace(" ", "")
    if not 15 <= len(compact) <= 34:
        return False
    moved = compact[4:] + compact[:4]
    digits = "".join(str(int(char, 36)) for char in moved)
    return int(digits) % 97 == 1


def _valid_bsn(value: str) -> bool:
    """The eleven test every citizen service number passes."""
    digits = [int(char) for char in value if char.isdigit()]
    if len(digits) != 9:
        return False
    total = sum(digit * weight for digit, weight in zip(digits[:8], range(9, 1, -1), strict=True))
    return (total - digits[8]) % 11 == 0 and total != 0
