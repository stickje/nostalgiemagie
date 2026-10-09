"""Status van ingeplande posts en de noodrem (overslaan via Telegram)."""
import datetime as dt
import json
import os

import config, telegram


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


def verwerken():
    """Haalt overslaan-verzoeken uit Telegram en zet die posts op 'overgeslagen'.

    Werkt ook voor posts die pas later in de week online gaan: de keuze wordt
    in het JSON-bestand van die dag bewaard.
    """
    vandaag = config.vandaag().isoformat()
    for datum in sorted(telegram.overslaan_verzoeken(vandaag)):
        label = config.dag_label(dt.date.fromisoformat(datum))
        post = lees(datum)
        if not post:
            telegram.bericht(f"Voor {label} staat nog geen post klaar, dus er valt niets over te slaan.")
        elif post.get("status") == "geplaatst":
            telegram.bericht(f"De post van {label} staat al online. Verwijder hem zo nodig in Instagram zelf.")
        elif post.get("status") != "overgeslagen":
            post["status"] = "overgeslagen"
            bewaar(datum, post)
            telegram.bericht(f"Oké, de post van {label} wordt overgeslagen.")
