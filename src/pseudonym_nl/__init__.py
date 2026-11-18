"""Reversible pseudonymisation for text sent to a language model: names, contact details and numbers
leave as placeholders such as `[PERSON_K3J9QX]` and come back in the answer; secrets leave not at all."""

from pseudonym_nl import languages  # noqa: F401  registers the built-in languages
from pseudonym_nl.engine import LEVELS, Pseudonymiser, StreamRestorer, placeholder
from pseudonym_nl.kinds import KINDS, Kind
from pseudonym_nl.known import KnownName, Matcher, organisations, people
from pseudonym_nl.language import Found, Language, Profile, Rule, available, first_names, get, register
from pseudonym_nl.redact import redact_secrets

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
