from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -*- coding: utf-8 -*-
def main():
    # FastAPI: sobiraem app, registriruem system.md
    try:
        from fastapi import FastAPI
        from modules.reports.system_http import register_fastapi
        app = FastAPI()
        print("register_fastapi:", register_fastapi(app))
        routes = [r.path for r in app.routes]
        print("paths:", [p for p in routes if "/compat/reports/system.md" in p])
    except Exception as e:
        print("fastapi not available:", e.__class__.__name__)
    print("ok")
if __name__ == "__main__":
    main()