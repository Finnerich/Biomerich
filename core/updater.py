import re

import requests

GITHUB_REPO = "Finnerich/Biomerich"

_LIST_URL = "https://api.github.com/repos/{repo}/releases"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "SolRich-Updater",
}

_CHANNEL_MATCHERS = [
    ("hotfix",       re.compile(r"(?:hotfix|hf|fix)", re.I)),
    ("early-access", re.compile(r"(?:early[-_ ]?access|ea)", re.I)),
    ("rc",           re.compile(r"(?:rc|release[-_ ]?candidate)", re.I)),
    ("alpha",        re.compile(r"(?:alpha|a(?=\d))", re.I)),
    ("beta",         re.compile(r"(?:beta|b(?=\d))", re.I)),
]
_UNSTABLE = {"alpha", "beta", "early-access", "rc"}

_CHANNEL_RANK = {
    "alpha": 0,
    "beta": 1,
    "rc": 2,
    "early-access": 3,
    "stable": 4,
    "hotfix": 5,
}

def _normalize(tag):
    return (tag or "").strip().lstrip("vV").lower()

def _split_tag(tag):
    
    body = _normalize(tag)
    m = re.match(r"\d+(?:\.\d+)*", body)
    num = m.group(0) if m else ""
    return num, body[len(num):].lstrip(".-_+ ")

def _numeric(tag):
    num, _ = _split_tag(tag)
    parts = [int(p) for p in num.split(".") if p.isdigit()]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])

def _parse_channel(tag):
    
    _, suffix = _split_tag(tag)
    if not suffix:
        return "stable", 0
    for name, matcher in _CHANNEL_MATCHERS:
        m = matcher.match(suffix)
        if m:
            nm = re.match(r"[-_. ]?(\d+)", suffix[m.end():])
            return name, (int(nm.group(1)) if nm else 1)
    return "stable", 0

def _channel(tag):
    return _parse_channel(tag)[0]

def is_unstable(tag):
    return _channel(tag) in _UNSTABLE

def rank(tag):
    
    num = _numeric(tag)
    channel, build = _parse_channel(tag)
    return (num, _CHANNEL_RANK.get(channel, _CHANNEL_RANK["stable"]), build)

def update_available(latest_tag, current):
    
    if not latest_tag:
        return False
    return rank(latest_tag) > rank(current)

def _fetch_releases(repo):
    r = requests.get(
        _LIST_URL.format(repo=repo),
        headers=_HEADERS,
        params={"per_page": 100},
        timeout=10,
    )
    if r.status_code == 404:
        return None, "no_releases"
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        return None, "bad_response"
    return data, None

def _release_entry(rel, repo):
    tag = (rel.get("tag_name") or rel.get("name") or "").strip()
    channel = _channel(tag)
    assets, exe = [], None
    for a in (rel.get("assets") or []):
        url = a.get("browser_download_url")
        name = (a.get("name") or "").strip()
        if not url:
            continue
        item = {"name": name, "url": url, "size": int(a.get("size") or 0)}
        assets.append(item)
        if exe is None and name.lower().endswith(".exe"):
            exe = item
    return {
        "tag": tag,
        "name": (rel.get("name") or tag).strip(),
        "body": rel.get("body") or "",
        "url": rel.get("html_url") or f"https://github.com/{repo}/releases/tag/{tag}",
        "publishedAt": rel.get("published_at") or rel.get("created_at") or "",
        "prerelease": bool(rel.get("prerelease")),
        "channel": channel,
        "unstable": channel in _UNSTABLE,
        "assets": assets,
        "exeName": exe["name"] if exe else None,
        "exeUrl": exe["url"] if exe else None,
        "exeSize": exe["size"] if exe else 0,
    }

def check_for_update(current_version, repo=GITHUB_REPO):
    result = {
        "ok": False,
        "available": False,
        "current": current_version or "?",
        "latest": None,
        "url": None,
        "channel": "stable",
        "unstable": False,
        "error": None,
    }
    if not repo or "/" not in repo:
        result["error"] = "no_repo_configured"
        return result
    try:
        data, err = _fetch_releases(repo)
    except (requests.RequestException, ValueError) as exc:
        result["error"] = f"request_failed: {exc}"
        return result
    if err:
        result["error"] = err
        return result

    entries = [_release_entry(rel, repo) for rel in data
               if not rel.get("draft") and (rel.get("tag_name") or rel.get("name"))]
    entries = [e for e in entries if e["tag"]]
    if not entries:
        result["error"] = "no_releases"
        return result

    latest = max(entries, key=lambda e: rank(e["tag"]))
    result["ok"] = True
    result["latest"] = latest["tag"]
    result["url"] = latest["url"]
    result["channel"] = latest["channel"]
    result["unstable"] = latest["unstable"]
    result["available"] = update_available(latest["tag"], current_version)
    return result

def get_all_releases(current_version="", repo=GITHUB_REPO):
    result = {
        "ok": False,
        "current": current_version or "?",
        "latest": None,
        "available": False,
        "unstable": False,
        "channel": "stable",
        "releases": [],
        "error": None,
    }
    if not repo or "/" not in repo:
        result["error"] = "no_repo_configured"
        return result
    try:
        data, err = _fetch_releases(repo)
    except (requests.RequestException, ValueError) as exc:
        result["error"] = f"request_failed: {exc}"
        return result
    if err:
        result["error"] = err
        return result

    releases = []
    for rel in data:
        if rel.get("draft"):
            continue
        entry = _release_entry(rel, repo)
        if entry["tag"]:
            releases.append(entry)

    releases.sort(key=lambda e: rank(e["tag"]), reverse=True)

    result["ok"] = True
    result["releases"] = releases
    if releases:
        latest = releases[0]
        result["latest"] = latest["tag"]
        result["channel"] = latest["channel"]
        result["unstable"] = latest["unstable"]
        result["available"] = update_available(latest["tag"], current_version)
    return result
