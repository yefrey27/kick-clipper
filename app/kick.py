"""Cliente para los endpoints publicos de Kick.

Kick esta detras de Cloudflare, asi que usamos curl_cffi con huella de Chrome.
Si falla, probamos el host api.kick.com que suele ser mas permisivo.
"""
import os
import random
import time

try:
    from curl_cffi import requests as crequests
    HAS_CFFI = True
except Exception:                                    # pragma: no cover
    import httpx
    HAS_CFFI = False

WEB = "https://kick.com/api/v2"
PRIVATE = "https://api.kick.com/private/v1"

IMPERSONATE = ["chrome124", "chrome120", "chrome110", "safari17_0"]

# Los runners de GitHub salen por IPs de datacenter y Cloudflare las mira con lupa.
# Si pones el secreto KICK_PROXY (http://user:pass@host:puerto) todo sale por ahi.
PROXY = os.getenv("KICK_PROXY", "").strip()
PROXIES = {"http": PROXY, "https": PROXY} if PROXY else None

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://kick.com/",
    "Origin": "https://kick.com",
}


class KickError(RuntimeError):
    pass


def _get(url: str, params: dict | None = None, tries: int = 3):
    last = None
    for attempt in range(tries):
        try:
            if HAS_CFFI:
                r = crequests.get(
                    url,
                    params=params,
                    headers=HEADERS,
                    impersonate=random.choice(IMPERSONATE),
                    proxies=PROXIES,
                    timeout=25,
                )
            else:
                r = httpx.get(url, params=params, headers=HEADERS, timeout=25,
                              proxy=PROXY or None, follow_redirects=True)
            if r.status_code == 404:
                raise KickError("no existe (404)")
            if r.status_code in (403, 429, 503):
                last = KickError(f"bloqueado por Cloudflare ({r.status_code})")
                time.sleep(2 + attempt * 3)
                continue
            r.raise_for_status()
            return r.json()
        except KickError:
            raise
        except Exception as exc:                     # red, json invalido, etc.
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise KickError(str(last or "sin respuesta"))


def get_channel(slug: str) -> dict:
    slug = slug.strip().lower().lstrip("@").rstrip("/").split("/")[-1]
    try:
        data = _get(f"{WEB}/channels/{slug}")
    except KickError:
        data = _get(f"{PRIVATE}/channels/{slug}")
        data = data.get("data", data)
    user = data.get("user") or {}
    return {
        "id": data.get("id"),
        "slug": data.get("slug") or slug,
        "display_name": user.get("username") or data.get("slug") or slug,
        "avatar": user.get("profile_pic") or data.get("banner_image", {}).get("url"),
        "followers": data.get("followers_count") or data.get("followersCount") or 0,
        "live": bool(data.get("livestream")),
    }


def _normalize(raw: dict, fallback_slug: str) -> dict:
    channel = raw.get("channel") or {}
    creator = raw.get("creator") or {}
    category = raw.get("category") or {}
    slug = channel.get("slug") or fallback_slug
    cid = str(raw.get("id"))
    return {
        "id": cid,
        "channel_slug": slug,
        "title": (raw.get("title") or "").strip() or "Sin titulo",
        "url": f"https://kick.com/{slug}?clip=clip_{cid}" if not cid.startswith("clip_")
               else f"https://kick.com/{slug}?clip={cid}",
        # clip_url suele ser el master m3u8; video_url a veces trae mp4 directo
        "source_url": raw.get("video_url") or raw.get("clip_url"),
        "thumbnail": raw.get("thumbnail_url") or raw.get("thumbnail"),
        "duration": int(raw.get("duration") or 0),
        "views": int(raw.get("views") or raw.get("view_count") or 0),
        "likes": int(raw.get("likes") or raw.get("likes_count") or 0),
        "category": category.get("name") or "",
        "creator": creator.get("username") or "",
        "created_at": raw.get("created_at") or raw.get("started_at"),
    }


def get_clips(slug: str, limit: int = 60, sort: str = "date", window: str = "month"):
    """Trae clips del canal paginando por cursor.

    sort: date | view | likes     window: day | week | month | all
    """
    out, cursor, seen = [], "0", set()
    while len(out) < limit:
        params = {"cursor": cursor, "sort": sort, "time": window}
        try:
            data = _get(f"{WEB}/channels/{slug}/clips", params)
        except KickError:
            data = _get(f"{PRIVATE}/channels/{slug}/clips", params)
        batch = data.get("clips") or data.get("data") or []
        if not batch:
            break
        for raw in batch:
            clip = _normalize(raw, slug)
            if clip["id"] in seen or not clip["source_url"]:
                continue
            seen.add(clip["id"])
            out.append(clip)
        cursor = data.get("nextCursor") or data.get("next_cursor")
        if not cursor:
            break
        time.sleep(0.6)
    return out[:limit]


def get_trending(limit: int = 40, window: str = "day"):
    """Clips en tendencia de toda la plataforma, para descubrir canales."""
    data = _get(f"{WEB}/clips", {"cursor": "0", "sort": "view", "time": window})
    batch = data.get("clips") or data.get("data") or []
    return [_normalize(c, (c.get("channel") or {}).get("slug", "")) for c in batch[:limit]]
