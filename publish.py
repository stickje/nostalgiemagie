"""Avondrun: controleert de noodrem en plaatst de post op Instagram."""
import json
import os
import sys
import time

import requests

from nm import config, instagram, telegram


def bewaar(pad, post):
    with open(pad, "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=1)


def wacht_op_afbeeldingen(urls):
    for poging in range(10):
        if all(requests.head(u, timeout=20).status_code == 200 for u in urls):
            return True
        time.sleep(30)
    return False


def plaatsen():
    d = config.vandaag().isoformat()
    pad = os.path.join(config.POSTS_DIR, f"{d}.json")
    if not os.path.exists(pad):
        telegram.bericht(f"Er staat geen post klaar voor {d}. Is de ochtendrun gelukt?")
        return 1
    with open(pad, encoding="utf-8") as f:
        post = json.load(f)
    if post.get("status") in ("geplaatst", "overgeslagen"):
        print(f"Al afgehandeld: {post['status']}")
        return 0

    if telegram.is_overgeslagen(d):
        post["status"] = "overgeslagen"
        bewaar(pad, post)
        telegram.bericht(f"Oké, de post van {d} is overgeslagen. Morgen gewoon weer een nieuwe.")
        return 0

    urls = [f"{config.PAGES_URL}/posts/{naam}" for naam in post["afbeeldingen"]]
    if not wacht_op_afbeeldingen(urls):
        telegram.bericht(f"De afbeeldingen van {d} zijn niet online te vinden, dus er is niets geplaatst.\n{urls[0]}")
        return 1

    if config.DRY_RUN:
        post["status"] = "proef"
        bewaar(pad, post)
        telegram.bericht(f"Proefmodus: de post van {d} zou nu geplaatst zijn. Er is niets op Instagram gezet.")
        return 0

    try:
        link = instagram.plaats(urls, post["caption"])
    except Exception as ex:
        telegram.bericht(f"Plaatsen op Instagram mislukt voor {d}.\nFout: {ex}")
        return 1
    post["status"] = "geplaatst"
    post["link"] = link
    bewaar(pad, post)
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
