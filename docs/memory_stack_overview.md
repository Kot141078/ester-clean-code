# Esther: the circuit of memory, sleep and experience (summary)

MOSTY:
- Yavnyy: (Zhurnal → Son → Refleksiya → Opyt → Myshlenie).
- Skrytyy #1: (Tekhnicheskie sobytiya → Chelovecheski chitaemye insayty).
- Hidden #2: (Vector/structural memory → compact context for LLM).

ZEMNOY ABZATs:
For an engineer, this is pipeline: input events are written to memory,
the night cycle cleans them, compresses and aggregates, and the thinking layer receives
ready-made context without manual “passphrases”.

## 1. Potok dannykh

1. **Dnem**
   - Sobytiya/zhurnal → `modules.memory.events` / `journal` / prochie istochniki.
   - Recording via existing API/alias, nothing new is imposed.

2. **Nochyu**
   - `/memory/sleep/run_now` → `modules.memory.sleep_alias` → `modules.memory.daily_cycle.run_cycle()`
   - V `daily_cycle`:
     - yosumary_dayo - summary of the day (if there are records).
     - `memory_qa` — optsionalnyy QC (B-slot/flag).
     - `memory_policies` — optsionalnoe primenenie politik.
     - `memory_backup` — optsionalnyy bekap.
     - `daily_reflection` — insayty na osnove svodki.
     - Yoeksperienze_sinkyo - optional update of anchor from insights.

3. **Opyt**
   - `modules.memory.experience`:
     - `build_experience_profile()` — chitaet insayty.
     - `sync_experience()` — po flagam sozdaet `kind="anchor"`.

4. **Myshlenie**
   - `modules.thinking.experience_context_adapter.get_experience_context()`:
     - Stroit kompaktnyy blok:
       - key motives (top_terms),
       - neskolko insaytov.
     - Ready for inclusion in prompt/context systems.

## 2. ENV-flagi

- Son / nightly:
  - `ESTER_MEMORY_SLEEP_AB=A|B`
  - `ESTER_MEMORY_SLEEP_QA=1`
  - `ESTER_MEMORY_SLEEP_POLICY=1`
  - `ESTER_MEMORY_SLEEP_BACKUP=1`
  - `ESTER_MEMORY_REFLECT=0|1`
  - `ESTER_MEMORY_EXPERIENCE_IN_SLEEP=1` — shag experience_sync.

- Opyt:
  - `ESTER_MEMORY_EXPERIENCE_AB=A|B`
  - ёESTER_MEMORY_EXPERIENCE_VRITE=1е - allow anchor.

- Thinking-adapter:
  - `ESTER_THINKING_EXPERIENCE=1|0`
  - `ESTER_THINKING_EXPERIENCE_MAX_CHARS=N`

## 3. Ispolzovanie bez kodovoy frazy

V orchestrator/LM Studio/Judge:

```python
from modules.thinking.experience_context_adapter import get_experience_context

base_system = \"... bazovaya sistemnaya instruktsiya ...\"
exp = get_experience_context()
if exp:
    system_prompt = base_system + \"\\n\\n\" + exp
else:
    system_prompt = base_system
```

Ester sama:
- buy events,
- in his sleep he rolls them up into summaries/insignts,
- formiruet sloy opyta,
- feeds it into thinking through an adapter.
The user just speaks like a human being.

## 4. Diagnostika

```bash
python tools/show_memory_stack_status.py
```

Vyvod:
- status sna,
- profil opyta,
- preview of the context for thinking.
