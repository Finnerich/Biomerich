

from copy import deepcopy


IS_COMPONENTS_V2 = 1 << 15

ACTION_ROW = 1
BUTTON = 2
SECTION = 9
TEXT_DISPLAY = 10
THUMBNAIL = 11
MEDIA_GALLERY = 12
FILE = 13
SEPARATOR = 14
CONTAINER = 17

SPACING_SMALL = 1
SPACING_LARGE = 2

BUTTON_PRIMARY = 1
BUTTON_SECONDARY = 2
BUTTON_SUCCESS = 3
BUTTON_DANGER = 4
BUTTON_LINK = 5


def _media(url, description=None, spoiler=False):
    item = {"media": {"url": url}, "spoiler": bool(spoiler)}
    if description:
        item["description"] = description
    return item


class Button:
    

    @staticmethod
    def link(label, url, emoji=None, disabled=False):
        button = {
            "type": BUTTON,
            "style": BUTTON_LINK,
            "label": str(label),
            "url": str(url),
            "disabled": bool(disabled),
        }
        if emoji:
            button["emoji"] = emoji
        return button

    @staticmethod
    def interactive(label, custom_id, style=BUTTON_PRIMARY, emoji=None,
                    disabled=False):
        if style not in (BUTTON_PRIMARY, BUTTON_SECONDARY,
                         BUTTON_SUCCESS, BUTTON_DANGER):
            raise ValueError("Interactive button style must be between 1 and 4")
        button = {
            "type": BUTTON,
            "style": style,
            "label": str(label),
            "custom_id": str(custom_id),
            "disabled": bool(disabled),
        }
        if emoji:
            button["emoji"] = emoji
        return button


class Container:
    

    def __init__(self, accent_color=None, spoiler=False):
        if accent_color is not None and not 0 <= int(accent_color) <= 0xFFFFFF:
            raise ValueError("accent_color must be between 0x000000 and 0xFFFFFF")
        self.accent_color = int(accent_color) if accent_color is not None else None
        self.spoiler = bool(spoiler)
        self.components = []

    def text(self, content):
        self.components.append({"type": TEXT_DISPLAY, "content": str(content)})
        return self

    def section(self, *texts, thumbnail=None, button=None,
                thumbnail_description=None, thumbnail_spoiler=False):
        
        if thumbnail and button:
            raise ValueError("A Section can have a thumbnail or a button, not both")
        if not thumbnail and not button:
            raise ValueError("A Section needs a thumbnail or button accessory")
        if not 1 <= len(texts) <= 3:
            raise ValueError("A Section needs between 1 and 3 text fields")
        if thumbnail:
            accessory = {
                "type": THUMBNAIL,
                "media": {"url": str(thumbnail)},
                "spoiler": bool(thumbnail_spoiler),
            }
            if thumbnail_description:
                accessory["description"] = str(thumbnail_description)
        else:
            accessory = deepcopy(button)
        self.components.append({
            "type": SECTION,
            "components": [
                {"type": TEXT_DISPLAY, "content": str(text)} for text in texts
            ],
            "accessory": accessory,
        })
        return self

    def thumbnail(self, text, url, description=None, spoiler=False):
        
        return self.section(
            text,
            thumbnail=url,
            thumbnail_description=description,
            thumbnail_spoiler=spoiler,
        )

    def separator(self, divider=True, spacing=SPACING_SMALL):
        if spacing not in (SPACING_SMALL, SPACING_LARGE):
            raise ValueError("Separator spacing must be SPACING_SMALL or SPACING_LARGE")
        self.components.append({
            "type": SEPARATOR,
            "divider": bool(divider),
            "spacing": spacing,
        })
        return self

    def action_row(self, *components):
        if not 1 <= len(components) <= 5:
            raise ValueError("An Action Row needs between 1 and 5 components")
        self.components.append({
            "type": ACTION_ROW,
            "components": [deepcopy(component) for component in components],
        })
        return self

    def media_gallery(self, *urls, description=None, spoiler=False):
        if not 1 <= len(urls) <= 10:
            raise ValueError("A Media Gallery needs between 1 and 10 items")
        self.components.append({
            "type": MEDIA_GALLERY,
            "items": [
                _media(str(url), description=description, spoiler=spoiler)
                for url in urls
            ],
        })
        return self

    def file(self, attachment_url, spoiler=False):
        if not str(attachment_url).startswith("attachment://"):
            raise ValueError("File components require an attachment:// URL")
        self.components.append({
            "type": FILE,
            "file": {"url": str(attachment_url)},
            "spoiler": bool(spoiler),
        })
        return self

    def raw(self, component):
        
        self.components.append(deepcopy(component))
        return self

    def build(self):
        result = {
            "type": CONTAINER,
            "spoiler": self.spoiler,
            "components": deepcopy(self.components),
        }
        if self.accent_color is not None:
            result["accent_color"] = self.accent_color
        return result


class Message:
    

    def __init__(self):
        self.components = []

    def container(self, container):
        component = container.build() if isinstance(container, Container) else container
        self.components.append(deepcopy(component))
        return self

    def text(self, content):
        self.components.append({"type": TEXT_DISPLAY, "content": str(content)})
        return self

    def raw(self, component):
        self.components.append(deepcopy(component))
        return self

    def build(self):
        if not self.components:
            raise ValueError("A Components v2 message needs at least one component")
        return {
            "flags": IS_COMPONENTS_V2,
            "components": deepcopy(self.components),
        }
