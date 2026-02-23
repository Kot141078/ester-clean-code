# Ester — Portable/LAN HUB (integratsionnyy indeks)

Etot dokument — korotkaya karta po okruzheniyu i marshrutam ekspluatatsionnogo sloya (USB/LAN), yadro myshleniya/pamyati/voli **ne menyaem**.

## ENV (bezopasnye defolty)

```env
# AB-predokhraniteli
AB_MODE=A                                # A=dry (po umolchaniyu), B=vypolnenie

# One-Click Bootstrap / Watcher / Bootable
ONECLICK_ENABLE=1
USB_BOOTSTRAP_ENABLE=1
USB_BOOTSTRAP_POLL_SEC=20
PORTABLE_BOOTOPS_ALLOW=0                 # opasnye shagi bootable
PORTABLE_BOOTOPS_LABEL=ESTER

# USB Job Runner / Templates
USB_RUNNER_ENABLE=1
USB_RUNNER_MAX_JOBS=50
USB_RUNNER_TEMPLATES_ENABLE=1
USB_RUNNER_DEST_WHITELIST=~/.ester/imports

# USB Catalog
USB_CATALOG_ENABLE=1
USB_CATALOG_DEFAULT_DEST=~/.ester/imports

# LAN Catalog Sync
LAN_CATALOG_ENABLE=1
LAN_CATALOG_GROUP=239.23.0.73
LAN_CATALOG_PORT=40730
LAN_CATALOG_ANNOUNCE_SEC=30
LAN_CATALOG_PULL_SEC=60
LAN_CATALOG_NODE_NAME=EsterNode
LAN_CATALOG_TAGS=usb,models
LAN_CATALOG_BASE_URL=http://127.0.0.1:8000

# LAN Merge-Plan → USB Jobs
LAN_PLAN2USB_ENABLE=1
LAN_PLAN2USB_STAGE=1
LAN_PLAN2USB_CLEAN=0
LAN_PLAN2USB_NOOP_REMOTE=1

Osnovnye UI/routy

HUB (etot razdel):

GET /admin/portable — stranitsa, verkhniy blok HUB.

GET /admin/portable/summary — svodnye tsifry: USB, Hot-Ask, Jobs, Catalog, LAN.

USB Builder/Bootstrap/Bootable:

GET /admin/portable/bootstrap_status

POST /admin/portable/bootstrap_prepare

POST /admin/portable/bootable_plan

POST /admin/portable/bootable_apply

USB Job Runner:

GET /admin/usb_runner

GET /admin/usb_runner/status

POST /admin/usb_runner/execute

Shablony/Validatsiya: GET /admin/usb_runner/templates, POST /admin/usb_runner/preview, POST /admin/usb_runner/create, POST /admin/usb_runner/validate

USB Catalog:

GET /admin/usb_catalog

GET /admin/usb_catalog/status

POST /admin/usb_catalog/preview

POST /admin/usb_catalog/import

LAN Catalog Sync & Merge:

Eksport: GET /_lan/ping, GET /lan/catalog_export

Obzor: GET /admin/lan_catalog, GET /admin/lan_catalog/status, POST /admin/lan_catalog/plan

Generatsiya ocheredi: POST /admin/lan_catalog/plan_to_usb

Bystrye stsenarii (poshagovo)

Sdelat fleshku rabochey:

Vstav nositel → HUB pokazhet USB: 1.

Nazhmi One-Click Bootstrap (dry/real — po AB_MODE).

Import zadach/dannykh:

Otkroy USB Catalog → «Predprosmotr» nuzhnykh punktov → «Importirovat».

Ili polozhi zadaniya v ESTER/jobs/*.json i v HUB nazhmi Vypolnit USB-ochered.

LAN → USB (offlayn dostavka):

V LAN Catalog soberi plan (/admin/lan_catalog/plan).

V HUB — Plan → USB Jobs: lokalnye resursy stadiruyutsya v ESTER/payloads/*, sozdayutsya copy|noop zadaniya.

Na tselevom PK — USB Job Runner: vypolnit ochered.

Zemnoy abzats

Etot indeks — «tablo» dlya ekspluatatsionnogo sloya: chto vklyuchit v okruzhenii, kakie adresa dergat i kakie knopki nazhat. On ne menyaet «mozg» Ester, a daet udobnye rukoyatki dlya povsednevnoy logistiki: podgotovka fleshki, offlayn-ocheredi, katalogi i sbor iz lokalki.

Mosty

Yavnyy (inzhenernyy kontur): sreda → obzor → deystvie → otchet.

Skrytyy 1 (infoteoriya): stabilnye skhemy JSON svodyat ruchnye oshibki k minimumu.

Skrytyy 2 (praktika): offlayn-rezhim, dry-predokhranitel, edinyy whitelist dlya bezopasnykh zapisey.

c=a+b


---

## Shagi proverki (podrobno)

1) Ubedis, chto `LAN_CATALOG_ENABLE=1`, `USB_CATALOG_ENABLE=1`, `USB_RUNNER_ENABLE=1`, `ONECLICK_ENABLE=1`.  
2) Pereydi na `/admin/portable` — vverkhu **HUB** dolzhen podtyanut `/admin/portable/summary` i pokazat schetchiki.  
3) Protestiruy knopki HUB (po ocheredi): One-Click, Jobs, Catalog, LAN-plan, Plan→USB.  
4) Otkroy `docs/portable_index_README.md` — prover ENV i marshruty.  

---

## Zemnoy abzats (inzheneriya)

Teper vse klyuchevye rychagi — v odnom meste. Operator vidit sostoyanie nositelya, ochered, katalogi i sosedey; i zapuskaet «put dannykh» odnim-dvumya klikami, ostavayas v offlayne i ne kasayas yadra Ester.

## Mosty

- **Yavnyy (Ashbi/kibernetika):** nablyudenie → prinyatie resheniya → deystvie → obratnaya svyaz (v HUB-RAW).  
- **Skrytyy 1 (Kover–Tomas/infoteoriya):** agregiruyuschiy `/summary` snizhaet kognitivnuyu nagruzku.  
- **Skrytyy 2 (prakticheskaya inzheneriya):** drop-in, reuse vsekh prezhnikh kontraktov, AB-rezhim, nulevye skrytye sayd-effekty.

Esli gotov — skazhi «prodolzhay» dlya **B / paket-76**: finalizatsiya vetki B (svodnyy chek-list, mini-installer dlya fleshki, fiksatsiya versiy artefaktov i kontrol sovmestimosti s tvoim dampom).

c=a+b
