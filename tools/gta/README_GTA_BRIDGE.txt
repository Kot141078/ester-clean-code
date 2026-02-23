Ester GTA V Copilot Bridge
==========================

Purpose
-------
Send GTA V single-player telemetry to Ester:
  POST http://127.0.0.1:8090/gta/ingest

Server endpoints
----------------
- GET  /gta/ping
- GET  /gta/status
- GET  /gta/last
- POST /gta/ingest
- POST /gta/advice
- GET  /gta/admin

Quick smoke (without game)
--------------------------
POST /gta/ingest with JSON:
{
  "ask": true,
  "state": {
    "wanted": 2,
    "hp": 90,
    "armor": 30,
    "in_vehicle": true,
    "vehicle": "Kuruma",
    "speed_kmh": 95,
    "zone": "Downtown"
  }
}

ScriptHookVDotNet mode
----------------------
1) Install ScriptHookV + ScriptHookVDotNet into your GTA V folder.
2) Copy EsterGtaBridge.cs to:
   <GTA>\scripts\EsterGtaBridge.cs
3) Start Ester backend (run_ester_fixed.py).
4) Start GTA V (single-player).

Notes
-----
- This is for single-player / local sandbox use.
- Do not use in competitive online modes that violate game ToS.
- Bridge is telemetry-only by default (no auto-control).
