"""Status van ingeplande posts: kiezen tussen opties en de noodrem (overslaan via Telegram).

Een dag-bestand docs/posts/<datum>.json heeft:
  opties  lijst van posts (rubriek, titel, caption, slides, afbeeldingen, controle)
  keuze   index van de gekozen optie, of None
  status  'kiezen' (nog geen keuze), 'klaar', 'overgeslagen', 'geplaatst', 'proef', 'geen keuze'
Na een keuze staan de velden van de gekozen optie ook bovenaan (slides, caption, afbeeldingen, ...),
zodat plaatsen en opnieuw maken alleen naar de bovenste velden hoeven te kijken.
"""
import datetime as dt
import json
import os

import config, telegram

OPTIEVELDEN = ("rubriek", "titel", "caption", "slides", "afbeeldingen")


def pad(datum: str) -> str:
    return os.path.join(config.POSTS_DIR, f"{datum}.json")


def lees(datum: str) -> dict | None:
    if not os.path.exists(pad(datum)):
        return None
    with open(pad(datum), encoding="utf-8") as f:
        return json.load(f)


def bewaar(datum: str, post: dict):
    with open(pad(datum), "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=1)


def kies(post: dict, index: int) -> dict:
    """Maakt optie `index` (0-based) de gekozen post."""
    optie = post["opties"][index]
    post["keuze"] = index
    for veld in OPTIEVELDEN:
        if veld in optie:
            post[veld] = optie[veld]
    if post.get("status") in ("kiezen", "geen keuze", "overgeslagen", None):
        post["status"] = "klaar"
    return post


def bewaar_gekozen(post: dict):
    """Schrijft de bovenste velden terug in de gekozen optie (na een aanpassing)."""
    if post.get("keuze") is not None and post.get("opties"):
        optie = post["opties"][post["keuze"]]
        for veld in OPTIEVELDEN:
            if veld in post:
                optie[veld] = post[veld]
    return post


def verwerken():
    """Haalt keuzes en overslaan-verzoeken uit Telegram en legt ze vast in het bestand van die dag.

    Werkt ook voor dagen later in de week: de keuze blijft in het JSON-bestand van die dag staan.
    """
    vandaag = config.vandaag().isoformat()
    verzoek = telegram.verzoeken(vandaag)

    for datum, n in sorted(verzoek["kies"].items()):
        label = config.dag_label(dt.date.fromisoformat(datum))
        post = lees(datum)
        if not post or not post.get("opties"):
            telegram.bericht(f"Voor {label} staan geen opties klaar.")
        elif post.get("status") == "geplaatst":
            telegram.bericht(f"De post van {label} staat al online; je keuze is niet meer veranderd.")
        elif not 1 <= n <= len(post["opties"]):
            telegram.bericht(f"Optie {n} bestaat niet voor {label}.")
        else:
            kies(post, n - 1)
            verzoek["overslaan"].discard(datum)  # in dezelfde batch gekozen én overgeslagen: kiezen gaat voor
            bewaar(datum, post)
            telegram.bericht(f"Optie {n} gekozen voor {label}: {post.get('titel', '')}. "
                             "Die gaat die dag om 18.00 uur online.", knop_datum=datum)

    for datum in sorted(verzoek["overslaan"]):
        label = config.dag_label(dt.date.fromisoformat(datum))
        post = lees(datum)
        if not post:
            telegram.bericht(f"Voor {label} staat nog geen post klaar, dus er valt niets over te slaan.")
        elif post.get("status") == "geplaatst":
            telegram.bericht(f"De post van {label} staat al online. Verwijder hem zo nodig in Instagram zelf.")
        elif post.get("status") != "overgeslagen":
            post["status"] = "overgeslagen"
            bewaar(datum, post)
            telegram.bericht(f"Oké, de post van {label} wordt overgeslagen. Kies alsnog een optie om dat ongedaan te maken.")
