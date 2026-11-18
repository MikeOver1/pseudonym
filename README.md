# pseudonym-nl

Reversible pseudonymisation of Dutch text before it goes to a language model. What leaves carries
placeholders such as `[PERSON_K3J9QX]`, never the names, contact details and numbers the text held;
the model's answer reads back with the real values.

- **Dutch identifiers, checked:** IBAN (mod-97), BSN (eleven test, only with "BSN" or
  "burgerservicenummer" nearby), KvK and btw-nummers, Dutch phone numbers in every notation,
  postcodes, street addresses, birth dates next to "geboren".
- **Names:** people by shape (a first name from a list of about 1,000 Dutch, Flemish and
  international names followed by a surname with its particles, a title such as "mevr." or
  "de heer", a speaker at the start of a line), organisations by their legal form ("B.V.",
  "Stichting") and names you supply: customers, staff, suppliers. Once a name is found, its
  surname and first name on their own are replaced too.
- **Secrets are removed for good:** API tokens, private keys, passwords in URLs, configuration and
  written-out login instructions become `[REDACTED]` and never come back.
- **Stable placeholders:** a keyed HMAC of the value, so the same person is the same placeholder in
  every message of every conversation and nothing about order or count leaks. Notations count as one
  value: `06-12345678` and `+31612345678` share a placeholder.
- **Restores what the model writes back,** also when it mangles the placeholder (`person k3j9qx`),
  and while streaming, with placeholders split over chunks. A placeholder the model invents reads
  back as `[onbekend]`, never as a guess.
- No model, no network, no dependencies: plain Python 3.11+.

## Use

```python
from pseudonym_nl import Matcher, Pseudonymiser, StreamRestorer, organisations, people

known = Matcher.build(people(["Anna de Vries", "Pieter Bakker"]) + organisations(["Veilinghuis Oost B.V."]))
pz = Pseudonymiser(
    key=b"a secret only the server holds",
    level="identifiers",  # "off", "identifiers" or "strict"
    matcher=known,  # optional: names you know
    own_hosts=frozenset({"bakkerijzoet.nl"}),
    never=frozenset({"Bakkerij Zoet", "Claude"}),  # never replaced
)

sent = pz.text("Anna de Vries (06-12345678) vraagt of Veilinghuis Oost op NL91ABNA0417164300 betaalt.")
# '[PERSON_…] ([PHONE_…]) vraagt of [ORG_…] op [IBAN_…] betaalt.'

answer = call_your_model(sent)
print(pz.restore(answer))

# streaming
restorer = StreamRestorer(pz)
for chunk in stream_your_model(sent):
    print(restorer.feed(chunk), end="")
print(restorer.finish())

pz.summary()  # {'IBAN': 1, 'ORG': 1, 'PERSON': 1, 'PHONE': 1}
pz.mapping  # placeholder -> [kind, value]; store it with the conversation
```

To continue a conversation later, create a `Pseudonymiser` with the same key and the stored
`mapping`. Keep both private: the mapping holds the real values.

**Levels:** `identifiers` replaces everything above. `strict` also takes every run of capitalised
words: a person when it opens with a known first name, an organisation otherwise. That catches more,
and also some things that are not names.

## Limits

Pattern-based detection never finds everything: a name without a recognisable first name, title or
legal form, written in lower case, passes at the `identifiers` level. Supply the names you know
(`people`, `organisations`), use `strict` for free text, and treat this as a strong reduction of
what a provider sees, not a guarantee.

## Develop

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
```
