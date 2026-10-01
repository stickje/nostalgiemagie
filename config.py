"""Instellingen voor Nostalgiemagie. Geheime sleutels komen uit GitHub Secrets."""
import os
import datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Amsterdam")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
IG_API_VERSION = os.environ.get("IG_API_VERSION", "v23.0")

# Openbare map waar GitHub Pages de afbeeldingen neerzet,
# bijvoorbeeld https://stickje.github.io/nostalgiemagie
PAGES_URL = os.environ.get("PAGES_URL", "").rstrip("/")

# Proefmodus: alles draait, maar er wordt niets op Instagram geplaatst.
DRY_RUN = (os.environ.get("DRY_RUN") or "true").lower() in ("1", "true", "ja", "yes")

# Regel onder elke caption.
AI_REGEL = os.environ.get("AI_REGEL", "Samengesteld met hulp van AI, gecontroleerd door de redactie.")

MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december"]
DAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]

# Rubriek per weekdag (0 = maandag).
RUBRIEKEN = {0: "dag", 1: "dag", 2: "tv", 3: "dag", 4: "raad", 5: "dag", 6: "dag"}

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS_DIR = os.path.join(ROOT, "docs", "posts")
STATE_FILE = os.path.join(ROOT, "used.json")
TEMPLATES_DIR = ROOT


def vandaag() -> dt.date:
    forced = os.environ.get("DATUM")  # handig om te testen, bv. 2026-10-01
    if forced:
        return dt.date.fromisoformat(forced)
    return dt.datetime.now(TZ).date()


def datum_lang(d: dt.date) -> str:
    return f"{d.day} {MAANDEN[d.month - 1]}"
