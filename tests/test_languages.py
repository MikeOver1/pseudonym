"""Every language pack, the language-neutral core included, is held to its own examples: what it says
it finds is replaced and reads back, what it says it leaves alone stays as it is, alone and with every
other language active. A new pack is tested by registering it; nothing here needs to change."""

import time

import pytest

from pseudonym import Pseudonymiser, available, get
from pseudonym.core import CORE

PACKS = [CORE, *(get(code) for code in available())]
ALL = available()
CASES = [(lang, text, kind) for lang in PACKS for text, kind in lang.found]
QUIET = [(lang, text) for lang in PACKS for text in lang.left_alone]


def ids(case):
    return case.code if hasattr(case, "code") else str(case)[:40]


@pytest.mark.parametrize("together", [False, True], ids=["alone", "together"])
@pytest.mark.parametrize(("lang", "text", "kind"), CASES, ids=ids)
def test_what_a_language_finds_is_replaced_and_read_back(lang, text, kind, together):
    p = Pseudonymiser(key=b"k", languages=ALL if together else [lang])
    sent = p.text(text)
    assert f"[{kind}_" in sent, sent
    assert p.restore(sent) == text


@pytest.mark.parametrize("together", [False, True], ids=["alone", "together"])
@pytest.mark.parametrize(("lang", "text"), QUIET, ids=ids)
def test_what_a_language_leaves_alone_stays(lang, text, together):
    assert Pseudonymiser(key=b"k", languages=ALL if together else [lang]).text(text) == text


@pytest.mark.parametrize("lang", PACKS, ids=ids)
def test_every_pack_has_examples(lang):
    assert lang.found and lang.left_alone


@pytest.mark.parametrize("lang", PACKS, ids=ids)
def test_long_text_takes_linear_time(lang):
    """A pattern that backtracks over the whole text makes this take minutes instead of milliseconds."""
    samples = [" ".join(["Aaaa"] * 20000), "1" * 50000, " ".join(t for t, _ in lang.found) * 20]
    p = Pseudonymiser(key=b"k", level="strict", languages=[lang])
    for text in samples:
        start = time.perf_counter()
        p.text(text)
        assert time.perf_counter() - start < 3, text[:40]
