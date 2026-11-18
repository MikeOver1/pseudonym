"""Dutch, with the identifiers of the Netherlands. Flemish names are in the name list; Belgian numbers
are not yet (see CONTRIBUTING.md on adding a country)."""

import re

from pseudonym.core import DATE
from pseudonym.kinds import Kind
from pseudonym.language import Language, Rule, first_names, register


def valid_bsn(value: str) -> bool:
    """The eleven test every citizen service number (BSN) passes."""
    digits = [int(c) for c in value if c.isdigit()]
    if len(digits) != 9:
        return False
    total = sum(d * w for d, w in zip(digits[:8], range(9, 1, -1), strict=True))
    return (total - digits[8]) % 11 == 0 and total != 0


NL = register(
    Language(
        code="nl",
        name="Nederlands",
        first_names=first_names(__name__),
        particles=frozenset({"van", "de", "der", "den", "het", "te", "ter", "ten", "'t", "v.", "d."}),
        titles=(r"dhr\.?", r"mevr\.?", r"mw\.?", r"mr\.?", r"drs\.?", r"dr\.?", r"ir\.?", r"ing\.?", r"de heer", r"mevrouw", r"meneer", r"familie", r"fam\.", r"t\.a\.v\.?"),
        not_names=frozenset(
            """Januari Februari Maart April Mei Juni Juli Augustus September Oktober November December
            Maandag Dinsdag Woensdag Donderdag Vrijdag Zaterdag Zondag Vandaag Morgen Gisteren
            Offerte Voorstel Factuur Planning Overleg Vergadering Agenda Notulen Project
            Nederland Holland België Amsterdam Rotterdam Utrecht Groningen Arnhem Nijmegen Eindhoven Zwolle
            Haarlem Leiden Delft Tilburg Breda Maastricht Antwerpen Brussel Gent""".split()
        ),
        empty_values=frozenset(
            """onbekend nvt n.v.t. divers diversen intern particulier prive privé klant klanten gast gasten
            relatie bedrijf bedrijven overig overige geen nog nader te bepalen ntb familie fam""".split()
        ),
        org_suffixes=(r"B\.?V\.?", r"N\.?V\.?", r"V\.?O\.?F\.?", r"C\.?V\.?", r"Holding", r"Groep"),
        org_prefixes=("Stichting", "Gemeente", "Vereniging", "Coöperatie", "Provincie", "Waterschap"),
        org_joiners=("en", "van", "de", "der", "den", "het", "voor", "'t"),
        rules=(
            Rule(Kind.PHONE, re.compile(r"(?<![\w+])(?:0031[\s\-.]?(?:\(0\)[\s\-.]?)?|0)(?:\d[\s\-.]?){8}\d(?!\d)")),
            Rule(Kind.NATIONAL_ID, re.compile(r"\b\d{9}\b|\b\d{4}\.\d{2}\.\d{3}\b"), check=valid_bsn, context=re.compile(r"(?i)\b(?:bsn|burgerservicenummer|sofi-?nummer)\b")),
            Rule(Kind.COMPANY_ID, re.compile(r"\b\d{8}\b"), context=re.compile(r"(?i)\b(?:kvk|kamer van koophandel|handelsregister)\b")),
            Rule(Kind.VAT_ID, re.compile(r"\bNL\s?\d{9}\s?B\s?\d{2}\b")),
            Rule(Kind.BIRTHDATE, DATE, context=re.compile(r"(?i)\b(?:geboren|geboortedatum|geb\.)")),
            Rule(Kind.POSTCODE, re.compile(r"\b[1-9]\d{3}[ ]?(?!SA|SD|SS)[A-Z]{2}\b")),
            # at most five words before the suffix: keeps long capitalised runs linear
            Rule(
                Kind.ADDRESS,
                re.compile(
                    r"\b[A-Z][a-zà-ÿ]+(?:[- ][A-Za-zà-ÿ]+){0,4}(?:straat|laan|weg|plein|singel|gracht|kade|dijk|dreef|hof|pad|park|steeg|baan|markt|erf)"
                    r"\s\d{1,4}(?:[ -]?[a-zA-Z]\b|-\d{1,3})?"
                ),
            ),
        ),
        phone_prefixes=(("31", "0"),),
        tlds=frozenset({"frl", "amsterdam"}),
        public_hosts=frozenset({"overheid.nl", "rijksoverheid.nl", "government.nl", "belastingdienst.nl", "kvk.nl", "google.nl", "belgium.be"}),
        password_labels=(r"wachtwoord",),
        login_words=(r"inlog\w*", r"ingelogd", r"log (?:je|u) in", r"gebruikersnaam", r"wachtwoord"),
        unknown="[onbekend]",
        labels={
            Kind.PERSON: "namen",
            Kind.ORG: "organisaties",
            Kind.EMAIL: "e-mailadressen",
            Kind.PHONE: "telefoonnummers",
            Kind.IBAN: "bankrekeningen",
            Kind.CARD: "betaalkaarten",
            Kind.NATIONAL_ID: "burgerservicenummers",
            Kind.COMPANY_ID: "KvK-nummers",
            Kind.VAT_ID: "btw-nummers",
            Kind.BIRTHDATE: "geboortedata",
            Kind.POSTCODE: "postcodes",
            Kind.ADDRESS: "adressen",
            Kind.IP: "IP-adressen",
            Kind.HOST: "hostnamen",
            "REDACTED": "geheimen",
        },
        found=(
            ("Mail anna@bouwbedrijf-oost.nl voor de offerte", Kind.EMAIL),
            ("Bel 06-12345678 morgen", Kind.PHONE),
            ("Bel +31 6 1234 5678 morgen", Kind.PHONE),
            ("Bel 0031 (0)6 1234 5678 morgen", Kind.PHONE),
            ("Betaal op NL91 ABNA 0417 1643 00 graag", Kind.IBAN),
            ("Haar BSN is 111222333.", Kind.NATIONAL_ID),
            ("KvK-nummer 12345678 staat op de factuur", Kind.COMPANY_ID),
            ("Btw-nummer NL123456789B01", Kind.VAT_ID),
            ("Zij is geboren op 12-03-1980 in Zwolle", Kind.BIRTHDATE),
            ("Het kantoor zit op 1234 AB in Zwolle", Kind.POSTCODE),
            ("Adres: Hoofdstraat 12, Zwolle", Kind.ADDRESS),
            ("Zie intranet.klant.nl voor het rooster", Kind.HOST),
            ("Jansen Installatietechniek B.V. levert de pomp", Kind.ORG),
            ("Stichting Het Park huurt de zaal", Kind.ORG),
            ("Anna de Vries tekent de offerte", Kind.PERSON),
            ("Mevr. J. Smit tekent de offerte", Kind.PERSON),
            ("De heer Pietersen belt morgen", Kind.PERSON),
            ("Sophie van den Berg is de contactpersoon", Kind.PERSON),
            ("Zie Pieter Bakker voor de sleutel", Kind.PERSON),
            ("Graag t.a.v. Mohammed el Idrissi sturen", Kind.PERSON),
        ),
        left_alone=(
            "Order 123456789 is verzonden",  # nine digits, but nothing says it is a BSN
            "Bestelling 12345678 staat klaar",  # eight digits without KvK nearby
            "Rekening NL12 ABCD 1234 5678 90",  # fails the IBAN check
            "Versie 1.2.3 van Django",
            "Op 12-03-2026 is het overleg",  # a date, no birth date
            "Het Zwolse kantoor",
            "Doel: een offerte van 150 woorden",  # a label, not a speaker
            "Maandag Offerte Bespreken",
            "Draai setup.py en lees README.md",
            "Klant ID 12345 is gesloten",
        ),
    )
)
