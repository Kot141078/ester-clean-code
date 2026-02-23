# -*- coding: utf-8 -*-
import json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
out = {}
try:
    from modules.computer_use.anchors_suggest import OUT_PATH, export_heatmap, suggest_anchors
    r = export_heatmap()
    out["anchors_export"] = (r["ok"] and r["path"].endswith(".png") and r["url"].startswith("/data/"))
    out["anchors_suggest"] = len(suggest_anchors("Alpha beta gamma alpha").get("anchors", [])) >= 3
except Exception as e:
    out["anchors_error"] = str(e)

try:
    from listeners.lan_sync_watcher import scan, collect, diff
    s = scan()
    c = collect()
    out["lan_scan_ok"] = s.get("ok") and c.get("ok")
    out["lan_diff_ok"] = isinstance(diff({"items":[]},{"items":["x"]}), dict)
except Exception as e:
    out["lan_error"] = str(e)

try:
    from rule_engine import evaluate
    out["rule_eval"] = len(evaluate({"risk": 10}, [{"if":[{"var":"risk","op":"gt","value":5}],"then":{"a":1}}])["decisions"])==1
except Exception as e:
    out["rule_error"] = str(e)

print(json.dumps(out, ensure_ascii=False, indent=2))