# -*- coding: utf-8 -*-
"""tests/stress_ingest.py - generator korpusa i nagruzochnyy inzhest s uchetom dedupa.

Name:
  • Sinteticheski sozdaet N dokumentov zadannogo razmera, chast — blizkie dublikaty.
  • Skladyvaet fayly v ./tmp/ingest_gen i podaet v IngestManager (bez vneshnikh zavisimostey).
  • Pechataet metriki: skorost inzhesta (fayly/s), dolyu otbroshennykh dedupom, itog po chankam.

CLI:
  python tests/stress_ingest.py --docs 200 --size 120000 --dup-rate 0.35 --workers 1

Argumenty:
  --docs kolichestvo faylov
  --size size odnogo fayla (simvolov), ~ ravnomerno
  --dup-rate dolya dublikatov (0..1), generiruyutsya per-frazovye perefrazy
  --workers skolko potokov obrabotki vyzvat sinkhronno (dlya demonstratsii)
  --persist katalog dannykh (po umolchaniyu ./data)

Zemnoy abzats (inzheneriya):
This skript - “trenazhernyy patron”: proveryaet, kak konveyer vedet sebya pod nepreryvnoy podachey,
skolko “struzhki” (dubley) otsekaetsya, i ne klinit li mekhanizm.

Mosty:
- Yavnyy (Kibernetika ↔ Arkhitektura): nagruzka+obratnaya svyaz metrik pokazyvaet ustoychivost regulyatorov dedupa.
- Skrytyy 1 (Infoteoriya ↔ Ekonomika): kontroliruemaya dolya dubley izmeryaet ekonomiyu IO/diska ot MinHash.
- Skrytyy 2 (Anatomiya ↔ PO): kak nagruzochnyy test serdtsa - rastim pulse i smotrim, derzhit li sosudistaya sistema.

# c=a+b"""
from __future__ import annotations

import argparse, os, random, string, time, pathlib, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _rand_word():
    alph = "abvgdeziyklmnoprstufkhtschshscheyuya"
    L = random.randint(4,10)
    return "".join(random.choice(alph) for _ in range(L))

def _paragraph(seed: int, target_chars: int) -> str:
    random.seed(seed)
    words = []
    while len(" ".join(words)) < target_chars:
        words.append(_rand_word())
        if len(words) % random.randint(8,15) == 0:
            words.append("\n")
    base = " ".join(words)
    # insert "chapters" for L1
    return ("Glava 1\n" + base[: target_chars//2] + "\nGlava 2\n" + base[target_chars//2 : target_chars])

def _near_dup(text: str) -> str:
    # easy paraphrases - synonymous substitutions/rearrangements: enough for Minnash
    parts = text.split()
    random.shuffle(parts)
    for i in range(0, len(parts), 17):
        parts[i] = parts[i][::-1]
    return " ".join(parts)

def _gen_corpus(out_dir: str, docs: int, size: int, dup_rate: float) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    base_count = int(docs * (1.0 - dup_rate))
    # bazovye unikalnye
    for i in range(base_count):
        t = _paragraph(1000 + i, size)
        p = os.path.join(out_dir, f"u_{i:05d}.txt")
        open(p, "w", encoding="utf-8").write(t)
        paths.append(p)
    # dublikaty
    rest = docs - base_count
    for i in range(rest):
        src = paths[i % base_count]
        t = _near_dup(open(src, "r", encoding="utf-8").read())
        p = os.path.join(out_dir, f"d_{i:05d}.txt")
        open(p, "w", encoding="utf-8").write(t)
        paths.append(p)
    random.shuffle(paths)
    return paths

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", type=int, default=200)
    ap.add_argument("--size", type=int, default=120000)
    ap.add_argument("--dup-rate", type=float, default=0.35)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--persist", default="./data")
    args = ap.parse_args()

    out_dir = "./tmp/ingest_gen"
    paths = _gen_corpus(out_dir, args.docs, args.size, max(0.0, min(1.0, args.dup_rate)))

    # lokalnyy IngestManager (bez avtozapuska, sinkhronnye tiki)
    from modules.ingest_manager import IngestManager
    m = IngestManager(vstore=None, memory_manager=None, inbox_dir=None, persist_dir=args.persist, autostart=False)

    t0 = time.time()
    job_ids = [m.submit_file(p) for p in paths]
    # imitiruem workers tikami
    processed = 0
    while processed < len(job_ids):
        for _ in range(max(1, args.workers)):
            m._run_worker()
        processed = sum(1 for j in m.list_jobs() if j["status"] in ("DONE","ERROR","SKIPPED_DUP"))
        time.sleep(0.05)
    t1 = time.time()

    # metriki dedupa
    metrics_path = os.path.join(args.persist, "metrics_dedup.json")
    dedup = {"seen": 0, "accepted": 0, "dropped": 0}
    try:
        dedup = json.loads(open(metrics_path, "r", encoding="utf-8").read())
    except Exception:
        pass

    done = [j for j in m.list_jobs() if j["status"] == "DONE"]
    skipped = [j for j in m.list_jobs() if j["status"] == "SKIPPED_DUP"]
    print(json.dumps({
        "ingested_files": len(done),
        "skipped_duplicates": len(skipped),
        "total_jobs": len(job_ids),
        "elapsed_sec": round(t1 - t0, 2),
        "files_per_sec": round(len(job_ids) / max(0.001, (t1 - t0)), 2),
        "dedup_metrics": dedup
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()