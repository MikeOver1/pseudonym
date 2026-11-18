"""What holds in every language: e-mail addresses, IBANs, payment cards, international phone numbers,
EU VAT numbers, IP addresses and host names, the legal forms seen worldwide, and the words that label
a secret in configuration. Detection always uses CORE; languages add to it."""

from __future__ import annotations

import re

from pseudonym_nl.kinds import Kind
from pseudonym_nl.language import Language, Rule


def valid_iban(value: str) -> bool:
    compact = re.sub(r"\s", "", value)
    if not 15 <= len(compact) <= 34:
        return False
    moved = compact[4:] + compact[:4]
    return int("".join(str(int(char, 36)) for char in moved)) % 97 == 1


def luhn(value: str) -> bool:
    digits = [int(c) for c in value if c.isdigit()]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def not_local_ip(value: str) -> bool:
    return value not in {"0.0.0.0", "127.0.0.1", "255.255.255.255"}


# A date in the usual written forms, for the languages to gate with the words that make it a birth date.
DATE = re.compile(
    r"\b(?:[0-3]?\d[-/.][01]?\d[-/.](?:19|20)\d{2}"  # 14-03-1985, 03/14/1985
    r"|(?:19|20)\d{2}-[01]\d-[0-3]\d"  # 1985-03-14
    r"|[0-3]?\d [^\W\d_]{3,9}\.? (?:19|20)\d{2}"  # 14 March 1985, 14 mrt. 1985
    r"|[^\W\d_]{3,9}\.? [0-3]?\d,? (?:19|20)\d{2})\b"  # March 14, 1985
)
EU_VAT = re.compile(r"\b(?:AT|BE|BG|CY|CZ|DE|DK|EE|EL|ES|FI|FR|HR|HU|IE|IT|LT|LU|LV|MT|NL|PL|PT|RO|SE|SI|SK|XI|GB)[ ]?[0-9A-Z]{8,12}\b")
VAT_CONTEXT = re.compile(r"(?i)\b(?:vat|btw|ust|mwst|tva|iva|moms|alv|dph|ddv|pvm|áfa|tax id)\b")

CORE = Language(
    code="core",
    name="Language-neutral",
    particles=frozenset({"de", "la", "le", "da", "di", "del", "della", "von", "van", "el", "al", "bin", "ibn", "ben"}),
    not_names=frozenset(
        {
            "Excel",
            "Word",
            "Teams",
            "Outlook",
            "Google",
            "Drive",
            "Gmail",
            "Slack",
            "Zoom",
            "Jira",
            "GitHub",
            "GitLab",
            "LinkedIn",
            "WhatsApp",
            "Dashboard",
            "Sales",
            "Marketing",
            "Finance",
            "Office",
            "Support",
            "Team",
        }
    ),
    empty_values=frozenset({"test", "n/a", "na", "tbd", "none", "null", "-"}),
    org_suffixes=(r"GmbH", r"AG", r"S\.?A\.?", r"S\.?A\.?S\.?", r"S\.?r\.?l\.?", r"S\.?L\.?", r"Ltd\.?", r"Inc\.?", r"LLC", r"PLC"),
    org_joiners=("&",),
    rules=(
        Rule(Kind.EMAIL, re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+){1,10}(?![\w-])")),
        Rule(Kind.IBAN, re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b"), check=valid_iban),
        Rule(Kind.CARD, re.compile(r"(?<![\d-])[3-6]\d{3}(?:[ -]?\d{4}){2}[ -]?\d{1,7}(?![\d-])"), check=luhn),
        # with a plus; national formats, and "00" before a country code, come with the languages
        Rule(Kind.PHONE, re.compile(r"(?<![\w+])\+[1-9]\d{0,2}(?:[\s\-.]?\(?\d\)?){6,13}(?!\d)")),
        Rule(Kind.VAT_ID, EU_VAT, context=VAT_CONTEXT),
        Rule(Kind.IP, re.compile(r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}(?![\d.])"), check=not_local_ip),
    ),
    # generic top-level domains; a country's own come with its language, which keeps "user.id" and
    # "setup.py" from being taken for hosts until someone writes for Indonesia or Paraguay
    tlds=frozenset("com org net edu gov eu int io ai co me tv dev app cloud info biz online shop site store tech xyz".split()),
    # hosts that identify no one: public infrastructure, documentation and the tools everyone uses
    public_hosts=frozenset(
        """amazonaws.com anthropic.com claude.ai apple.com atlassian.com cloudflare.com docker.com example.com example.org
        example.net github.com gitlab.com google.com googleapis.com microsoft.com office.com mozilla.org npmjs.com openai.com
        pypi.org python.org sentry.io slack.com stackoverflow.com w3.org wikipedia.org youtube.com linkedin.com facebook.com
        instagram.com whatsapp.com supabase.co vercel.app europa.eu gov mil""".split()
    ),
    password_labels=(r"password", r"passwd", r"pwd", r"passphrase"),
    login_words=(r"login", r"log in", r"sign in", r"username", r"user name", r"password"),
    found=(
        ("Card 4111 1111 1111 1111 expires", Kind.CARD),
        ("Mail an jan.muller@firma.de bitte", Kind.EMAIL),
        ("IBAN DE89 3704 0044 0532 0130 00", Kind.IBAN),
        ("Ruf +49 30 1234567 an", Kind.PHONE),
        ("USt-IdNr DE123456789", Kind.VAT_ID),
        ("Server 10.20.30.40 is down", Kind.IP),
        ("Ask Müller GmbH", Kind.ORG),
    ),
    left_alone=(
        "Card 4111 1111 1111 1112 fails the check",
        "Listen on 127.0.0.1 and 0.0.0.0",
        "Docs at docs.python.org and github.com",
        "Use a 2024-01-01 cut-off",
    ),
)
