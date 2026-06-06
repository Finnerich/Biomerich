import re

import requests

GITHUB_REPO = "Finnerich/Biomerich"

_API_URL = "https://api.github.com/repos/{repo}/releases/latest"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Biomerich-Updater",
}

def _parse_version(v: str) -> tuple:
    v = (v or "").strip().lstrip("vV")
    parts = []
    for chunk in re.split(r"[.\-+_]", v):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            break
    return tuple(parts) if parts else (0,)

def _is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)

def check_for_update(current_version: str, repo: str = GITHUB_REPO) -> dict:
    result = {
        "ok": False,
        "available": False,
        "current": current_version or "?",
        "latest": None,
        "url": None,
        "error": None,
    }

    if not repo or "/" not in repo:
        result["error"] = "no_repo_configured"
        return result

    try:
        r = requests.get(
            _API_URL.format(repo=repo),
            headers=_HEADERS,
            timeout=8,
        )
        if r.status_code == 404:
            result["error"] = "no_releases"
            return result
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        result["error"] = f"request_failed: {e}"
        return result

    tag = (data.get("tag_name") or data.get("name") or "").strip()
    html_url = data.get("html_url") or f"https://github.com/{repo}/releases/latest"

    if not tag:
        result["error"] = "no_tag"
        return result

    result["ok"] = True
    result["latest"] = tag
    result["url"] = html_url
    result["available"] = _is_newer(tag, current_version)
    return result
