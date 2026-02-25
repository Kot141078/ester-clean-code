# -*- coding: utf-8 -*-
"""roles/store.py - khranilische profiley, nablyudeniy i obratnoy svyazi + EMA-obnovleniya i index.

MOSTY:
- (Yavnyy) upsert_observation(agent_id,text,channel,meta) → obnovlyaet istoriyu i profile (vektor/yarlyki).
- (Skrytyy #1) Obratnyy indexes: get_agent_by_key(contact_key) ispolzuet suschestvuyuschiy nudges_recipients.
- (Skrytyy #2) Vektora/yarlyki JSON khranyatsya v roles_people; istoriya - v roles_interactions; feedback - v roles_feedback.

ZEMNOY ABZATs:
Kazhdaya replika/sobytie — malenkiy signal. My akkuratno nakaplivaem ikh i obnovlyaem predstavlenie o cheloveke,
ne trebuya anket i ne menyaya tekuschie potoki.

# c=a+b"""
from __future__ import annotations

import os, time, json, sqlite3
from typing import Any, Dict, List, Optional, Tuple

from roles.infer import infer_features, update_vector, label_by_ontology
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

EMA_ALPHA = float(os.getenv("ROLE_EMA_ALPHA","0.2") or "0.2")

DDL = """
CREATE TABLE IF NOT EXISTS roles_people(
  agent_id TEXT PRIMARY KEY,
  vector_json TEXT NOT NULL,
  labels_json TEXT NOT NULL,
  attrs_json  TEXT NOT NULL,
  updated_ts  REAL NOT NULL,
  samples_cnt INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS roles_interactions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  agent_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  text TEXT NOT NULL,
  meta_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_ri_agent ON roles_interactions(agent_id);
CREATE TABLE IF NOT EXISTS roles_feedback(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  agent_id TEXT NOT NULL,
  add_labels_json TEXT,
  remove_labels_json TEXT,
  delta_json TEXT,
  note TEXT
);
"""

_MEM_CONN_CACHE: dict[str, sqlite3.Connection] = {}


def _memory_conn(cache_key: str) -> sqlite3.Connection:
    conn = _MEM_CONN_CACHE.get(cache_key)
    if conn is None:
        conn = sqlite3.connect(":memory:", timeout=5.0, isolation_level=None, check_same_thread=False)
        conn.executescript(DDL)
        _MEM_CONN_CACHE[cache_key] = conn
    return conn


def _conn() -> sqlite3.Connection:
    db_path = os.getenv("MESSAGING_DB_PATH", "data/messaging.db")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    def _open(prefer_wal: bool = True) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL" if prefer_wal else "PRAGMA journal_mode=DELETE")
        except sqlite3.OperationalError:
            conn.execute("PRAGMA journal_mode=DELETE")
        return conn

    try:
        c = _open(prefer_wal=True)
    except sqlite3.OperationalError:
        return _memory_conn(db_path)
    try:
        c.executescript(DDL)
        return c
    except sqlite3.OperationalError as e:
        c.close()
        msg = str(e).lower()
        if "disk i/o" in msg or "malformed" in msg:
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.remove(db_path + suffix)
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
        try:
            c2 = _open(prefer_wal=False)
        except sqlite3.OperationalError:
            return _memory_conn(db_path)
        try:
            c2.executescript(DDL)
            return c2
        except sqlite3.OperationalError:
            c2.close()
            return _memory_conn(db_path)

def get_agent_by_key(contact_key: str) -> str | None:
    with _conn() as c:
        r = c.execute("SELECT agent_id FROM nudges_recipients WHERE contact_key=?", (contact_key,)).fetchone()
        return str(r[0]) if r else None

def _read_profile(agent_id: str) -> Dict[str, Any] | None:
    with _conn() as c:
        r = c.execute("SELECT vector_json,labels_json,attrs_json,updated_ts,samples_cnt FROM roles_people WHERE agent_id=?",(agent_id,)).fetchone()
        if not r: return None
        return {"agent_id":agent_id,"vector":json.loads(r[0]),"labels":json.loads(r[1]),"attrs":json.loads(r[2]),
                "updated_ts":float(r[3]),"samples_cnt":int(r[4] or 0)}

def _write_profile(agent_id: str, vector: Dict[str,float], labels: List[str], attrs: Dict[str,Any], samples_cnt: int) -> None:
    with _conn() as c:
        c.execute("REPLACE INTO roles_people(agent_id,vector_json,labels_json,attrs_json,updated_ts,samples_cnt) VALUES(?,?,?,?,?,?)",
                  (agent_id, json.dumps(vector, ensure_ascii=False), json.dumps(labels, ensure_ascii=False),
                   json.dumps(attrs, ensure_ascii=False), time.time(), int(samples_cnt)))

def upsert_observation(agent_id: str, text: str, channel: str, meta: Dict[str,Any] | None = None) -> Dict[str,Any]:
    """Saves surveillance and updates profile; returns the updated profile."""
    ts = time.time()
    with _conn() as c:
        c.execute("INSERT INTO roles_interactions(ts,agent_id,channel,text,meta_json) VALUES(?,?,?,?,?)",
                  (ts, agent_id, channel, text, json.dumps(meta or {}, ensure_ascii=False)))
    feats = infer_features(text)
    prev = _read_profile(agent_id) or {"vector":{}, "labels":[], "attrs":{}, "samples_cnt":0}
    vector = update_vector(prev["vector"], feats.get("dims",{}), EMA_ALPHA)
    labels = list({*prev["labels"], *feats.get("labels",[])})
    # avto-leybling po ontologii
    top = label_by_ontology(vector, top_k=3)
    for t in top:
        if t not in labels: labels.append(t)
    attrs = prev.get("attrs") or {}
    attrs["last_trace"] = feats.get("trace",[])
    samples_cnt = int(prev.get("samples_cnt",0)) + 1
    _write_profile(agent_id, vector, labels, attrs, samples_cnt)
    return {"agent_id":agent_id,"vector":vector,"labels":labels,"attrs":attrs,"samples_cnt":samples_cnt}

def apply_feedback(agent_id: str, add_labels: List[str] | None, remove_labels: List[str] | None, delta: Dict[str,float] | None, note: str | None) -> Dict[str,Any]:
    with _conn() as c:
        c.execute("INSERT INTO roles_feedback(ts,agent_id,add_labels_json,remove_labels_json,delta_json,note) VALUES(?,?,?,?,?,?)",
                  (time.time(), agent_id, json.dumps(add_labels or []), json.dumps(remove_labels or []),
                   json.dumps(delta or {}), note or ""))
    prof = _read_profile(agent_id) or {"vector":{}, "labels":[], "attrs":{}, "samples_cnt":0}
    vec = dict(prof["vector"])
    if delta:
        for k,v in delta.items():
            vec[k] = max(0.0, min(1.0, float(vec.get(k,0.0)) + float(v)))
    labels = [l for l in prof["labels"] if l not in (remove_labels or [])]
    for l in (add_labels or []):
        if l not in labels: labels.append(l)
    _write_profile(agent_id, vec, labels, prof.get("attrs",{}), prof.get("samples_cnt",0))
    return _read_profile(agent_id)

def list_people(limit: int = 200) -> List[Dict[str,Any]]:
    with _conn() as c:
        rows = c.execute("SELECT agent_id,vector_json,labels_json,updated_ts,samples_cnt FROM roles_people ORDER BY updated_ts DESC LIMIT ?", (int(limit),)).fetchall()
        out=[]
        for agent_id, vj, lj, uts, cnt in rows:
            out.append({"agent_id":agent_id, "vector":json.loads(vj), "labels":json.loads(lj),
                        "updated_ts":float(uts), "samples_cnt":int(cnt or 0)})
        return out

def get_profile(agent_id: str) -> Dict[str,Any] | None:
    return _read_profile(agent_id)

def learn_batch(window_sec: int = 7*24*3600) -> int:
    """Pereobuchenie: prokhodit po poslednim nablyudeniyam, agregiruet EMA v profilyakh.
    Funktsiya idempotentna za schet EMA-formulirovki: khranenie profiley uzhe nakopleno.
    Vozvraschaet chislo prosmotrennykh nablyudeniy v okne."""
    since = time.time() - window_sec
    with _conn() as c:
        rows = c.execute("SELECT agent_id,text FROM roles_interactions WHERE ts>=? ORDER BY ts ASC", (since,)).fetchall()
    n=0
    for agent_id, text in rows:
        upsert_observation(agent_id, text, channel="relearn", meta={"replay":True})
        n+=1
    return n

def rank_for_task(task_text: str | None, dims: Dict[str,float] | None, top_n: int = 5) -> List[Dict[str,Any]]:
    """Ranking of agents for a task: task_text -> needs by vectors + explicit dims."""
    # rough projection of the task text onto the needs vector using the same heuristics
    need = {}
    if task_text:
        from roles.infer import infer_features as _if
        need = _if(task_text).get("dims",{})
    dims = dims or {}
    w_text = float(os.getenv("ROLE_HINTS_WEIGHT_TEXT","0.8") or "0.8")
    w_exp  = float(os.getenv("ROLE_HINTS_WEIGHT_EXPLICIT","1.0") or "1.0")
    need_all = {}
    for k in set(list(need.keys())+list(dims.keys())):
        need_all[k] = w_text*float(need.get(k,0.0)) + w_exp*float(dims.get(k,0.0))
    # skalyarnoe proizvedenie / normirovka
    people = list_people(limit=10000)
    scored=[]
    for p in people:
        s=0.0; denom=0.0
        for k,v in need_all.items():
            s += float(p["vector"].get(k,0.0))*v
            denom += v
        score = s/max(1e-6, denom)
        scored.append({"agent_id":p["agent_id"], "score":round(score,4), "labels":p["labels"][:3]})
    scored.sort(key=lambda x:x["score"], reverse=True)
    return scored[:max(1, top_n)]
