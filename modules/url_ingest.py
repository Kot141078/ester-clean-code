# -*- coding: utf-8 -*-
from modules.net_manager import ingest_url as fetch
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# Alias wrapper
def process(url):
    return fetch(url)