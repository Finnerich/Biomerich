from datetime import datetime, timezone

import copy
import json
import queue
import threading
import functools
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from . import biomes
from . import discord_components as cv2
from . import event_log

FOOTER_TEXT = "SolRich"
FOOTER_ICON = (
    "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/solrich-logo.png"
)
DISCORD_INVITE = "https://discord.gg/X7dbbQ5pXV"
CREATOR_CREDIT = (
    "Macro made by [youtube.com/@Finnerich](https://www.youtube.com/@Finnerich)"
)

COLOR_GREEN = 0x57F287
COLOR_RED = 0xED4245
COLOR_ORANGE = 0xFAA61A
COLOR_GREY = 0x4F5460


IS_COMPONENTS_V2 = cv2.IS_COMPONENTS_V2
COMPONENT_TEXT_DISPLAY = cv2.TEXT_DISPLAY
COMPONENT_MEDIA_GALLERY = cv2.MEDIA_GALLERY
COMPONENT_CONTAINER = cv2.CONTAINER
SPACING_SMALL = cv2.SPACING_SMALL
SPACING_LARGE = cv2.SPACING_LARGE

MERCHANT_COLORS = {
    "mari": 0xFFFFFF,
    "jester": 0x9B59B6,
    "rin": 0xFAA61A,
}

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
        _wh_worker = threading.Thread(
            target=_wh_loop, name="webhook-worker", daemon=True
        )
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


def _components_webhook_url(url):
    
    if "/api/webhooks/" in url:
        url = url.replace("/api/webhooks/", "/api/v10/webhooks/")
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["with_components"] = "true"
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def _payload_for(message, content=""):
    
    if message.get("flags") != IS_COMPONENTS_V2 or not message.get("components"):
        raise ValueError("Webhook messages must use Discord Components v2")
    payload = copy.deepcopy(message)
    if content:
        payload["components"].insert(
            0,
            {
                "type": cv2.TEXT_DISPLAY,
                "content": content,
            },
        )
    return payload


def _post(url, message, content="", components=None):
    
    if not url:
        return False
    _enqueue(_post_sync, url, message, content, components)
    return True


def _post_sync(url, message, content="", components=None):
    if not url:
        return False
    payload = _payload_for(message, content)
    if components:
        payload["components"] = copy.deepcopy(components)

    if payload.get("flags") == IS_COMPONENTS_V2:
        url = _components_webhook_url(url)

    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        error_msg = f"[Webhook] sending failed ({url[:40]}...): {e}"
        if "r" in locals() and r.text:
            error_msg += f" | Response: {r.text}"
        print(error_msg)
        return False


def _post_with_image(url, message, image_bytes, filename="screenshot.png", content=""):
    
    if not url:
        return False
    _enqueue(_post_with_image_sync, url, message, image_bytes, filename, content)
    return True


def _post_with_image_sync(
    url, message, image_bytes, filename="screenshot.png", content=""
):
    
    if not url:
        return False
    payload = _payload_for(message, content)
    url = _components_webhook_url(url)
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
        if "r" in locals() and r.text:
            error_msg += f" | Response: {r.text}"
        print(error_msg)
        return False


def _post_with_images(url, message, images, content=""):
    
    if not url or not images:
        return False
    _enqueue(_post_with_images_sync, url, message, images, content)
    return True


def _post_with_images_sync(url, message, images, content=""):
    
    if not url or not images:
        return False
    payload = _payload_for(message, content)
    url = _components_webhook_url(url)
    try:
        files = {"payload_json": (None, json.dumps(payload), "application/json")}
        for i, (name, data) in enumerate(images):
            files[f"files[{i}]"] = (name, data, "image/png")
        r = requests.post(url, files=files, timeout=20)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        error_msg = f"[Webhook] multi-image send failed ({url[:40]}...): {e}"
        if "r" in locals() and r.text:
            error_msg += f" | Response: {r.text}"
        print(error_msg)
        return False


def _container(color):
    return cv2.Container(accent_color=color)


def _add_author(container, account):
    
    account = account or {}
    user_id = account.get("robloxUserId")
    username = account.get("robloxUsername") or account.get("name")
    if user_id and username:
        profile_url = f"https://www.roblox.com/users/{user_id}/profile"
        container.text(
            f"-# **[{username}]({profile_url})**  •  `{user_id}`"
        )
    else:
        container.text("-# **Account not found**")
    container.separator(divider=False, spacing=SPACING_SMALL)
    return container


def _add_header(container, content, thumbnail=None):
    if thumbnail:
        container.section(content, thumbnail=thumbnail)
    else:
        container.text(content)
    return container


def _add_footer(container, version, separator=True):
    
    created_at = int(datetime.now(timezone.utc).timestamp())
    if separator:
        container.separator(divider=False, spacing=SPACING_SMALL)
    container.text(f"-# **{FOOTER_TEXT} v{version}**  •  <t:{created_at}:F>")
    return container


def _add_support_footer(container, version):
    
    container.separator(spacing=SPACING_SMALL)
    container.text(f"> ### **[Support Server]({DISCORD_INVITE})**")
    container.separator(spacing=SPACING_SMALL)
    _add_footer(container, version, separator=False)
    return container


def _add_biome_event_layout(
    container,
    account,
    biome_key,
    title,
    session_time,
    version,
    simulation_line="",
):
    
    account = account or {}
    _add_author(container, account)
    _add_header(
        container,
        f"{title}\n{simulation_line}"
        f"> ## **[Support Server]({DISCORD_INVITE})**\n"
        f"> {CREATOR_CREDIT}",
        thumbnail=biomes.thumbnail(biome_key) or None,
    )
    container.separator(spacing=SPACING_SMALL)
    container.text(
        f"**Account**: {account.get('name', '?')}\n"
        f"**Session Time:** {session_time}"
    )
    private_server_link = account.get("link", "")
    if private_server_link:
        container.separator(spacing=SPACING_SMALL)
        container.action_row(
            cv2.Button.link(
                "Join Private Server",
                private_server_link,
                emoji={"name": "📬"},
            )
        )
        container.separator(spacing=SPACING_SMALL)
        _add_footer(container, version, separator=False)
    else:
        _add_footer(container, version)
    return container


def _message(container):
    return cv2.Message().container(container).build()


def macro_started(urls, account_names, version):
    name_count = len(account_names) if account_names else 0
    webhook_count = len(urls) if urls else 0
    container = _container(COLOR_GREEN)
    container.section(
        "## SolRich Started\n"
        f"**Accounts:** {name_count}\n"
        f"**Webhooks:** {webhook_count}\n"
        f"**Version:** v{version}",
        thumbnail=FOOTER_ICON,
    )
    container.separator(spacing=SPACING_SMALL)
    container.text(f"> ### [Support Server]({DISCORD_INVITE})")
    container.separator(spacing=SPACING_SMALL)
    _add_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message)
    for url in urls:
        _post(url, message)


def macro_stopped(urls, session_time, version):
    container = _container(COLOR_RED)
    container.section(
        "## SolRich Stopped\n"
        f"**Session Time:** {session_time}\n"
        f"**Version:** v{version}",
        thumbnail=FOOTER_ICON,
    )
    container.separator(spacing=SPACING_SMALL)
    container.text(f"> ### [Support Server]({DISCORD_INVITE})")
    container.separator(spacing=SPACING_SMALL)
    _add_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message)
    for url in urls:
        _post(url, message)


def biome_started(
    urls,
    account,
    biome_key,
    session_time,
    version,
    unknown=False,
    ping_content=None,
):
    name = biomes.display_name(biome_key)

    if ping_content is not None:
        content = ping_content
    else:
        content = "@everyone" if biomes.is_ping_biome(biome_key) else ""

    title = f"# Biome Started - {name}"
    sim_line = ""

    container = _container(biomes.color_of(biome_key))
    _add_biome_event_layout(
        container,
        account,
        biome_key,
        title,
        session_time,
        version,
        simulation_line=sim_line,
    )
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message, content=content)


def aura_found(
    urls,
    account,
    aura_name,
    rarity,
    version,
    *,
    category="",
    color=0xFFFFFF,
    condition_label="",
    session_time="00:00:00",
    ping_user_id="",
):
    
    account = account or {}
    account_name = account.get("name", "?")
    rarity_text = f" - 1 in {int(rarity):,}" if rarity else ""
    condition_text = f" ({condition_label})" if condition_label else ""
    simulation_text = ""

    try:
        accent_color = int(color)
    except (TypeError, ValueError):
        accent_color = 0xFFFFFF
    if not 0 <= accent_color <= 0xFFFFFF:
        accent_color = 0xFFFFFF

    container = _container(accent_color)
    _add_author(container, account)
    _add_header(
        container,
        f"## ✨ {account_name} HAS FOUND {aura_name}{rarity_text}"
        f"{condition_text}{simulation_text}",
    )
    container.separator(spacing=SPACING_SMALL)
    details = []
    if category:
        details.append(f"**Category:** {category}")
    details.extend([
        f"**Account:** {account_name}",
        f"**Session Time:** {session_time}",
    ])
    container.text("\n".join(details))
    _add_support_footer(container, version)
    message = _message(container)
    user_id = str(ping_user_id or "").strip()
    allowed_users = []
    if user_id.isdigit() and 15 <= len(user_id) <= 22:
        allowed_users = [user_id]
        content = f"<@{user_id}>"
    else:
        content = ""



    message["allowed_mentions"] = {
        "parse": [],
        "users": allowed_users,
        "roles": [],
        "replied_user": False,
    }
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message, content=content)






def biome_ended(
    urls,
    account,
    biome_key,
    session_time,
    version,
):
    name = biomes.display_name(biome_key)
    title = f"# Biome Ended - {name}"
    sim_line = ""
    container = _container(biomes.color_of(biome_key))
    _add_biome_event_layout(
        container,
        account,
        biome_key,
        title,
        session_time,
        version,
        simulation_line=sim_line,
    )
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message)


def roblox_disconnected(urls, account, version):
    container = _container(COLOR_ORANGE)
    _add_author(container, account)
    container.text(
        f"## Account Disconnected\n**Account:** {(account or {}).get('name', '?')}"
    )
    container.separator(spacing=SPACING_SMALL)
    container.text(f"> ### **[Support Server]({DISCORD_INVITE})**")
    container.separator(spacing=SPACING_SMALL)
    _add_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message)


def roblox_reconnected(urls, account, version):
    container = _container(COLOR_GREEN)
    _add_author(container, account)
    container.text(
        f"## Account Reconnected\n**Account:** {(account or {}).get('name', '?')}"
    )
    container.separator(spacing=SPACING_SMALL)
    container.text(f"> ### **[Support Server]({DISCORD_INVITE})**")
    container.separator(spacing=SPACING_SMALL)
    _add_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message)


def fake_rare_ping(urls, account, version):
    container = _container(COLOR_RED)
    _add_author(container, account)
    container.text(
        f"## ⚠️ Fake Rare Biome Ping Blocked\n"
        f"**Account:** {(account or {}).get('name', '?')}\n"
        f"A rare biome was logged right after a disconnect, so its ping was **not sent**."
    )
    container.separator(spacing=SPACING_SMALL)
    container.text(f"> ### **[Support Server]({DISCORD_INVITE})**")
    container.separator(spacing=SPACING_SMALL)
    _add_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message)


def fish_caught(urls, account, total_caught, since_sell, session_time, version):
    container = _container(COLOR_GREEN)
    _add_author(container, account)
    container.section(
        f"## Fish Caught\n"
        f"**Total Caught:** {total_caught}\n"
        f"**Since Last Sell:** {since_sell}\n"
        f"**Session Time:** {session_time}",
        thumbnail=FOOTER_ICON,
    )
    _add_support_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message)


def fish_failed(urls, account, total_caught, session_time, version):
    container = _container(COLOR_RED)
    _add_author(container, account)
    container.section(
        f"## Fishing Failed\n"
        f"**Total Caught:** {total_caught}\n"
        f"**Session Time:** {session_time}",
        thumbnail=FOOTER_ICON,
    )
    _add_support_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message)


def sell_route(
    urls, account, route_name, total_caught, session_time, version, shop=True
):
    detail = "with shop" if shop else "no shop"
    container = _container(COLOR_ORANGE)
    _add_author(container, account)
    container.section(
        f"## Sell Route Started\n"
        f"**Route:** {route_name or '?'} ({detail})\n"
        f"**Total Caught:** {total_caught}\n"
        f"**Session Time:** {session_time}",
        thumbnail=FOOTER_ICON,
    )
    _add_support_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message)


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
    detail_lines = [f"**Account:** {(account or {}).get('name', '?')}"]
    if detail:
        detail_lines.append(f"**Detail:** {detail}")
    detail_lines.append(f"**Session Time:** {session_time}")

    container = _container(color)
    _add_author(container, account)
    container.section(
        f"{head}\n" + "\n".join(detail_lines),
        thumbnail=FOOTER_ICON,
    )
    _add_support_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message)


def merchant_detected(
    urls, account, merchant_name, mid, session_time, version, image_bytes=None
):
    
    found = bool(merchant_name)

    if found:
        head = f"## Merchant Arrived - {merchant_name}"
        color = MERCHANT_COLORS.get((mid or "").lower(), COLOR_GREY)
    else:
        head = "## Merchant - No Match"
        color = COLOR_ORANGE

    container = _container(color)
    _add_author(container, account)
    container.section(
        f"{head}\n"
        f"**Account:** {(account or {}).get('name', '?')}\n"
        f"**Session Time:** {session_time}",
        thumbnail=FOOTER_ICON,
    )
    if image_bytes:
        container.separator(spacing=SPACING_SMALL)
        container.media_gallery(
            "attachment://merchant.png",
            description="Merchant capture",
        )
    private_server_link = str((account or {}).get("link") or "").strip()
    if found and private_server_link:
        container.separator(spacing=SPACING_SMALL)
        container.action_row(
            cv2.Button.link(
                "Join Private Server",
                private_server_link,
                emoji={"name": "📬"},
            )
        )
    _add_support_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message, image_bytes=image_bytes, account=account)
    for url in urls:
        if image_bytes:
            _post_with_image(url, message, image_bytes, filename="merchant.png")
        else:
            _post(url, message)


def merchant_autobuy(
    urls,
    account,
    merchant_name,
    mid,
    item,
    purchased,
    wanted,
    wanted_left,
    session_time,
    version,
):
    
    color = MERCHANT_COLORS.get((mid or "").lower(), COLOR_GREEN)
    container = _container(color)
    _add_author(container, account)
    container.section(
        f"## Merchant Auto Buy - {item}\n"
        f"**Merchant:** {merchant_name}\n"
        f"**Purchase Amount:** {purchased}\n"
        f"**Wanted Amount:** {wanted}\n"
        f"**Wanted Amount Left:** {wanted_left}\n"
        f"**Account:** {(account or {}).get('name', '?')}\n"
        f"**Session Time:** {session_time}",
        thumbnail=FOOTER_ICON,
    )
    _add_support_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message)


def autopop_used(urls, account, biome_key, used_items, session_time, version):
    
    if used_items:
        item_lines = "\n".join(f"• **{nm}** ×{amt}" for nm, amt in used_items)
    else:
        item_lines = "• _No items used_"
    container = _container(COLOR_GREEN)
    _add_author(container, account)
    container.section(
        f"## Auto Pop\n"
        f"**Account:** {(account or {}).get('name', '?')}\n"
        f"**Items Used:**\n{item_lines}\n"
        f"**Session Time:** {session_time}",
        thumbnail=FOOTER_ICON,
    )
    _add_support_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message)


def autopop_failsafe(urls, account, biome_key, missing_items, session_time, version):
    
    if missing_items:
        miss_lines = "\n".join(f"• **{nm}**" for nm in missing_items)
    else:
        miss_lines = "• _Unknown_"
    container = _container(COLOR_RED)
    _add_author(container, account)
    container.section(
        f"## Auto Pop Failsafe\n"
        f"**Account:** {(account or {}).get('name', '?')}\n"
        f"**Item(s) not found:**\n{miss_lines}\n"
        f"**Session Time:** {session_time}",
        thumbnail=FOOTER_ICON,
    )
    _add_support_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message)


def failsafe_result(urls, label, account, success, session_time, version, detail=""):
    
    if success:
        head = f"## {label} - Passed"
        color = COLOR_GREEN
    else:
        head = f"## {label} - Triggered"
        color = COLOR_RED
    detail_lines = []
    if account:
        detail_lines.append(f"**Account:** {(account or {}).get('name', '?')}")
    if detail:
        detail_lines.append(f"**Detail:** {detail}")
    detail_lines.append(f"**Session Time:** {session_time}")

    container = _container(color)
    _add_author(container, account)
    container.section(
        f"{head}\n" + "\n".join(detail_lines),
        thumbnail=FOOTER_ICON,
    )
    _add_support_footer(container, version)
    message = _message(container)
    event_log.maybe_log(message, account=account)
    for url in urls:
        _post(url, message)
