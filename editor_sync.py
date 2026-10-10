"""Hulpscript voor de scheduled task die de editor-artifact en de repo gelijk houdt.

  python editor_sync.py export <map>
      Schrijft per geplande dag (vandaag en later) een JSON-bestand <map>/<datum>.json met de velden
      voor de editor-database: datum, status, keuze, versie, titel en opties (per optie: rubriek,
      titel, caption, slides, foto_bestand). Op de laatste regel van de uitvoer staat FOTO'S: met
      de fotobestanden in docs/posts die als asset in de editor moeten staan.

  python editor_sync.py toepassen <datum> <bewerking.json> [<nieuwe-foto>|geen]
      Verwerkt een bewerking uit de editor: kiest optie bewerking.optie (0-based) en zet de
      aangepaste slides en caption erin. Met een fotopad wordt die foto de nieuwe foto; 'geen'
      haalt de foto weg. De laatste regel van de uitvoer is:
        RENDER   -> de visual is veranderd: start workflow renderen.yml met deze datum
        GEKOZEN  -> alleen gekozen of alleen de caption aangepast: niets opnieuw te maken
"""
import datetime as dt
import glob
import json
import os
import shutil
import sys

import config, noodrem


def _foto(slides):
    return next((s["waarden"].get("foto") for s in slides if s["waarden"].get("foto")), "") or ""


def export(uitmap):
    os.makedirs(uitmap, exist_ok=True)
    vandaag = config.vandaag().isoformat()
    fotos = []
    for pad in sorted(glob.glob(os.path.join(config.POSTS_DIR, "????-??-??.json"))):
        post = json.load(open(pad, encoding="utf-8"))
        datum = post.get("datum") or os.path.basename(pad)[:10]
        if datum < vandaag or not post.get("opties"):
            continue
        opties = []
        for o in post["opties"]:
            foto = _foto(o["slides"])
            if foto:
                fotos.append(foto)
            opties.append({"rubriek": o.get("rubriek", ""), "titel": o.get("titel", ""), "caption": o.get("caption", ""),
                           "slides": o["slides"], "foto_bestand": foto})
        doc = {"datum": datum, "status": post.get("status", "kiezen"), "keuze": post.get("keuze"),
               "versie": int(post.get("versie", 1)), "titel": post.get("titel", ""), "opties": opties}
        with open(os.path.join(uitmap, f"{datum}.json"), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        print(f"{datum}\t{doc['status']}\tkeuze {doc['keuze']}\tversie {doc['versie']}")
    print("FOTO'S: " + " ".join(sorted(set(fotos))))


def toepassen(datum, bewerking_pad, foto=None):
    post = noodrem.lees(datum)
    if not post or not post.get("opties"):
        sys.exit(f"Geen opties voor {datum}")
    if post.get("status") == "geplaatst":
        sys.exit(f"Post van {datum} staat al online")
    bew = json.load(open(bewerking_pad, encoding="utf-8"))
    if "bewerking" in bew:  # hele database-document meegegeven
        bew = bew["bewerking"]
    index = int(bew.get("optie", post.get("keuze") or 0))
    if not 0 <= index < len(post["opties"]):
        sys.exit(f"Optie {index + 1} bestaat niet voor {datum}")

    origineel = json.dumps(post["opties"][index]["slides"], sort_keys=True)
    noodrem.kies(post, index)

    nieuwe_foto = None
    if foto == "geen":
        nieuwe_foto = ""
    elif foto:
        n = len(glob.glob(os.path.join(config.POSTS_DIR, f"{datum}-eigen-*"))) + 1
        ext = ".png" if foto.lower().endswith(".png") else ".jpg"
        naam = f"{datum}-eigen-{n}{ext}"
        shutil.copyfile(foto, os.path.join(config.POSTS_DIR, naam))
        nieuwe_foto = naam

    if bew.get("slides") or nieuwe_foto is not None:
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
        dag = next((s["waarden"] for s in slides if s["template"] == "dag.html"), None)
        if dag and dag.get("kop"):
            post["titel"] = dag["kop"]
    if isinstance(bew.get("caption"), str) and bew["caption"].strip():
        post["caption"] = bew["caption"].strip()

    post["aangepast"] = dt.datetime.now(config.TZ).isoformat(timespec="minutes")
    noodrem.bewaar_gekozen(post)
    noodrem.bewaar(datum, post)
    veranderd = json.dumps(post["slides"], sort_keys=True) != origineel
    print(f"Optie {index + 1} gekozen voor {datum}" + (f", foto: {nieuwe_foto or 'geen'}" if nieuwe_foto is not None else ""))
    print("RENDER" if veranderd else "GEKOZEN")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "export":
        export(sys.argv[2])
    elif len(sys.argv) >= 4 and sys.argv[1] == "toepassen":
        toepassen(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    else:
        sys.exit(__doc__)
