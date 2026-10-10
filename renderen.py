"""Maakt de visual(s) van een geplande post opnieuw, op basis van de waarden in docs/posts/<datum>.json.

Gebruikt na een aanpassing in de editor: de nieuwe teksten en foto staan dan al in de JSON.
"""
import os
import sys

import config, noodrem, render, telegram


def main():
    datum = os.environ.get("DATUM", "").strip()
    post = noodrem.lees(datum) if datum else None
    if not post:
        print(f"Geen post gevonden voor '{datum}'")
        return 1
    if post.get("status") == "geplaatst":
        telegram.bericht(f"De post van {datum} staat al online, dus die is niet opnieuw gemaakt.")
        return 1
    if not post.get("slides"):
        telegram.bericht(f"Voor {datum} is nog geen optie gekozen, dus er valt niets opnieuw te maken.")
        return 1

    versie = int(post.get("versie", 1)) + 1
    optie = (post.get("keuze") or 0) + 1
    basis = os.path.join(config.POSTS_DIR, f"{datum}-o{optie}-v{versie}")
    oud = [os.path.join(config.POSTS_DIR, n) for n in post.get("afbeeldingen", [])]
    paden = render.render(post["slides"], basis)
    for pad in oud:  # vorige versie opruimen (de foto's zelf blijven staan)
        if pad not in paden and os.path.exists(pad):
            os.remove(pad)

    post.update(afbeeldingen=[os.path.basename(p) for p in paden], versie=versie)
    if post.get("status") != "overgeslagen":
        post["status"] = "klaar"
    noodrem.bewaar_gekozen(post)
    noodrem.bewaar(datum, post)
    telegram.voorbeeld(paden, post["caption"], datum, post["rubriek"],
                       f"Dit is de aangepaste versie van optie {optie}, en die is nu gekozen.")
    print(f"Opnieuw gemaakt: {datum} (versie {versie})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
