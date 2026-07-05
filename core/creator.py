import html
import re
import time

import requests

CREATOR_NAME = "Finnerich"
YT_CHANNEL_ID = "UCFxR9IIFaKhDp5CeQm04fYg"
YT_CHANNEL_URL = "https://www.youtube.com/channel/" + YT_CHANNEL_ID
ROBLOX_PROFILE_URL = "https://www.roblox.com/"
DISCORD_URL = "https://discord.gg/X7dbbQ5pXV"

CREATOR_NOTES = (
    "hi"
)

_CACHE_TTL = 60
_cache = {"ts": 0.0, "data": None}

def _fetch_subs():
    try:
        r = requests.get(
            f"https://api.socialcounts.org/youtube-live-subscriber-count/{YT_CHANNEL_ID}",
            timeout=8,
        )
        data = r.json()
        if isinstance(data, dict):
            for key in ("est_sub", "subscriberCount", "subscribers", "count", "sub_count"):
                value = data.get(key)
                if isinstance(value, (int, float)) and value >= 0:
                    return int(value)
            nested = data.get("data") or data.get("stats") or {}
            if isinstance(nested, dict):
                for key in ("est_sub", "subscriberCount", "subscribers", "count"):
                    value = nested.get(key)
                    if isinstance(value, (int, float)) and value >= 0:
                        return int(value)
    except (requests.RequestException, ValueError, AttributeError):
        pass
    try:
        r = requests.get(
            f"https://yt.lemnoslife.com/noKey/channels?part=statistics&id={YT_CHANNEL_ID}",
            timeout=8,
        )
        items = r.json().get("items", [])
        if items:
            return int(items[0]["statistics"]["subscriberCount"])
    except (requests.RequestException, ValueError, KeyError, IndexError):
        pass
    return None

def _is_livestream(entry_xml: str) -> bool:

    live_hints = re.search(
        r"<media:category[^>]*>(?:live|livestream|stream)</media:category>",
        entry_xml,
        re.IGNORECASE,
    )
    if live_hints:
        return True
    vid = re.search(r"<yt:videoId>([^<]+)</yt:videoId>", entry_xml)
    if vid:
        try:
            oe = requests.get(
                f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid.group(1)}&format=json",
                timeout=6,
            )
            oe_data = oe.json()
            thumb = oe_data.get("thumbnail_url", "")
            if "live" in thumb.lower():
                return True
        except Exception:
            pass
    return False

def _fetch_latest_video():
    try:
        r = requests.get(
            f"https://www.youtube.com/feeds/videos.xml?channel_id={YT_CHANNEL_ID}",
            timeout=8,
        )
        xml = r.text or ""
        parts = xml.split("<entry>")
        for entry in parts[1:]:
            if _is_livestream(entry):
                continue
            vid = re.search(r"<yt:videoId>([^<]+)</yt:videoId>", entry)
            if not vid:
                continue
            video_id = vid.group(1)
            title = re.search(r"<title>([^<]*)</title>", entry)
            views = re.search(r'<media:statistics views="(\d+)"', entry)
            published = re.search(r"<published>([^<]+)</published>", entry)
            return {
                "id": video_id,
                "title": html.unescape(title.group(1)) if title else "",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumb": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                "views": int(views.group(1)) if views else None,
                "published": published.group(1) if published else "",
            }
    except (requests.RequestException, ValueError):
        pass
    return None

def get_stats(force=False):
    now = time.time()
    if not force and _cache["data"] and now - _cache["ts"] < _CACHE_TTL:
        return _cache["data"]
    data = {"video": _fetch_latest_video()}
    _cache["data"] = data
    _cache["ts"] = now
    return data

def links():
    return {
        "name": CREATOR_NAME,
        "youtube": YT_CHANNEL_URL,
        "roblox": ROBLOX_PROFILE_URL,
        "discord": DISCORD_URL,
        "notes": CREATOR_NOTES,
    }
