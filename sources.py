"""Bronnen ophalen: Wikipedia (gebeurtenissen, TV-programma's) en Wikimedia Commons (open foto's)."""
import html
import random
import re

import requests

from .config import datum_lang

UA = {"User-Agent": "NostalgiemagieBot/1.0 (Instagram-pagina @nostalgiemagie)"}
WIKI = "https://nl.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"

# Categorieën waaruit 'Vergeten TV' kiest. Uitbreiden mag: elke nl.wikipedia-categorie werkt.
TV_CATEGORIEEN = [
    "Categorie:Programma van de AVRO",
    "Categorie:Programma van de VARA",
    "Categorie:Programma van de TROS",
    "Categorie:Programma van de KRO",
    "Categorie:Programma van de NCRV",
    "Categorie:Programma van de VPRO",
    "Categorie:Programma van de Veronica",
    "Categorie:Programma van RTL 4",
    "Categorie:Nederlands kinderprogramma op televisie",
    "Categorie:Nederlands spelprogramma",
]

# Licenties die we zonder toestemming mogen gebruiken (met naamsvermelding).
OPEN_LICENTIES = ("cc0", "public domain", "cc by 4.0", "cc by-sa 4.0", "cc by 3.0", "cc by-sa 3.0")


def _get(url, params):
    params = {**params, "format": "json", "formatversion": 2}
    r = requests.get(url, params=params, headers=UA, timeout=30)
    r.raise_for_status()
    return r.json()


def _schoon(tekst: str) -> str:
    """Wikicode omzetten naar leesbare tekst."""
    tekst = re.sub(r"<ref[^>]*/>", "", tekst)
    tekst = re.sub(r"<ref[^>]*>.*?</ref>", "", tekst, flags=re.S)
    for _ in range(3):
        tekst = re.sub(r"\{\{[^{}]*\}\}", "", tekst)
    tekst = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", tekst)
    tekst = re.sub(r"\[https?://\S+\s([^\]]+)\]", r"\1", tekst)
    tekst = re.sub(r"'{2,}", "", tekst)
    tekst = re.sub(r"<[^>]+>", "", tekst)
    return html.unescape(re.sub(r"\s+", " ", tekst)).strip()


def gebeurtenissen(d, max_jaar):
    """Gebeurtenissen op deze datum volgens de Nederlandse Wikipedia-datumpagina."""
    titel = datum_lang(d)
    data = _get(WIKI, {"action": "parse", "page": titel, "prop": "wikitext"})
    wikitext = data["parse"]["wikitext"]
    m = re.search(r"==\s*Gebeurtenissen\s*==(.*?)(?:\n==[^=]|\Z)", wikitext, re.S)
    blok = m.group(1) if m else ""
    uit = []
    for regel in blok.splitlines():
        m = re.match(r"^\*+\s*(?:\[\[)?(\d{3,4})(?:\]\])?\s*[-–—:]\s*(.+)$", regel.strip())
        if not m:
            continue
        jaar = int(m.group(1))
        tekst = _schoon(m.group(2))
        if 1880 <= jaar <= max_jaar and len(tekst) > 15:
            uit.append({"jaar": jaar, "tekst": tekst})
    bron = f"https://nl.wikipedia.org/wiki/{titel.replace(' ', '_')}"
    return uit, bron


def tv_kandidaten(aantal, al_gebruikt):
    """Een paar willekeurige Nederlandse TV-programma's met hun intro van Wikipedia."""
    titels = []
    for cat in random.sample(TV_CATEGORIEEN, k=min(4, len(TV_CATEGORIEEN))):
        try:
            data = _get(WIKI, {"action": "query", "list": "categorymembers", "cmtitle": cat,
                               "cmnamespace": 0, "cmlimit": 200})
            titels += [p["title"] for p in data["query"]["categorymembers"]]
        except Exception as e:  # categorie bestaat niet of tijdelijke fout
            print(f"Categorie overgeslagen ({cat}): {e}")
    titels = [t for t in set(titels) if t not in al_gebruikt]
    random.shuffle(titels)
    kandidaten = []
    for titel in titels[: aantal * 2]:
        data = _get(WIKI, {"action": "query", "prop": "extracts", "exintro": 1,
                           "explaintext": 1, "titles": titel})
        pagina = data["query"]["pages"][0]
        intro = (pagina.get("extract") or "").strip()
        if len(intro) > 150:
            kandidaten.append({
                "titel": titel,
                "intro": intro[:1500],
                "bron": f"https://nl.wikipedia.org/wiki/{titel.replace(' ', '_')}",
            })
        if len(kandidaten) >= aantal:
            break
    return kandidaten


def _jaar_uit(meta):
    for veld in ("DateTimeOriginal", "DateTime"):
        waarde = _schoon(meta.get(veld, {}).get("value", ""))
        m = re.search(r"(18|19|20)\d{2}", waarde)
        if m:
            return int(m.group(0))
    return None


def archieffotos(zoekterm, jaar=None, limiet=20, al_gebruikt=()):
    """Open foto's van het Nationaal Archief via Wikimedia Commons."""
    query = f'incategory:"Images_from_Nationaal_Archief" {zoekterm}'.strip()
    data = _get(COMMONS, {"action": "query", "generator": "search", "gsrsearch": query,
                          "gsrnamespace": 6, "gsrlimit": limiet, "prop": "imageinfo",
                          "iiprop": "url|extmetadata", "iiurlwidth": 1600})
    fotos = []
    for pagina in (data.get("query") or {}).get("pages", []):
        if pagina["title"] in al_gebruikt:
            continue
        info = (pagina.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        licentie = _schoon(meta.get("LicenseShortName", {}).get("value", ""))
        if not any(l in licentie.lower() for l in OPEN_LICENTIES):
            continue
        foto_jaar = _jaar_uit(meta)
        if jaar and foto_jaar != jaar:
            continue
        fotos.append({
            "titel": pagina["title"],
            "url": info.get("thumburl") or info.get("url"),
            "pagina": info.get("descriptionurl"),
            "beschrijving": _schoon(meta.get("ImageDescription", {}).get("value", ""))[:600],
            "maker": _schoon(meta.get("Artist", {}).get("value", "")) or "Nationaal Archief",
            "licentie": licentie,
            "jaar": foto_jaar,
        })
    return fotos
