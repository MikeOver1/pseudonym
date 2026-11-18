"""Secrets are not replaced by a placeholder but removed, and never put back: tokens with a recognisable
prefix, private keys, credentials in URLs and configuration, and passwords written out in a login
instruction. The words that label a password or announce a login come from every registered
language, whichever languages detection uses."""

from __future__ import annotations

import re

from pseudonym.language import Profile

REDACTED = "[REDACTED]"

# Each pattern's whole match is the secret.
TOKENS = [
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
QUOTED_SECRET = re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?key|token|client[_-]?secret)\b(\s*[:=]\s*)(['\"])([^'\"\s]{8,})\3")
ENV_SECRET = re.compile(r"(?m)^(\s*(?:export\s+)?[A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY|ACCESS_KEY)[A-Z0-9_]*\s*[:=]\s*)(?!\[REDACTED\])(\S{6,})\s*$")
# A line that is nothing but a password-shaped word (lower and upper case, digit and symbol), shortly
# after the text speaks of logging in.
PASSWORD_LINE = re.compile(r"(?m)^([ \t]*)(?=\S*[a-z])(?=\S*[A-Z])(?=\S*\d)(?=\S*[^\w\s])(?!\S*(?:://|@))(\S{8,64})[ \t]*$")
LOGIN_REACH = 300


def redact_secrets(text: str) -> tuple[str, int]:
    """The text with every secret removed, and how many were."""
    profile = Profile.of()
    count = 0

    def gone(_m: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return REDACTED

    def keep(*groups: int, quote: int | None = None) -> callable:
        def sub(m: re.Match[str]) -> str:
            nonlocal count
            count += 1
            q = m.group(quote) if quote else ""
            return "".join(m.group(g) for g in groups) + q + REDACTED + q

        return sub

    for pattern in TOKENS:
        text = pattern.sub(gone, text)
    text = URL_PASSWORD.sub(lambda m: keep(1)(m) + m.group(3), text)
    text = QUOTED_SECRET.sub(keep(1, 2, quote=3), text)
    text = profile.quoted_password.sub(keep(1, 2, quote=3), text)
    text = ENV_SECRET.sub(keep(1), text)
    text = profile.labelled_password.sub(keep(1, 2), text)

    def after_login(m: re.Match[str]) -> str:
        nonlocal count
        if not profile.login_context.search(text, max(0, m.start() - LOGIN_REACH), m.start()):
            return m.group()
        count += 1
        return f"{m.group(1)}{REDACTED}"

    text = PASSWORD_LINE.sub(after_login, text)
    return text, count
