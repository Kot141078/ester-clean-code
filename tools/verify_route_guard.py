from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def main():
    try:
        from fastapi import FastAPI
        app = FastAPI()
        from modules.tools import route_guard as rg
        import os
        os.environ["ESTER_ROUTE_GUARD"] = "1"
        rg.enable_for_fastapi(app)
        @app.get("/echo")
        def _ok(): return {"ok": True}
        # povtor
        @app.get("/echo")
        def _dup(): return {"ok": False}
        # check: the second one should not be added
        paths = [(r.path, sorted(list(r.methods or []))) for r in app.routes]
        print("routes:", [p for p in paths if "/echo" in p[0]])
    except Exception as e:
        print("fastapi not available:", e.__class__.__name__)
    print("ok")
if __name__ == "__main__":
    main()