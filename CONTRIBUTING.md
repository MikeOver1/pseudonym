# Contributing

Bug reports with a sentence that was missed or wrongly replaced are the most useful contribution:
put the text, the languages and the level in the issue. Never paste real personal data; invent a
name and use a documented test number.

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## How detection is organised

| Module | Holds |
| --- | --- |
| `kinds.py` | The closed set of placeholder kinds: `PERSON`, `ORG`, `PHONE`, `NATIONAL_ID`, … |
| `language.py` | `Language` (plain data), `Rule` (one identifier pattern), the registry, and `Profile`: the active languages merged with the core and compiled. |
| `core.py` | `CORE`, the language-neutral part: e-mail, IBAN, cards, international phone numbers, EU VAT, IP addresses, generic top-level domains, international legal forms. |
| `languages/<code>/` | One pack per language: `__init__.py` with a `Language`, and `first_names.txt`. |
| `names.py` | Finding people, organisations, hosts and identifiers with a `Profile`. |
| `known.py` | Names you supply, and the forms a text writes them in. |
| `redact.py` | Secrets, removed for good. |
| `engine.py` | `Pseudonymiser` and `StreamRestorer`. |

## Adding a language

A language is data, not code: you fill in a `Language` and the engine does the rest. English
(`languages/en`) and Dutch (`languages/nl`) are complete examples to copy from.

1. **Create the pack.** Copy `languages/en/` to `languages/<code>/`, using the ISO 639-1 code
   (`de`, `fr`, `pl`). Set `code` and `name` (in the language itself: "Deutsch").

2. **First names** go in `first_names.txt`, whitespace-separated, capitalised as written, with
   accents. Include the names common among the people who write and are written about in that
   language, not only the traditional ones. Leave out names that are also ordinary capitalised
   words in your language and put those in `not_first_names` instead (English leaves out "Will",
   "May", "Mark"): they would turn every sentence that starts with them into a name. When the list
   is large enough to be noisy, measure it on real prose (see step 7).

3. **Words around names:**
   - `particles`: lower-case surname particles ("von", "zu" in German; "de", "du" in French).
   - `titles`: regex fragments matched case-insensitively ("herr", "frau", r"dr\.?"). Wrap a title
     that is also a common word in `(?-i:…)` to require its capital, as English does with "Miss".
   - `not_names`: capitalised words that end no name: months, weekdays, cities, words like
     "Meeting" or "Rechnung" that follow a first name in headings.
   - `empty_values`: lower-case values in a customer or contact field that name nobody
     ("unbekannt", "privat").

4. **Organisations:** `org_suffixes` are regex fragments for legal forms after a name
   (r"GmbH", r"e\.\s?V\."); `org_prefixes` are words that open one ("Stiftung", "Verein");
   `org_joiners` are the lower-case words inside a name ("und", "für"). Forms used across many
   countries (GmbH, S.A., Ltd, Inc) are already in `CORE`.

5. **Identifiers** are `Rule`s: a kind from `kinds.py`, a pattern, and optionally a `check` and a
   `context`.
   - Give a `check` for every number with a check digit (IBAN-style mod-97, Luhn, the Dutch eleven
     test): an arbitrary number then does not count.
   - Give a `context` for every number that has no check and no distinctive shape: it then counts
     only when one of those words occurs in the 60 characters before it ("KvK", "company number").
   - **Bound every repetition** (`{0,5}`, not `*` or `+`) where the pattern can match across words.
     A pattern that can backtrack over a whole text makes long texts take minutes instead of
     milliseconds; the test suite runs every pack over 20,000 capitalised words to catch this.
   - National phone notations go in `rules`; give the country code and trunk prefix in
     `phone_prefixes` (`("49", "0")`) so `+49 30 1234567` and `030 1234567` share a placeholder.
   - Birth dates: use `core.DATE` with your language's words for "born" as `context`.
   - Country top-level domains go in `tlds`, public-sector hosts that identify no one in
     `public_hosts`.

6. **Secrets and presentation:** `password_labels` and `login_words` are the words that announce a
   password ("Passwort", r"melden Sie sich an"). `labels` names each kind for people
   (`Kind.PHONE: "Telefonnummern"`), `unknown` is what an invented placeholder reads back as
   ("[unbekannt]").

7. **Examples are the tests.** Fill `found` with sentences that each hold one identifier, name or
   organisation, paired with its kind, and `left_alone` with sentences that only look like they
   hold one: a number without its context word, a heading that starts with a first name, a file
   name with a country's domain. `tests/test_languages.py` runs every registered pack's examples
   with the pack alone and with every other language active, so a rule that clashes with another
   language shows up. Add a prose test like `test_english_prose_loses_its_people_and_nothing_else`
   when the language capitalises much.

8. **Register it** by importing the module in `languages/__init__.py`, then run the tests.

## Countries that share a language

Names belong to a language; identifiers, phone numbers and postcodes belong to a country. A pack is
named after its language and holds the identifiers of the country it is mostly written in: `nl` has
Dutch numbers, `en` British and American ones.

For another country that writes the same language, add a pack with only what differs and the
country's code: `languages/nl_be/` with `code="nl-BE"`, holding Belgian rules (rijksregisternummer,
KBO/BCE number, `+32`, Belgian postcodes) and no names. It is used together with its language:
`Pseudonymiser(key, languages=["nl", "nl-BE"])`. Its `found` examples then contain identifiers only,
since names come from the language pack.

## Packs outside this repository

`register()` makes any `Language` available by its code, so a pack can live in your own package:

```python
from pseudonym import Language, register

register(Language(code="x-acme", name="Acme jargon", not_names=frozenset({"Widget", "Sprocket"})))
```

A `Language` object can also be passed directly: `Pseudonymiser(key, languages=["en", MY_PACK])`.

## A new kind

The placeholder kinds are a closed set, so restoring recognises a placeholder whichever languages are
active and so that ordinary words are not taken for one. If no kind fits your identifier, propose a
new one in `kinds.py` in its own pull request; most national numbers fit `NATIONAL_ID`,
`COMPANY_ID` or `VAT_ID`.
