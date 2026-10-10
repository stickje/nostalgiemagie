"""Vult de HTML-templates in de huisstijl en zet ze om naar JPEG (1080 x 1350)."""
import base64
import html
import os
import re

from PIL import Image
from playwright.sync_api import sync_playwright

from config import POSTS_DIR, TEMPLATES_DIR

BREEDTE, HOOGTE = 1080, 1350


def _data_uri(bestand: str) -> str:
    """Foto uit docs/posts als data-URI, zodat de render niet van een externe server afhangt."""
    if not bestand:
        return ""
    if bestand.startswith(("http://", "https://", "data:")):
        return bestand
    pad = os.path.join(POSTS_DIR, os.path.basename(bestand))
    if not os.path.exists(pad):
        print(f"Foto niet gevonden: {pad}")
        return ""
    soort = "png" if pad.lower().endswith(".png") else "jpeg"
    with open(pad, "rb") as f:
        return f"data:image/{soort};base64," + base64.b64encode(f.read()).decode()


def voorbereiden(waarden: dict) -> dict:
    """Leidt de afgeleide velden af uit de opgeslagen waarden (foto, kopgrootte)."""
    w = dict(waarden)
    if "foto" in w:
        uri = _data_uri(w["foto"])
        w["foto_url"] = uri
        if uri:
            w["foto_block"] = f'<div class="foto" style="background-image:url(\'{uri}\')"></div>'
        else:
            w["foto_block"] = f'<div class="foto leeg"><span>{html.escape(str(w.get("jaar", "")))}</span></div>'
    return w


def _vul(template: str, waarden: dict) -> str:
    waarden = voorbereiden(waarden)
    with open(os.path.join(TEMPLATES_DIR, template), encoding="utf-8") as f:
        bron = f.read()
    # {{naam}} wordt ge-escaped, {{{naam}}} wordt als HTML ingevoegd.
    bron = re.sub(r"\{\{\{(\w+)\}\}\}", lambda m: str(waarden.get(m.group(1), "")), bron)
    return re.sub(r"\{\{(\w+)\}\}", lambda m: html.escape(str(waarden.get(m.group(1), ""))), bron)


def kopgrootte(tekst: str, groot=92, middel=76, klein=62) -> str:
    n = len(tekst)
    return f"{groot if n <= 28 else middel if n <= 48 else klein}px"


def render(slides: list, uitvoer_basis: str) -> list:
    """slides: lijst van (templatebestand, waarden). Geeft de paden van de JPEG's terug."""
    paden = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pagina = browser.new_page(viewport={"width": BREEDTE, "height": HOOGTE})
        for i, slide in enumerate(slides, start=1):
            template, waarden = (slide["template"], slide["waarden"]) if isinstance(slide, dict) else slide
            pagina.set_content(_vul(template, waarden), wait_until="networkidle", timeout=60000)
            pagina.evaluate("document.fonts.ready")
            pagina.wait_for_timeout(500)
            png = f"{uitvoer_basis}-{i}.png"
            jpg = f"{uitvoer_basis}-{i}.jpg"
            pagina.screenshot(path=png, clip={"x": 0, "y": 0, "width": BREEDTE, "height": HOOGTE})
            Image.open(png).convert("RGB").save(jpg, "JPEG", quality=92, optimize=True)
            os.remove(png)
            paden.append(jpg)
        browser.close()
    return paden
