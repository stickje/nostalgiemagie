"""Hulpscript voor de scheduled task die de editor-artifact en de repo gelijk houdt.

  python editor_sync.py export <map>
      Schrijft per geplande post (vandaag en later) een JSON-bestand <map>/<datum>.json met de velden
      die in de editor-database horen. Het veld 'foto_bestand' noemt het fotobestand in docs/posts
      (leeg als er geen foto is); dat bestand moet als asset geüpload worden.

  python editor_sync.py toepassen <datum> <bewerking.json> [<nieuwe-foto>|geen]
      Zet een bewerking uit de editor (slides, caption) in docs/posts/<datum>.json.
      Met een fotopad wordt die foto de nieuwe foto van de post; 'geen' haalt de foto weg.
      Daarna: workflow renderen.yml starten met deze datum.
"""
import datetime as dt
import glob
import json
import os
import shutil
import sys

import config, noodrem


def export(uitmap):
    os.makedirs(uitmap, exist_ok=True)
    vandaag = config.vandaag().isoformat()
    for pad in sorted(glob.glob(os.path.join(config.POSTS_DIR, "????-??-??.json"))):
        post = json.load(open(pad, encoding="utf-8"))
        datum = post.get("datum") or os.path.basename(pad)[:10]
        if datum < vandaag or not post.get("slides"):
            continue
        foto = next((s["waarden"].get("foto") for s in post["slides"] if s["waarden"].get("foto")), "") or ""
        doc = {
            "datum": datum, "rubriek": post.get("rubriek", ""), "titel": post.get("titel", ""),
            "status": post.get("status", "klaar"), "caption": post.get("caption", ""),
            "slides": post["slides"], "versie": int(post.get("versie", 1)), "foto_bestand": foto,
        }
        with open(os.path.join(uitmap, f"{datum}.json"), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        print(f"{datum}\tversie {doc['versie']}\tfoto: {foto or '-'}")


def toepassen(datum, bewerking_pad, foto=None):
    post = noodrem.lees(datum)
    if not post:
        sys.exit(f"Geen post voor {datum}")
    if post.get("status") == "geplaatst":
        sys.exit(f"Post van {datum} staat al online")
    bew = json.load(open(bewerking_pad, encoding="utf-8"))
    if "bewerking" in bew:  # hele database-document meegegeven
        bew = bew["bewerking"]

    nieuwe_foto = None
    if foto == "geen":
        nieuwe_foto = ""
    elif foto:
        n = len(glob.glob(os.path.join(config.POSTS_DIR, f"{datum}-eigen-*"))) + 1
        ext = ".png" if foto.lower().endswith(".png") else ".jpg"
        naam = f"{datum}-eigen-{n}{ext}"
        shutil.copyfile(foto, os.path.join(config.POSTS_DIR, naam))
        nieuwe_foto = naam

    oud = {s["template"]: s for s in post["slides"]}
    slides = []
    for s in bew.get("slides") or post["slides"]:
        basis = oud.get(s["template"], {"waarden": {}})
        waarden = {**basis["waarden"], **s.get("waarden", {})}
        if "foto" in basis["waarden"]:
            waarden["foto"] = basis["waarden"]["foto"] if nieuwe_foto is None else nieuwe_foto
        if s["template"] == "dag.html" and str(waarden.get("jaar", "")).isdigit():
            waarden["jaren"] = int(datum[:4]) - int(waarden["jaar"])
        slides.append({"template": s["template"], "waarden": waarden})

    post["slides"] = slides
    if isinstance(bew.get("caption"), str) and bew["caption"].strip():
        post["caption"] = bew["caption"].strip()
    dag = next((s["waarden"] for s in slides if s["template"] == "dag.html"), None)
    if dag and dag.get("kop"):
        post["titel"] = dag["kop"]
    post["aangepast"] = dt.datetime.now(config.TZ).isoformat(timespec="minutes")
    noodrem.bewaar(datum, post)
    print(f"Toegepast op {datum}" + (f", foto: {nieuwe_foto or 'geen'}" if nieuwe_foto is not None else ""))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "export":
        export(sys.argv[2])
    elif len(sys.argv) >= 4 and sys.argv[1] == "toepassen":
        toepassen(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    else:
        sys.exit(__doc__)
