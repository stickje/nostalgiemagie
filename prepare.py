"""Ochtendrun: maakt de post van vandaag en stuurt een voorbeeld naar Telegram."""
import datetime as dt
import glob
import html
import json
import os
import random
import sys
import traceback

from nm import config, render, sources, telegram, writer

JUBILEA = (25, 40, 50, 60, 75, 100)


def laad_state():
    with open(config.STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def bewaar_state(state):
    for k in state:
        state[k] = state[k][-500:]
    with open(config.STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def foto_credit(foto):
    return f"Foto: {foto['maker']} / Nationaal Archief ({foto['licentie']})"


def maak_dag(d, state):
    events, bron = sources.gebeurtenissen(d, max_jaar=d.year - 15)
    events = [e for e in events if f"{e['jaar']}:{e['tekst'][:40]}" not in state["events"]]
    if not events:
        raise RuntimeError("Geen gebeurtenissen gevonden op Wikipedia")
    jubilea = [e for e in events if d.year - e["jaar"] in JUBILEA]
    rest = [e for e in events if e not in jubilea]
    random.shuffle(rest)
    kandidaten = (jubilea + rest)[:40]

    uit = writer.schrijf_dag(config.datum_lang(d), d.year, kandidaten)
    e = kandidaten[int(uit["index"])]

    foto = None
    try:
        fotos = sources.archieffotos(uit.get("zoekterm", ""), jaar=e["jaar"], al_gebruikt=state["fotos"])
        foto = fotos[0] if fotos else None
    except Exception as ex:
        print(f"Geen foto gevonden: {ex}")

    if foto:
        foto_block = f'<div class="foto" style="background-image:url(\'{html.escape(foto["url"])}\')"></div>'
        bron_beeld = f"Bron: Wikipedia · {foto_credit(foto)}"
    else:
        foto_block = f'<div class="foto leeg"><span>{e["jaar"]}</span></div>'
        bron_beeld = "Bron: Wikipedia"

    waarden = {
        "datum": f"{config.DAGEN[d.weekday()].capitalize()} {config.datum_lang(d)} {e['jaar']}",
        "kop": uit["kop"], "kop_size": render.kopgrootte(uit["kop"]),
        "ondertitel": uit["ondertitel"], "jaren": d.year - e["jaar"],
        "foto_block": foto_block, "bron": bron_beeld,
    }
    controle = f"Wikipedia ({e['jaar']}): {e['tekst']}\n{bron}"
    if foto:
        controle += f"\n\nFoto ({foto['jaar']}): {foto['beschrijving'] or 'geen beschrijving'}\n{foto['pagina']}"
        state["fotos"].append(foto["titel"])
    state["events"].append(f"{e['jaar']}:{e['tekst'][:40]}")
    bronregels = [f"Bron: Wikipedia, {config.datum_lang(d)}"] + ([foto_credit(foto)] if foto else [])
    return {"rubriek": "Op deze dag", "slides": [("dag.html", waarden)], "uit": uit,
            "bronregels": bronregels, "controle": controle}


def maak_tv(d, state):
    kandidaten = sources.tv_kandidaten(5, state["tv"])
    if not kandidaten:
        raise RuntimeError("Geen TV-programma's gevonden")
    uit = writer.schrijf_tv(kandidaten)
    if int(uit.get("index", -1)) < 0:
        raise RuntimeError("Geen geschikt TV-programma tussen de kandidaten")
    k = kandidaten[int(uit["index"])]
    state["tv"].append(k["titel"])
    waarden = {
        "datum": d.strftime("%d-%m-%Y"), "naam": uit["naam"],
        "kop_size": render.kopgrootte(uit["naam"], 96, 80, 64),
        "omroep_jaren": uit.get("omroep_jaren", ""), "tekst": uit["tekst"],
    }
    controle = f"{k['titel']}:\n{k['intro'][:700]}\n{k['bron']}"
    return {"rubriek": "Vergeten TV", "slides": [("tv.html", waarden)], "uit": uit,
            "bronregels": [f"Bron: Wikipedia, {k['titel']}"], "controle": controle}


def maak_raad(d, state):
    foto = None
    for jaar in random.sample(range(1950, 1990), 6):
        try:
            fotos = sources.archieffotos(str(jaar), jaar=jaar, al_gebruikt=state["fotos"])
        except Exception as ex:
            print(f"Zoeken mislukt voor {jaar}: {ex}")
            continue
        if fotos:
            foto = random.choice(fotos[:8])
            break
    if not foto:
        raise RuntimeError("Geen geschikte archieffoto gevonden")
    state["fotos"].append(foto["titel"])
    uit = writer.schrijf_raad(foto)

    juist = foto["jaar"]
    fout = random.sample([juist + x for x in range(-14, 15) if abs(x) >= 3 and juist + x < d.year], 2)
    opties = [juist] + fout
    random.shuffle(opties)
    letter = "ABC"[opties.index(juist)]
    vraag = {"foto_url": foto["url"], "hint": uit["hint"], "a": opties[0], "b": opties[1], "c": opties[2]}
    antwoord = {"jaar": juist, "letter": letter, "uitleg": uit.get("uitleg", ""), "credit": foto_credit(foto)}
    controle = f"Juiste jaar volgens archief: {juist} (antwoord {letter})\n{foto['beschrijving'] or 'geen beschrijving'}\n{foto['pagina']}"
    return {"rubriek": "Raad het jaar", "slides": [("raad.html", vraag), ("raad-antwoord.html", antwoord)],
            "uit": uit, "bronregels": [foto_credit(foto)], "controle": controle}


def caption_maken(post):
    uit = post["uit"]
    tags = " ".join("#" + t.strip().lstrip("#").replace(" ", "") for t in uit.get("hashtags", [])[:10])
    delen = [uit["caption"].strip(), "\n".join(post["bronregels"]), config.AI_REGEL, tags]
    return "\n\n".join(x for x in delen if x)[:2150]


def opruimen(d):
    grens = d - dt.timedelta(days=60)
    for pad in glob.glob(os.path.join(config.POSTS_DIR, "*.jpg")):
        try:
            if dt.date.fromisoformat(os.path.basename(pad)[:10]) < grens:
                os.remove(pad)
        except ValueError:
            pass


def main():
    d = config.vandaag()
    state = laad_state()
    makers = {"dag": maak_dag, "tv": maak_tv, "raad": maak_raad}
    rubriek = config.RUBRIEKEN[d.weekday()]
    try:
        try:
            post = makers[rubriek](d, state)
        except Exception:
            if rubriek == "dag":
                raise
            traceback.print_exc()
            print("Terugvallen op 'Op deze dag'")
            post = maak_dag(d, state)

        basis = os.path.join(config.POSTS_DIR, d.isoformat())
        paden = render.render(post["slides"], basis)
        caption = caption_maken(post)
        with open(basis + ".json", "w", encoding="utf-8") as f:
            json.dump({"datum": d.isoformat(), "rubriek": post["rubriek"], "caption": caption,
                       "afbeeldingen": [os.path.basename(p) for p in paden], "status": "klaar"},
                      f, ensure_ascii=False, indent=1)
        bewaar_state(state)
        opruimen(d)
        telegram.voorbeeld(paden, caption, d.isoformat(), post["rubriek"], post["controle"])
        print(f"Klaar: {post['rubriek']} voor {d}")
    except Exception as ex:
        traceback.print_exc()
        telegram.bericht(f"Nostalgiemagie kon vandaag ({d}) geen post maken.\nFout: {ex}")
        sys.exit(1)


if __name__ == "__main__":
    main()
