# Poyasneniya k presetu RuleHub

**Naznachenie**  
Printsipy «ne navredi» pri avtoprimenenii artefaktov, s prioritetom prevyu-rezhima. Upravlenie dvumya ENV-flagami: `ESTER_AGENT_BUILDER_AB` i `ESTER_AGENT_BUILDER_WRITE`.

**Potoki i posledstviya**  
- Pri narushenii usloviy — deystvie perevoditsya v `preview_only=true`, v profile pishetsya zametka.  
- Pri vypolnenii — `guarded_apply` razreshen, logi pomechayutsya kak `info`.  
- Telemetriya skryvaet polya s kontentom faylov (minimizatsiya utechek).

**Integratsiya s UI**  
Ekran `docs/agent_builder.html` ispolzuet te zhe ruchki, chto i adminka RuleHub:  
- chtenie/sokhranenie YAML cherez `/rulehub/config` (sm. `static/admin_rulehub.js`) :contentReference[oaicite:5]{index=5};  
- sostoyanie/pereklyuchenie cherez `/rulehub/state` i `/rulehub/toggle` (pri zhelanii) :contentReference[oaicite:6]{index=6}.  

**Zemnoy abzats**  
Eto «strakhovka» dlya samoizmeneniy: polzovatelyu udobno, a Ester — v bezopasnosti. Snachala ideya i plan, potom prevyu, dalshe — zapis tolko pri yavnoy sanktsii.
  
c=a+b
