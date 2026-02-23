# Agent Builder dlya Ester — rukovodstvo po bezopasnomu ispolzovaniyu

## Chto eto
Mini-nadstroyka, pozvolyayuschaya Ester opisyvat, planirovat i sobirat agentov po tselyam — bez izmeneniya suschestvuyuschikh kontraktov. UI obraschaetsya k imeyuschimsya ruchkam `/thinking/act`, `/thinking/cascade/*`, `/rulehub/*`, a avtorizatsiya vypolnyaetsya cherez obschiy mekhanizm JWT iz adminki.
  
**Mosty**  
- Yavnyy: (UX ↔ Mysli/Kaskad) — knopki v `docs/agent_builder.html` vyzyvayut `/thinking/act`, `/thinking/cascade/execute`.  
- Skrytyy #1: (UX ↔ RuleHub) — tot zhe ekran pozvolyaet chitat/sokhranyat YAML cherez `/rulehub/config`.  
- Skrytyy #2: (UX ↔ Avtorizatsiya) — edinyy JWT-potok iz `static/admin.js`.

## Bezopasnye rezhimy (A/B + WRITE)
- `ESTER_AGENT_BUILDER_AB`: `A` (defolt, bezopasnyy), `B` (eksperiment).  
- `ESTER_AGENT_BUILDER_WRITE`: `0` (defolt — zapis zapreschena), `1` (razreshit zapis).  
Politika RuleHub (iz preseta) dopolnitelno proveryaet: slot=A, WRITE=1 i otsutstvie konfliktov — inache deystviya ostayutsya v prevyu.

## Rabochiy potok
1. Zadayte tsel i auditoriyu → «Opisat agenta».  
2. «Sformirovat plan» → (pri zhelanii) «Vypolnit plan» — dry-run.  
3. «Sformirovat fayly (preview)» — vidite tochnyy spisok artefaktov.  
4. Pri osoznannom reshenii vklyuchite zapis (`ESTER_AGENT_BUILDER_WRITE=1`, slot=A) i «Primenit fayly».  
5. Pri neobkhodimosti zadeystvuyte RuleHub-preset, chtoby unifitsirovat i zastrakhovat protseduru.

## Gde lezhit UI
- `docs/agent_builder.html` — staticheskaya panel (podobno drugim dokumentam v `docs/`) :contentReference[oaicite:3]{index=3}.  
- Skript: `static/admin_agent_builder.js`.  
- Obschiy JWT-khelper: `static/admin.js` (v proekte uzhe est) :contentReference[oaicite:4]{index=4}.

## Zemnoy abzats
Eto praktichnyy «pult» dlya Ester: vy formuliruete tsel — ona sobiraet opisanie, plan i prevyu faylov; dalee, pri yavnom razreshenii i pod prismotrom RuleHub, bezopasno primenyaet izmeneniya. Nichego lishnego: vse kontrakty prezhnie, a upravlenie — znakomymi knopkami.
  
c=a+b
