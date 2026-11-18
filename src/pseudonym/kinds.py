"""What a placeholder can stand for.

The set is closed on purpose: restoring recognises a placeholder by its kind, so a kind every language
shares keeps a stored conversation readable whichever languages are active later, and keeps ordinary
words followed by six letters from being taken for one. A language that needs another kind proposes
it here.
"""

from __future__ import annotations


class Kind:
    PERSON = "PERSON"
    ORG = "ORG"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    IBAN = "IBAN"
    CARD = "CARD"  # payment card number
    NATIONAL_ID = "NATIONAL_ID"  # citizen or social security number: BSN, SSN, NINO
    COMPANY_ID = "COMPANY_ID"  # company register or tax number: KvK, Companies House, EIN
    VAT_ID = "VAT_ID"
    BIRTHDATE = "BIRTHDATE"
    POSTCODE = "POSTCODE"
    ADDRESS = "ADDRESS"
    IP = "IP"
    HOST = "HOST"


KINDS: tuple[str, ...] = tuple(v for k, v in vars(Kind).items() if k.isupper())
REDACTED = "REDACTED"  # not a kind: a removed secret, never restored

LABELS: dict[str, str] = {
    Kind.PERSON: "names",
    Kind.ORG: "organisations",
    Kind.EMAIL: "email addresses",
    Kind.PHONE: "phone numbers",
    Kind.IBAN: "bank accounts",
    Kind.CARD: "card numbers",
    Kind.NATIONAL_ID: "national ID numbers",
    Kind.COMPANY_ID: "company numbers",
    Kind.VAT_ID: "VAT numbers",
    Kind.BIRTHDATE: "birth dates",
    Kind.POSTCODE: "postcodes",
    Kind.ADDRESS: "addresses",
    Kind.IP: "IP addresses",
    Kind.HOST: "host names",
    REDACTED: "secrets",
}
