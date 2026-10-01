"""Vult de HTML-templates in de huisstijl en zet ze om naar JPEG (1080 x 1350)."""
import html
import os
import re

from PIL import Image
from playwright.sync_api import sync_playwright

from .config import TEMPLATES_DIR

BREEDTE, HOOGTE = 1080, 1350


def _vul(template: str, waarden: dict) -> str:
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
        for i, (template, waarden) in enumerate(slides, start=1):
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
