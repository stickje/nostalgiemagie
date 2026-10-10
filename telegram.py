"""Telegram: voorbeelden sturen met knoppen (kiezen, aanpassen, overslaan) en die knoppen later uitlezen."""
import datetime as dt
import json
import re

import requests

from config import EDITOR_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, dag_label

API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
SKIP_WOORDEN = ("overslaan", "skip", "stop")


def _post(methode, **kwargs):
    r = requests.post(f"{API}/{methode}", timeout=60, **kwargs)
    if not r.ok:
        print(f"Telegram {methode} mislukt: {r.text}")
    return r


def _knop(datum: str, opties: int = 0) -> str:
    rijen = []
    if opties:
        rijen.append([{"text": f"Kies {n}", "callback_data": f"kies:{datum}:{n}"} for n in range(1, opties + 1)])
    rij = []
    if EDITOR_URL.startswith("https://"):
        rij.append({"text": "Aanpassen", "url": f"{EDITOR_URL}#d{datum.replace('-', '')}"})
    rij.append({"text": "Overslaan", "callback_data": f"skip:{datum}"})
    rijen.append(rij)
    return json.dumps({"inline_keyboard": rijen})


def bericht(tekst: str, knop_datum: str | None = None, opties: int = 0):
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": tekst[:4000], "disable_web_page_preview": True}
    if knop_datum:
        data["reply_markup"] = _knop(knop_datum, opties)
    return _post("sendMessage", data=data)


def _album(items: list):
    """items: lijst van (pad, onderschrift). Eén album van 2-10 foto's, of één losse foto."""
    if len(items) == 1:
        pad, onder = items[0]
        with open(pad, "rb") as f:
            return _post("sendPhoto", data={"chat_id": TELEGRAM_CHAT_ID, "caption": onder[:1024]}, files={"photo": f})
    media, files = [], {}
    for i, (pad, onder) in enumerate(items[:10]):
        files[f"f{i}"] = open(pad, "rb")
        media.append({"type": "photo", "media": f"attach://f{i}", "caption": onder[:1024]})
    try:
        return _post("sendMediaGroup", data={"chat_id": TELEGRAM_CHAT_ID, "media": json.dumps(media)}, files=files)
    finally:
        for f in files.values():
            f.close()


def opties_voorbeeld(datum: str, opties: list):
    """Stuurt de opties van één dag als album (één foto per optie, met de caption eronder) en
    daarna een bericht met de knoppen Kies 1/2/3, Aanpassen en Overslaan.
    opties: lijst van dicts met 'paden', 'caption', 'rubriek', 'titel', 'controle'."""
    d = dt.date.fromisoformat(datum)
    _album([(o["paden"][0], f"Optie {n} · {o['rubriek']}\n\n{o['caption']}") for n, o in enumerate(opties, start=1)])
    regels = [f"{n}. {o['titel']}\n   {o['controle']}" for n, o in enumerate(opties, start=1)]
    bericht(
        f"{dag_label(d).capitalize()}: welke optie gaat om 18.00 uur online?\n\n" + "\n\n".join(regels) +
        "\n\nZonder keuze wordt er die dag niets geplaatst. Bij Raad het jaar zit de antwoordslide er ook bij.",
        knop_datum=datum, opties=len(opties),
    )


def voorbeeld(afbeeldingen: list, caption: str, datum: str, rubriek: str, controle: str):
    """Stuurt de afbeelding(en) en video's, de caption en de controle-info met de knop."""
    def soort(pad):
        return "video" if pad.lower().endswith((".mp4", ".mov", ".webm")) else "photo"
    if len(afbeeldingen) == 1:
        s = soort(afbeeldingen[0])
        with open(afbeeldingen[0], "rb") as f:
            _post("sendVideo" if s == "video" else "sendPhoto", data={"chat_id": TELEGRAM_CHAT_ID}, files={s: f})
    else:
        media, files = [], {}
        for i, pad in enumerate(afbeeldingen[:10]):
            files[f"f{i}"] = open(pad, "rb")
            media.append({"type": soort(pad), "media": f"attach://f{i}"})
        _post("sendMediaGroup", data={"chat_id": TELEGRAM_CHAT_ID, "media": json.dumps(media)}, files=files)
        for f in files.values():
            f.close()
    bericht(caption)
    d = dt.date.fromisoformat(datum)
    bericht(
        f"Post voor {dag_label(d)} ({rubriek}) staat klaar en gaat die dag om 18.00 uur online.\n\n"
        f"{controle}\n\n"
        "Niet blij? Tik op Aanpassen om tekst of foto te wijzigen, of op Overslaan.",
        knop_datum=datum,
    )


def verzoeken(vandaag: str) -> dict:
    """Leest alle nieuwe knoppen en berichten. Geeft {"overslaan": {datums}, "kies": {datum: optie}}.

    - Knop 'Kies n' onder de opties van een dag: kies optie n voor die datum (laatste keuze telt).
    - Knop 'Overslaan': die datum overslaan.
    - Bericht 'overslaan': vandaag; 'overslaan 14-10' of 'overslaan 2026-10-14': die datum.
    Telegram bewaart nieuwe berichten 24 uur; ochtend- en avondrun lezen ze allebei uit.
    """
    r = requests.get(f"{API}/getUpdates", params={"timeout": 0}, timeout=60)
    updates = r.json().get("result", []) if r.ok else []
    if not r.ok:
        print(f"Telegram getUpdates mislukt: {r.text}")
    uit, laatste = {"overslaan": set(), "kies": {}}, None
    for u in updates:
        laatste = u["update_id"]
        cb = u.get("callback_query")
        if cb and str(cb.get("message", {}).get("chat", {}).get("id")) == str(TELEGRAM_CHAT_ID):
            data = cb.get("data") or ""
            m = re.fullmatch(r"skip:(\d{4}-\d{2}-\d{2})", data)
            k = re.fullmatch(r"kies:(\d{4}-\d{2}-\d{2}):(\d)", data)
            if m:
                uit["overslaan"].add(m.group(1))
            elif k:
                uit["kies"][k.group(1)] = int(k.group(2))
            _post("answerCallbackQuery", data={"callback_query_id": cb["id"], "text": "Ontvangen, wordt verwerkt"})
        msg = u.get("message") or {}
        if str(msg.get("chat", {}).get("id")) != str(TELEGRAM_CHAT_ID):
            continue
        woorden = (msg.get("text") or "").strip().lower().split()
        if not woorden or woorden[0] not in SKIP_WOORDEN:
            continue
        if len(woorden) == 1:
            uit["overslaan"].add(vandaag)
        else:
            datum = _lees_datum(woorden[1], vandaag)
            if datum:
                uit["overslaan"].add(datum)
            else:
                bericht(f"Die datum snap ik niet: '{woorden[1]}'. Gebruik bijvoorbeeld 'overslaan 14-10'.")
    if laatste is not None:  # verwerkte berichten opruimen
        requests.get(f"{API}/getUpdates", params={"offset": laatste + 1, "timeout": 0}, timeout=60)
    return uit


def _lees_datum(tekst: str, vandaag: str) -> str | None:
    try:
        return dt.date.fromisoformat(tekst).isoformat()
    except ValueError:
        pass
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})", tekst)
    if not m:
        return None
    basis = dt.date.fromisoformat(vandaag)
    try:
        d = dt.date(basis.year, int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    if d < basis - dt.timedelta(days=7):  # bv. in december '03-01' bedoelt volgend jaar
        d = d.replace(year=d.year + 1)
    return d.isoformat()
