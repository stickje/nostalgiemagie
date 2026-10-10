"""Avondrun: controleert de noodrem en plaatst de post op Instagram."""
import sys
import time

import requests

import config, instagram, noodrem, telegram


def wacht_op_afbeeldingen(urls):
    for poging in range(10):
        if all(requests.head(u, timeout=20).status_code == 200 for u in urls):
            return True
        time.sleep(30)
    return False


def plaatsen():
    d = config.vandaag().isoformat()
    noodrem.verwerken()
    post = noodrem.lees(d)
    if not post:
        telegram.bericht(f"Er staat geen post klaar voor {d}. Is de ochtendrun gelukt?")
        return 1
    if post.get("status") in ("geplaatst", "overgeslagen", "geen keuze"):
        print(f"Al afgehandeld: {post['status']}")
        return 0
    if post.get("status") == "kiezen" or not post.get("afbeeldingen"):
        post["status"] = "geen keuze"
        noodrem.bewaar(d, post)
        telegram.bericht(f"Je hebt voor vandaag ({d}) geen optie gekozen, dus er is niets geplaatst.")
        return 0

    urls = [f"{config.PAGES_URL}/posts/{naam}" for naam in post["afbeeldingen"]]
    if not wacht_op_afbeeldingen(urls):
        telegram.bericht(f"De afbeeldingen van {d} zijn niet online te vinden, dus er is niets geplaatst.\n{urls[0]}")
        return 1

    if config.DRY_RUN:
        post["status"] = "proef"
        noodrem.bewaar(d, post)
        telegram.bericht(f"Proefmodus: de post van {d} zou nu geplaatst zijn. Er is niets op Instagram gezet.")
        return 0

    try:
        link = instagram.plaats(urls, post["caption"])
    except Exception as ex:
        telegram.bericht(f"Plaatsen op Instagram mislukt voor {d}.\nFout: {ex}")
        return 1
    post["status"] = "geplaatst"
    post["link"] = link
    noodrem.bewaar(d, post)
    telegram.bericht(f"Geplaatst! {link}")
    return 0


def main():
    code = plaatsen()
    nieuw = instagram.vernieuw_token()
    if nieuw and nieuw != config.IG_ACCESS_TOKEN:
        print(f"::add-mask::{nieuw}")
        with open("new_token.txt", "w") as f:
            f.write(nieuw)
    sys.exit(code)


if __name__ == "__main__":
    main()
