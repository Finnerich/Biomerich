

import time

from . import win_input, win_windows, ocr, status_events, merchants_data, screenshot
from . import detection, merchant_logic


class MerchantController:
    def __init__(self, auto):
        self.auto = auto

    def _merchant_calib(self):
        return ((self.auto._auto().get("merchants", {}) or {}).get("calib", {}) or {})

    def _merchant_detect(self, ev, duration=5.0, acc_id=None):
        
        general = self._merchant_calib().get("general", {}) or {}
        skip = (general.get("pixels", {}) or {}).get("dialogue_skip")
        name_region = (general.get("regions", {}) or {}).get("merchant_name")
        has_skip = isinstance(skip, (list, tuple)) and len(skip) == 2
        has_region = isinstance(name_region, (list, tuple)) and len(name_region) == 4
        if not has_skip or not has_region:
            print("[Merchant] Detect skipped: set General calibration "
                  "(Dialogue Skip point + Merchant Name region).")
            status_events.push_event(
                "Merchant: calibrate Dialogue Skip + Name region", kind="warn", ttl=2.5)
            return None

        sx, sy = int(skip[0]), int(skip[1])
        status_events.push_event("Merchant: skipping dialogue…", kind="info", ttl=2.0)

        try:
            win_input.move_to(sx, sy, duration=0.08)
        except Exception:
            pass
        end = time.time() + max(1.0, float(duration))
        while time.time() < end:
            if ev.is_set():
                return None
            win_input.press_key("e")
            win_input.click_at(sx, sy)
            time.sleep(0.25)

        if not ocr.available():
            print("[Merchant] Detect: OCR not available — cannot read merchant name.")
            status_events.push_event("Merchant: OCR not installed", kind="warn", ttl=2.5)
            self._close_unknown_dialogue(ev)
            return None
        x, y, w, h = (int(v) for v in name_region)





        try:
            win_input.move_to(max(5, x - 240), max(5, y - 140), duration=0.08)
        except Exception:
            pass
        time.sleep(0.3)

        mid, score, reads = None, 0.0, []
        for attempt in range(3):
            if ev.is_set():
                return None
            reads = ocr.read_region_variants(x, y, w, h)
            text = " ".join(reads)
            mid, score = merchants_data.detect_merchant_id(text)
            if mid:
                break
            if attempt < 2:
                print(f"[Merchant] Name unreadable (reads={reads!r}) — retrying…")
                time.sleep(0.6)
        if mid:
            name = merchants_data.detect_merchant_name(mid)
            print(f"[Merchant] Detected '{name}' (score {score:.2f}, reads={reads!r}).")
            status_events.push_event(f"Merchant found: {name}", kind="good", ttl=3.0)
            try:
                self.auto.config.increment_merchant(mid)
            except Exception as e:
                print(f"[Merchant] Count increment failed: {e}")
            self._merchant_arrival(mid, name, acc_id, ev)
            return mid
        print(f"[Merchant] No merchant matched (best score {score:.2f}, reads={reads!r}).")
        status_events.push_event("Merchant: no match", kind="bad", ttl=2.5)
        self._close_unknown_dialogue(ev)
        return None

    def _close_unknown_dialogue(self, ev):
        
        seen = set()
        for mid in ("mari", "jester", "rin"):
            pos = self._merchant_point(mid, "leave_button")
            if not pos or pos in seen:
                continue
            seen.add(pos)
            print(f"[Merchant] Closing unidentified dialogue via '{mid}' Leave button.")
            try:
                self._click_xy(pos[0], pos[1], 0.6, ev)
            except RuntimeError:
                return
            except Exception:
                pass

    def _merchant_point(self, group, slot):
        g = self._merchant_calib().get(group, {}) or {}
        pos = (g.get("pixels", {}) or {}).get(slot)
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            return (int(pos[0]), int(pos[1]))
        return None

    def _merchant_region(self, group, name):
        g = self._merchant_calib().get(group, {}) or {}
        box = (g.get("regions", {}) or {}).get(name)
        if isinstance(box, (list, tuple)) and len(box) == 4:
            return tuple(int(v) for v in box)
        return None

    def _click_xy(self, x, y, settle, ev):
        try:
            win_input.move_to(x + 60, y + 60, duration=0.05)
            time.sleep(0.04)
            win_input.move_to(x, y, duration=0.08)
            time.sleep(0.05)
        except Exception:
            pass
        win_input.click_at(x, y)
        if ev.is_set():
            raise RuntimeError("stopped")
        time.sleep(settle)

    def _merchant_click(self, group, slot, settle, ev):
        pos = self._merchant_point(group, slot)
        if not pos:
            raise RuntimeError(f"merchant click point '{group}/{slot}' is not set")
        self._click_xy(pos[0], pos[1], settle, ev)

    def _merchant_click_region(self, group, name, settle, ev):
        box = self._merchant_region(group, name)
        if not box:
            raise RuntimeError(f"merchant region '{group}/{name}' is not set")
        x, y, w, h = box
        self._click_xy(x + w // 2, y + h // 2, settle, ev)

    def _merchant_shop_ready(self):
        pts = all(self._merchant_point("shop", k)
                  for k in ("buy_button", "amount_box", "set_max_button", "close_button"))
        regs = all(self._merchant_region("shop", k)
                   for k in merchants_data.required_shop_region_keys())
        return pts and regs

    def _autobuy_wanted(self, mid, acc_id):
        
        try:
            entry = self.auto.config.merchant_autobuy(acc_id, mid)
        except Exception:
            return {}
        return merchant_logic.armed_autobuy_items(entry)

    def _merchant_arrival(self, mid, name, acc_id, ev):
        
        shot_on = self.auto._notif_on("merchantScreenshot")
        wanted = self._autobuy_wanted(mid, acc_id) if mid in merchants_data.AUTOBUY_MERCHANTS else {}
        buy_on = bool(wanted) and self._merchant_shop_ready()
        if wanted and not buy_on:
            print("[Merchant] Auto Buy skipped: Merchant Shop calibration incomplete.")
        has_shop = mid in ("mari", "jester")
        open_btn = self._merchant_point(mid, "open_button") if has_shop else None
        open_shop = has_shop and (shot_on or buy_on) and open_btn is not None
        if has_shop and (shot_on or buy_on) and open_btn is None:
            print(f"[Merchant] '{mid}' Open Button not calibrated — staying in the dialogue.")

        if not open_shop:
            image = self._merchant_shot(acc_id) if shot_on else None
            self.auto._notify_merchant(acc_id, name, mid=mid, image_bytes=image)
            if self._merchant_point(mid, "leave_button"):
                self._merchant_click(mid, "leave_button", 1.0, ev)
            else:
                print(f"[Merchant] '{mid}' Leave Button not calibrated — dialogue stays open.")
            return

        self._merchant_click(mid, "open_button", 3.0, ev)
        image = self._merchant_shot(acc_id) if shot_on else None
        self.auto._notify_merchant(acc_id, name, mid=mid, image_bytes=image)
        if buy_on:
            try:
                self._merchant_autobuy(mid, acc_id, ev)
            except RuntimeError:
                raise
            except Exception as e:
                print(f"[Merchant] Auto Buy failed: {e}")
        self._merchant_click("shop", "close_button", 2.0, ev)

    def _merchant_autobuy(self, mid, acc_id, ev):
        
        if not ocr.available():
            print("[Merchant] Auto Buy: OCR not available.")
            return
        status_events.push_event(f"Merchant Auto Buy · {merchants_data.detect_merchant_name(mid)}",
                                 kind="info", ttl=2.5)
        use_title = self._merchant_region("shop", "item_name") is not None
        bought = 0
        for slot_key in merchants_data.ITEM_SLOT_KEYS:
            if ev.is_set():
                raise RuntimeError("stopped")
            wanted = self._autobuy_wanted(mid, acc_id)
            if not wanted:
                break
            box = self._merchant_region("shop", slot_key)
            if not box:
                continue

            if use_title:
                self._merchant_click_region("shop", slot_key, 1.5, ev)
                item, score = self._identify_shop_item(mid)
                if not item:
                    print(f"[Merchant] Auto Buy: slot '{slot_key}' not identified from title.")
                    continue
                print(f"[Merchant] Auto Buy: slot '{slot_key}' → '{item}' "
                      f"(title, score {score:.2f}).")
                if item not in wanted:
                    continue
                bought += self._merchant_buy_selected(
                    mid, item, wanted[item]["amount"], acc_id, ev,
                    buy_all=wanted[item]["all"])
            else:
                x, y, w, h = box
                reads = ocr.read_region_variants(x, y, w, h, color_boost=True)
                item, score = self._match_reads(mid, reads)
                if not item or item not in wanted:
                    continue
                print(f"[Merchant] Auto Buy: slot '{slot_key}' → '{item}' "
                      f"(tab, score {score:.2f}).")
                self._merchant_click_region("shop", slot_key, 1.5, ev)
                bought += self._merchant_buy_selected(
                    mid, item, wanted[item]["amount"], acc_id, ev,
                    buy_all=wanted[item]["all"])
        if not bought:
            print("[Merchant] Auto Buy: nothing bought "
                  f"at {merchants_data.detect_merchant_name(mid)}.")

    @staticmethod
    def _match_reads(mid, reads):
        return detection.match_reads(mid, reads)

    def _identify_shop_item(self, mid):
        
        box = self._merchant_region("shop", "item_name")
        if not box:
            return None, 0.0
        x, y, w, h = box
        reads = ocr.read_region_variants(x, y, w, h, color_boost=True)
        best, best_score = self._match_reads(mid, reads)
        if not best:
            print(f"[Merchant] Title unmatched (reads={reads!r}).")
        return best, best_score

    @staticmethod
    def _parse_stock_text(text, confident_only=False):
        return detection.parse_stock_text(text, confident_only)

    def _read_stock_left(self):
        
        box = self._merchant_region("shop", "amount_label")
        if not box or not ocr.available():
            return None
        x, y, w, h = box
        reads = ocr.read_region_variants(x, y, w, h, color_boost=True)
        for confident in (True, False):
            for txt in reads:
                n = self._parse_stock_text(txt, confident_only=confident)
                if n is not None and n >= 0:
                    print(f"[Merchant] Stock label read '{txt}' → {n}"
                          f"{'' if confident else ' (fallback)'}")
                    return n
        print(f"[Merchant] Stock label unreadable (reads={reads!r}).")
        return None

    def _merchant_buy_selected(self, mid, item, want, acc_id, ev, buy_all=False):
        
        stock = self._read_stock_left()
        if stock is None:
            status_events.push_event(f"Auto Buy: stock unreadable · {item}", kind="warn", ttl=2.5)
            print(f"[Merchant] Auto Buy: stock label unreadable — skipping '{item}'.")
            return 0
        if stock <= 0:
            print(f"[Merchant] Auto Buy: '{item}' is sold out.")
            return 0
        use_max, purchased = merchant_logic.buy_plan(stock, want, buy_all)
        if use_max:
            self._merchant_click("shop", "set_max_button", 0.6, ev)
        else:
            self._merchant_click("shop", "amount_box", 0.55, ev)
            win_input.select_all_and_clear()
            time.sleep(0.20)
            win_input.type_text(str(want))
            time.sleep(0.45)
        self._merchant_click("shop", "buy_button", 1.0, ev)
        if buy_all:
            before, left = "All", "All"
        else:
            before, left = self.auto.config.decrement_merchant_autobuy(acc_id, mid, item, purchased)
        try:
            self.auto.config.add_merchant_buy(acc_id, mid, item, purchased)
        except Exception as e:
            print(f"[Merchant] Buy log write failed: {e}")
        print(f"[Merchant] Auto Buy: bought {purchased}× '{item}' ({left} still wanted).")
        status_events.push_event(f"Auto Buy: {purchased}× {item}", kind="good", ttl=2.5)
        self.auto._notify_autobuy(acc_id, mid, item, purchased, before, left)
        return purchased

    def _merchant_shot(self, acc_id=None):
        
        if not self.auto._notif_on("merchantScreenshot"):
            return None
        try:
            hwnd = self.auto._windows.get(acc_id) if acc_id is not None else None
            if hwnd:
                rect = win_windows.window_rect(hwnd)
                shot = screenshot.grab_window_png(rect)
                if shot:
                    return shot
                print("[Merchant] Window capture unavailable — skipping screenshot.")
                return None

            print("[Merchant] No Roblox window resolved — skipping screenshot.")
            return None
        except Exception as e:
            print(f"[Merchant] Screenshot failed: {e}")
            return None
