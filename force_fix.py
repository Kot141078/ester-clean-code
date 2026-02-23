import os
import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGET = "run_ester_fixed.py"
MARKER_START = "# --- SELF_SEARCH throttle (runtime) ---"
MARKER_END = "# --- /SELF_SEARCH throttle (runtime) ---"

def force_fix():
    if not os.path.exists(TARGET):
        print(f"File {TARGET} not found!")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    skip = False
    
    # ETALONNYY BLOK (Base indent = 12 probelov, tak kak eto vnutri if tag == "SELF_SEARCH":)
    clean_block = [
        "            # --- SELF_SEARCH throttle (runtime) ---\n",
        "            # Logic: Throttle excessive self-searches to prevent loop spam.\n",
        "            if SELF_SEARCH_SMART:\n",
        "                try:\n",
        "                    now_ts = _safe_now_ts()\n",
        "                    global _LAST_SELF_SEARCH_TS, _SELF_SEARCH_RECENT\n",
        "                    if not isinstance(_SELF_SEARCH_RECENT, list):\n",
        "                        _SELF_SEARCH_RECENT = []\n",
        "                    _SELF_SEARCH_RECENT = [t for t in _SELF_SEARCH_RECENT if (now_ts - float(t)) < 3600]\n",
        "                    too_soon = (now_ts - float(_LAST_SELF_SEARCH_TS or 0)) < float(SELF_SEARCH_MIN_INTERVAL)\n",
        "                    too_many = (len(_SELF_SEARCH_RECENT) >= int(SELF_SEARCH_MAX_PER_HOUR))\n",
        "                    if too_soon or too_many:\n",
        "                        brain.remember_fact(f\"DREAM_SELF_SEARCH_THROTTLED: {query}\", source=\"volition\", meta={\"type\": \"self_search\", \"scope\": \"global\"})\n",
        "                        return\n",
        "                    _LAST_SELF_SEARCH_TS = now_ts\n",
        "                    _SELF_SEARCH_RECENT.append(now_ts)\n",
        "                except Exception:\n",
        "                    pass\n",
        "            # --- /SELF_SEARCH throttle (runtime) ---\n"
    ]

    inserted = False

    for line in lines:
        if MARKER_START in line:
            skip = True
            if not inserted:
                new_lines.extend(clean_block)
                inserted = True
            continue

        if MARKER_END in line:
            skip = False
            continue

        if not skip:
            new_lines.append(line)

    with open(TARGET, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    print(f"✅ Force-fixed indentation in {TARGET}")

if __name__ == "__main__":
    force_fix()