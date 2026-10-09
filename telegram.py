"""Telegram: voorbeelden sturen met knop 'Overslaan', en verzoeken om over te slaan uitlezen."""
import datetime as dt
import json
import re

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, dag_label

API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
SKIP_WOORDEN = ("overslaan", "skip", "stop")


def _post(methode, **kwargs):
    r = requests.post(f"{API}/{methode}", timeout=60, **kwargs)
    if not r.ok:
        print(f"Telegram {methode} mislukt: {r.text}")
    return r


def _knop(datum: str) -> str:
    return json.dumps({"inline_keyboard": [[{"text": "Overslaan", "callback_data": f"skip:{datum}"}]]})


def bericht(tekst: str, knop_datum: str | None = None):
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": tekst[:4000], "disable_web_page_preview": True}
    if knop_datum:
        data["reply_markup"] = _knop(knop_datum)
    return _post("sendMessage", data=data)


def voorbeeld(afbeeldingen: list, caption: str, datum: str, rubriek: str, controle: str):
    """Stuurt de afbeelding(en), de caption en de controle-info met de knop."""
    if len(afbeeldingen) == 1:
        with open(afbeeldingen[0], "rb") as f:
            _post("sendPhoto", data={"chat_id": TELEGRAM_CHAT_ID}, files={"photo": f})
    else:
        media, files = [], {}
        for i, pad in enumerate(afbeeldingen):
            files[f"f{i}"] = open(pad, "rb")
            media.append({"type": "photo", "media": f"attach://f{i}"})
        _post("sendMediaGroup", data={"chat_id": TELEGRAM_CHAT_ID, "media": json.dumps(media)}, files=files)
        for f in files.values():
            f.close()
    bericht(caption)
    d = dt.date.fromisoformat(datum)
    bericht(
        f"Post voor {dag_label(d)} ({rubriek}) staat klaar en gaat die dag om 18.00 uur online.\n\n"
        f"Controleer even:\n{controle}\n\n"
        "Klopt er iets niet? Tik op Overslaan.",
        knop_datum=datum,
    )


def overslaan_verzoeken(vandaag: str) -> set:
    """Leest alle nieuwe knoppen en berichten en geeft de datums terug die overgeslagen moeten worden.

    - Knop 'Overslaan' onder een voorbeeld: die datum.
    - Bericht 'overslaan': de post van vandaag.
    - Bericht 'overslaan 2026-10-14' of 'overslaan 14-10': die datum.
    Telegram bewaart nieuwe berichten 24 uur; ochtend- en avondrun lezen ze allebei uit.
    """
    r = requests.get(f"{API}/getUpdates", params={"timeout": 0}, timeout=60)
    updates = r.json().get("result", []) if r.ok else []
    if not r.ok:
        print(f"Telegram getUpdates mislukt: {r.text}")
    datums, laatste = set(), None
    for u in updates:
        laatste = u["update_id"]
        cb = u.get("callback_query")
        if cb and str(cb.get("message", {}).get("chat", {}).get("id")) == str(TELEGRAM_CHAT_ID):
            m = re.fullmatch(r"skip:(\d{4}-\d{2}-\d{2})", cb.get("data") or "")
            if m:
                datums.add(m.group(1))
                _post("answerCallbackQuery", data={"callback_query_id": cb["id"], "text": "Wordt overgeslagen"})
        msg = u.get("message") or {}
        if str(msg.get("chat", {}).get("id")) != str(TELEGRAM_CHAT_ID):
            continue
        tekst = (msg.get("text") or "").strip().lower()
        woorden = tekst.split()
        if not woorden or woorden[0] not in SKIP_WOORDEN:
            continue
        if len(woorden) == 1:
            datums.add(vandaag)
        else:
            datum = _lees_datum(woorden[1], vandaag)
            if datum:
                datums.add(datum)
            else:
                bericht(f"Die datum snap ik niet: '{woorden[1]}'. Gebruik bijvoorbeeld 'overslaan 14-10'.")
    if laatste is not None:  # verwerkte berichten opruimen
        requests.get(f"{API}/getUpdates", params={"offset": laatste + 1, "timeout": 0}, timeout=60)
    return datums


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
