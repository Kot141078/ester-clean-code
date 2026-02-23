# R2/scripts/r2_cron_example.ps1 — primer planirovschika dlya Windows (Task Scheduler)
# Mosty: (Yavnyy) Enderton — zapuskaemaya komanda; (Skrytye) Ashbi — prostoy regulyator; Cover&Thomas — zhurnal snizhaet neopredelennost.
# Zemnoy abzats: demonstratsiya — dva shaga: trigger → otchet. Mozhno obernut v planirovschik.
# c=a+b

param(
  [string]$Config = "tests/fixtures/ingest_config.json"
)
python tools/r2_trigger.py --config $Config
python tools/r2_audit_report.py --out ingest_audit.md
