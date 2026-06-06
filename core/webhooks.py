from datetime import datetime, timezone

import requests

from . import biomes

FOOTER_TEXT = "Biomerich"
FOOTER_ICON = "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/fuh.jpg"
DISCORD_INVITE = "https://discord.gg/X7dbbQ5pXV"

COLOR_GREEN = 0x57F287
COLOR_RED = 0xED4245
COLOR_ORANGE = 0xFAA61A
COLOR_GREY = 0x4F5460

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _post(url, embed, content="", components=None):
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
        description=f"## Biomerich Started\n**Accounts: ** {name_count}\n**Webhooks: ** {webhook_count}\n**Version: ** v{version}\n\n**[Support Server]({DISCORD_INVITE})**",
        color=COLOR_GREEN,
        thumbnail=FOOTER_ICON,
        version=version
    )
    for url in urls:
        _post(url, embed)

def macro_stopped(urls, session_time, version):
    embed = _base_embed(
        description=f"## Biomerich Stopped\n**Session Time: ** {session_time}\n**Version: ** v{version}\n\n**[Support Server]({DISCORD_INVITE})**",
        color=COLOR_RED,
        thumbnail=FOOTER_ICON,
        version=version
    )
    for url in urls:
        _post(url, embed)

def biome_started(urls, account, biome_key, session_time, version, unknown=False):
    name = biomes.display_name(biome_key)

    is_ping = biomes.is_ping_biome(biome_key)

    link = (account or {}).get("link", "")

    content = "@everyone" if is_ping else ""

    embed = _base_embed(
        description=f"## Biome Started - {name}\n> ### **[Join Server]({link})**\n**Account: **{(account or {}).get('name','?')}\n**Session Time: ** {session_time}",
        color=biomes.color_of(biome_key),
        thumbnail=biomes.thumbnail(biome_key) or None,
        author=_author_for(account),
        version=version
    )
    for url in urls:
        _post(url, embed, content=content)

def biome_ended(urls, account, biome_key, session_time, version):
    name = biomes.display_name(biome_key)
    embed = _base_embed(
        description=f"## Biome Ended - {name}\n> ### **[Support Server]({DISCORD_INVITE})**\n**Account: **{(account or {}).get('name','?')}\n**Session Time: ** {session_time}",
        color=biomes.color_of(biome_key),
        thumbnail=biomes.thumbnail(biome_key) or None,
        author=_author_for(account),
        version=version
    )
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
    for url in urls:
        _post(url, embed)
