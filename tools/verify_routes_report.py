from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def main():
    try:
        from fastapi import FastAPI
        from modules.reports.routes_http import register_fastapi
        app = FastAPI()
        # a couple of routes, including a double
        @app.get("/ping")
        def _p(): return {"ok": True}
        @app.get("/ping")
        def _p2(): return {"ok": True}
        print("register_fastapi:", register_fastapi(app))
        paths = [r.path for r in app.routes]
        print("paths:", [p for p in paths if "/compat/reports/routes.md" in p])
    except Exception as e:
        print("fastapi not available:", e.__class__.__name__)
    print("ok")
if __name__ == "__main__":
    main()