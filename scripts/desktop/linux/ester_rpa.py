# scripts/desktop/linux/ester_rpa.py
# Naznachenie: lokalnyy RPA (127.0.0.1:8732) dlya Xvfb.
#   GET  /health
#   GET  /screen                       -> { ok, png_b64 }
#   POST /open {"app":"xterm"|"thunar"}
#   POST /click {"x":int,"y":int}
#   POST /type {"text":"..."}          (trebuet xdotool)
#   POST /ocr_click {"needle":"...", "lang":"eng+rus"}  -> klik po naydennomu tekstu (tesseract tsv)
#   POST /slot {"slot":"A"|"B"}        -> pereklyuchenie A/B (fayl /opt/ester/active.slot)
#
# Zavisimosti:
#   apt install -y tesseract-ocr xdotool x11-apps netpbm pngtools  (dlya screen cherez xwd/xwdtopnm/pnmtopng)
#
# MOSTY/ZEMLYa sm. Windows-versiyu — analogichny. Vse lokalno, oflayn.
#
# c=a+b

from http.server import BaseHTTPRequestHandler, HTTPServer
import base64, json, subprocess, os, re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from Xlib import display, X
    d = display.Display()
except Exception:
    d = None

ALLOW_APPS = {
    "xterm": "/usr/bin/xterm",
    "thunar": "/usr/bin/thunar"
}

ACTIVE_SLOT_PATH = "/opt/ester/active.slot"
os.makedirs("/opt/ester", exist_ok=True)
if not os.path.exists(ACTIVE_SLOT_PATH):
    with open(ACTIVE_SLOT_PATH, "w") as f:
        f.write("A")

def move_click(x, y):
    if d is None:
        return False
    root = d.screen().root
    root.warp_pointer(int(x), int(y)); d.sync()
    root.fake_input(X.ButtonPress, 1); d.sync()
    root.fake_input(X.ButtonRelease, 1); d.sync()
    return True

def type_text(text):
    try:
        subprocess.Popen(["/usr/bin/xdotool", "type", "--delay", "0", text])
        return True
    except FileNotFoundError:
        return False

def open_app(name):
    cmd = ALLOW_APPS.get(name)
    if not cmd:
        return False
    env = os.environ.copy()
    if d:
        env["DISPLAY"] = d.get_display_name()
    subprocess.Popen([cmd], env=env)
    return True

def take_screen_b64():
    # Universalnyy sposob bez Pillow: xwd -> pnm -> png -> b64
    try:
        xwd = subprocess.Popen(["/usr/bin/xwd", "-root", "-silent"], stdout=subprocess.PIPE)
        xwdtopnm = subprocess.Popen(["/usr/bin/xwdtopnm"], stdin=xwd.stdout, stdout=subprocess.PIPE)
        pnmtopng = subprocess.Popen(["/usr/bin/pnmtopng"], stdin=xwdtopnm.stdout, stdout=subprocess.PIPE)
        png_bytes = pnmtopng.communicate()[0]
        return base64.b64encode(png_bytes).decode("ascii")
    except Exception:
        return ""

def ocr_click(needle:str, lang:str):
    tess = "/usr/bin/tesseract"
    if not os.path.exists(tess):
        return {"ok": False, "error": "tesseract_not_found"}
    png_b64 = take_screen_b64()
    if not png_b64:
        return {"ok": False, "error": "screen_failed"}
    tmpdir = "/tmp/ester_rpa"
    os.makedirs(tmpdir, exist_ok=True)
    png_path = os.path.join(tmpdir, "shot.png")
    with open(png_path, "wb") as f:
        f.write(base64.b64decode(png_b64))
    if not lang:
        lang = "eng+rus"
    # TSV
    p = subprocess.Popen([tess, png_path, "stdout", "-l", lang, "tsv"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _ = p.communicate()
    lines = out.decode("utf-8", "ignore").splitlines()
    needle_l = needle.lower()
    for ln in lines:
        if re.match(r"^\d+\t", ln):
            cols = ln.split("\t")
            if len(cols) >= 12:
                text = cols[11] or ""
                if text and needle_l in text.lower():
                    left = int(cols[6]); top = int(cols[7]); w = int(cols[8]); h = int(cols[9])
                    cx = left + w//2; cy = top + h//2
                    if move_click(cx, cy):
                        return {"ok": True, "hit": {"x": cx, "y": cy, "box": {"left": left, "top": top, "width": w, "height": h}, "text": text}}
                    else:
                        return {"ok": False, "error": "click_failed"}
    return {"ok": False, "error": "text_not_found"}

class H(BaseHTTPRequestHandler):
    def _send(self, code=200, obj=None):
        body = json.dumps(obj or {})
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        if self.path == "/health":
            with open(ACTIVE_SLOT_PATH, "r") as f:
                slot = f.read().strip()
            self._send(200, {"ok": True, "agent": "ester-linux", "slot": slot}); return
        if self.path == "/screen":
            b64 = take_screen_b64()
            if not b64:
                self._send(500, {"ok": False, "error": "screen_failed"}); return
            self._send(200, {"ok": True, "png_b64": b64}); return
        self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(ln).decode("utf-8") if ln else "{}"
        try:
            data = json.loads(raw or "{}")
        except Exception:
            return self._send(400, {"ok": False, "error": "bad_json"})

        if self.path == "/open":
            app = (data.get("app") or "").strip().lower()
            if not open_app(app):
                return self._send(400, {"ok": False, "error": "app_not_allowed"})
            return self._send(200, {"ok": True})

        if self.path == "/click":
            try:
                x = int(data.get("x")); y = int(data.get("y"))
            except Exception:
                return self._send(400, {"ok": False, "error": "x_y_required"})
            if not move_click(x, y):
                return self._send(500, {"ok": False, "error": "click_failed"})
            return self._send(200, {"ok": True})

        if self.path == "/type":
            text = (data.get("text") or "")
            if not text:
                return self._send(400, {"ok": False, "error": "text_required"})
            if not type_text(text):
                return self._send(500, {"ok": False, "error": "xdotool_missing"})
            return self._send(200, {"ok": True})

        if self.path == "/ocr_click":
            needle = (data.get("needle") or "").strip()
            lang = (data.get("lang") or "eng+rus").strip()
            if not needle:
                return self._send(400, {"ok": False, "error": "needle_required"})
            res = ocr_click(needle, lang)
            return self._send(200 if res.get("ok") else 400, res)

        if self.path == "/slot":
            slot = (data.get("slot") or "").strip().upper()
            if slot not in ("A", "B"):
                return self._send(400, {"ok": False, "error": "slot_invalid"})
            with open(ACTIVE_SLOT_PATH, "w") as f:
                f.write(slot)
            return self._send(200, {"ok": True, "slot": slot})

        return self._send(404, {"ok": False, "error": "not_found"})

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8732), H).serve_forever()