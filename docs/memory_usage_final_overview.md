# MemoryUsage_Final_v1 — finalnaya sborka steka pamyati Ester

## Chto uzhe umeet Ester

1. **Zhurnal sobytiy (`/memory/journal`)**
   - Prinimaet sobytiya cherez HTTP i utilitu `tools/log_to_journal.py`.
   - Vse sobytiya prevraschayutsya v kompaktnye `event`-zapisi s vektorami.

2. **Nochnoy tsikl sna (`/memory/sleep`)**
   - Endpointy:
     - `GET /memory/sleep/status` — sostoyanie tsikla.
     - `POST /memory/sleep/run_now` — zapustit odin tsikl.
   - Logika:
     - Chitaet sobytiya zhurnala za poslednie sutki.
     - Stroit dnevnoe rezyume (summary_day).
     - Zapuskaet modul refleksii (daily_reflection).
     - Optsionalno podklyuchaet sloy opyta (experience).

3. **Refleksiya**
   - Iz dnevnogo rezyume vydelyayutsya insayty:
     - glavnyy vyvod dnya,
     - klyuchevye temy,
     - emotsionalnyy fon.
   - Eti insayty ne teryayut detaley: ispolzuyutsya i v opyte, i v kontekste myshleniya.

4. **Sloy opyta (`modules.memory.experience`)**
   - Chitaet posledniy uspeshnyy nochnoy tsikl cherez:
     - pryamoy vyzov `daily_cycle.status()`, ili
     - myagkiy most `set_last_sleep_status()` (yavnyy most sna → opyta).
   - Stroit profil:
     - `total_insights`
     - `top_terms`
     - `sample` (korotkie vyderzhki).
   - Mozhet porozhdat yakorya (`kind=anchor`) cherez `sync_experience()`
     pri vklyuchennom flage zapisi.

5. **Most k myshleniyu (`modules.thinking.experience_context_adapter`)**
   - Sobiraet profil opyta v kompaktnyy tekst dlya kaskada myshleniya.
   - Ne menyaet kaskad, a daet emu ustoychivyy kontekst «chto dlya Ester seychas vazhno».

---

## Mosty (dlya priemochnogo kontrolya)

- Yavnyy most:
  - `daily_cycle` → `experience.set_last_sleep_status()` → `experience.build_experience_profile()`.
- Skrytyy most #1:
  - `reflection.insights` → ispolzuyutsya kak syre dlya `top_terms` i `anchors`.
- Skrytyy most #2:
  - `journal` → `sleep.summary_day` → `reflection` → `experience` → `thinking_context_adapter`.

---

## Zemnoy abzats (analogiya)

Kak u cheloveka:
- Zhurnal — eto syrye dnevnye vpechatleniya.
- Nochnoy tsikl — eto faza sna, gde proiskhodit sortirovka i chistka.
- Refleksiya — osmyslennaya formulirovka vyvodov.
- Opyt — dolgovremennaya pamyat, kuda popadayut ne vse detali, a vyzhimka suti.
Raznitsa v tom, chto u Ester eto determinirovano, prozrachno i upravlyaetsya flagami,
bez khimicheskogo khaosa i s vozmozhnostyu vosproizvesti kazhdyy shag.

---
