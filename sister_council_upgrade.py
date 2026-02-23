# -*- coding: utf-8 -*-
"""
sister_council_upgrade.py — patch run_ester_fixed.py (P2P «Sovet sester» + Passport path fix)

YaVNYY MOST:
  c = a + b  →  «semeynyy sovet» (a: chelovek/vopros Owner, b: protsedury/uzly), otvet — sintez.

SKRYTYE MOSTY:
  - Ashby (requisite variety): dobavlyaem esche odin kontur raznoobraziya (sestra) i daem arbitrazhu (synth) stabilizirovat.
  - Cover&Thomas (channel capacity): sestra daet korotkoe «mnenie», a ne gigabayty konteksta — ekonomim kanal/tokeny.

ZEMNOY ABZATs (inzheneriya/anatomiya):
  Eto pokhozhe na prostuyu elektricheskuyu tsep s parallelnymi vetkami: web-reshenie, lokalnye mneniya i «vetka sestry»
  idut odnovremenno, kak tok po neskolkim rezistoram. A taymaut — eto predokhranitel: esli vetka zavisla,
  ostalnaya skhema prodolzhaet rabotat, a ne «vybivaet probki» vsemu uzlu.

A/B-sloty i avto-otkat:
  A-slot — .bak-rezervnaya kopiya, B-slot — izmenennyy fayl. Pri provale validatsii — otkat na A.
"""

import os
import re
import shutil
import datetime
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGET_FILE = "run_ester_fixed.py"

# --- 1) Vzhivlenie «Soveta sester» bez razrusheniya kaskada ---
NEW_SYNTH_METHOD = r'''
    async def synthesize_thought(
        self,
        user_text: str,
        safe_history: List[Dict[str, Any]],
        base_system_prompt: str,
        identity_prompt: str,
        people_context: str,
        evidence_memory: str,
        file_context: str,
        facts_str: str,
        daily_report: str, chat_id: int = None) -> str:
        synth = self.pick_reply_synth()

        # --- P2P: mnenie sestry (ne blokiruet sbor mneniy) ---
        sister_task = None
        try:
            _timeout_raw = os.getenv("SISTER_OPINION_TIMEOUT", "30")
            sister_timeout = float(_timeout_raw) if _timeout_raw else 30.0
        except Exception:
            sister_timeout = 30.0

        # Vazhno: ne padaem, esli po kakoy-to prichine funktsiya sestry otsutstvuet
        if "ask_sister_opinion" in globals():
            try:
                sister_task = asyncio.create_task(ask_sister_opinion(user_text))
            except Exception:
                sister_task = None

        # Reshenie o web-search mozhet byt dorogim (LLM), parallelim.
        web_decision_task = asyncio.create_task(need_web_search_llm(synth, user_text))

        evidence_web = ""
        try:
            do_web = await web_decision_task
            if do_web and WEB_AVAILABLE and not CLOSED_BOX:
                evidence_web = await get_web_evidence_async(user_text, 3)
            if chat_id and evidence_web:
                WEB_CONTEXT_BY_CHAT[str(chat_id)] = evidence_web.strip()
        except Exception:
            evidence_web = ""

        evidence_web = truncate_text(evidence_web, MAX_WEB_CHARS)
        evidence_memory = truncate_text(evidence_memory, MAX_MEMORY_CHARS)
        file_context = truncate_text(file_context, MAX_FILE_CHARS)

        opinion_tasks = []
        for p in self.active:
            role_hint = self._role_hint(p)
            sys_msg = (
                base_system_prompt
                + "\n\n"
                + identity_prompt
                + (f"\n\n{role_hint}" if role_hint else "")
                + "\n\nZADAChA: Day svoy otvet/mnenie na vopros polzovatelya. "
                  "Esli ne uveren — otmet (nizkaya/srednyaya/vysokaya). "
                  "Ne ssylaysya na to, chego ne videl."
            )
            src = (
                f"\n\n[ISTOChNIKI]\n[PEOPLE_REGISTRY]: {people_context or 'Pusto'}\n"
                f"[PAMYaT]: {evidence_memory or 'Pusto'}\n"
                f"[FAYL]: {file_context or 'Pusto'}\n"
                f"[ZhURNAL DNYa]: {daily_report or 'Pusto'}\n"
            )
            msgs = [{"role": "system", "content": truncate_text(sys_msg + src, MAX_SYNTH_PROMPT_CHARS)}]
            msgs.extend(safe_history)
            msgs.append({"role": "user", "content": truncate_text(user_text, 20000)})
            opinion_tasks.append(self._ask_provider(p, msgs, temperature=0.7, chat_id=chat_id))

        opinions_raw = await asyncio.gather(*opinion_tasks, return_exceptions=True)
        opinions: List[Tuple[str, str, float, str]] = []
        for r in opinions_raw:
            if isinstance(r, Exception):
                continue
            provider = str(r.get("provider", ""))
            text = (r.get("text") or "").strip()
            sec = float(r.get("seconds") or 0.0)
            err = (r.get("error") or "").strip()
            if not text and err:
                text = f"[ERROR from {provider}] {err}"
            opinions.append((provider, truncate_text(text, MAX_OPINION_CHARS), sec, err))

        if not opinions:
            opinions = [("local", "Pusto.", 0.0, "no opinions")]

        # --- zhdem sestru, no s taymautom ---
        sister_opinion = ""
        if sister_task is not None:
            try:
                sister_opinion = await asyncio.wait_for(sister_task, timeout=max(1.0, float(sister_timeout)))
            except asyncio.TimeoutError:
                try:
                    sister_task.cancel()
                except Exception:
                    pass
                sister_opinion = ""
            except Exception:
                sister_opinion = ""

        if sister_opinion:
            opinions.append(("sister", truncate_text(str(sister_opinion).strip(), MAX_OPINION_CHARS), 0.0, ""))
            logging.info("[HIVE] Sister's opinion integrated.")
        else:
            logging.info("[HIVE] Sister was silent.")

        pool_text = "\n\n".join([f"=== {p} ({sec:.1f}s) ===\n{t}" for (p, t, sec, _) in opinions])
        pool_text = truncate_text(pool_text, MAX_SYNTH_PROMPT_CHARS)

        # VAZhNO: kaskad sokhranyaem (ne rezhem kachestvo)
        if CASCADE_REPLY_ENABLED:
            try:
                return await self._cascade_reply(
                    synth=synth,
                    base_system_prompt=base_system_prompt,
                    identity_prompt=identity_prompt,
                    people_context=people_context,
                    evidence_memory=evidence_memory,
                    evidence_web=evidence_web,
                    file_context=file_context,
                    pool_text=pool_text,
                    facts_str=facts_str,
                    daily_report=daily_report,
                    safe_history=safe_history,
                    user_text=user_text,
                )
            except Exception as e:
                logging.warning(f"[CASCADE] failed: {e}")

        is_owner = ("OWNER" in (identity_prompt or "").upper())
        emotional_mode = bool(is_owner and _is_emotional_text(user_text))

        if emotional_mode:
            out_style = "Otvet lichnyy/emotsionalnyy: otvechay kak Ester — teplo, pryamo, bez zagolovkov «Fakty/Interpretatsiya»."
            out_format = "FORMAT: tselnyy chelovecheskiy otvet."
        else:
            out_style = "Otvet tekhnicheskiy/delovoy: mozhno «Fakty / Interpretatsiya / Mnenie/Gipoteza»."
            out_format = "FORMAT:\n- Fakty\n- Interpretatsiya\n- Mnenie/Gipoteza (esli nuzhno)"

        synth_system = f"""{base_system_prompt}

{identity_prompt}

[PEOPLE_REGISTRY]:
{people_context or "Pusto"}

{out_style}

YOU ARE SINTEZATOR (HIVE).
Soberi luchshiy otvet, ispolzuya:
1) pul mneniy provayderov,
2) pamyat,
3) veb-fakty (esli est),
4) fayl (esli est),
5) zhurnal dnya (esli vopros pro “s kem obschalas/kto pisal segodnya” — TOLKO ottuda).

{out_format}

ANTI-EKhO: ne povtoryay gromkie utverzhdeniya bez opory na istochniki.

ISTOChNIKI:
[PAMYaT]: {evidence_memory or "Pusto"}
[WEB]: {evidence_web or "Pusto"}
[FAYL]: {file_context or "Pusto"}
[ZhURNAL DNYa]:
{daily_report}

PUL MNENIY:
{pool_text}

{facts_str}
""".strip()

        synth_messages = [{"role": "system", "content": truncate_text(synth_system, MAX_SYNTH_PROMPT_CHARS)}]
        synth_messages.extend(safe_history[-30:])
        synth_messages.append({"role": "user", "content": truncate_text(user_text, 20000)})

        final = await _safe_chat(synth, synth_messages, temperature=0.7, max_tokens=MAX_OUT_TOKENS)
        final = (final or "").strip()
        return final or opinions[0][1]
'''.lstrip("\n")

# --- 2) «Patch 2»: edinyy put profilea + fiksy datetime/hardcode ---
PASSPORT_HELPER = r'''
def _passport_jsonl_path() -> str:
    """
    Edinyy put k profileu pamyati (jsonl).
    Ispolzuem ESTER_HOME esli zadan, inache — otnositelnyy ./data/passport/clean_memory.jsonl
    """
    base = (os.environ.get("ESTER_HOME") or "").strip()
    if base:
        base = os.path.expandvars(os.path.expanduser(base))
        return os.path.join(base, "data", "passport", "clean_memory.jsonl")
    return os.path.join("data", "passport", "clean_memory.jsonl")
'''.lstrip("\n")

NEW_PERSIST_FUNC = r'''
def _persist_to_passport(role: str, text: str):
    # --- HIPPOCAMPUS WRITE (V2: With Dreams) ---
    try:
        path = _passport_jsonl_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)

        ts = datetime.datetime.now().isoformat()
        rec = {"timestamp": ts}

        if role == "user":
            rec["role_user"] = text
        elif role == "assistant":
            rec["role_assistant"] = text
        elif role == "thought":
            # Markiruem mysl, chtoby otlichat ot realnosti
            rec["role_system"] = f"[[INTERNAL MEMORY/DREAM]]: {text}"
            rec["tags"] = ["insight", "internal"]
        else:
            rec["role_misc"] = text

        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        logging.warning(f"[PASSPORT] persist failed: {e}")
'''.lstrip("\n")


def _ts():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _backup_file(path: Path) -> Path:
    backup = path.with_suffix(path.suffix + f".bak.{_ts()}")
    shutil.copy2(path, backup)
    return backup


def _find_block_by_markers(content: str, start_marker: str, end_marker: str) -> tuple[int, int]:
    s = content.find(start_marker)
    if s == -1:
        return (-1, -1)
    e = content.find(end_marker, s + len(start_marker))
    if e == -1:
        return (s, -1)
    return (s, e)


def _replace_method_synthesize_thought(content: str) -> tuple[str, bool]:
    # Ischem nachalo metoda (vnutri klassa) i konets bloka do "hive = EsterHiveMind()"
    start_pat = "\n    async def synthesize_thought("
    end_pat = "\n\nhive = EsterHiveMind()"
    s, e = _find_block_by_markers(content, start_pat, end_pat)
    if s == -1 or e == -1:
        return content, False

    # Sokhranyaem veduschiy perenos stroki, chtoby ne lomat formatirovanie
    before = content[:s + 1]
    after = content[e + 1:]
    new_content = before + NEW_SYNTH_METHOD + after
    return new_content, True


def _ensure_passport_helper_and_fix_paths(content: str) -> tuple[str, bool]:
    changed = False

    # 1) Vstavlyaem helper pered _persist_to_passport esli esche net
    if "_passport_jsonl_path" not in content:
        idx = content.find("def _persist_to_passport")
        if idx == -1:
            return content, False
        content = content[:idx] + PASSPORT_HELPER + "\n" + content[idx:]
        changed = True

    # 2) Zamenyaem funktsiyu _persist_to_passport tselikom (chinit i hardcode, i datetime.datetime.datetime)
    m = re.search(r"^def _persist_to_passport\([^\n]*\):\n(?:^[ \t].*\n)*", content, flags=re.MULTILINE)
    if not m:
        return content, False

    # konets bloka berem do sleduyuschego top-level def/class ili EOF
    block_start = m.start()
    scan = content[m.end():]
    m2 = re.search(r"^(def|class)\s+", scan, flags=re.MULTILINE)
    block_end = m.end() + (m2.start() if m2 else len(scan))
    content = content[:block_start] + NEW_PERSIST_FUNC + "\n" + content[block_end:]
    changed = True

    # 3) Podmena hardcode v restore_context_from_passport
    if r'passport_path = r"D:\ester-project\data\passport\clean_memory.jsonl"' in content:
        content = content.replace(
            r'passport_path = r"D:\ester-project\data\passport\clean_memory.jsonl"',
            "passport_path = _passport_jsonl_path()"
        )
        changed = True

    return content, changed


def _validate(content: str) -> tuple[bool, str]:
    if "hive = EsterHiveMind()" not in content:
        return False, "Ne nayden marker 'hive = EsterHiveMind()' (pokhozhe, struktura fayla izmenilas)."

    if "datetime.datetime.datetime" in content:
        return False, "Ostalas konstruktsiya 'datetime.datetime.datetime' — eto tochno upadet."

    if r"D:\ester-project\data\passport\clean_memory.jsonl" in content:
        return False, "Ostalsya zhestko proshityy put profilea D:\\ester-project\\... (patch 2 ne primenilsya)."

    if "async def synthesize_thought" in content and "SISTER_OPINION_TIMEOUT" not in content:
        return False, "synthesize_thought ne obnovlen (net SISTER_OPINION_TIMEOUT)."

    return True, "OK"


def apply_patch():
    print("🚀 Patch: Sovet sester (P2P) + Passport path fix (patch 2)")
    print(f"🎯 Tsel: {TARGET_FILE}")

    target = Path(TARGET_FILE)
    if not target.exists():
        print("❌ Fayl ne nayden.")
        return False

    backup = _backup_file(target)
    print(f"🧷 Backup (A-slot): {backup.name}")

    content = target.read_text(encoding="utf-8", errors="replace")

    # Idempotentnost: esli uzhe propatcheno — ne trogaem
    already = (
        ("SISTER_OPINION_TIMEOUT" in content)
        and ("_passport_jsonl_path" in content)
        and ("datetime.datetime.datetime" not in content)
    )
    if already:
        print("ℹ️ Pokhozhe, patch uzhe primenen (povtor ne nuzhen).")
        return True

    content2, ok_pass = _ensure_passport_helper_and_fix_paths(content)
    if not ok_pass:
        print("❌ Ne udalos primenit patch 2 (passport). Otkat.")
        shutil.copy2(backup, target)
        return False

    content3, ok_syn = _replace_method_synthesize_thought(content2)
    if not ok_syn:
        print("❌ Ne udalos obnovit synthesize_thought. Otkat.")
        shutil.copy2(backup, target)
        return False

    ok, msg = _validate(content3)
    if not ok:
        print(f"❌ Validatsiya provalena: {msg}")
        print("↩️ Otkat na backup.")
        shutil.copy2(backup, target)
        return False

    target.write_text(content3, encoding="utf-8", errors="strict")
    print("✅ Gotovo. Fayl obnovlen (B-slot).")
    return True


if __name__ == "__main__":
    try:
        ok = apply_patch()
        if not ok:
            print("⚠️ Patch ne primenen (sm. soobscheniya vyshe).")
    finally:
        try:
            input("\nNazhmi Enter dlya zaversheniya...")
        except Exception:
            pass
