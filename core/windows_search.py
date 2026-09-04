

from __future__ import annotations

import ctypes
import os
import sys
import uuid
from pathlib import Path
from typing import Callable, Optional


class WindowsSearchError(RuntimeError):
    pass


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _is_windows() -> bool:
    return os.name == "nt"


def _current_executable() -> Optional[Path]:
    
    if not getattr(sys, "frozen", False):
        return None
    executable = Path(sys.executable).resolve()
    if executable.suffix.casefold() != ".exe" or not executable.is_file():
        return None
    return executable


def _shortcut_path(dev_build: bool = False) -> Path:
    roaming = os.environ.get("APPDATA", "").strip()
    if not roaming:
        raise WindowsSearchError("appdata_unavailable")
    filename = "SolRich Dev.lnk" if dev_build else "SolRich.lnk"
    return Path(roaming) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / filename


def _guid(value: str) -> _GUID:
    
    raw = uuid.UUID(value).bytes_le
    return _GUID.from_buffer_copy(raw)


def _write_shell_link(destination: Path, target: Path, dev_build: bool = False) -> None:
    
    if not _is_windows():
        raise WindowsSearchError("unsupported_platform")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.is_dir():
        raise WindowsSearchError("invalid_shortcut_path")

    temporary = destination.with_name(f".{destination.stem}-{uuid.uuid4().hex}.lnk")
    ole32 = ctypes.OleDLL("ole32")
    hresult = ctypes.c_int32
    coinit_apartment_threaded = 0x2
    clsctx_inproc_server = 0x1
    rpc_e_changed_mode = -2147417850
    initialized_here = False
    shell_link = ctypes.c_void_p()
    persist_file = ctypes.c_void_p()

    def check(result: int, operation: str) -> None:
        if int(result) < 0:
            raise WindowsSearchError(f"{operation}_failed_0x{int(result) & 0xFFFFFFFF:08x}")

    def method(pointer: ctypes.c_void_p, index: int, *argtypes):
        table = ctypes.cast(
            pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        prototype = ctypes.WINFUNCTYPE(hresult, ctypes.c_void_p, *argtypes)
        return prototype(table[index])

    try:
        init_result = int(ole32.CoInitializeEx(None, coinit_apartment_threaded))
        if init_result in (0, 1):
            initialized_here = True
        elif init_result != rpc_e_changed_mode:
            check(init_result, "com_initialize")

        clsid = _guid("00021401-0000-0000-C000-000000000046")
        iid_shell_link = _guid("000214F9-0000-0000-C000-000000000046")
        iid_persist_file = _guid("0000010b-0000-0000-C000-000000000046")

        ole32.CoCreateInstance.argtypes = [
            ctypes.POINTER(_GUID),
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(_GUID),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        ole32.CoCreateInstance.restype = hresult
        check(
            ole32.CoCreateInstance(
                ctypes.byref(clsid),
                None,
                clsctx_inproc_server,
                ctypes.byref(iid_shell_link),
                ctypes.byref(shell_link),
            ),
            "create_shell_link",
        )

        check(method(shell_link, 20, ctypes.c_wchar_p)(shell_link, str(target)), "set_target")
        check(
            method(shell_link, 9, ctypes.c_wchar_p)(shell_link, str(target.parent)),
            "set_working_directory",
        )
        description = "SolRich Dev" if dev_build else "SolRich - Sol's RNG Macro"
        check(
            method(shell_link, 7, ctypes.c_wchar_p)(shell_link, description),
            "set_description",
        )
        check(
            method(shell_link, 17, ctypes.c_wchar_p, ctypes.c_int)(
                shell_link, str(target), 0
            ),
            "set_icon",
        )

        query_interface = method(
            shell_link,
            0,
            ctypes.POINTER(_GUID),
            ctypes.POINTER(ctypes.c_void_p),
        )
        check(
            query_interface(
                shell_link, ctypes.byref(iid_persist_file), ctypes.byref(persist_file)
            ),
            "query_persist_file",
        )
        check(
            method(persist_file, 6, ctypes.c_wchar_p, ctypes.c_int)(
                persist_file, str(temporary), 1
            ),
            "save_shortcut",
        )
        if not temporary.is_file():
            raise WindowsSearchError("shortcut_not_created")
        os.replace(temporary, destination)
    finally:
        release_type = ctypes.WINFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p)
        if persist_file.value:
            table = ctypes.cast(
                persist_file, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
            ).contents
            release_type(table[2])(persist_file)
        if shell_link.value:
            table = ctypes.cast(
                shell_link, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
            ).contents
            release_type(table[2])(shell_link)
        if initialized_here:
            ole32.CoUninitialize()
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def status(dev_build: bool = False) -> dict:
    
    if not _is_windows():
        return {
            "ok": True,
            "supported": False,
            "available": False,
            "installed": False,
            "error": "unsupported_platform",
        }
    try:
        shortcut = _shortcut_path(dev_build)
    except WindowsSearchError as exc:
        return {
            "ok": True,
            "supported": True,
            "available": False,
            "installed": False,
            "error": str(exc),
        }
    target = _current_executable()
    return {
        "ok": True,
        "supported": True,
        "available": target is not None,
        "installed": shortcut.is_file(),
        "shortcutPath": str(shortcut),
        "targetPath": str(target) if target else "",
        "devBuild": bool(dev_build),
        "error": None if target else "built_app_required",
    }


def install(
    dev_build: bool = False,
    *,
    writer: Callable[[Path, Path, bool], None] = _write_shell_link,
) -> dict:
    
    current = status(dev_build)
    if not current.get("supported"):
        return {**current, "ok": False}
    target = _current_executable()
    if target is None:
        return {**current, "ok": False, "error": "built_app_required"}
    try:
        destination = _shortcut_path(dev_build)
        writer(destination, target, dev_build)
        return {**status(dev_build), "ok": True, "repaired": bool(current.get("installed"))}
    except Exception as exc:
        print(f"[Windows Search] Could not create shortcut: {exc}")
        return {**status(dev_build), "ok": False, "error": "shortcut_create_failed"}


def uninstall(dev_build: bool = False) -> dict:
    
    if not _is_windows():
        return {**status(dev_build), "ok": False, "error": "unsupported_platform"}
    try:
        shortcut = _shortcut_path(dev_build)
        if shortcut.exists() and not shortcut.is_file():
            raise WindowsSearchError("invalid_shortcut_path")
        shortcut.unlink(missing_ok=True)
        return {**status(dev_build), "ok": True}
    except Exception as exc:
        print(f"[Windows Search] Could not remove shortcut: {exc}")
        return {**status(dev_build), "ok": False, "error": "shortcut_remove_failed"}
