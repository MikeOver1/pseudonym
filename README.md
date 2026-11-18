# pseudonym

Reversible pseudonymisation of text before it goes to a language model. What leaves carries
placeholders such as `[PERSON_K3J9QX]`, never the names, contact details and numbers the text held;
the model's answer reads back with the real values.

Detection is split into a language-neutral core and language packs. **English** (with UK and US
identifiers) and **Dutch** (with Dutch identifiers) ship with it; [CONTRIBUTING.md](CONTRIBUTING.md)
explains how to add another.

- **In every language:** e-mail addresses, IBANs (mod-97), payment cards (Luhn), phone numbers
  written with a country code, EU VAT numbers next to a word like "VAT" or "USt", IP addresses,
  host names, and organisations with an international legal form (GmbH, S.A., Ltd, Inc).
- **Per language:** the country's own identifiers, checked where they carry a check digit and
  counted only next to the words that name them where they don't (a Dutch BSN, a UK National
  Insurance number, a US Social Security number, company numbers); national phone notations,
  postcodes, street addresses, birth dates next to "born" or "geboren"; first names, titles,
  surname particles and legal forms for finding people and organisations by shape.
- **Names:** people by shape (a first name from the language's list followed by a surname, a name
  after a title such as "Mrs." or "de heer", a speaker at the start of a line), organisations by
  their legal form ("Ltd", "B.V.", "Stichting") and names you supply: customers, staff, suppliers.
  Once a name is found, its surname and first name on their own are replaced too.
- **Secrets are removed for good:** API tokens, private keys, passwords in URLs, configuration and
  written-out login instructions become `[REDACTED]` and never come back.
- **Stable placeholders:** a keyed HMAC of the value, so the same person is the same placeholder in
  every message of every conversation and nothing about order or count leaks. Notations count as one
  value: `06-12345678` and `+31 6 1234 5678` share a placeholder.
- **Restores what the model writes back,** also when it mangles the placeholder (`person k3j9qx`),
  and while streaming, with placeholders split over chunks. A placeholder the model invents reads
  back as `[unknown]` (in Dutch `[onbekend]`), never as a guess.
- No model, no network, no dependencies: plain Python 3.11+.

## Use

```python
from pseudonym import Matcher, Pseudonymiser, StreamRestorer, organisations, people

languages = ["en"]  # or ["nl"], ["en", "nl"]; `available()` lists them
known = Matcher.build(people(["Sarah Thompson", "David Okonkwo"], languages) + organisations(["Northwind Traders Ltd"], languages=languages))
pz = Pseudonymiser(
    key=b"a secret only the server holds",
    languages=languages,
    level="identifiers",  # "off", "identifiers" or "strict"
    matcher=known,  # optional: names you know
    own_hosts=frozenset({"example-bakery.com"}),
    never=frozenset({"Example Bakery", "Claude"}),  # never replaced
)

sent = pz.text("Sarah Thompson (020 7946 0018) asks whether Northwind Traders pays into GB82WEST12345698765432.")
# '[PERSON_…] ([PHONE_…]) asks whether [ORG_…] pays into [IBAN_…].'

answer = call_your_model(sent)
print(pz.restore(answer))

# streaming
restorer = StreamRestorer(pz)
for chunk in stream_your_model(sent):
    print(restorer.feed(chunk), end="")
print(restorer.finish())

pz.summary()  # {'IBAN': 1, 'ORG': 1, 'PERSON': 1, 'PHONE': 1}
pz.profile.labels["PHONE"]  # 'phone numbers', in the first language's words
pz.mapping  # placeholder -> [kind, value]; store it with the conversation
```

To continue a conversation later, create a `Pseudonymiser` with the same key and the stored
`mapping`. Keep both private: the mapping holds the real values. Restoring works whichever
languages are active: placeholder kinds (`PERSON`, `NATIONAL_ID`, `POSTCODE`, …) are the same in
every language.

**Languages** are required: name the ones your text is written in. Each adds its first names, words
and rules, so every language you add finds more and also mistakes a little more for a name. A
language's ordinary words also stop the same-spelled first names of another from opening a name by
shape: with English active, "Frank Bakker" and "Mark de Jong" are no longer found that way, with
Dutch alone they are. Secrets are removed in every registered language whichever you name.

**Levels:** `identifiers` replaces everything above. `strict` also takes every run of capitalised
words: a person when it opens with a known first name, an organisation otherwise. That catches more,
and also headings and product names that are not names at all.

## Limits

Pattern-based detection never finds everything: a name without a recognisable first name, title or
legal form, written in lower case, passes at the `identifiers` level, and so does a first name that
is also an ordinary word in an active language ("Will", "Mark", "May"). Supply the names you know
(`people`, `organisations`), use `strict` for free text, and treat this as a strong reduction of
what a provider sees, not a guarantee.

## Develop

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
```
