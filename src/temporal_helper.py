# -*- coding: utf-8 -*-
"""
Temporal Helper for Ester: rabota s vremenem, datami.
Rasshiren: dobavil tekuschuyu datu, timezone.
"""
from datetime import datetime
from typing import Dict

import pytz
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def get_system_datetime(tz_name: str = "UTC") -> Dict[str, str]:
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "tz": tz.zone,
    }
