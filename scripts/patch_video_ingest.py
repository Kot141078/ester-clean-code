# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
TARGET = os.path.join(os.getcwd(), 'modules', 'media', 'video_ingest.py')
OLD = r'%\(id\)s.%(ext)s'
NEW = r'%(id)s.%(ext)s'
def patch(path: str) -> bool:
    if not os.path.isfile(path):
        print('skip: not found: ' + path)
        return False
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        src = f.read()
    if OLD in src:
        src = src.replace(OLD, NEW)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(src)
        print('patched: ' + path)
        return True
    print('no changes needed')
    return False
if __name__ == '__main__':
    patch(TARGET)