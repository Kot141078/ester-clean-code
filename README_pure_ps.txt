PURE PowerShell tools
- scripts/gen_owner_jwt_pure.ps1|.bat   — HS256 JWT generator bez Python/.NET HMACSHA256
- scripts/env_sanitize_pure.ps1|.bat    — .env sanitayzer bez Python
- tools/show_routes.ps1|.bat            — vyvesti soderzhimoe data\app\extra_routes.json

Rekomendovannyy poryadok:
1) tools\add_extra_routes_pure.bat
2) scripts\env_sanitize_pure.bat  → pravim .env po otchetu
3) scripts\gen_owner_jwt_pure.bat  → poluchit «khozyayskiy» token
4) py -3 app.py   (ili python app.py)

c=a+b
