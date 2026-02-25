from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -*- coding: utf-8 -*-
def main():
    # FastAPI: assembling a router (if fastAPI is surrounded)
    try:
        from fastapi import FastAPI
        from modules.reports.http import register_fastapi
        app = FastAPI()
        print("register_fastapi:", register_fastapi(app))
        # perechislim puti
        routes = [(r.path, ",".join(sorted([m for m in r.methods if m in {"GET","POST","PUT","DELETE"}]))) for r in app.routes]
        print("routes:", [p for p in routes if "/compat/reports" in p[0]])
    except Exception as e:
        print("fastapi not available:", e.__class__.__name__)
    print("ok")
if __name__ == "__main__":
    main()