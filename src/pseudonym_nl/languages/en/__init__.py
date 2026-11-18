"""English, with the identifiers of the United Kingdom and the United States."""

import re

from pseudonym_nl.core import DATE, VAT_CONTEXT
from pseudonym_nl.kinds import LABELS, Kind
from pseudonym_nl.language import Language, Rule, first_names, register

US_STATES = "A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY]"
STREET_TYPES = "Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Boulevard|Blvd|Court|Ct|Place|Pl|Way|Close|Crescent|Terrace|Square|Gardens|Grove|Parkway|Highway"

EN = register(
    Language(
        code="en",
        name="English",
        first_names=first_names(__name__),
        not_first_names=frozenset(
            """Will May Mark Bill Frank Grace Hope Joy Faith Rose Dawn Art Guy Rob Sue Pat Chase Rich Just Floor Job
            Bing Jet Summer April June August Penny Ray Max Ruby Amber Sky Story Hunter Victor Kelvin""".split()
        ),
        titles=(r"mr\.?", r"mrs\.?", r"ms\.?", r"mx\.?", r"dr\.?", r"prof\.?", r"(?-i:Miss)", r"(?-i:Sir)", r"(?-i:Dame)", r"(?-i:Lady)", r"(?-i:Lord)", r"attn\.?:?"),
        not_names=frozenset(
            """January February March April May June July August September October November December
            Monday Tuesday Wednesday Thursday Friday Saturday Sunday Today Tomorrow Yesterday Morning Afternoon
            Thanks Regards Cheers Update Updates Notes Meeting Report Review Summary Proposal Quote Invoice Agenda
            Minutes Project Plan Roadmap Street Road Avenue London Manchester Birmingham Leeds Glasgow Edinburgh
            Bristol Liverpool Cardiff Belfast Dublin England Scotland Wales Ireland Britain Kingdom America Canada
            Australia Chicago Boston Seattle Atlanta Texas California Florida Angeles Francisco""".split()
        ),
        empty_values=frozenset("unknown various internal private customer customers guest guests client clients company other none tbc tba family individual".split()),
        org_suffixes=(r"Ltd\.?", r"Limited", r"LLP", r"LLC", r"Inc\.?", r"Corp\.?", r"Corporation", r"Co\.", r"PLC", r"Group", r"Holdings", r"Foundation"),
        org_prefixes=("University of", "Bank of"),
        org_joiners=("and", "of", "the"),
        rules=(
            # UK: 0 and ten digits; US: area code, exchange and line, written with separators
            Rule(Kind.PHONE, re.compile(r"(?<![\w+])(?:0044[\s\-.]?(?:\(0\)[\s\-.]?)?|0)(?:\d[\s\-.]?){9}\d(?!\d)")),
            Rule(Kind.PHONE, re.compile(r"(?<![\w+])(?:1[\s\-.])?\(?[2-9]\d{2}\)?[\s\-.]\d{3}[\s\-.]\d{4}(?!\d)")),
            Rule(Kind.NATIONAL_ID, re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),  # US social security number
            Rule(Kind.NATIONAL_ID, re.compile(r"\b(?!000|666|9\d\d)\d{9}\b"), context=re.compile(r"(?i)\b(?:ssn|social security)")),
            Rule(Kind.NATIONAL_ID, re.compile(r"\b(?!BG|GB|KN|NK|NT|TN|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z] ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b")),  # UK National Insurance
            Rule(
                Kind.COMPANY_ID,
                re.compile(r"\b(?:\d{8}|(?:SC|NI|OC|SO|NC|FC)\d{6})\b"),
                context=re.compile(r"(?i)\b(?:company (?:no|number|reg)|companies house|registered in (?:england|scotland|wales)|crn)"),
            ),
            Rule(Kind.COMPANY_ID, re.compile(r"\b\d{2}-\d{7}\b"), context=re.compile(r"(?i)\b(?:ein|fein|employer identification|federal tax id)\b")),
            Rule(Kind.VAT_ID, re.compile(r"\bGB ?\d{3} ?\d{4} ?\d{2}(?: ?\d{3})?\b"), context=VAT_CONTEXT),
            Rule(Kind.BIRTHDATE, DATE, context=re.compile(r"(?i)\b(?:born|date of birth|birth ?date|birthday|dob|d\.o\.b)")),
            Rule(Kind.POSTCODE, re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b")),  # UK
            Rule(Kind.POSTCODE, re.compile(rf"\b(?:{US_STATES}) \d{{5}}(?:-\d{{4}})?\b")),  # US: a ZIP code counts after its state
            Rule(Kind.ADDRESS, re.compile(rf"\b\d{{1,5}}[A-Za-z]?\s+(?:[A-Z][a-z]+\s+){{1,3}}(?:{STREET_TYPES})\b\.?")),
        ),
        phone_prefixes=(("44", "0"), ("1", "")),
        tlds=frozenset({"uk", "us", "ie", "ca", "au", "nz"}),
        public_hosts=frozenset({"gov.uk", "nhs.uk", "police.uk", "gov.ie", "gc.ca", "gov.au", "bbc.co.uk", "google.co.uk"}),
        unknown="[unknown]",
        labels=LABELS,
        found=(
            ("Email john.smith@acme-widgets.com about the quote", Kind.EMAIL),
            ("Call 020 7946 0018 tomorrow", Kind.PHONE),
            ("Call +44 20 7946 0018 tomorrow", Kind.PHONE),
            ("Call (415) 555-0132 after lunch", Kind.PHONE),
            ("Pay into GB82 WEST 1234 5698 7654 32 please", Kind.IBAN),
            ("Her SSN is 123-45-6789.", Kind.NATIONAL_ID),
            ("NI number AB 12 34 56 C is on file", Kind.NATIONAL_ID),
            ("Company number 12345678 is on the invoice", Kind.COMPANY_ID),
            ("EIN 12-3456789 is on the form", Kind.COMPANY_ID),
            ("VAT number GB 123 4567 89", Kind.VAT_ID),
            ("She was born on 14 March 1985 in Leeds", Kind.BIRTHDATE),
            ("Date of birth: 03/14/1985", Kind.BIRTHDATE),
            ("The office is at SW1A 1AA in London", Kind.POSTCODE),
            ("Ship it to Springfield, IL 62704", Kind.POSTCODE),
            ("Address: 221B Baker Street, London", Kind.ADDRESS),
            ("See intranet.client.co.uk for the rota", Kind.HOST),
            ("Acme Widgets Ltd supplies the parts", Kind.ORG),
            ("Smith & Jones LLP sent the contract", Kind.ORG),
            ("Sarah Thompson signs the contract", Kind.PERSON),
            ("Mrs. J. Patel will sign", Kind.PERSON),
            ("Dr Okafor calls tomorrow", Kind.PERSON),
            ("Ask James O'Brien about the key", Kind.PERSON),
            ("Ask Graham McDonald about the key", Kind.PERSON),
            ("Emily Clarke: we agreed on Friday", Kind.PERSON),
        ),
        left_alone=(
            "Order 123456789 has shipped",
            "Version 1.2.3 of Django",
            "On 12/03/2026 we meet",  # a date, no birth date
            "Mark Complete when done",
            "May Day Plans",
            "Max Retries Exceeded",
            "Grace Period Ends Friday",
            "The Monday Meeting Notes",
            "Run setup.py and read README.md",
            "Thanks, Team",
            "I miss Paris already",
            "Error 404 at line 12",
            "user.id and request.ip are logged",
        ),
    )
)
