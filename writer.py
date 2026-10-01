"""Claude schrijft de posts, uitsluitend op basis van de aangeleverde bronnen."""
import json
import re

import anthropic

from .config import ANTHROPIC_API_KEY, CLAUDE_MODEL

SYSTEEM = """Je bent de redacteur van Nostalgiemagie, een Nederlandse Instagrampagina die elke dag
een stukje Nederland van vroeger laat zien.

Toon: warm, licht ironisch en een beetje ondeugend, zoals een oom die op een verjaardag vertelt
hoe het vroeger ging. Nooit belerend, nooit zoetsappig. Korte zinnen. Nederlands.

Harde regels:
- Gebruik ALLEEN feiten die letterlijk in de aangeleverde bronnen staan. Weet je iets niet zeker,
  laat het weg. Verzin geen namen, getallen, citaten of details.
- Een kop is jouw eigen formulering in krantenstijl, nooit een citaat uit een echte krant.
- Kies bij voorkeur iets met een Nederlandse link en iets dat mensen van 35+ zich herinneren
  of verrassend vinden. Vermijd onderwerpen met veel doden, oorlogsgeweld of groot leed,
  tenzij het een herdenking is die respectvol kan.
- De caption eindigt met een vraag aan de volgers, zoals "Weet jij dit nog?" of een variant.
- Geef 5 tot 8 Nederlandstalige hashtags zonder #, bijvoorbeeld nostalgie, vroeger.
- Antwoord UITSLUITEND met één geldig JSON-object, zonder uitleg of codeblok."""


def _vraag(opdracht: str) -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    antwoord = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=SYSTEEM,
        messages=[{"role": "user", "content": opdracht}],
    )
    tekst = "".join(b.text for b in antwoord.content if getattr(b, "type", "") == "text")
    tekst = re.sub(r"```(?:json)?", "", tekst).strip()
    return json.loads(tekst[tekst.index("{"): tekst.rindex("}") + 1])


def schrijf_dag(datum_tekst: str, huidig_jaar: int, events: list) -> dict:
    regels = []
    for i, e in enumerate(events):
        verschil = huidig_jaar - e["jaar"]
        jubileum = " (JUBILEUM)" if verschil in (25, 40, 50, 60, 75, 100) else ""
        regels.append(f"[{i}] {e['jaar']}{jubileum}: {e['tekst']}")
    opdracht = f"""Vandaag is het {datum_tekst} {huidig_jaar}. Dit zijn gebeurtenissen die op deze
datum plaatsvonden, volgens Wikipedia:

{chr(10).join(regels)}

Kies de gebeurtenis die het best past bij Nostalgiemagie. Jubilea hebben de voorkeur als ze even goed zijn.
Geef dit JSON-object:
{{"index": <nummer van de gekozen gebeurtenis>,
  "kop": "<kop in krantenstijl, max 8 woorden>",
  "ondertitel": "<1 of 2 zinnen voor op de afbeelding, max 180 tekens>",
  "caption": "<Instagramcaption van 3 tot 6 korte alinea's, gescheiden door een lege regel>",
  "hashtags": ["..."],
  "zoekterm": "<2 of 3 Nederlandse zoekwoorden om een archieffoto van precies dit onderwerp te vinden>"}}"""
    return _vraag(opdracht)


def schrijf_tv(kandidaten: list) -> dict:
    blokken = [f"[{i}] {k['titel']}\n{k['intro']}" for i, k in enumerate(kandidaten)]
    opdracht = f"""Rubriek: Vergeten TV. Dit zijn Wikipedia-intro's van Nederlandse TV-programma's:

{(chr(10) * 2).join(blokken)}

Kies het programma dat het meest nostalgisch is (bij voorkeur uitgezonden vóór 2005 en bij een groot
publiek bekend). Is geen enkel programma geschikt, geef dan {{"index": -1}}.
Anders dit JSON-object:
{{"index": <nummer>,
  "naam": "<naam van het programma>",
  "omroep_jaren": "<omroep en uitzendjaren zoals in de bron, bv. 'AVRO · 1976–1988', of leeg als onbekend>",
  "tekst": "<2 of 3 zinnen voor op de afbeelding, max 220 tekens>",
  "caption": "<caption van 3 tot 6 korte alinea's>",
  "hashtags": ["..."]}}"""
    return _vraag(opdracht)


def schrijf_raad(foto: dict) -> dict:
    opdracht = f"""Rubriek: Raad het jaar. Volgers zien deze archieffoto zonder jaartal en raden het jaar.
Het juiste jaar is {foto['jaar']}. Beschrijving van de foto volgens het archief:
{foto['beschrijving'] or '(geen beschrijving)'}

Geef dit JSON-object:
{{"hint": "<korte, speelse hint voor op de afbeelding zonder het jaartal of decennium te verraden, max 70 tekens>",
  "caption": "<caption van 2 tot 4 korte alinea's die uitnodigt om te raden; noem het jaar NIET;
               zeg dat ze eerst hun gok in de reacties zetten en dan naar de volgende slide swipen voor het antwoord>",
  "uitleg": "<1 of 2 zinnen voor op de antwoordslide over wat er op de foto te zien is, alleen uit de beschrijving, max 160 tekens>",
  "hashtags": ["..."]}}"""
    return _vraag(opdracht)
