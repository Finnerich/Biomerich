

import base64
import json
import os
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time

IS_WINDOWS = sys.platform == "win32"

ROBLOX_LOGIN_URL = "https://www.roblox.com/login"
_TIMEOUT_S = 240.0

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _bcrypt = ctypes.WinDLL("bcrypt", use_last_error=True)

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    class _BCRYPT_AUTH_INFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.ULONG),
            ("dwInfoVersion", wintypes.ULONG),
            ("pbNonce", ctypes.POINTER(ctypes.c_char)),
            ("cbNonce", wintypes.ULONG),
            ("pbAuthData", ctypes.POINTER(ctypes.c_char)),
            ("cbAuthData", wintypes.ULONG),
            ("pbTag", ctypes.POINTER(ctypes.c_char)),
            ("cbTag", wintypes.ULONG),
            ("pbMacContext", ctypes.POINTER(ctypes.c_char)),
            ("cbMacContext", wintypes.ULONG),
            ("cbAAD", wintypes.ULONG),
            ("cbData", ctypes.c_ulonglong),
            ("dwFlags", wintypes.ULONG),
        ]

    _bcrypt.BCryptOpenAlgorithmProvider.argtypes = (
        ctypes.POINTER(ctypes.c_void_p), wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.ULONG)
    _bcrypt.BCryptSetProperty.argtypes = (
        ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.ULONG, wintypes.ULONG)
    _bcrypt.BCryptGetProperty.argtypes = (
        ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG), wintypes.ULONG)
    _bcrypt.BCryptGenerateSymmetricKey.argtypes = (
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, wintypes.ULONG,
        ctypes.c_char_p, wintypes.ULONG, wintypes.ULONG)
    _bcrypt.BCryptDecrypt.argtypes = (
        ctypes.c_void_p, ctypes.c_char_p, wintypes.ULONG, ctypes.c_void_p,
        ctypes.c_char_p, wintypes.ULONG, ctypes.c_char_p, wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG), wintypes.ULONG)
    _bcrypt.BCryptDestroyKey.argtypes = (ctypes.c_void_p,)
    _bcrypt.BCryptCloseAlgorithmProvider.argtypes = (ctypes.c_void_p, wintypes.ULONG)

    def _dpapi_unprotect(data: bytes) -> bytes:
        
        blob_in = _DATA_BLOB(len(data), ctypes.cast(
            ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_char)))
        blob_out = _DATA_BLOB()
        if not _crypt32.CryptUnprotectData(
                ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
            raise OSError("CryptUnprotectData failed")
        try:
            return ctypes.string_at(blob_out.pbData, int(blob_out.cbData))
        finally:
            if blob_out.pbData:
                _kernel32.LocalFree(blob_out.pbData)

    def _aes_gcm_decrypt(key: bytes, nonce: bytes, ct: bytes, tag: bytes) -> bytes:
        h_alg = ctypes.c_void_p()
        if _bcrypt.BCryptOpenAlgorithmProvider(ctypes.byref(h_alg), "AES", None, 0) != 0:
            raise OSError("BCryptOpenAlgorithmProvider failed")
        h_key = ctypes.c_void_p()
        try:
            gcm = ctypes.create_unicode_buffer("ChainingModeGCM")
            _bcrypt.BCryptSetProperty(h_alg, "ChainingMode",
                                      ctypes.cast(gcm, ctypes.c_void_p), ctypes.sizeof(gcm), 0)
            obj_len = wintypes.ULONG(0)
            got = wintypes.ULONG(0)
            _bcrypt.BCryptGetProperty(h_alg, "ObjectLength", ctypes.byref(obj_len),
                                      ctypes.sizeof(obj_len), ctypes.byref(got), 0)
            key_obj = ctypes.create_string_buffer(obj_len.value)
            if _bcrypt.BCryptGenerateSymmetricKey(
                    h_alg, ctypes.byref(h_key), key_obj, obj_len.value, key, len(key), 0) != 0:
                raise OSError("BCryptGenerateSymmetricKey failed")

            auth = _BCRYPT_AUTH_INFO()
            auth.cbSize = ctypes.sizeof(_BCRYPT_AUTH_INFO)
            auth.dwInfoVersion = 1
            nonce_buf = ctypes.create_string_buffer(nonce, len(nonce))
            auth.pbNonce = ctypes.cast(nonce_buf, ctypes.POINTER(ctypes.c_char))
            auth.cbNonce = len(nonce)
            tag_buf = ctypes.create_string_buffer(tag, len(tag))
            auth.pbTag = ctypes.cast(tag_buf, ctypes.POINTER(ctypes.c_char))
            auth.cbTag = len(tag)

            out = ctypes.create_string_buffer(len(ct))
            res = wintypes.ULONG(0)
            ct_buf = ctypes.create_string_buffer(ct, len(ct))
            status = _bcrypt.BCryptDecrypt(
                h_key, ct_buf, len(ct), ctypes.byref(auth), None, 0,
                out, len(ct), ctypes.byref(res), 0)
            if status != 0:
                raise OSError(f"BCryptDecrypt failed (0x{status & 0xffffffff:08x})")
            return out.raw[:res.value]
        finally:
            if h_key:
                _bcrypt.BCryptDestroyKey(h_key)
            _bcrypt.BCryptCloseAlgorithmProvider(h_alg, 0)


def _find_browser():
    
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pfx86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    chrome = [os.path.join(b, "Google", "Chrome", "Application", "chrome.exe")
              for b in (local, pf, pfx86) if b]
    edge = [os.path.join(b, "Microsoft", "Edge", "Application", "msedge.exe")
            for b in (pf, pfx86) if b]
    for path in chrome:
        if os.path.isfile(path):
            return path, "Chrome"
    for path in edge:
        if os.path.isfile(path):
            return path, "Edge"
    return None, None


def _read_local_state_key(profile_dir: str):
    path = os.path.join(profile_dir, "Local State")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        enc = base64.b64decode(data["os_crypt"]["encrypted_key"])
        if enc[:5] == b"DPAPI":
            enc = enc[5:]
        return _dpapi_unprotect(enc)
    except Exception:
        return None


def _cookie_db_paths(profile_dir: str):
    default = os.path.join(profile_dir, "Default")
    return [
        os.path.join(default, "Network", "Cookies"),
        os.path.join(default, "Cookies"),
    ]


def _decrypt_cookie(enc: bytes, key) -> str:
    if not enc:
        return ""
    try:
        prefix = enc[:3]
        if prefix in (b"v10", b"v11") and key:
            nonce, ct, tag = enc[3:15], enc[15:-16], enc[-16:]
            return _aes_gcm_decrypt(key, nonce, ct, tag).decode("utf-8", "ignore")
        if prefix == b"v20":
            return ""
        return _dpapi_unprotect(enc).decode("utf-8", "ignore")
    except Exception:
        return ""


def _read_roblosecurity(profile_dir: str, key) -> str:
    for db in _cookie_db_paths(profile_dir):
        if not os.path.isfile(db):
            continue
        tmp = db + ".solrich.tmp"
        try:
            for suffix in ("", "-wal", "-shm"):
                src = db + suffix
                if os.path.isfile(src):
                    shutil.copy2(src, tmp + suffix)
            con = sqlite3.connect(tmp)
            try:
                rows = con.execute(
                    "SELECT encrypted_value FROM cookies "
                    "WHERE name='.ROBLOSECURITY' AND host_key LIKE '%roblox.com' "
                    "ORDER BY LENGTH(encrypted_value) DESC"
                ).fetchall()
            finally:
                con.close()
            for (enc,) in rows:
                token = _decrypt_cookie(bytes(enc), key)
                if token and "WARNING" in token and len(token) > 100:
                    return token
        except Exception:
            pass
        finally:
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.remove(tmp + suffix)
                except OSError:
                    pass
    return ""


def _ws_connect(ws_url: str, timeout: float = 5.0):
    if not ws_url.startswith("ws://"):
        raise OSError("bad ws url")
    rest = ws_url[5:]
    host_port, _, path = rest.partition("/")
    path = "/" + path
    host, _, port_s = host_port.partition(":")
    port = int(port_s or 80)
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(req.encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise OSError("ws handshake closed")
        buf += chunk
    if b" 101 " not in buf.split(b"\r\n", 1)[0]:
        raise OSError("ws upgrade refused")
    return sock


def _ws_send(sock, text: str):
    payload = text.encode("utf-8")
    n = len(payload)
    header = bytearray([0x81])
    if n < 126:
        header.append(0x80 | n)
    elif n < 65536:
        header.append(0x80 | 126)
        header += struct.pack(">H", n)
    else:
        header.append(0x80 | 127)
        header += struct.pack(">Q", n)
    mask = os.urandom(4)
    header += mask
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    sock.sendall(bytes(header) + masked)


def _ws_recv(sock) -> bytes:
    def _read(n):
        out = b""
        while len(out) < n:
            c = sock.recv(n - len(out))
            if not c:
                raise OSError("ws closed")
            out += c
        return out

    first = _read(2)
    length = first[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", _read(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _read(8))[0]
    return _read(length) if length else b""


def _read_token_cdp(profile_dir: str) -> str:
    
    portfile = os.path.join(profile_dir, "DevToolsActivePort")
    if not os.path.isfile(portfile):
        return ""
    try:
        with open(portfile, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        if len(lines) < 2:
            return ""
        port, ws_path = int(lines[0]), lines[1]
        sock = _ws_connect(f"ws://127.0.0.1:{port}{ws_path}")
    except Exception:
        return ""
    try:
        _ws_send(sock, json.dumps({"id": 1, "method": "Storage.getCookies"}))
        for _ in range(60):
            payload = _ws_recv(sock)
            if not payload:
                continue
            try:
                msg = json.loads(payload.decode("utf-8", "ignore"))
            except Exception:
                continue
            if msg.get("id") != 1:
                continue
            cookies = ((msg.get("result") or {}).get("cookies")) or []
            for c in cookies:
                if c.get("name") == ".ROBLOSECURITY" and "roblox.com" in (c.get("domain") or ""):
                    v = c.get("value") or ""
                    if "WARNING" in v and len(v) > 100:
                        return v
            return ""
    except Exception:
        return ""
    finally:
        try:
            sock.close()
        except Exception:
            pass
    return ""


def _delete_temp_profile(path: str) -> bool:
    
    if not path:
        return True
    temp_root = os.path.normcase(os.path.realpath(tempfile.gettempdir()))
    target = os.path.normcase(os.path.realpath(path))
    if (
        os.path.dirname(target) != temp_root
        or not os.path.basename(target).startswith("solrich-login-")
    ):
        print("[BrowserLogin] Refused to delete an unexpected profile path.")
        return False
    for attempt in range(6):
        try:
            shutil.rmtree(target)
        except FileNotFoundError:
            return True
        except OSError:
            pass
        if not os.path.exists(target):
            return True
        time.sleep(0.25 * (attempt + 1))
    print("[BrowserLogin] Temporary login profile could not be fully deleted.")
    return False


class BrowserLogin:
    

    def __init__(self):
        self._lock = threading.Lock()
        self._proc = None
        self._tmp = None
        self._stop = threading.Event()
        self._thread = None
        self.active = False

    def start(self, on_done) -> dict:
        if not IS_WINDOWS:
            return {"ok": False, "error": "not_windows"}
        with self._lock:
            if self.active:
                return {"ok": False, "error": "already_running"}
            exe, name = _find_browser()
            if not exe:
                return {"ok": False, "error": "no_browser"}
            self._stop.clear()
            self.active = True
            self._thread = threading.Thread(
                target=self._run, args=(exe, name, on_done), daemon=True)
            self._thread.start()
            return {"ok": True, "browser": name}

    def cancel(self):
        self._stop.set()

    def _run(self, exe, name, on_done):
        token, error = "", None
        cleanup_ok = True
        try:
            self._tmp = tempfile.mkdtemp(prefix="solrich-login-")
            args = [
                exe,
                f"--user-data-dir={self._tmp}",
                "--no-first-run",
                "--no-default-browser-check",
                "--no-service-autorun",
                "--disable-sync",
                "--remote-debugging-address=127.0.0.1",
                "--remote-debugging-port=0",
                "--remote-allow-origins=*",
                "--new-window",
                ROBLOX_LOGIN_URL,
            ]
            self._proc = subprocess.Popen(args)
            print(f"[BrowserLogin] Opened {name} for login.")
            started = time.monotonic()
            deadline = started + _TIMEOUT_S
            while not self._stop.is_set() and time.monotonic() < deadline:
                token = _read_token_cdp(self._tmp)
                if not token:
                    key = _read_local_state_key(self._tmp)
                    token = _read_roblosecurity(self._tmp, key)
                if token:
                    break
                if (self._proc.poll() is not None
                        and (time.monotonic() - started) > 4.0):
                    error = "closed"
                    break
                self._stop.wait(1.3)
            if token:
                error = None
            elif error is None:
                error = "cancelled" if self._stop.is_set() else "timeout"
        except Exception as e:
            error = str(e)
            print(f"[BrowserLogin] Failed: {e}")
        finally:
            cleanup_ok = self._cleanup()
        if not cleanup_ok:


            token = ""
            error = "cleanup_failed"
        on_done(token or None, None if token else error)

    def _cleanup(self):
        with self._lock:
            self.active = False
        proc = self._proc
        self._proc = None
        if proc:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    creationflags=0x08000000,
                    timeout=6, capture_output=True,
                )
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
        time.sleep(0.5)
        deleted = True
        if self._tmp:
            deleted = _delete_temp_profile(self._tmp)
            self._tmp = None
        return deleted
