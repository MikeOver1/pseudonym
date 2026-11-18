"""The pseudonymiser: what leaves for the model carries placeholders, and the answer reads back."""

import pytest

from pseudonym import KINDS, Kind, Matcher, Profile, Pseudonymiser, StreamRestorer, available, organisations, people, placeholder, redact_secrets

NL = ["nl"]

KEY = b"test-key"
OWN = frozenset({"Bakkerij Zoet", "bakkerijzoet", "Claude", "Anthropic"})
KNOWN = people(["Anna de Vries", "Pieter Bakker", "Karin van Dijk", "Jan Jansen"], NL) + organisations(["Veilinghuis Oost B.V.", "Gemeente Zwolle", "Particulier", "test"], languages=NL)


def pz(level="identifiers"):
    return Pseudonymiser(key=KEY, level=level, languages=NL, matcher=Matcher.build(KNOWN), own_hosts=frozenset({"bakkerijzoet.nl"}), never=OWN)


@pytest.mark.parametrize(
    ("text", "back"),
    [
        ("Vraag het Veilinghuis Oost B.V.", None),
        ("Vraag het veilinghuis oost", "Vraag het Veilinghuis Oost B.V."),  # a short form reads back as the full name
    ],
)
def test_known_organisations_are_replaced_and_read_back(text, back):
    p = pz()
    sent = p.text(text)
    assert "[ORG_" in sent, sent
    assert p.restore(sent) == (back or text)


@pytest.mark.parametrize(
    "text",
    [
        "Bakkerij Zoet verzorgt het diner met Claude",
        "Kijk op www.bakkerijzoet.nl en google.com",
        "Dijk is geen naam en Particulier is geen klant",
    ],
)
def test_own_and_empty_names_are_left_alone(text):
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
    assert p.restore("Vraag [PERSON_ZZZZZZ].") == "Vraag [onbekend]."


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
    text, removed = redact_secrets('SENTRY_AUTH_TOKEN=abc123def456\nwachtwoord = "hunter2hunter2"\npostgres://app:s3cretpass@db:5432/app')
    assert removed == 3
    assert "SENTRY_AUTH_TOKEN=[REDACTED]" in text and 'wachtwoord = "[REDACTED]"' in text and "postgres://app:[REDACTED]@db" in text


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
    second = Pseudonymiser(key=KEY, languages=["en"], mapping=dict(first.mapping))  # restoring needs no particular language
    assert second.restore(sent) == "Anna de Vries belt"


def test_known_organisation_in_an_email_slug_and_without_legal_form():
    p = pz()
    sent = p.text("info@veilinghuisoost.nl, Veilinghuis Oost BV, Gemeente Zwolle")
    assert "veilinghuis" not in sent.casefold() and "Zwolle" not in sent


@pytest.mark.parametrize("kind", KINDS)
def test_stream_restores_a_placeholder_split_at_every_boundary(kind):
    p = pz()
    ph = placeholder(KEY, kind, "waarde")
    p.mapping[ph] = [kind, "waarde"]
    written = ph.strip("[]").lower().replace("_", " ")
    text = f"Dag {ph}, en {written}! IP adres ok. In de [tabel] staat {kind}_ZZZZZZ en [REDACTED]."
    expected = p.restore(text)
    assert expected.count("waarde") == 2 and "[onbekend]" in expected, expected
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
    p = Pseudonymiser(key=KEY, languages=NL, matcher=Matcher.build(people(["Karin Verhoeven", "Sabine van Dijk"], NL)))
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
    p = Pseudonymiser(key=KEY, level="strict", languages=NL)
    assert "Bakkerij Zoet" not in p.text("De taart komt van Bakkerij Zoet uit Zwolle.")


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ("postgres://app:p@ss@db:5432/x", "ss@db"),  # an "@" in the password does not end it early
        ('password = "hunter2"', "hunter2"),  # short, quoted
        ('wachtwoord: "mijn geheime zin"', "geheime"),  # quoted, with spaces
    ],
)
def test_passwords_are_removed_whole(text, secret):
    redacted, removed = redact_secrets(text)
    assert removed == 1 and secret not in redacted and "[REDACTED]" in redacted, redacted


def test_the_host_after_a_url_password_stays():
    assert redact_secrets("postgres://app:p@ss@db:5432/x")[0] == "postgres://app:[REDACTED]@db:5432/x"


def test_phone_numbers_are_compared_without_country_code_or_trunk():
    nl = Profile.of(NL)
    assert placeholder(KEY, Kind.PHONE, "+31 (0)6 1234 5678", nl) == placeholder(KEY, Kind.PHONE, "06-12345678", nl)
    en = Profile.of(["en"])
    assert placeholder(KEY, Kind.PHONE, "+44 20 7946 0018", en) == placeholder(KEY, Kind.PHONE, "020 7946 0018", en)
    assert placeholder(KEY, Kind.PHONE, "+1 415 555 0132", en) == placeholder(KEY, Kind.PHONE, "(415) 555-0132", en)


def test_labels_come_from_the_first_language():
    assert Profile.of(["nl", "en"]).labels[Kind.PERSON] == "namen"
    assert Profile.of(["en", "nl"]).labels[Kind.PERSON] == "names"


def test_an_unknown_level_is_refused():
    with pytest.raises(ValueError):
        Pseudonymiser(key=KEY, languages=NL, level="max")


ENGLISH_MAIL = """Hi Rachel,

Thanks for the call on Tuesday. As discussed, Will and I reviewed the proposal from Northwind Traders Ltd
and we think it is a good fit. May I suggest we bring Tom Hughes from finance into the next meeting?
Grace Period terms are in section 4. The Project Kickoff is planned for March, and New York Office Hours
stay the same. Please Mark Complete any items you have finished in Jira before Friday.

Action items:
- Rachel: send the signed NDA to David Okonkwo by Thursday
- Tom Hughes: check the invoice against the Purchase Order
- Max Retries should stay at 3 in the Payment Service config

Best regards,
Laura Bennett
Head of Operations, Northwind Traders
"""


@pytest.mark.parametrize("languages", [["en"], None], ids=["en", "all"])
def test_english_prose_loses_its_people_and_nothing_else(languages):
    """Sentence capitals, title-case headings and names that are also words (Will, May, Grace, Mark,
    Max) are where shape-based detection goes wrong in English."""
    p = Pseudonymiser(key=KEY, languages=languages or available())
    sent = p.text(ENGLISH_MAIL)
    assert sorted(v for _, v in p.mapping.values()) == ["David Okonkwo", "Laura Bennett", "Northwind Traders Ltd", "Rachel", "Tom Hughes"]
    assert "Northwind" not in sent and "Head of Operations" in sent
    assert p.restore(sent) == ENGLISH_MAIL.replace("Operations, Northwind Traders", "Operations, Northwind Traders Ltd")


def test_secrets_are_removed_in_every_language_whichever_are_active():
    p = Pseudonymiser(key=KEY, languages=["en"])
    assert "geheim123" not in p.text("Wachtwoord: geheim123")


def test_a_language_s_ordinary_words_only_block_first_names_when_it_is_active():
    assert "Frank" not in pz().text("Frank Bakker belt morgen")
    assert Pseudonymiser(key=KEY, languages=["en", "nl"]).text("Frank Bakker belt morgen") == "Frank Bakker belt morgen"


def test_hosts_in_common_country_domains_are_found_in_any_language():
    assert "firma" not in Pseudonymiser(key=KEY, languages=["en"]).text("See intranet.firma.de")
