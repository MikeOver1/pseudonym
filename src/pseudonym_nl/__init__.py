"""Reversible pseudonymisation of Dutch text before it goes to a language model.

What leaves carries placeholders such as `[PERSON_K3J9QX]`, never the names, contact details and
numbers the text held; the model's answer reads back with the real values.
"""

from pseudonym_nl.engine import LEVELS, Pseudonymiser, StreamRestorer, placeholder
from pseudonym_nl.known import KnownName, Matcher, organisations, people
from pseudonym_nl.patterns import Kind, redact_secrets

__all__ = [
    "LEVELS",
    "Kind",
    "KnownName",
    "Matcher",
    "Pseudonymiser",
    "StreamRestorer",
    "organisations",
    "people",
    "placeholder",
    "redact_secrets",
]
