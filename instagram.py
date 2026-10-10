"""Plaatsen via de Instagram API met Instagram Login (graph.instagram.com)."""
import time

import requests

from config import IG_ACCESS_TOKEN, IG_API_VERSION, IG_USER_ID

BASE = f"https://graph.instagram.com/{IG_API_VERSION}"


def _check(r):
    if not r.ok:
        raise RuntimeError(f"Instagram-fout {r.status_code}: {r.text}")
    return r.json()


def _wacht_tot_klaar(container_id: str, pogingen: int = 30):
    for _ in range(pogingen):
        data = _check(requests.get(f"{BASE}/{container_id}",
                                   params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN}, timeout=30))
        status = data.get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container {container_id} status {status}")
        time.sleep(5)
    raise RuntimeError("Instagram bleef te lang bezig met verwerken")


def _container(params: dict) -> str:
    params = {**params, "access_token": IG_ACCESS_TOKEN}
    cid = _check(requests.post(f"{BASE}/{IG_USER_ID}/media", data=params, timeout=60))["id"]
    _wacht_tot_klaar(cid, 120 if params.get("media_type") in ("VIDEO", "REELS") else 30)  # video duurt langer
    return cid


def _is_video(url: str) -> bool:
    return url.lower().split("?")[0].endswith((".mp4", ".mov"))


def plaats(afbeelding_urls: list, caption: str) -> str:
    """Plaatst één foto of een carrousel (foto's en video's). Geeft de permalink terug."""
    if len(afbeelding_urls) == 1:
        creatie = _container({"image_url": afbeelding_urls[0], "caption": caption})
    else:
        kinderen = [_container({"media_type": "VIDEO", "video_url": u, "is_carousel_item": "true"} if _is_video(u)
                               else {"image_url": u, "is_carousel_item": "true"}) for u in afbeelding_urls[:10]]
        creatie = _container({"media_type": "CAROUSEL", "children": ",".join(kinderen), "caption": caption})
    media_id = _check(requests.post(f"{BASE}/{IG_USER_ID}/media_publish",
                                    data={"creation_id": creatie, "access_token": IG_ACCESS_TOKEN},
                                    timeout=60))["id"]
    info = _check(requests.get(f"{BASE}/{media_id}",
                               params={"fields": "permalink", "access_token": IG_ACCESS_TOKEN}, timeout=30))
    return info.get("permalink", "")


def vernieuw_token() -> str | None:
    """Verlengt de token met 60 dagen. Geeft de nieuwe token terug, of None bij een fout."""
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": IG_ACCESS_TOKEN}, timeout=30)
    if r.ok and r.json().get("access_token"):
        return r.json()["access_token"]
    print(f"Token vernieuwen mislukt: {r.text}")
    return None
