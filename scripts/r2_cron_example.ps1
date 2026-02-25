# P2/skripts/p2_cron_example.ps1 - example of a scheduler for Windows (Task Scheduler)
# Bridges: (Explicit) Enderton - triggered command; (Hidden) Ashby is a simple regulator; Carpet&Thomas - the magazine reduces uncertainty.
# Zemnoy abzats: demonstratsiya - dva shaga: trigger → otchet. Mozhno obernut v planirovschik.
# c=a+b

param(
  [string]$Config = "tests/fixtures/ingest_config.json"
)
python tools/r2_trigger.py --config $Config
python tools/r2_audit_report.py --out ingest_audit.md
