# Ester: kontur pamyati, sna i opyta (svodka)

MOSTY:
- Yavnyy: (Zhurnal → Son → Refleksiya → Opyt → Myshlenie).
- Skrytyy #1: (Tekhnicheskie sobytiya → Chelovecheski chitaemye insayty).
- Skrytyy #2: (Vektornaya/strukturnaya pamyat → kompaktnyy kontekst dlya LLM).

ZEMNOY ABZATs:
Dlya inzhenera eto pipeline: vkhodnye sobytiya pishutsya v pamyat,
nochnoy tsikl ikh chistit, szhimaet i agregiruet, a sloy myshleniya poluchaet
gotovyy kontekst bez ruchnykh «kodovykh fraz».

## 1. Potok dannykh

1. **Dnem**
   - Sobytiya/zhurnal → `modules.memory.events` / `journal` / prochie istochniki.
   - Zapis cherez suschestvuyuschie API/alias, nichego novogo ne navyazano.

2. **Nochyu**
   - `/memory/sleep/run_now` → `modules.memory.sleep_alias` → `modules.memory.daily_cycle.run_cycle()`
   - V `daily_cycle`:
     - `summary_day` — svodka dnya (esli est zapisi).
     - `memory_qa` — optsionalnyy QC (B-slot/flag).
     - `memory_policies` — optsionalnoe primenenie politik.
     - `memory_backup` — optsionalnyy bekap.
     - `daily_reflection` — insayty na osnove svodki.
     - `experience_sync` — optsionalnoe obnovlenie anchors iz insaytov.

3. **Opyt**
   - `modules.memory.experience`:
     - `build_experience_profile()` — chitaet insayty.
     - `sync_experience()` — po flagam sozdaet `kind="anchor"`.

4. **Myshlenie**
   - `modules.thinking.experience_context_adapter.get_experience_context()`:
     - Stroit kompaktnyy blok:
       - klyuchevye motivy (top_terms),
       - neskolko insaytov.
     - Gotov dlya vklyucheniya v system prompt/kontekst.

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
  - `ESTER_MEMORY_EXPERIENCE_WRITE=1` — razreshit anchors.

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
- kopit sobytiya,
- vo sne svorachivaet ikh v summary/insights,
- formiruet sloy opyta,
- podaet ego v myshlenie cherez adapter.
Polzovatel prosto govorit po-chelovecheski.

## 4. Diagnostika

```bash
python tools/show_memory_stack_status.py
```

Vyvod:
- status sna,
- profil opyta,
- prevyu konteksta dlya myshleniya.
