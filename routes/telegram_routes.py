# -*- coding: utf-8 -*-
# routes/telegram_routes.py
"""
Sovmestimost s dampom: «naslednyy» modul Telegram.

Zadacha:
  • Save importoputi i imena iz dampa, no fakticheski ispolzovat novuyu realizatsiyu.
  • Isklyuchit dubli endpointov i razlichiya povedeniya mezhdu polling/webhook.

Kak rabotaet:
  • R eeksportiruem Blueprint `bp` Re funktsiyu-registrator `register_telegram_webhook`
    iz novoy realizatsii `routes.telegram_webhook_routes`.
  • R' `routes/register_all.py` uzhe est zaschita: esli /tg/webhook zaregistrirovan — etot modul ne podklyuchaetsya vtoroy raz.

Zemnoy abzats (inzheneriya):
Eto «perekidnoy nozh»: staroe gnezdo ostaetsya na meste, no provod idet na novyy schit.
Net raskhozhdeniy, net kopipasty — odna tochka istiny.

Mosty:
- Yavnyy (Kibernetika v†" Arkhitektura): edinyy kontur upravleniya Telegram pri sokhranenii vneshnego interfeysa.
- Skrytyy 1 (Infoteoriya v†" Interfeysy): ustranyaem dublirovanie koda — menshe entropii.
- Skrytyy 2 (Anatomiya v†" PO): kak smena neyronnoy tsepi pri sokhranenii funktsii — povedenie to zhe, struktura luchshe.

"""
from __future__ import annotations

# Reeksport novoy realizatsii pod «starym» imenem.
from routes.telegram_webhook_routes import bp, register as register_telegram_webhook  # type: ignore

# Sovmestimye imena dlya raznykh starykh importov.
telegram_bp = bp  # type: ignore

def register(app):
    return register_telegram_webhook(app)

__all__ = ["bp", "telegram_bp", "register", "register_telegram_webhook"]
