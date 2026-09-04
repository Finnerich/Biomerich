

import re
from urllib.parse import quote

from . import extra_calibrations, fishing_presets, merchants_data, presets


IMAGE_ROOT = (
    "https://raw.githubusercontent.com/Finnerich/Boterich-Images/"
    "main/CALIBRATION_IMAGES"
)


def _lookup_label(scope, slot, group=None):
    if scope == "automation":
        if slot == "first_item_region":
            return "First Item Slot (Region)"
        return dict(presets.PIXEL_SLOTS).get(slot, slot.replace("_", " ").title())

    if scope == "fishing":
        return (
            dict(fishing_presets.PIXEL_SLOTS).get(slot)
            or dict(fishing_presets.REGION_SLOTS).get(slot)
            or slot.replace("_", " ").title()
        )

    if scope == "merchant":
        merchant_group = next(
            (item for item in merchants_data.calib_groups() if item["key"] == group),
            None,
        )
        if merchant_group:
            entries = merchant_group.get("points", []) + merchant_group.get(
                "regions", []
            )
            return dict(entries).get(slot, slot.replace("_", " ").title())

    if scope == "extra":
        extra_group = extra_calibrations.group(group)
        if extra_group:
            entries = extra_group.get("points", []) + extra_group.get("regions", [])
            for subgroup in extra_group.get("subgroups", []):
                entries += subgroup.get("points", []) + subgroup.get("regions", [])
            return dict(entries).get(slot, slot.replace("_", " ").title())

    if scope == "autopop":
        return "Amount Label Region"

    return slot.replace("_", " ").title()


def _image_paths(scope, slot, group, label):
    if scope == "automation":
        folder = "inventory"
    elif scope == "merchant":
        folder = f"merchants/{group}"
    elif scope == "extra":
        folder = str(group or "extra")
    else:
        folder = scope

    label_slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    base_paths = [f"{folder}/{slot}"]
    if label_slug and label_slug != slot:
        base_paths.append(f"{folder}/{label_slug}")
    base_paths.append(slot)

    urls = []
    for base_path in dict.fromkeys(base_paths):
        encoded_path = quote(base_path, safe="/")
        for extension in ("png", "jpg", "webp"):
            urls.append(f"{IMAGE_ROOT}/{encoded_path}.{extension}")
    return urls


def build_guide(scope, slot, *, group=None, is_region=False, step=1):
    
    label = _lookup_label(scope, slot, group)

    if is_region:
        step = 2 if int(step) == 2 else 1
        instruction = (
            "Click the exact bottom-right corner now."
            if step == 2
            else "Click the exact top-left corner first."
        )
        progress = f"REGION · STEP {step} OF 2"
    else:
        if scope == "fishing" and slot in {"bite_indicator", "bar_sample"}:
            instruction = (
                "Use the pixel magnifier, then click the exact pixel in its centre."
            )
        else:
            instruction = "Click the exact target once."
        progress = "CLICK POINT"

    return {
        "title": label,
        "instruction": instruction,
        "progress": progress,
        "imageUrls": _image_paths(scope, slot, group, label),
    }
