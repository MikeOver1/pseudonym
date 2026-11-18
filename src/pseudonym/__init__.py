"""Reversible pseudonymisation for text sent to a language model: names, contact details and numbers
leave as placeholders such as `[PERSON_K3J9QX]` and come back in the answer; secrets leave not at all."""

from pseudonym import languages  # noqa: F401  registers the built-in languages
from pseudonym.engine import LEVELS, Pseudonymiser, StreamRestorer, placeholder
from pseudonym.kinds import KINDS, Kind
from pseudonym.known import KnownName, Matcher, organisations, people
from pseudonym.language import Found, Language, Profile, Rule, available, first_names, get, register
from pseudonym.redact import redact_secrets

__all__ = [
    "KINDS",
    "LEVELS",
    "Found",
    "Kind",
    "KnownName",
    "Language",
    "Matcher",
    "Profile",
    "Pseudonymiser",
    "Rule",
    "StreamRestorer",
    "available",
    "first_names",
    "get",
    "organisations",
    "people",
    "placeholder",
    "redact_secrets",
    "register",
]
