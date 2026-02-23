Ester — Release Pack v1
-----------------------
Soderzhimoe:
- release/ — gotovaya k ustanovke sborka (zip mozhno razdat klientu)
- presets/ — YAML-presety pravil
- docs/PRICING.md — tseny/pakety
- static/pricing.json — tseny dlya lendinga
- landing/ — staticheskiy lending (GitHub Pages)
- scripts/make_release.sh — skript dlya sborki release/*.zip iz shablonov

Bystryy start (lokalno):
  1) Otkroy landing/index.html v brauzere (ili zadeploy na GitHub Pages).
  2) Raspakuy release/ na servere i zapusti: bash install_ester_pro.sh
  3) Zapolni sekrety v /opt/ester/secrets/.env i perezapusti docker compose.

Udachi!
