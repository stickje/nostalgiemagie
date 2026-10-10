"""Claude schrijft de posts, uitsluitend op basis van de aangeleverde bronnen."""
import json
import re

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

SYSTEEM = """Je bent de redacteur van Nostalgiemagie, een Nederlandse Instagrampagina die elke dag
een stukje Nederland van vroeger laat zien.

Toon: warm en nuchter, zoals je het aan een vriend vertelt. Geen overdrijving, geen superlatieven,
geen geforceerde grapjes of woordspelingen, geen "Even rekenen" of "Wie kent het niet". Nederlands.

Harde regels:
- Gebruik ALLEEN feiten die letterlijk in de aangeleverde bronnen staan. Weet je iets niet zeker,
  laat het weg. Verzin geen namen, getallen, citaten of details.
- Een kop is jouw eigen formulering in krantenstijl, nooit een citaat uit een echte krant.
- Kies bij voorkeur iets met een Nederlandse link en iets dat mensen van 35+ zich herinneren
  of verrassend vinden. Vermijd onderwerpen met veel doden, oorlogsgeweld of groot leed,
  tenzij het een herdenking is die respectvol kan.
- CAPTION: maximaal 3 korte zinnen in totaal, op één regel na elkaar. Precies één emoji, op een
  passende plek. De laatste zin is een activerende vraag die uitnodigt om te reageren
  (een herinnering, een mening of een keuze), niet steeds "Weet jij dit nog?".
  Geen hashtags in de caption zelf.
- Geef 5 tot 8 Nederlandstalige hashtags zonder #, bijvoorbeeld nostalgie, vroeger.
- Antwoord UITSLUITEND met één geldig JSON-object, zonder uitleg of codeblok."""


def _lees_json(tekst: str) -> dict:
    tekst = re.sub(r"```(?:json)?", "", tekst).strip()
    begin, eind = tekst.find("{"), tekst.rfind("}")
    if begin < 0 or eind < begin:
        raise ValueError("geen JSON in het antwoord")
    return json.loads(tekst[begin: eind + 1])


def _vraag(opdracht: str, pogingen: int = 3) -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    berichten = [{"role": "user", "content": opdracht}]
    fout, tekst = None, ""
    for _ in range(pogingen):
        antwoord = client.messages.create(model=CLAUDE_MODEL, max_tokens=4000, system=SYSTEEM, messages=berichten)
        tekst = "".join(b.text for b in antwoord.content if getattr(b, "type", "") == "text")
        try:
            if antwoord.stop_reason == "max_tokens":
                raise ValueError("antwoord afgekapt")
            return _lees_json(tekst)
        except ValueError as ex:  # json.JSONDecodeError is ook een ValueError
            fout = ex
            print(f"Onbruikbaar antwoord ({ex}): {tekst[:500]!r}")
            berichten = [{"role": "user", "content": opdracht},
                         {"role": "assistant", "content": tekst.strip() or "(leeg)"},
                         {"role": "user", "content": "Dat was geen geldig JSON-object. Antwoord nu uitsluitend met "
                                                     "het gevraagde JSON-object, zonder andere tekst."}]
    kort = " ".join(tekst.split())[:200] or "(leeg antwoord)"
    raise RuntimeError(f"Claude gaf {pogingen}x geen bruikbaar antwoord ({fout}). Begin van het antwoord: {kort}")


def schrijf_dag(datum_tekst: str, huidig_jaar: int, events: list, aantal: int = 3) -> list:
    """Kiest `aantal` verschillende gebeurtenissen en schrijft voor elk een post. Geeft een lijst terug."""
    regels = []
    for i, e in enumerate(events):
        verschil = huidig_jaar - e["jaar"]
        jubileum = " (JUBILEUM)" if verschil in (25, 40, 50, 60, 75, 100) else ""
        regels.append(f"[{i}] {e['jaar']}{jubileum}: {e['tekst']}")
    opdracht = f"""Vandaag is het {datum_tekst} {huidig_jaar}. Dit zijn gebeurtenissen die op deze
datum plaatsvonden, volgens Wikipedia:

{chr(10).join(regels)}

Kies de {aantal} gebeurtenissen die het best passen bij Nostalgiemagie, zo verschillend mogelijk van
elkaar (onderwerp en decennium). Jubilea hebben de voorkeur als ze even goed zijn.
Geef dit JSON-object:
{{"opties": [
  {{"index": <nummer van de gekozen gebeurtenis>,
    "kop": "<kop in krantenstijl, max 8 woorden>",
    "ondertitel": "<1 korte zin voor op de afbeelding, max 120 tekens>",
    "caption": "<caption volgens de regels: max 3 zinnen, 1 emoji, eindigt met een activerende vraag>",
    "hashtags": ["..."],
    "zoekterm": "<2 of 3 Nederlandse zoekwoorden om een archieffoto van precies dit onderwerp te vinden>"}}
  ... in totaal {aantal} opties, elk met een andere index ...
]}}"""
    uit = _vraag(opdracht)
    opties = [o for o in uit.get("opties", []) if isinstance(o, dict) and str(o.get("index", "")).lstrip("-").isdigit()]
    gezien, schoon = set(), []
    for o in opties:
        i = int(o["index"])
        if 0 <= i < len(events) and i not in gezien:
            gezien.add(i)
            schoon.append(o)
    if not schoon:
        raise RuntimeError("Claude gaf geen bruikbare opties")
    return schoon[:aantal]


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
  "tekst": "<2 korte zinnen voor op de afbeelding, max 160 tekens>",
  "caption": "<caption volgens de regels: max 3 zinnen, 1 emoji, eindigt met een activerende vraag>",
  "hashtags": ["..."]}}"""
    return _vraag(opdracht)


def schrijf_raad(foto: dict) -> dict:
    opdracht = f"""Rubriek: Raad het jaar. Volgers zien deze archieffoto zonder jaartal en raden het jaar.
Het juiste jaar is {foto['jaar']}. Beschrijving van de foto volgens het archief:
{foto['beschrijving'] or '(geen beschrijving)'}

Geef dit JSON-object:
{{"hint": "<korte, speelse hint voor op de afbeelding zonder het jaartal of decennium te verraden, max 70 tekens>",
  "caption": "<caption volgens de regels (max 3 zinnen, 1 emoji); noem het jaar NIET; de vraag nodigt uit
               om een gok in de reacties te zetten en daarna te swipen voor het antwoord>",
  "uitleg": "<1 of 2 zinnen voor op de antwoordslide over wat er op de foto te zien is, alleen uit de beschrijving, max 160 tekens>",
  "hashtags": ["..."]}}"""
    return _vraag(opdracht)
