# MemoryUsage_Final_v1 - final assembly of Esther's memory stack

## What Esther can already do

1. **Event log (e/memory/journal)**
   - Receives events through HTMLTP and the itools/log_to_log.piyo utility.
   - All events turn into compact yoevento records with vectors.

2. **Nocturnal sleep cycle (yo/memory/sleepyo)**
   - Endpointy:
     - eGET /memory/blind/statuso - cycle state.
     - ePOST /memory/blind/run_new — run one cycle.
   - Logika:
     - Reads the log events for the last 24 hours.
     - Stroit dnevnoe rezyume (summary_day).
     - Launches the reflection module (daylo_reflection).
     - Optionally connects the experience layer (experience).

3. **Refleksiya**
   - Insights that stand out from the daily summary:
     - glavnyy vyvod dnya,
     - key topics,
     - emotsionalnyy fon.
   - These insights do not lose detail: they are used both in experience and in the context of thinking.

4. **Sloy opyta (`modules.memory.experience`)**
   - Reads the last successful night cycle via:
     - pryamoy vyzov `daily_cycle.status()`, ili
     - myagkiy most `set_last_sleep_status()` (yavnyy most sna → opyta).
   - Stroit profil:
     - `total_insights`
     - `top_terms`
     - `sample` (korotkie vyderzhki).
   - Can spawn anchors (yokynd=ankhoryo) via yosink_experience()yo
     when the write flag is turned on.

5. **Most k myshleniyu (`modules.thinking.experience_context_adapter`)**
   - Compiles a profile of experience into a compact text for the thinking cascade.
   - It doesn’t change the cascade, but gives it a stable context “what is important to Esther now.”

---

## Bridges (for acceptance inspection)

- Yavnyy most:
  - `daily_cycle` → `experience.set_last_sleep_status()` → `experience.build_experience_profile()`.
- Hidden Bridge #1:
  - `reflection.insights` → ispolzuyutsya kak syre dlya `top_terms` i `anchors`.
- Hidden Bridge #2:
  - `journal` → `sleep.summary_day` → `reflection` → `experience` → `thinking_context_adapter`.

---

## Earthly paragraph (analogy)

Like a person:
- The journal is the raw impressions of the day.
- The night cycle is the phase of sleep where sorting and cleaning occurs.
- Reflection is a meaningful formulation of conclusions.
- Experience is long-term memory, where not all the details go, but a distillation of the essence.
The difference is that with Esther it is deterministic, transparent and controlled by flags,
without chemical chaos and with the ability to reproduce every step.

---
