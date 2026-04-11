@echo off
REM Ester, start s privyazkoy k obschemu DATA_DIR (<data-root>)

REM Mosty:
REM - Yavnyy: (Start batnik ↔ peremennye okruzheniya) — kod chitaet nuzhnyy katalog bez pravok konfigov.
REM - Skrytyy #1: (Planirovschik ↔ Mapping) — startuem tolko esli Z: uzhe na meste.
REM - Skrytyy #2: (Snapshoty ↔ Indeksatsiya) — katalogi snapshots/inbox na obschem diske dostupny vsem uzlam.

REM Zemnoy abzats:
REM Proveryaem «panel pitaniya»: est li disk Z:. Net — vykhodim, da — zapuskaem «dvigatel» (Ester).

set DATA_DIR=<data-root>
set PERSIST_DIR=<data-root>

if not exist "%DATA_DIR%\." (
  echo [Ester] DATA_DIR nedostupen: %DATA_DIR%
  exit /b 1
)

REM Primer: zapusk vashego skripta/virtualnogo okruzheniya
REM cd /d <repo-root>
REM call venv\Scripts\activate
REM python app.py
echo [Ester] ok: DATA_DIR=%DATA_DIR%
REM TODO: podstavte svoyu komandu starta, esli otlichaetsya

REM c=a+b


