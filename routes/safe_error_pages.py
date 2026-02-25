# D:\ester-project\routes/safe_error_pages.py
# Polnyy fayl

from flask import Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _html(title, body):
    return f"""<!doctype html><meta charset="utf-8"><title>{title}</title>
    <style>body{{font:14px/1.5 system-ui,Segoe UI,Roboto,Arial;margin:24px;color:#111}}
    a{{color:#0645ad;text-decoration:none}}a:hover{{text-decoration:underline}}
    code{{background:#f6f8fa;padding:.1em .3em;border-radius:4px}}</style>
    <h1>{title}</h1>{body}<p><a href="/_safe/portal">/_safe/portal</a> · <a href="/">/</a></p>"""

def register(app):
    @app.errorhandler(404)
    def _404(e):
        return Response(_html("404 - ne naydeno",
                              "<p>Marshrut otsutstvuet. Open bezopasnyy portal po ssylke nizhe.</p>"),
                        404, mimetype="text/html")

    @app.errorhandler(500)
    def _500(e):
        return Response(_html("500 - internal error",
                              "<p>Proizoshla oshibka obrabotchika. Ispolzuyte bezopasnye ssylki.</p>"),
                        500, mimetype="text/html")

    @app.errorhandler(405)
    def _405(e):
        return Response(_html("405 - metod ne razreshen",
                              "<p>Poprobuyte drugoy HTTP-metod ili vernites na portal.</p>"),
                        405, mimetype="text/html")