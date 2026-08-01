from datetime import datetime, timezone

import json
import queue
import threading
import functools

import requests

from . import biomes
from . import event_log

FOOTER_TEXT = "SolRich"
FOOTER_ICON = "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/solrich-logo.png"
DISCORD_INVITE = "https://discord.gg/X7dbbQ5pXV"

COLOR_GREEN = 0x57F287
COLOR_RED = 0xED4245
COLOR_ORANGE = 0xFAA61A
COLOR_GREY = 0x4F5460

MERCHANT_COLORS = {
    "mari": 0xFFFFFF,
    "jester": 0x9B59B6,
    "rin": 0xFAA61A,
}

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

_wh_queue: "queue.Queue" = queue.Queue()
_wh_worker = None
_wh_lock = threading.Lock()

def _wh_loop():
    while True:
        job = _wh_queue.get()
        try:
            job()
        except Exception as e:
            print(f"[Webhook] worker job failed: {e}")
        finally:
            _wh_queue.task_done()

def _ensure_worker():
    global _wh_worker
    if _wh_worker is not None and _wh_worker.is_alive():
        return
    with _wh_lock:
        if _wh_worker is not None and _wh_worker.is_alive():
            return
        _wh_worker = threading.Thread(target=_wh_loop, name="webhook-worker", daemon=True)
        _wh_worker.start()

def _enqueue(fn, *args, **kwargs):
    _ensure_worker()
    _wh_queue.put(functools.partial(fn, *args, **kwargs))

def flush(timeout=10.0):
    
    import time as _t
    deadline = _t.monotonic() + timeout
    try:
        with _wh_queue.all_tasks_done:
            while _wh_queue.unfinished_tasks:
                remaining = deadline - _t.monotonic()
                if remaining <= 0:
                    break
                _wh_queue.all_tasks_done.wait(remaining)
    except Exception:
        pass

def _post(url, embed, content="", components=None):
    
    if not url:
        return False
    _enqueue(_post_sync, url, embed, content, components)
    return True

def _post_sync(url, embed, content="", components=None):
    if not url:
        return False
    payload = {"embeds": [embed]}
    if content:
        payload["content"] = content
    if components:
        payload["components"] = components
        if "/api/webhooks/" in url:
            url = url.replace("/api/webhooks/", "/api/v10/webhooks/")

    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        error_msg = f"[Webhook] sending failed ({url[:40]}...): {e}"
        if 'r' in locals() and r.text:
            error_msg += f" | Response: {r.text}"
        print(error_msg)
        return False

def _post_with_image(url, embed, image_bytes, filename="screenshot.png", content=""):
    
    if not url:
        return False
    _enqueue(_post_with_image_sync, url, embed, image_bytes, filename, content)
    return True

def _post_with_image_sync(url, embed, image_bytes, filename="screenshot.png", content=""):
    
    if not url:
        return False
    embed = dict(embed)
    embed["image"] = {"url": f"attachment://{filename}"}
    payload = {"embeds": [embed]}
    if content:
        payload["content"] = content
    try:
        files = {
            "payload_json": (None, json.dumps(payload), "application/json"),
            "files[0]": (filename, image_bytes, "image/png"),
        }
        r = requests.post(url, files=files, timeout=15)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        error_msg = f"[Webhook] image send failed ({url[:40]}...): {e}"
        if 'r' in locals() and r.text:
            error_msg += f" | Response: {r.text}"
        print(error_msg)
        return False

def _post_with_images(url, embed, images, content=""):
    
    if not url or not images:
        return False
    _enqueue(_post_with_images_sync, url, embed, images, content)
    return True

def _post_with_images_sync(url, embed, images, content=""):
    
    if not url or not images:
        return False
    embed = dict(embed)
    embed["image"] = {"url": f"attachment://{images[0][0]}"}
    payload = {"embeds": [embed]}
    if content:
        payload["content"] = content
    try:
        files = {"payload_json": (None, json.dumps(payload), "application/json")}
        for i, (name, data) in enumerate(images):
            files[f"files[{i}]"] = (name, data, "image/png")
        r = requests.post(url, files=files, timeout=20)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        error_msg = f"[Webhook] multi-image send failed ({url[:40]}...): {e}"
        if 'r' in locals() and r.text:
            error_msg += f" | Response: {r.text}"
        print(error_msg)
        return False

def _base_embed(description, title=None, color=0x4F5460, thumbnail=None, author=None, fields=None, version="?"):
    embed = {
        "description": description,
        "color": color,
        "timestamp": _now_iso(),
        "footer": {"text": f"{FOOTER_TEXT} v{version}", "icon_url": FOOTER_ICON},
    }
    if title:
        embed["title"] = title
    if thumbnail:
        embed["thumbnail"] = {"url": thumbnail}
    if author:
        embed["author"] = author
    if fields:
        embed["fields"] = fields
    return embed

def _author_for(account):
    if not account:
        return None
    a = {"name": account.get("name") or "Unknown"}
    if account.get("avatar"):
        a["icon_url"] = account["avatar"]
    return a

def macro_started(urls, account_names, version):
    name_count = len(account_names) if account_names else 0
    webhook_count = len(urls) if urls else 0
    embed = _base_embed(
        description=f"## SolRich Started\n**Accounts: ** {name_count}\n**Webhooks: ** {webhook_count}\n**Version: ** v{version}\n\n**[Support Server]({DISCORD_INVITE})**",
        color=COLOR_GREEN,
        thumbnail=FOOTER_ICON,
        version=version
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

def macro_stopped(urls, session_time, version):
    embed = _base_embed(
        description=f"## SolRich Stopped\n**Session Time: ** {session_time}\n**Version: ** v{version}\n\n**[Support Server]({DISCORD_INVITE})**",
        color=COLOR_RED,
        thumbnail=FOOTER_ICON,
        version=version
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

def biome_started(urls, account, biome_key, session_time, version, unknown=False,
                  ping_content=None):
    name = biomes.display_name(biome_key)

    link = (account or {}).get("link", "")

    if ping_content is not None:
        content = ping_content
    else:
        content = "@everyone" if biomes.is_ping_biome(biome_key) else ""

    title = f"## Biome Started - {name}"
    sim_line = ""

    embed = _base_embed(
        description=f"{title}\n{sim_line}> ### **[Join Server]({link})**\n**Account: **{(account or {}).get('name','?')}\n**Session Time: ** {session_time}",
        color=biomes.color_of(biome_key),
        thumbnail=biomes.thumbnail(biome_key) or None,
        author=_author_for(account),
        version=version
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed, content=content)



def biome_ended(urls, account, biome_key, session_time, version,
                ):
    name = biomes.display_name(biome_key)
    title = f"## Biome Ended - {name}"
    sim_line = ""
    embed = _base_embed(
        description=f"{title}\n{sim_line}> ### **[Support Server]({DISCORD_INVITE})**\n**Account: **{(account or {}).get('name','?')}\n**Session Time: ** {session_time}",
        color=biomes.color_of(biome_key),
        thumbnail=biomes.thumbnail(biome_key) or None,
        author=_author_for(account),
        version=version
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

def roblox_disconnected(urls, account, version):
    link = (account or {}).get("link", "")
    embed = _base_embed(
        description=f"## Account Disconnected\n> ### **[Support Server]({DISCORD_INVITE})**\n**Account: **{(account or {}).get('name','?')}",
        color=COLOR_ORANGE,
        author=_author_for(account),
        version=version
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

def roblox_reconnected(urls, account, version):
    embed = _base_embed(
        description=f"## Account Reconnected\n> ### **[Support Server]({DISCORD_INVITE})**\n**Account: **{(account or {}).get('name','?')}",
        color=COLOR_GREEN,
        author=_author_for(account),
        version=version
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

def fake_rare_ping(urls, account, version):
    embed = _base_embed(
        description=(
            f"## ⚠️ Fake Rare Biome Ping Blocked\n"
            f"> ### **[Support Server]({DISCORD_INVITE})**\n"
            f"**Account: **{(account or {}).get('name','?')}\n\n"
            f"A rare biome was logged right after a disconnect, so its ping was **not "
            f"sent**. An unverified ping like this can get you banned."
        ),
        color=COLOR_RED,
        author=_author_for(account),
        version=version
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

def fish_caught(urls, account, total_caught, since_sell, session_time, version):
    embed = _base_embed(
        description=(
            f"## Fish Caught\n"
            f"> ### **[Support Server]({DISCORD_INVITE})**\n"
            f"**Total Caught: ** {total_caught}\n"
            f"**Since Last Sell: ** {since_sell}\n"
            f"**Session Time: ** {session_time}"
        ),
        color=COLOR_GREEN,
        thumbnail=FOOTER_ICON,
        author=_author_for(account),
        version=version
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

def fish_failed(urls, account, total_caught, session_time, version):
    embed = _base_embed(
        description=(
            f"## Fishing Failed\n"
            f"> ### **[Support Server]({DISCORD_INVITE})**\n"
            f"**Total Caught: ** {total_caught}\n"
            f"**Session Time: ** {session_time}"
        ),
        color=COLOR_RED,
        thumbnail=FOOTER_ICON,
        author=_author_for(account),
        version=version
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

def sell_route(urls, account, route_name, total_caught, session_time, version, shop=True):
    detail = "with shop" if shop else "no shop"
    embed = _base_embed(
        description=(
            f"## Sell Route Started\n"
            f"> ### **[Support Server]({DISCORD_INVITE})**\n"
            f"**Route: ** {route_name or '?'} ({detail})\n"
            f"**Total Caught: ** {total_caught}\n"
            f"**Session Time: ** {session_time}"
        ),
        color=COLOR_ORANGE,
        thumbnail=FOOTER_ICON,
        author=_author_for(account),
        version=version
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

_TASK_TITLES = {
    "strangeController": "Strange Controller",
    "biomeRandomizer": "Biome Randomizer",
    "merchantTeleporter": "Merchant Detection",
}

def module_used(urls, task, account, success, session_time, version, detail=""):
    
    title = _TASK_TITLES.get(task, task)
    if success:
        head = f"## {title} - Used"
        color = COLOR_GREEN
    else:
        head = f"## {title} - Failed"
        color = COLOR_RED
    lines = [
        head,
        f"> ### **[Support Server]({DISCORD_INVITE})**",
        f"**Account: **{(account or {}).get('name','?')}",
    ]
    if detail:
        lines.append(f"**Detail: ** {detail}")
    lines.append(f"**Session Time: ** {session_time}")
    embed = _base_embed(
        description="\n".join(lines),
        color=color,
        thumbnail=FOOTER_ICON,
        author=_author_for(account),
        version=version
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

def merchant_detected(urls, account, merchant_name, mid, session_time, version, image_bytes=None):
    
    found = bool(merchant_name)
    link = (account or {}).get("link", "")

    if found:
        head = f"## Merchant Arrived - {merchant_name}"
        color = MERCHANT_COLORS.get((mid or "").lower(), COLOR_GREY)
        description = (
            f"{head}\n"
            f"> ### **[Join Server]({link})**\n"
            f"**Account: **{(account or {}).get('name','?')}\n"
            f"**Session Time: ** {session_time}"
        )
    else:

        head = "## Merchant - No Match"
        color = COLOR_ORANGE
        description = (
            f"{head}\n"
            f"**Account: **{(account or {}).get('name','?')}\n"
            f"**Session Time: ** {session_time}"
        )

    embed = _base_embed(
        description=description,
        color=color,
        thumbnail=FOOTER_ICON,
        author=_author_for(account),
        version=version
    )
    event_log.maybe_log(embed, image_bytes=image_bytes)
    for url in urls:
        if image_bytes:
            _post_with_image(url, embed, image_bytes, filename="merchant.png")
        else:
            _post(url, embed)

def merchant_autobuy(urls, account, merchant_name, mid, item, purchased, wanted, wanted_left, session_time, version):
    
    color = MERCHANT_COLORS.get((mid or "").lower(), COLOR_GREEN)
    embed = _base_embed(
        description=(
            f"## Merchant Auto Buy - {item}\n"
            f"> ### **[Support Server]({DISCORD_INVITE})**\n"
            f"**Merchant: ** {merchant_name}\n"
            f"**Purchase Amount: ** {purchased}\n"
            f"**Wanted Amount: ** {wanted}\n"
            f"**Wanted Amount Left: ** {wanted_left}\n"
            f"**Account: **{(account or {}).get('name','?')}\n"
            f"**Session Time: ** {session_time}"
        ),
        color=color,
        thumbnail=FOOTER_ICON,
        author=_author_for(account),
        version=version,
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

def autopop_used(urls, account, biome_key, used_items, session_time, version):
    
    link = (account or {}).get("link", "")
    if used_items:
        item_lines = "\n".join(f"• **{nm}** ×{amt}" for nm, amt in used_items)
    else:
        item_lines = "• _No items used_"
    embed = _base_embed(
        description=(
            f"## Auto Pop\n"
            f"> ### **[Join Server]({link})**\n"
            f"**Account: **{(account or {}).get('name','?')}\n"
            f"**Items Used:**\n{item_lines}\n"
            f"**Session Time: ** {session_time}"
        ),
        color=COLOR_GREEN,
        thumbnail=FOOTER_ICON,
        author=_author_for(account),
        version=version,
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

def autopop_failsafe(urls, account, biome_key, missing_items, session_time, version):
    
    if missing_items:
        miss_lines = "\n".join(f"• **{nm}**" for nm in missing_items)
    else:
        miss_lines = "• _Unknown_"
    embed = _base_embed(
        description=(
            f"## Auto Pop Failsafe\n"
            f"> ### **[Support Server]({DISCORD_INVITE})**\n"
            f"**Account: **{(account or {}).get('name','?')}\n"
            f"**Item(s) not found:**\n{miss_lines}\n"
            f"**Session Time: ** {session_time}"
        ),
        color=COLOR_RED,
        thumbnail=FOOTER_ICON,
        author=_author_for(account),
        version=version,
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)

def failsafe_result(urls, label, account, success, session_time, version, detail=""):
    
    if success:
        head = f"## {label} - Passed"
        color = COLOR_GREEN
    else:
        head = f"## {label} - Triggered"
        color = COLOR_RED
    lines = [
        head,
        f"> ### **[Support Server]({DISCORD_INVITE})**",
    ]
    if account:
        lines.append(f"**Account: **{(account or {}).get('name','?')}")
    if detail:
        lines.append(f"**Detail: ** {detail}")
    lines.append(f"**Session Time: ** {session_time}")
    embed = _base_embed(
        description="\n".join(lines),
        color=color,
        thumbnail=FOOTER_ICON,
        author=_author_for(account),
        version=version
    )
    event_log.maybe_log(embed)
    for url in urls:
        _post(url, embed)
