
---

### `docs/Privacy_and_Stealth_Policy.md`
```markdown
# Politika privatnosti i stels-rezhima

## Printsipy
- **Minimizatsiya**: sobiraem i logiruem tolko to, chto nuzhno dlya raboty.  
- **Prozrachnost**: v UI/soobscheniyakh agent chestno nazyvaet sebya assistentom.  
- **Etichnyy obkhod**: uvazhenie `robots.txt`, trottling, zapret na arkhivy.

## Redaktsiya logov
- Vklyuchenie: `REDACT_ENABLE=1`  
- Maskiruyutsya: email, telefony, IP, UUID, tokeny, nomera kart.  
- `REDACT_KEEP_LAST_N` — khvost dlya korrelyatsii (po umolchaniyu `4`).

## Vneshniy obkhod (crawler)
- Limity: `OUTBOUND_MAX_RPS`, `OUTBOUND_BUDGET_PER_MIN`.  
- `CRAWLER_RESPECT_ROBOTS=1` — obyazatelnoe uvazhenie `robots.txt`.  
- `CRAWLER_DISALLOW_ARCHIVES=1` — zapret skachivaniya arkhivov/blobov.

## Soobscheniya/interfeysy
- V produktive zapreschena imitatsiya «zhivogo cheloveka».  
- V messendzherakh — «nizkiy profil»: informativnaya podpis, vnyatnyy opt-out.  
  (Tekhnicheskaya realizatsiya adapterov Telegram/WhatsApp — sleduyuschaya iteratsiya.)

> ZEMNOY ABZATs: My «tikho i delovo» vypolnyaem zadachi, ne kopim lishnego i ne vydaem chuzhoe.  
> c=a+b
