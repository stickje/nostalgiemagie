"""Vult de HTML-templates in de huisstijl en zet ze om naar JPEG (1080 x 1350)."""
import base64
import html
import os
import re
import shutil
import subprocess

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


VIDEO_EXT = (".mp4", ".webm", ".mov", ".m4v")


def is_video(bestand: str) -> bool:
    return str(bestand or "").lower().endswith(VIDEO_EXT)


def _getal(w: dict, sleutel: str, standaard: float) -> float:
    try:
        return float(w.get(sleutel, standaard))
    except (TypeError, ValueError):
        return standaard


def foto_transform(w: dict) -> str:
    """CSS-transform uit de fotoknoppen in de editor (zelfde regels als de editor):
    foto_x / foto_y = verschuiving in % van het fotovak, foto_draai = graden,
    foto_zoom = factor (1 = passend), foto_spiegel = horizontaal spiegelen."""
    x, y = _getal(w, "foto_x", 0), _getal(w, "foto_y", 0)
    draai, zoom = _getal(w, "foto_draai", 0), _getal(w, "foto_zoom", 1) or 1
    spiegel = -1 if w.get("foto_spiegel") in (True, 1, "1", "true", "ja") else 1
    return f"translate({x:g}%,{y:g}%) rotate({draai:g}deg) scale({zoom:g}) scaleX({spiegel})"


def foto_block(bron: str, w: dict, lijst: bool = True) -> str:
    """De foto (of video) als element in het fotovak, met de aanpassingen uit de editor."""
    if not bron:
        return f'<div class="foto leeg"><span>{html.escape(str(w.get("jaar", "")))}</span></div>'
    stijl = ("position:absolute;left:0;top:0;width:100%;height:100%;object-fit:cover;"
             f"transform-origin:50% 50%;transform:{foto_transform(w)}")
    bron = html.escape(bron, quote=True)
    if w.get("soort") == "video" or is_video(w.get("foto", "")):
        el = f'<video src="{bron}" autoplay muted loop playsinline style="{stijl}"></video>'
    else:
        el = f'<img src="{bron}" alt="" style="{stijl}">'
    rand = ('<i style="position:absolute;inset:0;box-shadow:inset 0 0 60px rgba(60,30,10,.55);pointer-events:none"></i>'
            if lijst else "")
    return f'<div class="foto" style="overflow:hidden;background-image:none">{el}{rand}</div>'


def voorbereiden(waarden: dict, template: str = "") -> dict:
    """Leidt de afgeleide velden af uit de opgeslagen waarden (foto, achtergrond)."""
    w = dict(waarden)
    if template == "swipe.html":
        w.setdefault("achtergrond", "#000")
    if "foto" in w:
        uri = "" if is_video(w["foto"]) else _data_uri(w["foto"])
        w["foto_url"] = uri
        w["foto_block"] = foto_block(uri, w, lijst=template != "swipe.html")
    return w


def _vul(template: str, waarden: dict) -> str:
    waarden = voorbereiden(waarden, template)
    with open(os.path.join(TEMPLATES_DIR, template), encoding="utf-8") as f:
        bron = f.read()
    # {{naam}} wordt ge-escaped, {{{naam}}} wordt als HTML ingevoegd.
    bron = re.sub(r"\{\{\{(\w+)\}\}\}", lambda m: str(waarden.get(m.group(1), "")), bron)
    return re.sub(r"\{\{(\w+)\}\}", lambda m: html.escape(str(waarden.get(m.group(1), ""))), bron)


def kopgrootte(tekst: str, groot=92, middel=76, klein=62) -> str:
    n = len(tekst)
    return f"{groot if n <= 28 else middel if n <= 48 else klein}px"


def render(slides: list, uitvoer_basis: str) -> list:
    """slides: lijst van (templatebestand, waarden). Geeft de paden van de JPEG's (en MP4's) terug.
    Een swipe met een video wordt een MP4 met het logo erop (via ffmpeg)."""
    paden = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pagina = browser.new_page(viewport={"width": BREEDTE, "height": HOOGTE})
        for i, slide in enumerate(slides, start=1):
            template, waarden = (slide["template"], slide["waarden"]) if isinstance(slide, dict) else slide
            if template == "swipe.html" and is_video(waarden.get("foto", "")):
                laag = f"{uitvoer_basis}-{i}-logo.png"
                pagina.set_content(_vul(template, {"achtergrond": "transparent", "foto": ""}),
                                   wait_until="networkidle", timeout=60000)
                pagina.screenshot(path=laag, omit_background=True,
                                  clip={"x": 0, "y": 0, "width": BREEDTE, "height": HOOGTE})
                mp4 = f"{uitvoer_basis}-{i}.mp4"
                video_maken(os.path.join(POSTS_DIR, os.path.basename(waarden["foto"])), laag, waarden, mp4)
                os.remove(laag)
                paden.append(mp4)
                continue
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


def _ffmpeg() -> str:
    """ffmpeg van het systeem, anders die van het pakket imageio-ffmpeg."""
    pad = shutil.which("ffmpeg")
    if pad:
        return pad
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def video_maken(bron: str, logo_png: str, w: dict, uit: str):
    """Video vullend in 1080x1350 (zoals object-fit: cover), met dezelfde aanpassingen als in de
    editor (zoom, draaien, spiegelen, verschuiven) en het logo erover. Max. 60 seconden (Instagram)."""
    x, y = _getal(w, "foto_x", 0), _getal(w, "foto_y", 0)
    draai, zoom = _getal(w, "foto_draai", 0), _getal(w, "foto_zoom", 1) or 1
    spiegel = w.get("foto_spiegel") in (True, 1, "1", "true", "ja")
    hoek = f"{draai}*PI/180"
    keten = [f"scale={BREEDTE}:{HOOGTE}:force_original_aspect_ratio=increase", f"crop={BREEDTE}:{HOOGTE}"]
    if spiegel:
        keten.append("hflip")
    if zoom != 1:
        keten.append(f"scale=trunc(iw*{zoom}/2)*2:trunc(ih*{zoom}/2)*2")
    keten.append("format=rgba")
    if draai:
        keten.append(f"rotate={hoek}:ow=rotw({hoek}):oh=roth({hoek}):c=black@0")
    dx, dy = x * BREEDTE / 100, y * HOOGTE / 100
    graaf = (f"[0:v]{','.join(keten)}[m];color=c=black:s={BREEDTE}x{HOOGTE}:r=30[bg];"
             f"[bg][m]overlay=x=(W-w)/2+{dx}:y=(H-h)/2+{dy}:shortest=1[v1];"
             f"[v1][1:v]overlay=0:0,format=yuv420p[v]")
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", bron, "-i", logo_png,
                    "-filter_complex", graaf, "-map", "[v]", "-map", "0:a?", "-t", "60",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-r", "30",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", uit], check=True)
