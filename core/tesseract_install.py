

import os
import shutil
import sys
import tempfile
import threading
import zipfile

from .config import get_config_dir

INSTALL_SUBDIR = "tesseract"

DEFAULT_URLS = [
    "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe",
    "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.4.0.20240606.exe",
    "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe",
]

def download_urls() -> list:
    override = os.getenv("SOLRICH_TESSERACT_URL") or os.getenv("BIOMERICH_TESSERACT_URL")
    return [override] if override else list(DEFAULT_URLS)

def download_url() -> str:
    return download_urls()[0]

def install_dir() -> str:
    return str(get_config_dir() / INSTALL_SUBDIR)

def bundled_tesseract_path():
    
    exe = os.path.join(install_dir(), "tesseract.exe")
    return exe if os.path.exists(exe) else None

def _global_candidates():
    
    out = []
    pf = os.getenv("ProgramFiles", r"C:\Program Files")
    pf86 = os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.getenv("LOCALAPPDATA")
    out.append(os.path.join(pf, "Tesseract-OCR", "tesseract.exe"))
    out.append(os.path.join(pf86, "Tesseract-OCR", "tesseract.exe"))
    if local:
        out.append(os.path.join(local, "Programs", "Tesseract-OCR", "tesseract.exe"))
    return out

def _registry_tesseract():
    
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except Exception:
        return None
    dirs = []
    soft = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Tesseract-OCR"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Tesseract-OCR"),
    ]
    views = (getattr(winreg, "KEY_WOW64_64KEY", 0), getattr(winreg, "KEY_WOW64_32KEY", 0))
    for root, path in soft:
        for view in views:
            try:
                with winreg.OpenKey(root, path, 0, winreg.KEY_READ | view) as k:
                    for val in ("", "Path", "InstallDir", "Current InstallFolder"):
                        try:
                            v, _ = winreg.QueryValueEx(k, val)
                            if v:
                                dirs.append(str(v))
                        except OSError:
                            pass
            except OSError:
                pass
    unins = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Tesseract-OCR"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Tesseract-OCR"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Tesseract-OCR"),
    ]
    for root, path in unins:
        try:
            with winreg.OpenKey(root, path) as k:
                try:
                    v, _ = winreg.QueryValueEx(k, "InstallLocation")
                    if v:
                        dirs.append(str(v))
                except OSError:
                    pass
        except OSError:
            pass
    for d in dirs:
        exe = os.path.join(d, "tesseract.exe")
        if os.path.exists(exe):
            return exe
    return None

def find_tesseract():
    
    p = bundled_tesseract_path()
    if p:
        return p
    for c in _global_candidates():
        if os.path.exists(c):
            return c
    return _registry_tesseract()

def is_installed() -> bool:
    return find_tesseract() is not None

_install_lock = threading.Lock()
_installing = False

def is_installing() -> bool:
    return _installing

def _emit(progress, **payload):
    if progress:
        try:
            progress(payload)
        except Exception:
            pass

def _download(url: str, dest: str, progress) -> None:
    
    import requests

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }
    with requests.get(url, stream=True, timeout=(15, 90), headers=headers) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        last_pct = -1
        _emit(progress, stage="download", downloaded=0, total=total, percent=0)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=262144):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                pct = int(done * 100 / total) if total else 0
                if pct != last_pct or not total:
                    last_pct = pct
                    _emit(progress, stage="download", downloaded=done,
                          total=total, percent=pct)
        _emit(progress, stage="download", downloaded=done,
              total=total or done, percent=100)

def _find_tesseract_root(top: str):
    
    for root, _dirs, files in os.walk(top):
        if any(f.lower() == "tesseract.exe" for f in files):
            return root
    return None

def _install_from_zip(zip_path: str, target: str, progress) -> None:
    _emit(progress, stage="extract")
    tmp = tempfile.mkdtemp(prefix="solrich_tess_")
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        root = _find_tesseract_root(tmp)
        if not root:
            raise RuntimeError("tesseract.exe not found in the downloaded archive")
        os.makedirs(target, exist_ok=True)
        for name in os.listdir(root):
            src = os.path.join(root, name)
            dst = os.path.join(target, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def _install_from_exe(exe_path: str, progress) -> None:
    
    _emit(progress, stage="extract")
    _shell_execute_and_wait(exe_path, "/S")


_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_ERROR_CANCELLED = 1223
_INFINITE = 0xFFFFFFFF


def _shell_execute_and_wait(file: str, params: str) -> None:
    import ctypes
    from ctypes import wintypes

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", ctypes.c_ulong),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIcon", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    sei = SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = _SEE_MASK_NOCLOSEPROCESS
    sei.lpVerb = "runas"
    sei.lpFile = file
    sei.lpParameters = params
    sei.nShow = 1

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32.ShellExecuteExW.restype = wintypes.BOOL

    if not shell32.ShellExecuteExW(ctypes.byref(sei)):
        err = ctypes.get_last_error()
        if err == _ERROR_CANCELLED:
            raise RuntimeError("Installation cancelled at the Windows permission prompt.")
        raise RuntimeError(f"could not start installer (WinError {err})")

    h = sei.hProcess
    if not h:
        return
    try:
        kernel32.WaitForSingleObject(h, _INFINITE)
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        if code.value not in (0,):
            raise RuntimeError(f"installer exited with code {code.value}")
    finally:
        kernel32.CloseHandle(h)

def install(progress=None) -> dict:
    
    global _installing
    with _install_lock:
        if _installing:
            return {"ok": False, "error": "already_installing"}
        _installing = True
    tmp_file = None
    try:
        if sys.platform != "win32":
            return {"ok": False, "error": "Tesseract auto-install is Windows-only."}

        if is_installed():
            _emit(progress, stage="done")
            return {"ok": True, "path": find_tesseract()}

        urls = download_urls()
        is_exe = urls[0].lower().split("?")[0].endswith(".exe")
        suffix = ".exe" if is_exe else ".zip"

        fd, tmp_file = tempfile.mkstemp(suffix=suffix, prefix="solrich_tess_")
        os.close(fd)

        import time as _time
        last_err = None
        downloaded_ok = False
        for url in urls:
            for attempt in range(3):
                try:
                    if attempt > 0:
                        _emit(progress, stage="download", downloaded=0, total=0, percent=0)
                        _time.sleep(1.5)
                    _download(url, tmp_file, progress)
                    downloaded_ok = True
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
            if downloaded_ok:
                break
        if not downloaded_ok:
            raise last_err if last_err else RuntimeError("download failed")

        if is_exe:
            _install_from_exe(tmp_file, progress)
        else:
            _install_from_zip(tmp_file, install_dir(), progress)

        if not is_installed():
            return {"ok": False,
                    "error": "Install finished but tesseract.exe is missing."}
        _emit(progress, stage="done")
        return {"ok": True, "path": find_tesseract()}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass
        _installing = False
