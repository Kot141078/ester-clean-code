from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -*- coding: utf-8 -*-
def main():
    # FastAPI
    try:
        from fastapi import FastAPI
        from modules.reports.selfcheck_http import register_fastapi as reg
        app = FastAPI()
        print("selfcheck.register_fastapi:", reg(app))
        routes = [r.path for r in app.routes]
        print("paths:", [p for p in routes if "/compat/selfcheck" in p])
    except Exception as e:
        print("fastapi not available:", e.__class__.__name__)
    print("ok")
if __name__ == "__main__":
    main()