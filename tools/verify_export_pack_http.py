from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def main():
    try:
        from fastapi import FastAPI
        from modules.reports.export_http import register_fastapi
        app = FastAPI()
        print("register_fastapi:", register_fastapi(app))
        paths = [r.path for r in app.routes]
        show = [p for p in paths if "/compat/reports/download" in p]
        print("paths:", show)
    except Exception as e:
        print("fastapi not available:", e.__class__.__name__)
    print("ok")
if __name__ == "__main__":
    main()