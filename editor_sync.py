"""Hulpscript voor de scheduled task die de editor-artifact en de repo gelijk houdt.

  python editor_sync.py export <map>
      Schrijft per geplande dag (vandaag en later) een JSON-bestand <map>/<datum>.json met de velden
      voor de editor-database: datum, status, keuze, versie, titel en opties (per optie: rubriek,
      titel, caption, slides, foto_bestand). Op de laatste regel van de uitvoer staat FOTO'S: met
      de fotobestanden (ook die van swipes, foto's en video's) in docs/posts die als asset in de
      editor moeten staan.

  python editor_sync.py toepassen <datum> <bewerking.json> [<nieuwe-foto>|geen|-] [--assets <map>]
      Verwerkt een bewerking uit de editor: kiest optie bewerking.optie (0-based) en zet de
      aangepaste slides en caption erin. Met een fotopad wordt die foto de nieuwe hoofdfoto; 'geen'
      haalt de foto weg; '-' of weglaten = hoofdfoto ongewijzigd.
      --assets <map>: map met de opgehaalde editor-assets, als <asset-id>.<ext>. Daaruit komen
      de hoofdfoto (bewerking.foto_asset_id, als er geen fotopad is meegegeven) en nieuwe swipes
      (slides met template swipe.html en waarden.asset_id).
      Per overgenomen asset staat er een regel 'ASSET <asset-id> <bestand>' in de uitvoer: dat
      bestand staat al als dat asset in de editor (foto_urls.<bestand> = /_blob/<asset-id>).
      De laatste regel van de uitvoer is:
        RENDER   -> de visual is veranderd: start workflow renderen.yml met deze datum
        GEKOZEN  -> alleen gekozen of alleen de caption aangepast: niets opnieuw te maken
"""
import datetime as dt
import glob
import json
import os
import re
import shutil
import sys

import config, noodrem

SWIPE = "swipe.html"
MAX_SLIDES = 10  # Instagram-carrousel
FOTO_EXT = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXT = (".mp4", ".webm", ".mov", ".m4v")
# Waarden die de editor alleen voor het voorbeeld gebruikt en niet in de repo horen.
TIJDELIJK = ("asset_id", "foto_url", "foto_block", "url")


def _foto(slides):
    """Hoofdfoto: de eerste foto op een slide die geen swipe is."""
    return next((s["waarden"].get("foto") for s in slides
                 if s.get("template") != SWIPE and s["waarden"].get("foto")), "") or ""


def _alle_fotos(slides):
    return [s["waarden"]["foto"] for s in slides if s["waarden"].get("foto")]


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
            fotos += [f for f in _alle_fotos(o["slides"]) if os.path.exists(os.path.join(config.POSTS_DIR, f))]
            opties.append({"rubriek": o.get("rubriek", ""), "titel": o.get("titel", ""), "caption": o.get("caption", ""),
                           "slides": o["slides"], "foto_bestand": _foto(o["slides"])})
        doc = {"datum": datum, "status": post.get("status", "kiezen"), "keuze": post.get("keuze"),
               "versie": int(post.get("versie", 1)), "titel": post.get("titel", ""), "opties": opties}
        with open(os.path.join(uitmap, f"{datum}.json"), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        print(f"{datum}\t{doc['status']}\tkeuze {doc['keuze']}\tversie {doc['versie']}")
    print("FOTO'S: " + " ".join(sorted(set(fotos))))


def _asset_pad(assets, asset_id):
    if not assets or not asset_id or not re.fullmatch(r"[0-9a-f]{32}", str(asset_id)):
        return None
    for pad in glob.glob(os.path.join(assets, f"{asset_id}.*")):
        return pad
    return None


def _kopieer(bron, datum, soort):
    """Kopieert een geüpload bestand naar docs/posts/<datum>-<soort>-<n>.<ext> en geeft de naam terug."""
    ext = os.path.splitext(bron)[1].lower()
    if ext == ".jpeg":
        ext = ".jpg"
    if ext not in FOTO_EXT + VIDEO_EXT:
        sys.exit(f"Bestandstype {ext or '?'} wordt niet ondersteund")
    n = len(glob.glob(os.path.join(config.POSTS_DIR, f"{datum}-{soort}-*"))) + 1
    while glob.glob(os.path.join(config.POSTS_DIR, f"{datum}-{soort}-{n}.*")):
        n += 1
    naam = f"{datum}-{soort}-{n}{ext}"
    shutil.copyfile(bron, os.path.join(config.POSTS_DIR, naam))
    return naam


def _schoon(waarden):
    return {k: v for k, v in waarden.items() if k not in TIJDELIJK}


def toepassen(datum, bewerking_pad, foto=None, assets=None):
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
    overgenomen = []  # (asset-id, bestand)

    # Hoofdfoto
    nieuwe_foto = None
    asset_id = bew.get("foto_asset_id")
    if foto == "geen" or (not foto and asset_id == "geen"):
        nieuwe_foto = ""
    elif foto and foto != "-":
        nieuwe_foto = _kopieer(foto, datum, "eigen")
        if asset_id and asset_id != "geen":
            overgenomen.append((asset_id, nieuwe_foto))
    elif asset_id:
        pad = _asset_pad(assets, asset_id)
        if not pad:
            sys.exit(f"Foto {asset_id} niet gevonden in de opgehaalde assets")
        nieuwe_foto = _kopieer(pad, datum, "eigen")
        overgenomen.append((asset_id, nieuwe_foto))
    if nieuwe_foto and os.path.splitext(nieuwe_foto)[1] in VIDEO_EXT:
        sys.exit("De hoofdfoto moet een foto zijn; een video kan alleen als swipe")

    if bew.get("slides") or nieuwe_foto is not None:
        bestaand = [s for s in post["slides"] if s["template"] != SWIPE]
        oud = {}
        for s in bestaand:
            oud.setdefault(s["template"], s)
        voorblad, swipes = [], []
        for s in bew.get("slides") or post["slides"]:
            w_in = s.get("waarden", {}) or {}
            if s.get("template") == SWIPE:
                w = _schoon(w_in)
                if w_in.get("asset_id"):
                    pad = _asset_pad(assets, w_in["asset_id"])
                    if not pad:
                        sys.exit(f"Swipe {w_in['asset_id']} niet gevonden in de opgehaalde assets")
                    w["foto"] = _kopieer(pad, datum, "swipe")
                    overgenomen.append((w_in["asset_id"], w["foto"]))
                if not w.get("foto") or not os.path.exists(os.path.join(config.POSTS_DIR, w["foto"])):
                    sys.exit("Een swipe heeft geen foto of video")
                w["soort"] = "video" if os.path.splitext(w["foto"])[1].lower() in VIDEO_EXT else "foto"
                swipes.append({"template": SWIPE, "waarden": w})
                continue
            basis = oud.get(s["template"], {"waarden": {}})
            waarden = {**basis["waarden"], **_schoon(w_in)}
            if "foto" in basis["waarden"]:
                waarden["foto"] = basis["waarden"]["foto"] if nieuwe_foto is None else nieuwe_foto
            if s["template"] == "dag.html" and str(waarden.get("jaar", "")).isdigit():
                waarden["jaren"] = int(datum[:4]) - int(waarden["jaar"])
            voorblad.append({"template": s["template"], "waarden": waarden})
        if not voorblad:
            sys.exit("De post heeft geen voorblad meer")
        slides = voorblad + swipes
        if len(slides) > MAX_SLIDES:
            sys.exit(f"Te veel slides ({len(slides)}); Instagram staat er maximaal {MAX_SLIDES} toe")
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
    print(f"Optie {index + 1} gekozen voor {datum}" + (f", foto: {nieuwe_foto or 'geen'}" if nieuwe_foto is not None else "")
          + (f", swipes: {sum(s['template'] == SWIPE for s in post['slides'])}" if bew.get("slides") else ""))
    for aid, bestand in overgenomen:
        print(f"ASSET {aid} {bestand}")
    print("RENDER" if veranderd else "GEKOZEN")


if __name__ == "__main__":
    args = sys.argv[1:]
    assets = None
    if "--assets" in args:
        i = args.index("--assets")
        if i + 1 >= len(args):
            sys.exit("--assets heeft een map nodig")
        assets = args[i + 1]
        del args[i:i + 2]
    if len(args) >= 2 and args[0] == "export":
        export(args[1])
    elif len(args) >= 3 and args[0] == "toepassen":
        toepassen(args[1], args[2], args[3] if len(args) > 3 else None, assets)
    else:
        sys.exit(__doc__)
