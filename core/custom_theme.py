

import base64
import binascii
import io
import os

from PIL import Image, UnidentifiedImageError

from .config import get_config_dir


MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
_FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}
_PREFIX = "custom_theme_background."


def _known_paths():
    folder = os.path.abspath(get_config_dir())
    return [os.path.join(folder, _PREFIX + extension) for extension, _ in _FORMATS.values()]


def _decode_data_url(data_url):
    raw = str(data_url or "")
    if not raw.startswith("data:image/") or ";base64," not in raw[:80]:
        raise ValueError("invalid_data_url")
    encoded = raw.split(",", 1)[1]
    if len(encoded) > ((MAX_IMAGE_BYTES * 4) // 3) + 16:
        raise ValueError("file_too_large")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid_image") from exc
    if not payload or len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("file_too_large" if payload else "invalid_image")
    return payload


def save_background(config, data_url):
    try:
        payload = _decode_data_url(data_url)
        with Image.open(io.BytesIO(payload)) as image:
            width, height = image.size
            image_format = str(image.format or "").upper()
            if image_format not in _FORMATS:
                raise ValueError("unsupported_format")
            if width < 320 or height < 180:
                raise ValueError("image_too_small")
            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError("image_too_large")
            image.verify()
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return {"ok": False, "error": "invalid_image"}

    extension, mime = _FORMATS[image_format]
    folder = os.path.abspath(get_config_dir())
    os.makedirs(folder, exist_ok=True)
    filename = _PREFIX + extension
    destination = os.path.join(folder, filename)
    temporary = destination + ".tmp"
    try:
        with open(temporary, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        for old_path in _known_paths():
            if old_path != destination and os.path.isfile(old_path):
                os.remove(old_path)
        config.set_setting("customThemeBackgroundFile", filename)
        return {
            "ok": True,
            "name": filename,
            "mime": mime,
            "sizeBytes": len(payload),
            "width": width,
            "height": height,
        }
    except OSError as exc:
        try:
            if os.path.isfile(temporary):
                os.remove(temporary)
        except OSError:
            pass
        return {"ok": False, "error": "write_failed", "detail": str(exc)}


def load_background(config):
    filename = str(config.settings.get("customThemeBackgroundFile") or "")
    allowed_names = {os.path.basename(path) for path in _known_paths()}
    if filename not in allowed_names:
        return {"ok": True, "available": False}
    path = os.path.join(os.path.abspath(get_config_dir()), filename)
    if not os.path.isfile(path):
        return {"ok": True, "available": False}
    try:
        if os.path.getsize(path) > MAX_IMAGE_BYTES:
            return {"ok": False, "available": False, "error": "file_too_large"}
        with open(path, "rb") as source:
            payload = source.read()
        extension = filename.rsplit(".", 1)[-1].lower()
        mime = "image/jpeg" if extension == "jpg" else f"image/{extension}"
        encoded = base64.b64encode(payload).decode("ascii")
        return {
            "ok": True,
            "available": True,
            "name": filename,
            "dataUrl": f"data:{mime};base64,{encoded}",
        }
    except OSError as exc:
        return {"ok": False, "available": False, "error": "read_failed", "detail": str(exc)}


def clear_background(config):
    failed = []
    for path in _known_paths():
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            failed.append(os.path.basename(path))
    config.set_setting("customThemeBackgroundFile", "")
    return {"ok": not failed, "removed": not failed, "failed": failed}
