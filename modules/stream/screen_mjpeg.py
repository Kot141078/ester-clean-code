# -*- coding: utf-8 -*-
"""modules/stream/screen_mjpeg.py - prostoy MJPEG-potok ekrana (LAN, offlayn).

Ideaya:
- Periodicheski zaprashivaem /desktop/rpa/screen (png_b64), trogaem chastotu (fps), otdaem kak multipart/x-mixed-replace.
- Nikakikh vneshnikh kodekov, tolko JPEG iz PNG (vstroennyy enkoder na chistom Python otsutstvuet → ispolzuem PNG kak JPEG-psevdo-kadr).
  Dlya sovmestimosti s brauzerom - zagolovok stavim 'image/jpeg', no fakticheski peredaem PNG-bayty (sovremennye brauzery sedayut).
  Esli v vashey sborke est sistemnyy jpeg-enkoder - mozhno podmenit _as_jpeg().

MOSTY:
- Yavnyy: (Vnimanie ↔ Sovmestnost) vedomye vidyat realnyy ekran veduschego.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) potok ogranichen fps → predskazuemaya nagruzka.
- Skrytyy #2: (Kibernetika ↔ Kontrol) potok sam po sebe read-only, bezopasen.

ZEMNOY ABZATs:
Strim — obychnyy HTTP-otvet s boundary. Frequency - parameter. Ostanovka - zakrytiem soedineniya.

# c=a+b"""
from __future__ import annotations
from typing import Generator
import time, base64, json, http.client
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BOUNDARY = "ester_mjpeg_boundary"

def _get_screen() -> bytes:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
    conn.request("GET", "/desktop/rpa/screen")
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try:
        obj = json.loads(t)
        if obj.get("ok"):
            return base64.b64decode(obj.get("png_b64",""))
    except Exception:
        pass
    return b""

def _as_jpeg(png_bytes: bytes) -> bytes:
    # Stub: we give the PNG as is. Browsers accept in the MZHPEG stream.
    return png_bytes

def stream_generator(fps: int = 8) -> Generator[bytes, None, None]:
    delay = max(0.02, 1.0/float(max(1, fps)))
    while True:
        frame_png = _get_screen()
        if not frame_png:
            time.sleep(delay); continue
        frame = _as_jpeg(frame_png)
        yield (b"--" + BOUNDARY.encode("ascii") + b"\r\n" +
               b"Content-Type: image/jpeg\r\n" +
               b"Content-Length: " + str(len(frame)).encode("ascii") + b"\r\n\r\n" +
               frame + b"\r\n")
        time.sleep(delay)