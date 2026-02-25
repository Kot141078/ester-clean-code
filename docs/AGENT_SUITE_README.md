# Ester — Agent Suite (Builder, KIT, Report, Activity, One-Click)

This file is a roadmap for the new panels and actions added within AgentBuilderCore.

**Mosty**
- Yavnyy: (Dokumentatsiya ↔ UX) - opisyvaet, where lezhat paneli i kak oni obraschayutsya k suschestvuyuschim ruchkam `/thinking/act`, `/thinking/cascade/*`, `/rulehub/*`.
- Skrytyy #1: (Dokumentatsiya ↔ Bezopasnost) — fiksiruet A/B-rezhim i WRITE-flag dlya guarded_apply (bez izmeneniya kontraktov).
- Skrytyy #2: (Dokumentatsiya ↔ Memory) — rekomenduemye zametki/profile dlya audita, sinkhronno s tem, chto uzhe delaet kaskad.

---

## Karta paneley (vse — staticheskie dokumenty v `docs/`)

- Agent_Builder.html is a builder of agents on top of e/thinking/acto and cascade.
- `agent_builder_kit.html` — Sustainability Kit (cheklisty, metriki, mini-plan).  
- agent_report.html - assembly of MD/HTML reports, recording via guarded_apply.
- agent_activity.html - view the activity Builder/KIT/Report + digest plan.
- `activity_to_report.html` - “aktivnost → otchet” (MD/HTML + optsionalnaya zapis).
- `oneclick_green.html` — One-Click Green: iz tseli → bundle (spec/plan/files/report).

All panels use a common ZhVT helper from estatic/admin.yse (localStorage: eester.zhvtyo, eAuthorization header: Bearer ...e).

---

## ENV switches (safe by default)

- `ESTER_AGENT_BUILDER_AB`: `"A"` (defolt, bezopasnyy)/`"B"` (eksperiment).  
- ёSTER_AGENT_BUILDER_WRITEyo: ё0е (default - writing is prohibited)/е1е (allow writing).
RuleNow policies can additionally force previews and log events.

---

## Quick checklist for registering in menus/docks (without changing server routes)

1. **Ssylki v indeks-dokakh**  
   - Dobavte ssylki na stranitsy iz `docs/agent_suite_index.html` v your main indexes dokumentatsii (for example, v suschestvuyuschiy `docs/index.html`, esli on ispolzuetsya v proekte).
   - The link structure is relative, because All pages are in yodoss/yo.

2. **Navigation in the admin panel (optional)**
   - If you have your own “showcase” of links in the UI/portal, add items to the listed HTML.
   - Server routes are not required - these are static files.

3. **RuleHub-presety**  
   - Pri neobkhodimosti vklyuchite preset `docs/agent_builder_rulehub_preset.yaml` cherez stranitsu RuleHub (chtenie/sokhranenie YAML uzhe podderzhivaetsya suschestvuyuschey adminkoy).

4. **Smoke-test**  
   - Open lyubuyu panel → “Check okruzhenie” (pokazhet AB-slot i status RuleHub).
   - Perform the basic actions: sheet/describé/plan/esesote or compose/save (in the preview).
   - To record, enable **both** conditions: eAB=Ae and eVRITE=1e (and confirm the policy if it is enabled).

---

## Zemnoy abzats

Eto "oblozhka" k novomu funktsionalu: odin README i edinyy indexes navigatsii. Polzovatelyu - where i klikat; Ester - s prezhnimi kontraktami, bez syurprizov. A/B i WRITE delayut samoizmeneniya bezopasnymi po umolchaniyu.

c=a+b.
