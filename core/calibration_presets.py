

from __future__ import annotations

from math import gcd




SUGGESTED_DISPLAY_PROFILES = (
    {"width": 1366, "height": 768, "scale": 100},
    {"width": 2560, "height": 1440, "scale": 100},
    {"width": 3440, "height": 1440, "scale": 150},
    {"width": 1920, "height": 1200, "scale": 125},
    {"width": 3000, "height": 2000, "scale": 200},
    {"width": 2880, "height": 1920, "scale": 200},
    {"width": 3072, "height": 1920, "scale": 200},
)


_COMMON_RATIOS = (
    (16, 9),
    (16, 10),
    (4, 3),
    (3, 2),
    (21, 9),
    (32, 9),
)


def aspect_ratio(width, height) -> str:
    width, height = int(width or 0), int(height or 0)
    if width <= 0 or height <= 0:
        return "unknown"
    value = width / height
    for ratio_width, ratio_height in _COMMON_RATIOS:
        if abs(value - (ratio_width / ratio_height)) / value <= 0.012:
            return f"{ratio_width}:{ratio_height}"
    divisor = gcd(width, height)
    return f"{width // divisor}:{height // divisor}"
