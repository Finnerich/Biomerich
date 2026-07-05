

import os
import subprocess
import sys
import threading

_lock = threading.Lock()
_busy = False


def is_busy() -> bool:
    return _busy


def _emit(progress, **payload):
    if progress:
        try:
            progress(payload)
        except Exception:
            pass


def _downloads_dir() -> str:
    
    path = None
    if sys.platform == "win32":
        try:
            import winreg
            guid = "{374DE290-123F-4565-9164-39C4925E467B}"
            key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                val, _ = winreg.QueryValueEx(k, guid)
                if val:
                    path = os.path.expandvars(str(val))
        except OSError:
            path = None
    if not path:
        path = os.path.join(os.path.expanduser("~"), "Downloads")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        path = os.path.expanduser("~")
    return path


def _cleanup(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _safe_name(name: str) -> str:
    base = os.path.basename((name or "").strip()) or "SolRich-update.exe"
    base = "".join(c for c in base if c.isalnum() or c in "-_.() ").strip()
    if not base.lower().endswith(".exe"):
        base += ".exe"
    return base or "SolRich-update.exe"


def _download(url: str, dest: str, progress) -> None:
    
    import requests
    import time as _t

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    }
    with requests.get(url, stream=True, timeout=(15, 90), headers=headers) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        last_emit = 0.0
        _emit(progress, stage="download", downloaded=0, total=total, percent=0)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1048576):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                now = _t.monotonic()
                if now - last_emit >= 0.12:
                    last_emit = now
                    _emit(progress, stage="download", downloaded=done, total=total,
                          percent=(int(done * 100 / total) if total else 0))
        if total and done < total:
            raise RuntimeError(f"download incomplete ({done}/{total} bytes)")
        _emit(progress, stage="download", downloaded=done, total=total or done, percent=100)


def download_and_launch(url: str, name=None, progress=None) -> dict:
    
    global _busy
    with _lock:
        if _busy:
            return {"ok": False, "error": "already_running"}
        _busy = True
    try:
        if sys.platform != "win32":
            return {"ok": False, "error": "In-app install is Windows-only — use the GitHub link."}
        if not url or not url.lower().split("?")[0].endswith(".exe"):
            return {"ok": False, "error": "This release has no downloadable .exe — use the GitHub link."}

        dest = os.path.join(_downloads_dir(), _safe_name(name or url.rsplit("/", 1)[-1]))
        part = dest + ".part"

        import time as _time
        last_err = None
        for attempt in range(3):
            try:
                if attempt:
                    _emit(progress, stage="download", downloaded=0, total=0, percent=0)
                    _time.sleep(1.5)
                _download(url, part, progress)
                last_err = None
                break
            except Exception as e:
                last_err = e
        if last_err:
            _cleanup(part)
            raise last_err

        size = os.path.getsize(part) if os.path.exists(part) else 0
        magic = b""
        if size:
            with open(part, "rb") as fh:
                magic = fh.read(2)
        if magic != b"MZ" or size < 2_000_000:
            _cleanup(part)
            return {"ok": False, "error": (
                f"The downloaded update is corrupt or was blocked by antivirus ({size // 1024} KB). "
                "Add a Defender exclusion for SolRich, or download it from GitHub.")}

        _cleanup(dest)
        os.replace(part, dest)
        if not os.path.exists(dest) or os.path.getsize(dest) < 2_000_000:
            return {"ok": False, "error": (
                "Antivirus removed the downloaded update. Add a Defender exclusion for "
                "SolRich, or download it from GitHub.")}

        _emit(progress, stage="launch")
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen([dest], close_fds=True, creationflags=flags)
        _emit(progress, stage="done", path=dest)
        return {"ok": True, "path": dest}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        _busy = False
