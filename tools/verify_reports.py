from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def main():
    from modules.reports.summary import build_summary, render_markdown
    summary = build_summary({"entities": [{"id":1}, {"id":2}], "edges": [{"a":1}], "notes": []})
    md = render_markdown(summary, "Ester — KG Snapshot")
    print(md.splitlines()[0:6])
if __name__ == "__main__":
    main()