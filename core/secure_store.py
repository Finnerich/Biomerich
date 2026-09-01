import base64
import json
import os
import sys


IS_WINDOWS = sys.platform == "win32"
STORE_FILENAME = "tokens.dat"

_ENTROPY = b"Biomerich.AccountTokenStore.v1"
_OBFUSCATE_KEY = b"Biomerich-local-obfuscation-key"


class SecureStoreError(RuntimeError):
    pass


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
        blob = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        blob._buffer = buf
        return blob

    def _blob_to_bytes(blob):
        size = int(blob.cbData)
        raw = ctypes.string_at(blob.pbData, size)
        if blob.pbData:
            _kernel32.LocalFree(blob.pbData)
        return raw

    def _dpapi_encrypt(data):
        source = _blob(data)
        entropy = _blob(_ENTROPY)
        out = _DATA_BLOB()
        ok = _crypt32.CryptProtectData(
            ctypes.byref(source), None, ctypes.byref(entropy),
            None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out),
        )
        if not ok:
            raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
        return _blob_to_bytes(out)

    def _dpapi_decrypt(data):
        source = _blob(data)
        entropy = _blob(_ENTROPY)
        out = _DATA_BLOB()
        ok = _crypt32.CryptUnprotectData(
            ctypes.byref(source), None, ctypes.byref(entropy),
            None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out),
        )
        if not ok:
            raise OSError(ctypes.get_last_error(), "CryptUnprotectData failed")
        return _blob_to_bytes(out)


def _xor(data):
    
    key = _OBFUSCATE_KEY
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _dpapi_available():
    if not IS_WINDOWS:
        return False
    try:
        probe = _dpapi_encrypt(b"SolRich DPAPI check")
        return _dpapi_decrypt(probe) == b"SolRich DPAPI check"
    except OSError:
        return False


def _encode(plain):
    
    if not IS_WINDOWS:
        raise SecureStoreError("Windows encryption is unavailable on this platform")
    raw = (plain or "").encode("utf-8")
    try:
        return "d:" + base64.b64encode(_dpapi_encrypt(raw)).decode("ascii")
    except OSError as exc:
        raise SecureStoreError("Windows could not encrypt the login data") from exc


def _decode(stored):
    if not stored:
        return ""
    scheme, separator, payload = str(stored).partition(":")
    if not separator:
        return ""
    try:
        raw = base64.b64decode(payload.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
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
        self.path = os.path.abspath(os.path.join(str(directory), STORE_FILENAME))
        self._load_error = False
        self._data = self._load()
        self._migration_failed = False
        self._migrate_legacy_entries()

    def _load(self):
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            self._load_error = True
            return {}

    def _save(self):
        tmp = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        except OSError as exc:
            try:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            except OSError:
                pass
            raise SecureStoreError("Could not save the encrypted login data") from exc

    def _migrate_legacy_entries(self):
        legacy_keys = [key for key, value in self._data.items() if str(value).startswith("o:")]
        if not legacy_keys:
            return
        migrated = dict(self._data)
        try:
            for key in legacy_keys:
                plain = _decode(migrated[key])
                if not plain:
                    raise SecureStoreError("Legacy login data could not be decoded")
                migrated[key] = _encode(plain)
            old_data = self._data
            self._data = migrated
            try:
                self._save()
            except Exception:
                self._data = old_data
                raise
            print(f"[SecureStore] Migrated {len(legacy_keys)} legacy token(s) to Windows DPAPI.")
        except (SecureStoreError, OSError) as exc:
            self._migration_failed = True
            print(f"[SecureStore] Legacy token migration failed: {exc}")

    def set(self, key, token):
        key = str(key)
        if not (token or "").strip():
            return self.delete(key)
        if self._load_error:
            raise SecureStoreError(
                "The existing login-data file is damaged; refusing to overwrite it"
            )
        encoded = _encode(token.strip())
        previous = self._data.get(key)
        self._data[key] = encoded
        try:
            self._save()
        except Exception:
            if previous is None:
                self._data.pop(key, None)
            else:
                self._data[key] = previous
            raise
        return True

    def get(self, key):
        return _decode(self._data.get(str(key), ""))

    def has(self, key):
        return str(key) in self._data

    def delete(self, key):
        key = str(key)
        if key not in self._data:
            return False
        previous = self._data[key]
        del self._data[key]
        try:
            if self._data:
                self._save()
            else:
                self._remove_store_file()
        except Exception:
            self._data[key] = previous
            raise
        return True

    def _remove_store_file(self):
        for path in (self.path, self.path + ".tmp"):
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError as exc:
                raise SecureStoreError("Could not delete the stored login data") from exc

    def clear(self):
        
        previous = self._data
        self._data = {}
        try:
            self._remove_store_file()
        except Exception:
            self._data = previous
            raise
        self._migration_failed = False
        self._load_error = False
        return True

    def status(self):
        schemes = [str(value).partition(":")[0] for value in self._data.values()]
        encrypted = sum(1 for scheme in schemes if scheme == "d")
        legacy = sum(1 for scheme in schemes if scheme == "o")
        unreadable = sum(
            1 for value in self._data.values()
            if str(value).partition(":")[0] not in ("d", "o") or not _decode(value)
        )
        available = _dpapi_available()
        protected = available and legacy == 0 and unreadable == 0 and not self._load_error
        return {
            "status": "protected" if protected else ("warning" if self._data or self._load_error else "unavailable"),
            "encryption": "windows_dpapi" if available else "unavailable",
            "encrypted": protected,
            "scope": "current_windows_user" if available else "none",
            "storageFile": self.path,
            "fileExists": os.path.exists(self.path),
            "storedTokens": len(self._data),
            "encryptedTokens": encrypted,
            "legacyTokens": legacy,
            "unreadableTokens": unreadable,
            "migrationFailed": self._migration_failed,
            "corruptStore": self._load_error,
        }
