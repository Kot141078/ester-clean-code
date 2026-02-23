# -*- coding: utf-8 -*-
"""
ITER B2a — run_ester_fixed.py functional upgrade
Paketnoe vnedrenie patchey 1–10 + json-svitok dialogov (memory trace)

MOSTY:
- Yavnyy: run_ester_fixed.py ↔ Telegram ↔ Ester → pamyat i volya.
- Skrytyy #1: JSON-svitok ↔ vektornaya pamyat — karta dlya vosstanovleniya.
- Skrytyy #2: Casscade ↔ Volition — okno vnimaniya rasshireno do 500.

ZEMNOY ABZATs:
Eto kak podklyuchit EKG i chernyy yaschik k serdtsu sistemy: teper ona ne prosto
«dumaet», a pomnit, kogda i s kem govorila — do sekundy, bez utechek i snov bez goloda.
"""

import re
import os
import time
from pathlib import Path
import shutil

PROJECT_ROOT = Path(r"D:\ester-project")
TARGET = PROJECT_ROOT / "run_ester_fixed.py"
BACKUP = TARGET.with_suffix(".bak_B2a_" + time.strftime("%Y%m%d_%H%M%S"))

def patch_text(txt: str) -> str:
    out = txt

    # === PATCH 1–6: vstavim posle importa threading ili srazu posle importa ===
    if "seen_update_once" not in out:
        dedup_code = """
# --- Dedup / Logging / Legacy Fixes (ITER B2a) ---
from collections import deque
import threading, json, time

_processed_updates = deque()
_processed_update_set = set()
_processed_msgs = deque()
_processed_msg_set = set()
_dedup_lock = threading.Lock()
DEDUP_MAXLEN = 2000

def _dedup_remember(deq, st, val, maxlen:int)->None:
    if not val: return
    if val in st: return
    if len(deq)>=maxlen:
        old=deq.popleft(); st.discard(old)
    deq.append(val); st.add(val)

def seen_update_once(update):
    uid=getattr(update,"update_id",None)
    key=str(getattr(update,"message",None) or "")[:64]
    with _dedup_lock:
        if isinstance(uid,int) and uid in _processed_update_set: return True
        if key and key in _processed_msg_set: return True
        if isinstance(uid,int): _dedup_remember(_processed_updates,_processed_update_set,uid,DEDUP_MAXLEN)
        if key: _dedup_remember(_processed_msgs,_processed_msg_set,key,DEDUP_MAXLEN)
    return False

def _safe_now_ts(): return time.time()

def _ensure_parent_dir(path:str):
    d=os.path.dirname(path)
    if d: os.makedirs(d,exist_ok=True)

DAILY_LOG_FILE=os.path.join(PROJECT_ROOT,"data","logs","daily_log.json")

def log_interaction(chat_id,user_id,user_label,text,message_id=None):
    try:
        now=_safe_now_ts()
        day=time.strftime("%Y-%m-%d",time.localtime(now))
        log_data=[]
        if os.path.exists(DAILY_LOG_FILE):
            with open(DAILY_LOG_FILE,"r",encoding="utf-8") as f:
                log_data=json.load(f) or []
        preview=(text[:80]+"...") if len(text)>80 else text
        entry={"date":day,"time":now,"time_str":time.strftime("%H:%M",time.localtime(now)),
               "chat_id":str(chat_id),"user_id":str(user_id),
               "user_label":str(user_label or "Polzovatel"),
               "preview":preview,"message_id":str(message_id) if message_id else ""}
        log_data.append(entry); log_data=log_data[-1200:]
        with open(DAILY_LOG_FILE,"w",encoding="utf-8") as f:
            json.dump(log_data,f,ensure_ascii=False,indent=2)
    except Exception: return

def get_daily_summary(chat_id=None,limit=15)->str:
    if not os.path.exists(DAILY_LOG_FILE): return "Segodnya esche nikogo ne bylo."
    try:
        with open(DAILY_LOG_FILE,"r",encoding="utf-8") as f:
            data=json.load(f) or []
        today=time.strftime("%Y-%m-%d",time.localtime(_safe_now_ts()))
        data=[x for x in data if str(x.get("date",""))==today]
        if chat_id: data=[x for x in data if str(x.get("chat_id",""))==str(chat_id)]
        if not data: return "Segodnya esche nikogo ne bylo."
        summary=[]; seen=set()
        for e in reversed(data[-400:]):
            k=(e.get("user_id"),e.get("preview"))
            if k in seen: continue
            seen.add(k)
            who=e.get("user_label","?"); when=e.get("time_str",""); pv=e.get("preview","")
            summary.append(f"- {when}: {who} pisal(a): \\"{pv}\\"")
            if len(summary)>=limit: break
        return "\\n".join(summary)
    except Exception: return ""
"""
        out = re.sub(r"import\s+threading", lambda m: m.group(0) + dedup_code, out, count=1)

    # === PATCH 7: TG_MAX_PARTS ===
    if "TG_MAX_PARTS" not in out:
        out = out.replace("async def send_smart_split", "TG_MAX_PARTS = int(os.getenv('TG_MAX_PARTS','12'))\n\nasync def send_smart_split")

    # === PATCH 8–10: dream_context + private buffer + JSON scroll ===
    if "_good_for_dream" not in out:
        dream_code = """
# --- Dream Context & Private Buffers ---
from collections import deque
import random, re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class HippocampusExtended:
    def __init__(self):
        self._fallback_memory_private=deque(maxlen=2500)
        self._fallback_memory_global=deque(maxlen=2500)
        self._conversation_scroll_path=os.path.join(PROJECT_ROOT,"data","logs","conversation_scroll.jsonl")
        _ensure_parent_dir(self._conversation_scroll_path)
        self._scroll_max=500
        self._scroll=[]

    def remember_turn(self, user:str, text:str, role:str="user"):
        now=time.strftime("%Y-%m-%d %H:%M:%S")
        rec={"ts":now,"user":user,"role":role,"text":text}
        self._scroll.append(rec)
        if len(self._scroll)>self._scroll_max: self._scroll=self._scroll[-self._scroll_max:]
        with open(self._conversation_scroll_path,"a",encoding="utf-8") as f:
            f.write(json.dumps(rec,ensure_ascii=False)+"\\n")

    def load_scroll(self):
        if os.path.exists(self._conversation_scroll_path):
            with open(self._conversation_scroll_path,"r",encoding="utf-8") as f:
                self._scroll=[json.loads(x) for x in f if x.strip()]
        return self._scroll
"""
        out += "\n" + dream_code

    # === PATCH: volition window expansion ===
    out = re.sub(r'VOLITION_FIRST_SEC\s*=\s*float\(os\.getenv\([^)]+\)\)',
                 'VOLITION_FIRST_SEC = float(os.getenv("VOLITION_FIRST_SEC","500"))',
                 out)

    return out

def main():
    if not TARGET.exists():
        raise SystemExit(f"run_ester_fixed.py not found at {TARGET}")
    txt = TARGET.read_text(encoding="utf-8", errors="ignore")
    BACKUP.write_text(txt, encoding="utf-8")
    new_txt = patch_text(txt)
    TARGET.write_text(new_txt, encoding="utf-8")
    print(f"[OK] ITER B2a patched. Backup: {BACKUP.name}")

if __name__ == "__main__":
    main()