"""The pseudonymiser: what leaves for the model carries placeholders, and the answer reads back."""

import pytest

from pseudonym_nl.engine import UNKNOWN, Pseudonymiser, StreamRestorer, placeholder
from pseudonym_nl.known import Matcher, organisations, people
from pseudonym_nl.patterns import Kind, redact_secrets

KEY = b"test-key"
OWN = frozenset({"Bakkerij Zoet", "bakkerijzoet", "Claude", "Anthropic"})
KNOWN = people(["Anna de Vries", "Pieter Bakker", "Karin van Dijk", "Jan Jansen"]) + organisations(["Veilinghuis Oost B.V.", "Gemeente Zwolle", "Particulier", "test"])


def pz(level="identifiers"):
    return Pseudonymiser(key=KEY, level=level, matcher=Matcher.build(KNOWN), own_hosts=frozenset({"bakkerijzoet.nl"}), never=OWN)


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Mail anna@veilinghuis-oost.nl voor de offerte", Kind.EMAIL),
        ("Bel 06-12345678 morgen", Kind.PHONE),
        ("Bel +31 6 1234 5678 morgen", Kind.PHONE),
        ("Betaal op NL91 ABNA 0417 1643 00 graag", Kind.IBAN),
        ("Haar BSN is 111222333.", Kind.BSN),
        ("KvK-nummer 12345678 staat op de factuur", Kind.KVK),
        ("Btw-nummer NL123456789B01", Kind.BTW),
        ("Zij is geboren op 12-03-1980 in Zwolle", Kind.BIRTHDATE),
        ("Het kantoor zit op 1234 AB in Zwolle", Kind.POSTCODE),
        ("Adres: Hoofdstraat 12, Zwolle", Kind.ADDRESS),
        ("De server staat op 10.20.30.40 intern", Kind.IP),
        ("Zie intranet.klant.nl voor het menu", Kind.HOST),
        ("Vraag het Veilinghuis Oost B.V.", Kind.ORG),
        ("Vraag het veilinghuis oost", "Vraag het Veilinghuis Oost B.V."),  # a short form reads back as the full name
        ("Jansen Catering B.V. levert de wijn", Kind.ORG),
        ("Stichting Het Park huurt de zaal", Kind.ORG),
        ("Anna de Vries tekent de offerte", Kind.PERSON),
        ("Mevr. J. Smit tekent de offerte", Kind.PERSON),
        ("De heer Pietersen belt morgen", Kind.PERSON),
        ("Sophie van den Berg is de contactpersoon", Kind.PERSON),
        ("Zie Pieter Bakker voor de sleutel", Kind.PERSON),  # a capitalised word before the name does not hide it
        ("Graag t.a.v. Mohammed el Idrissi sturen", Kind.PERSON),
    ],
)
def test_identifiers_are_replaced_and_read_back(text, kind):
    back = text
    if kind.startswith("Vraag"):
        kind, back = Kind.ORG, kind
    p = pz()
    sent = p.text(text)
    assert f"[{kind}_" in sent, sent
    assert p.restore(sent).casefold() == back.casefold()


@pytest.mark.parametrize(
    "text",
    [
        "Order 123456789 is verzonden",  # nine digits, but nothing says it is a BSN
        "Bestelling 12345678 staat klaar",  # eight digits without KvK nearby
        "Rekening NL12 ABCD 1234 5678 90",  # fails the IBAN check
        "Versie 1.2.3 van Django",
        "Op 12-03-2026 is het diner",  # a date, no birth date
        "Bakkerij Zoet verzorgt het diner met Claude",
        "Kijk op www.bakkerijzoet.nl en google.com",
        "Dijk is geen naam en Particulier is geen klant",
        "Het Zwolse kantoor",
        "Doel: een offerte van 150 woorden",  # a label, not a speaker
    ],
)
def test_what_only_looks_like_an_identifier_is_left_alone(text):
    assert pz().text(text) == text


def test_known_people_by_first_name_surname_and_lower_case():
    p = pz()
    sent = p.text("Anna belt morgen; de Vries tekent, ANNA DE VRIES ook. Van Dijk betaalt, karin van dijk weet ervan.")
    ph = placeholder(KEY, Kind.PERSON, "Anna de Vries")
    assert sent.count(ph) == 3
    assert sent.count(placeholder(KEY, Kind.PERSON, "Karin van Dijk")) == 2
    for word in ("Anna", "Vries", "Dijk", "karin"):
        assert word not in sent


def test_a_name_found_once_is_replaced_everywhere_including_its_surname():
    p = pz()
    sent = p.text("Sophie van den Berg belde. Later belde van den Berg nog eens, en Sophie van den Berg mailde.")
    assert sent.count(placeholder(KEY, Kind.PERSON, "Sophie van den Berg")) == 3
    assert "Berg" not in sent


def test_the_same_value_is_the_same_placeholder_across_runs_and_formats():
    assert pz().text("Bel 0612345678") == pz().text("Bel +31612345678")
    assert pz().text("anna@x.nl") == pz().text("Anna@X.nl")


def test_strict_takes_every_run_of_capitalised_words():
    loose, strict = pz(), pz("strict")
    text = "De wijn komt van Wijnkoperij De Gouden Druif en Bram Kerkhof regelt het."
    assert "Gouden Druif" in loose.text(text)
    sent = strict.text(text)
    assert "Gouden Druif" not in sent and "[ORG_" in sent
    assert "Kerkhof" not in sent
    assert strict.restore(sent) == text


def test_placeholders_already_made_are_not_touched_again():
    p = pz()
    once = p.text("Anna de Vries")
    assert p.text(once) == once


def test_a_mangled_placeholder_is_read_back_and_an_invented_one_is_unknown():
    p = pz()
    made = p.text("Anna de Vries")
    kind, code = made.strip("[]").split("_")
    assert p.restore(f"Vraag {kind.lower()} {code.lower()}.") == "Vraag Anna de Vries."
    assert p.restore("Vraag [PERSON_ZZZZZZ].") == f"Vraag {UNKNOWN}."


@pytest.mark.parametrize(
    "secret",
    ["glpat-abcdefghijklmnopqrstuv", "xoxb-1234567890-abcdefghij", "sk-proj-abcdefghijklmnopqrstuvwxyz0123", "AKIAABCDEFGHIJKLMNOP", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"],
)
def test_secrets_are_removed_for_good(secret):
    p = pz()
    sent = p.text(f"token: {secret} gebruiken")
    assert secret not in sent and "[REDACTED]" in sent
    assert secret not in p.restore(sent)


def test_secrets_in_configuration_keep_their_name():
    text, removed = redact_secrets('SENTRY_AUTH_TOKEN=abc123def456\nwachtwoord = "hunter2hunter2"\npostgres://hal:s3cretpass@db:5432/hal')
    assert removed == 3
    assert "SENTRY_AUTH_TOKEN=[REDACTED]" in text and 'wachtwoord = "[REDACTED]"' in text and "postgres://hal:[REDACTED]@db" in text


def test_credentials_in_a_work_instruction_are_removed():
    text, removed = redact_secrets("Hier log je in met onderstaande gegevens:\nfacturen@example.nl\nVoorbeeld2024!\nWachtwoord: geheim123\nNa inloggen kies je Factuur maken.")
    assert removed == 2
    assert "Voorbeeld2024!" not in text and "geheim123" not in text
    assert "facturen@example.nl" in text and "Wachtwoord: [REDACTED]" in text and "Na inloggen kies je Factuur maken." in text


def test_password_shaped_words_away_from_a_login_stay():
    text = "Artikel\nKoelkast-XL2!\nZie https://Example.nl/Pad2!"
    assert redact_secrets(text) == (text, 0)


def test_summary_counts_what_was_replaced():
    p = pz()
    p.text("Anna de Vries (anna@x.nl, 06-12345678) en Pieter Bakker")
    assert p.summary() == {"EMAIL": 1, "PERSON": 2, "PHONE": 1}


def test_off_level_changes_nothing():
    assert pz("off").text("Anna de Vries, 06-12345678") == "Anna de Vries, 06-12345678"


def test_mapping_carries_over_to_a_new_pseudonymiser():
    first = pz()
    sent = first.text("Anna de Vries belt")
    second = Pseudonymiser(key=KEY, mapping=dict(first.mapping))
    assert second.restore(sent) == "Anna de Vries belt"


def test_known_organisation_in_an_email_slug_and_without_legal_form():
    p = pz()
    sent = p.text("info@veilinghuisoost.nl, Veilinghuis Oost BV, Gemeente Zwolle")
    assert "veilinghuis" not in sent.casefold() and "Zwolle" not in sent


def test_stream_restores_a_placeholder_split_at_every_boundary():
    p = pz()
    ph = p.text("Anna de Vries")
    text = f"Dag {ph}, en {ph.strip('[]').lower().replace('_', ' ')}! IP adres ok. In de [tabel] staat PERSON_ZZZZZZ en [REDACTED]."
    expected = p.restore(text)
    for n in range(1, len(text)):
        sr = StreamRestorer(p)
        out = sr.feed(text[:n]) + sr.feed(text[n:]) + sr.finish()
        assert out == expected, (n, out)


def test_stream_releases_text_that_cannot_hold_a_placeholder():
    sr = StreamRestorer(pz())
    assert sr.feed("Dit is gewone tekst. ") == "Dit is gewone tekst. "
    assert sr.feed("Een [ lange rij zonder sluithaak " + "x" * 40).startswith("Een [ lange rij")


def test_known_single_name_forms_do_not_split_an_unknown_full_name():
    # the app knows a Karin and a van Dijk; the text's Karin van Dijk is someone else
    p = Pseudonymiser(key=KEY, matcher=Matcher.build(people(["Karin Verhoeven", "Sabine van Dijk"])))
    sent = p.text("Mail aan Karin van Dijk over het diner. Karin belt. Van Dijk tekent.")
    assert sent.count("[PERSON_") == 3
    assert p.restore(sent) == "Mail aan Karin van Dijk over het diner. Karin van Dijk belt. Karin van Dijk tekent."


def test_a_protected_name_does_not_end_a_person_found_by_shape():
    p = pz("strict")
    text = "Sophie Bakkerij Zoet bakt, en Bakkerij Zoet levert."
    sent = p.text(text)
    assert sent.count("Bakkerij Zoet") == 2, sent
    assert p.restore(sent) == text


def test_without_never_the_company_is_just_another_organisation():
    p = Pseudonymiser(key=KEY, level="strict")
    assert "Bakkerij Zoet" not in p.text("De taart komt van Bakkerij Zoet uit Zwolle.")
