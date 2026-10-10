"""Ochtendrun: maakt de post van vandaag en stuurt een voorbeeld naar Telegram."""
import datetime as dt
import glob
import html
import json
import os
import random
import re
import sys
import time
import traceback

import requests

import config, noodrem, render, sources, telegram, writer

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
    """Naamsvermelding, alleen als de licentie die eist (CC BY / CC BY-SA). CC0 en publiek domein: niets."""
    lic = (foto.get("licentie") or "").lower()
    if "cc0" in lic or "public domain" in lic or "publiek domein" in lic:
        return ""
    delen = [d.strip() for d in (foto.get("maker") or "").split("/")
             if d.strip() and not re.search(r"\d|neg\.|item|stroken", d, re.I)]
    maker = " / ".join(delen[:2]) or "Nationaal Archief"
    lic = re.sub(r"\s+nl$", "", foto.get("licentie") or "").strip()
    return f"Foto: {maker} / Nationaal Archief ({lic})"


def bewaar_foto(foto, d, optie=1):
    """Downloadt de archieffoto naast de post, zodat hij later opnieuw te gebruiken en aan te passen is."""
    naam = f"{d.isoformat()}-o{optie}-foto.jpg"
    r = requests.get(foto["url"], headers=sources.UA, timeout=60)
    r.raise_for_status()
    with open(os.path.join(config.POSTS_DIR, naam), "wb") as f:
        f.write(r.content)
    return naam


def maak_dag(d, state, aantal=3, start=1):
    """Geeft een lijst van maximaal `aantal` posts voor 'Op deze dag', elk over een ander onderwerp."""
    events, bron = sources.gebeurtenissen(d, max_jaar=d.year - 15)
    events = [e for e in events if f"{e['jaar']}:{e['tekst'][:40]}" not in state["events"]]
    if not events:
        raise RuntimeError("Geen gebeurtenissen gevonden op Wikipedia")
    jubilea = [e for e in events if d.year - e["jaar"] in JUBILEA]
    rest = [e for e in events if e not in jubilea]
    random.shuffle(rest)
    kandidaten = (jubilea + rest)[:40]

    posts = []
    for n, uit in enumerate(writer.schrijf_dag(config.datum_lang(d), d.year, kandidaten, aantal), start=start):
        e = kandidaten[int(uit["index"])]
        foto = None
        try:
            fotos = sources.archieffotos(uit.get("zoekterm", ""), jaar=e["jaar"], al_gebruikt=state["fotos"])
            foto = fotos[0] if fotos else None
        except Exception as ex:
            print(f"Geen foto gevonden: {ex}")
        fotobestand = ""
        if foto:
            try:
                fotobestand = bewaar_foto(foto, d, n)
            except Exception as ex:
                print(f"Foto downloaden mislukt: {ex}")
                foto = None
        waarden = {
            "datum": f"{config.DAGEN[d.weekday()].capitalize()} {config.datum_lang(d)} {e['jaar']}",
            "kop": uit["kop"], "ondertitel": uit["ondertitel"], "jaren": d.year - e["jaar"], "jaar": e["jaar"],
            "foto": fotobestand,
        }
        controle = f"Wikipedia ({e['jaar']}): {e['tekst'][:200]}"
        if foto:
            controle += f"\nFoto ({foto['jaar']}): {(foto['beschrijving'] or 'geen beschrijving')[:150]}"
            state["fotos"].append(foto["titel"])
        state["events"].append(f"{e['jaar']}:{e['tekst'][:40]}")
        posts.append({"rubriek": "Op deze dag", "slides": [("dag.html", waarden)], "uit": uit,
                      "bronregels": [foto_credit(foto)] if foto and foto_credit(foto) else [], "controle": controle,
                      "bron": bron})
    return posts


def maak_tv(d, state, n=1):
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
            "bronregels": [], "controle": controle}


def maak_raad(d, state, n=1):
    """Eén Raad-het-jaar-post. Probeert tot 15 willekeurige jaren; per jaar ruimer zoeken dan voorheen,
    zodat er op vrijdag drie Raad-het-jaar-opties uitkomen in plaats van één."""
    foto = None
    for jaar in random.sample(range(1950, 1990), 15):
        try:
            fotos = sources.archieffotos(str(jaar), jaar=jaar, limiet=50, al_gebruikt=state["fotos"])
        except Exception as ex:
            print(f"Zoeken mislukt voor {jaar}: {ex}")
            time.sleep(1)
            continue
        if fotos:
            foto = random.choice(fotos[:12])
            break
    if not foto:
        raise RuntimeError("Geen geschikte archieffoto gevonden")
    state["fotos"].append(foto["titel"])
    try:
        uit = writer.schrijf_raad(foto)
    except Exception as ex:  # één keer opnieuw proberen (bv. onleesbaar antwoord)
        print(f"Tekst schrijven mislukt, opnieuw: {ex}")
        uit = writer.schrijf_raad(foto)

    juist = foto["jaar"]
    fout = random.sample([juist + x for x in range(-14, 15) if abs(x) >= 3 and juist + x < d.year], 2)
    opties = [juist] + fout
    random.shuffle(opties)
    letter = "ABC"[opties.index(juist)]
    vraag = {"foto": bewaar_foto(foto, d, n), "hint": uit["hint"], "a": opties[0], "b": opties[1], "c": opties[2]}
    antwoord = {"jaar": juist, "letter": letter, "uitleg": uit.get("uitleg", "")}
    controle = f"Juiste jaar volgens archief: {juist} (antwoord {letter}). {(foto['beschrijving'] or '')[:150]}"
    return {"rubriek": "Raad het jaar", "slides": [("raad.html", vraag), ("raad-antwoord.html", antwoord)],
            "uit": uit, "bronregels": [foto_credit(foto)] if foto_credit(foto) else [], "controle": controle}


def caption_maken(post):
    uit = post["uit"]
    tags = " ".join("#" + t.strip().lstrip("#").replace(" ", "") for t in uit.get("hashtags", [])[:10])
    delen = [uit["caption"].strip(), "\n".join(post["bronregels"]), config.AI_REGEL, tags]
    return "\n\n".join(x for x in delen if x)[:2150]


def opruimen(d):
    grens = d - dt.timedelta(days=60)
    for pad in [p for ext in ("jpg", "png", "mp4", "webm", "mov") for p in glob.glob(os.path.join(config.POSTS_DIR, f"*.{ext}"))]:
        try:
            if dt.date.fromisoformat(os.path.basename(pad)[:10]) < grens:
                os.remove(pad)
        except ValueError:
            pass


AANTAL_OPTIES = 3
AFGEHANDELD = ("kiezen", "klaar", "geplaatst", "overgeslagen", "proef", "geen keuze")


def maak_opties(d, state):
    """Maakt AANTAL_OPTIES posts voor datum d. Lukt de rubriek van die dag niet, dan vult
    'Op deze dag' aan."""
    rubriek = config.RUBRIEKEN[d.weekday()]
    posts = []
    if rubriek == "dag":
        posts = maak_dag(d, state, AANTAL_OPTIES)
    else:
        maker = {"tv": maak_tv, "raad": maak_raad}[rubriek]
        for n in range(1, AANTAL_OPTIES + 3):  # twee extra pogingen, zodat alle opties van de rubriek zijn
            if len(posts) >= AANTAL_OPTIES:
                break
            try:
                posts.append(maker(d, state, n))
            except Exception:
                traceback.print_exc()
        if len(posts) < AANTAL_OPTIES:
            print("Aanvullen met 'Op deze dag'")
            try:
                posts += maak_dag(d, state, AANTAL_OPTIES - len(posts), start=AANTAL_OPTIES + 3)  # eigen fotonamen, geen botsing
            except Exception:
                if not posts:
                    raise
                traceback.print_exc()
    if not posts:
        raise RuntimeError("Geen enkele optie gelukt")

    opties = []
    for n, post in enumerate(posts, start=1):
        paden = render.render(post["slides"], os.path.join(config.POSTS_DIR, f"{d.isoformat()}-o{n}"))
        uit = post["uit"]
        opties.append({
            "rubriek": post["rubriek"],
            "titel": uit.get("kop") or uit.get("naam") or uit.get("hint") or "",
            "caption": caption_maken(post),
            "afbeeldingen": [os.path.basename(p) for p in paden],
            "slides": [{"template": t, "waarden": w} for t, w in post["slides"]],
            "controle": post["controle"],
            "paden": paden,
        })
    return opties


def maak_dag_bestand(d, state):
    """Maakt de opties voor datum d, bewaart ze en stuurt ze naar Telegram. Geeft de JSON terug."""
    opties = maak_opties(d, state)
    data = {"datum": d.isoformat(), "status": "kiezen", "keuze": None, "versie": 1,
            "opties": [{k: v for k, v in o.items() if k != "paden"} for o in opties]}
    noodrem.bewaar(d.isoformat(), data)
    bewaar_state(state)
    try:
        telegram.opties_voorbeeld(d.isoformat(), opties)
    except Exception as ex:  # opties staan klaar, alleen het voorbeeld kwam niet aan
        traceback.print_exc()
        telegram.bericht(f"De opties voor {config.dag_label(d)} staan klaar, maar het voorbeeld kon niet "
                         f"verstuurd worden ({ex}). Kies in de editor.", knop_datum=d.isoformat(), opties=len(opties))
    return data


def omschrijf(post):
    if post.get("status") == "kiezen":
        return f"{len(post.get('opties') or [])} opties, nog kiezen"
    return f"{post.get('titel', '')} [{post.get('status')}]"


def main():
    os.makedirs(config.POSTS_DIR, exist_ok=True)
    start = config.vandaag()
    dagen = max(1, min(14, int(os.environ.get("DAGEN") or 1)))
    noodrem.verwerken()
    state = laad_state()

    regels, mislukt = [], 0
    for i in range(dagen):
        d = start + dt.timedelta(days=i)
        label = config.dag_label(d)
        bestaand = noodrem.lees(d.isoformat())
        if bestaand and bestaand.get("status") in AFGEHANDELD:
            regels.append(f"{label}: {omschrijf(bestaand)}")
            if dagen == 1 and bestaand["status"] == "klaar":
                telegram.bericht(f"Vanavond om 18.00 uur gaat online: {bestaand.get('titel') or bestaand.get('rubriek')}. "
                                 "Niet goed? Kies een andere optie, pas hem aan of sla over.",
                                 knop_datum=d.isoformat(), opties=len(bestaand.get("opties") or []))
            elif dagen == 1 and bestaand["status"] == "kiezen":
                keuzes = "\n".join(f"{n}. {o.get('titel', '')}" for n, o in enumerate(bestaand.get("opties") or [], start=1))
                telegram.bericht(f"Je hebt nog geen optie gekozen voor vandaag. Zonder keuze wordt er om 18.00 uur "
                                 f"niets geplaatst.\n\n{keuzes}", knop_datum=d.isoformat(),
                                 opties=len(bestaand.get("opties") or []))
            continue
        try:
            data = maak_dag_bestand(d, state)
            regels.append(f"{label}: {omschrijf(data)}")
            print(f"Klaar: {len(data['opties'])} opties voor {d}")
        except Exception as ex:
            traceback.print_exc()
            mislukt += 1
            regels.append(f"{label}: MISLUKT")
            telegram.bericht(f"Nostalgiemagie kon geen post maken voor {label}.\nFout: {ex}")
        if dagen > 1:
            time.sleep(2)  # Telegram niet overspoelen

    opruimen(start)
    if dagen > 1:
        telegram.bericht("Planning:\n\n" + "\n".join(regels) +
                         "\n\nKies per dag een optie met de knoppen onder de opties. Elke dag om 18.00 uur gaat "
                         "de gekozen optie online; zonder keuze wordt er die dag niets geplaatst.")
    if mislukt == dagen:
        sys.exit(1)


if __name__ == "__main__":
    main()
