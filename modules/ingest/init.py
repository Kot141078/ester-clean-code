from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
"""modules.ingest - paket poglotiteley kontenta (ingesters).

MOSTY:
- (Yavnyy) Nalichie paketa snimaet importa-krusheniya starykh routov.
- (Skrytyy #1) Gotov rasshiryatsya (pdf/docx/html) bez izmeneniya importov.
- (Skrytyy #2) Sovmestim s closed_box: zavisimosti ne trebuyutsya.

ZEMNOY ABZATs:
This is “priemnyy lotok”: syuda dobavlyaem obrabotchiki raznykh formatov.

# c=a+b"""
__all__ = ["code_ingest", "process"]
# c=a+b
