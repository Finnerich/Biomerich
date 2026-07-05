import base64
import json
import os
import sys

IS_WINDOWS = sys.platform == "win32"

STORE_FILENAME = "tokens.dat"

_ENTROPY = b"Biomerich.AccountTokenStore.v1"
_OBFUSCATE_KEY = b"Biomerich-local-obfuscation-key"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    _CRYPTPROTECT_UI_FORBIDDEN = 0x01

    def _blob(data):
        buf = ctypes.create_string_buffer(data, len(data))
        return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    def _blob_to_bytes(blob):
        size = int(blob.cbData)
        raw = ctypes.string_at(blob.pbData, size)
        if blob.pbData:
            _kernel32.LocalFree(blob.pbData)
        return raw

    def _dpapi_encrypt(data):
        out = _DATA_BLOB()
        entropy = _blob(_ENTROPY)
        ok = _crypt32.CryptProtectData(
            ctypes.byref(_blob(data)), None, ctypes.byref(entropy),
            None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out),
        )
        if not ok:
            raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
        return _blob_to_bytes(out)

    def _dpapi_decrypt(data):
        out = _DATA_BLOB()
        entropy = _blob(_ENTROPY)
        ok = _crypt32.CryptUnprotectData(
            ctypes.byref(_blob(data)), None, ctypes.byref(entropy),
            None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out),
        )
        if not ok:
            raise OSError(ctypes.get_last_error(), "CryptUnprotectData failed")
        return _blob_to_bytes(out)

def _xor(data):
    key = _OBFUSCATE_KEY
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

def _encode(plain):
    raw = (plain or "").encode("utf-8")
    if IS_WINDOWS:
        try:
            return "d:" + base64.b64encode(_dpapi_encrypt(raw)).decode("ascii")
        except OSError:
            pass
    return "o:" + base64.b64encode(_xor(raw)).decode("ascii")

def _decode(stored):
    if not stored:
        return ""
    scheme, _, payload = stored.partition(":")
    try:
        raw = base64.b64decode(payload.encode("ascii"))
    except (ValueError, UnicodeDecodeError):
        return ""
    if scheme == "d" and IS_WINDOWS:
        try:
            return _dpapi_decrypt(raw).decode("utf-8", "replace")
        except OSError:
            return ""
    if scheme == "o":
        return _xor(raw).decode("utf-8", "replace")
    return ""

class SecureStore:
    def __init__(self, directory):
        self.path = os.path.join(str(directory), STORE_FILENAME)
        self._data = self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f)
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        except OSError as e:
            print(f"[SecureStore] Saving failed: {e}")

    def set(self, key, token):
        key = str(key)
        if not (token or "").strip():
            return self.delete(key)
        self._data[key] = _encode(token.strip())
        self._save()

    def get(self, key):
        return _decode(self._data.get(str(key), ""))

    def has(self, key):
        return str(key) in self._data

    def delete(self, key):
        if str(key) in self._data:
            del self._data[str(key)]
            self._save()

    def clear(self):
        
        if self._data:
            self._data = {}
            self._save()
