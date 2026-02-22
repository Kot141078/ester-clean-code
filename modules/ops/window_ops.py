# -*- coding: utf-8 -*-
"""
modules/ops/window_ops.py — krossplatformennye operatsii s oknami:
  - perechislenie okon (title, rect, id)
  - fokusirovka okna po id/chasti zagolovka
  - zakhvat izobrazheniya okna (base64 PNG)
  - otpravka goryachey klavishi (CTRL+S, ALT+TAB i t.p.)

Windows: Win32 (ctypes), zakhvat cherez PIL.ImageGrab.grab(bbox=rect).
Linux (X11): xdotool / wmctrl / xwininfo / xwd (trebuyutsya pakety: xdotool, wmctrl, x11-apps/netpbm/pngtools)

MOSTY:
- Yavnyy: (Volya ↔ Okno) vybor tseli («glaz») i deystvie («ruka») na urovne OS.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) ID/rect okna → determinirovannaya tsel dlya RPA/shablonov.
- Skrytyy #2: (Anatomiya ↔ Inzheneriya) «fokus» kak povorot golovy; «snimok okna» kak fovea setchatki.

ZEMNOY ABZATs:
Daet Ester tochechnyy kontrol: ne ves ekran, a konkretnoe okno. Eto snizhaet shum i uskoryaet sensory.

# c=a+b
"""
from __future__ import annotations
import sys, os, platform, base64, io, subprocess, re
from typing import List, Dict, Any, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_IS_WIN = platform.system().lower().startswith("win")

def _b64_png(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode("ascii")

# ---------- Windows ----------
if _IS_WIN:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    GWL_STYLE = -16
    WS_VISIBLE = 0x10000000

    def _enum_windows() -> List[Dict[str, Any]]:
        EnumWindows = user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        GetWindowTextW = user32.GetWindowTextW
        GetWindowTextLengthW = user32.GetWindowTextLengthW
        IsWindowVisible = user32.IsWindowVisible
        GetWindowRect = user32.GetWindowRect

        res: List[Dict[str, Any]] = []
        def _cb(hwnd, lParam):
            if not IsWindowVisible(hwnd):
                return True
            length = GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buff = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()
            if not title:
                return True
            rect = wintypes.RECT()
            GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 or h <= 0:
                return True
            res.append({
                "id": int(hwnd),
                "title": title,
                "rect": {"left": int(rect.left), "top": int(rect.top), "width": int(w), "height": int(h)}
            })
            return True
        EnumWindows(EnumWindowsProc(_cb), 0)
        return res

    def list_windows() -> List[Dict[str, Any]]:
        return _enum_windows()

    def focus_by_id(wid: int) -> bool:
        return bool(user32.SetForegroundWindow(wintypes.HWND(wid)))

    def focus_by_title(substr: str) -> Optional[int]:
        for w in list_windows():
            if substr.lower() in (w["title"].lower()):
                if focus_by_id(w["id"]):
                    return w["id"]
        return None

    def capture_rect(rect: Dict[str, int]) -> str:
        from PIL import ImageGrab, Image
        left = rect["left"]; top = rect["top"]; w = rect["width"]; h = rect["height"]
        box = (left, top, left + w, top + h)
        im = ImageGrab.grab(bbox=box, all_screens=True)
        bio = io.BytesIO(); im.save(bio, format="PNG")
        return _b64_png(bio.getvalue())

    def capture_by_id(wid: int) -> Optional[str]:
        for w in list_windows():
            if w["id"] == wid:
                return capture_rect(w["rect"])
        return None

    # Hotkeys
    def send_hotkey(seq: str) -> bool:
        """
        seq vida: 'CTRL+S', 'ALT+TAB', 'CTRL+SHIFT+ESC'
        """
        VK = {
            "CTRL": 0x11, "SHIFT": 0x10, "ALT": 0x12,
            "ESC": 0x1B, "TAB": 0x09, "ENTER": 0x0D,
            "S": 0x53, "C": 0x43, "V": 0x56, "A": 0x41, "F4": 0x73
        }
        parts = [p.strip().upper() for p in seq.split("+") if p.strip()]
        if not parts: return False
        # press mods
        for p in parts[:-1]:
            vk = VK.get(p); 
            if vk: user32.keybd_event(vk, 0, 0, 0)
        # press last
        last = parts[-1]; vk = VK.get(last)
        if vk: user32.keybd_event(vk, 0, 0, 0)
        # release last
        if vk: user32.keybd_event(vk, 0, 2, 0)
        # release mods (reverse)
        for p in reversed(parts[:-1]):
            vk = VK.get(p)
            if vk: user32.keybd_event(vk, 0, 2, 0)
        return True

# ---------- Linux (X11) ----------
else:
    def _run(cmd: str) -> Tuple[int, str, str]:
        p = subprocess.run(cmd, shell=True, text=True, capture_output=True)
        return p.returncode, p.stdout.strip(), p.stderr.strip()

    def list_windows() -> List[Dict[str, Any]]:
        # wmctrl -l : 0x03200007  0 host Title...
        code, out, err = _run("wmctrl -l")
        res: List[Dict[str, Any]] = []
        if code != 0:
            return res
        for ln in out.splitlines():
            m = re.match(r"^(0x[0-9a-fA-F]+)\s+\S+\s+\S+\s+(.*)$", ln)
            if not m: 
                continue
            wid_hex, title = m.groups()
            wid = int(wid_hex, 16)
            # xwininfo -id wid
            c2, out2, _ = _run(f"xwininfo -id {wid_hex}")
            if c2 == 0:
                left = top = width = height = 0
                mm = re.search(r"Absolute upper-left X:\s+(\d+).*?Absolute upper-left Y:\s+(\d+).*?Width:\s+(\d+).*?Height:\s+(\d+)", out2, re.S)
                if mm:
                    left, top, width, height = map(int, mm.groups())
                res.append({"id": wid, "title": title.strip(),
                            "rect": {"left": left, "top": top, "width": width, "height": height}})
        return res

    def focus_by_id(wid: int) -> bool:
        code, _, _ = _run(f"xdotool windowactivate {wid}")
        return code == 0

    def focus_by_title(substr: str) -> Optional[int]:
        ws = list_windows()
        for w in ws:
            if substr.lower() in w["title"].lower():
                if focus_by_id(w["id"]):
                    return w["id"]
        return None

    def capture_by_id(wid: int) -> Optional[str]:
        # xwd -silent -id WID | xwdtopnm | pnmtopng
        code = subprocess.call(f"xwd -silent -id {wid} | xwdtopnm | pnmtopng > /tmp/ester_win.png", shell=True)
        if code != 0:
            return None
        with open("/tmp/ester_win.png", "rb") as f:
            return _b64_png(f.read())

    def capture_rect(rect: Dict[str, int]) -> str:
        # zakhvat vsego ekrana i obrezka (fallback, trebuet ImageMagick/Pillow — ne ispolzuem; ostavim cherez xwd kornevogo)
        code = subprocess.call("xwd -silent -root | xwdtopnm | pnmtopng > /tmp/ester_root.png", shell=True)
        if code != 0:
            return ""
        from PIL import Image
        left, top, w, h = rect["left"], rect["top"], rect["width"], rect["height"]
        im = Image.open("/tmp/ester_root.png")
        crop = im.crop((left, top, left+w, top+h))
        bio = io.BytesIO(); crop.save(bio, format="PNG")
        return _b64_png(bio.getvalue())

    def send_hotkey(seq: str) -> bool:
        # Preobrazuem v format xdotool: ctrl+s → key ctrl+s
        seq = seq.strip().lower().replace("+", "+")
        code, _, _ = _run(f"xdotool key {seq}")
        return code == 0