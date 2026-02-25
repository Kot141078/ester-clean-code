# Poyasneniya k presetu RuleHub

**Naznachenie**  
Printsipy “ne navredi” pri avtoprimenenii artefaktov, s prioritetom prevyu-rezhima. Upravlenie dvumya ENV-flagami: `ESTER_AGENT_BUILDER_AB` i `ESTER_AGENT_BUILDER_WRITE`.

**Potoki i posledstviya**  
- If the conditions are violated, the action is transferred to epreview_only=three, and a note is written in the profile.
- When executed, guarded_application is enabled, logs are marked as einfoyo.
- Telemetry hides fields with file content (minimizing leaks).

**Integratsiya s UI**  
The edoss/agent_builder.html screen uses the same handles as the RuleNov admin panel:
- chtenie/sokhranenie YAML cherez `/rulehub/config` (sm. `static/admin_rulehub.js`) :contentReference[oaicite:5]{index=5};
- state/switching through ё/rulen/article and ё/rulen/toggle (if desired) : contentReference: 6шЗФ0З.

**Zemnoy abzats**  
This is “strakhovka” dlya samoizmeneniy: polzovatelyu udobno, and Ester - v bezopasnosti. Snachala ideya i plan, potom prevyu, dalshe - zapis tolko pri yavnoy sanktsii.
  
c=a+b
