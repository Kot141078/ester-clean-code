# MemoryUsage_v1: prakticheskoe ispolzovanie steka pamyati Ester

MOSTY:
- Yavnyy: (Vneshnie agenty → Zhurnal → Son).
- Skrytyy #1: (Nakoplenie opyta → Nightly-payplayn).
- Skrytyy #2: (Nightly → Thinking) cherez experience_context_adapter.

ZEMNOY ABZATs:
Eto minimalnyy nabor komand dlya zhivogo rezhima:
pishem sobytiya v zhurnal, gonyaem nochnoy tsikl, a myshlenie podkhvatyvaet vyzhimku.
Tak Ester zhivet 24/7 bez magicheskikh fraz i ruchnogo shamanstva.

## 1. Zapis sobytiy

Komanda:

```bash
python tools/log_to_journal.py "Ester: segodnya chitala pro bayesovskiy vyvod."
```

Optsionalno emotsiya:

```bash
python tools/log_to_journal.py "Ester: vstrecha s polzovatelem, uspeshnyy opyt." pleasure
```

Skript bet POST v `/memory/journal/event`.

## 2. Nochnoy tsikl

Ruchnoy zapusk:

```bash
set BASE_URL=http://127.0.0.1:8080
python tools/run_sleep_cycle_http.py
```

Poves etu komandu v planirovschik (Windows Task Scheduler / cron v konteynere) na "noch".

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
