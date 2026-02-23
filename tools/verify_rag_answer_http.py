from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def main():
    try:
        from fastapi import FastAPI
        from modules.rag.http_answer import register_fastapi
        app = FastAPI()
        print("register_fastapi:", register_fastapi(app))
        paths = [r.path for r in app.routes]
        print("paths:", [p for p in paths if "/compat/rag/answer" in p])
    except Exception as e:
        print("fastapi not available:", e.__class__.__name__)
    print("ok")
if __name__ == "__main__":
    main()