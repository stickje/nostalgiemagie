"""Telegram: voorbeeld sturen met knop 'Overslaan', en om 18.00 uur controleren of erop is gedrukt."""
import json

import requests

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
SKIP_WOORDEN = ("overslaan", "skip", "stop")


def _post(methode, **kwargs):
    r = requests.post(f"{API}/{methode}", timeout=60, **kwargs)
    if not r.ok:
        print(f"Telegram {methode} mislukt: {r.text}")
    return r


def bericht(tekst: str, knop_datum: str | None = None):
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": tekst[:4000], "disable_web_page_preview": True}
    if knop_datum:
        data["reply_markup"] = json.dumps({"inline_keyboard": [[
            {"text": "Overslaan", "callback_data": f"skip:{knop_datum}"}]]})
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
    bericht(
        f"Post voor {datum} ({rubriek}) staat klaar en gaat om 18.00 uur online.\n\n"
        f"Controleer even:\n{controle}\n\n"
        "Klopt er iets niet? Tik op Overslaan of stuur 'overslaan'.",
        knop_datum=datum,
    )


def is_overgeslagen(datum: str) -> bool:
    r = requests.get(f"{API}/getUpdates", params={"timeout": 0}, timeout=60)
    updates = r.json().get("result", []) if r.ok else []
    overslaan, laatste = False, None
    for u in updates:
        laatste = u["update_id"]
        cb = u.get("callback_query")
        if cb and cb.get("data") == f"skip:{datum}":
            overslaan = True
            _post("answerCallbackQuery", data={"callback_query_id": cb["id"], "text": "Overgeslagen"})
        msg = u.get("message") or {}
        if str(msg.get("chat", {}).get("id")) == str(TELEGRAM_CHAT_ID):
            if (msg.get("text") or "").strip().lower() in SKIP_WOORDEN:
                overslaan = True
    if laatste is not None:  # verwerkte berichten opruimen
        requests.get(f"{API}/getUpdates", params={"offset": laatste + 1, "timeout": 0}, timeout=60)
    return overslaan
