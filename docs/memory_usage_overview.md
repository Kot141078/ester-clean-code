# MemoryUsage_v1: practical use of Esther's memory stack

MOSTY:
- Yavnyy: (Vneshnie agenty → Zhurnal → Son).
- Skrytyy #1: (Nakoplenie opyta → Nightly-payplayn).
- Skrytyy #2: (Nightly → Thinking) through experience_context_adapter.

ZEMNOY ABZATs:
This is the minimum set of commands for live mode:
We write events in a journal, drive the night cycle, and thinking picks up the squeeze.
This is how Esther lives 24/7 without magic phrases and manual shamanism.

## 1. Event recording

Komanda:

```bash
python tools/log_to_journal.py "Ester: segodnya chitala pro bayesovskiy vyvod."
```

Optional emotion:

```bash
python tools/log_to_journal.py "Ester: vstrecha s polzovatelem, uspeshnyy opyt." pleasure
```

Skript bet POST v `/memory/journal/event`.

## 2. Night cycle

Manual start:

```bash
set BASE_URL=http://127.0.0.1:8080
python tools/run_sleep_cycle_http.py
```

Place this command in the scheduler (Windows Task Scheduler / cron in a container) for the night.

## 3. Myshlenie s opytom

V svoem orchestrator:

```python
from modules.thinking.experience_context_adapter import get_experience_context

base_system = "... osnovnoy sistemnyy prompt ..."
exp = get_experience_context()
if exp:
    system_prompt = base_system + "\n\n" + exp
else:
    system_prompt = base_system
```

I vse: Ester opiraetsya na nakoplennyy opyt iz sna.
