# -*- coding: utf-8 -*-
from __future__ import annotations

"""celery_shim.py — minimalnaya zamena Celery, chtoby project ne padal bez zavisimosti.

This is NE Celery. This is “perekhodnik”, chtoby:
- `from celery import Celery, shared_task` ne lomal zapusk utilit
- funktsii mogli vyzyvatsya sinkhronno cherez `.delay()` (na samom dele prosto vyzov)

Esli tebe realno nuzhna ochered/vorkery - stav celery+redis i ispolzuy nastoyaschiy Celery.

Mosty:
- Yavnyy: otsutstvie vneshney zavisimosti → stabilnyy import i zapusk utilit.
- Skrytye:
  1) Inzheneriya ↔ ekspluatatsiya: degradatsiya vmesto krakha pri nedostupnom servise (redis/celery).
  2) Kibernetika ↔ kontrol: v shim net “magii raspredeleniya”, tolko yavnye vyzovy - menshe skrytykh effektov.

ZEMNOY ABZATs: v kontse fayla."""

from dataclasses import dataclass
from typing import Any, Callable, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@dataclass
class _AsyncCall:
    fn: Callable[..., Any]

    def delay(self, *args: Any, **kwargs: Any) -> Any:
        return self.fn(*args, **kwargs)

    def apply_async(self, args: Optional[tuple] = None, kwargs: Optional[dict] = None, **_opt: Any) -> Any:
        return self.fn(*(args or ()), **(kwargs or {}))


def shared_task(fn: Callable[..., Any]) -> _AsyncCall:
    return _AsyncCall(fn=fn)


class Celery:
    def __init__(self, name: str, broker: str = "", backend: str = "", **_kw: Any) -> None:
        self.name = name
        self.broker = broker
        self.backend = backend

    def task(self, fn: Callable[..., Any]) -> _AsyncCall:
        return shared_task(fn)


ZEMNOY = """ZEMNOY ABZATs (anatomiya/inzheneriya):
Shim - eto kak ruchnoy domkrat vmesto podemnika v servise.
Podemnik (Celery+Redis) kruche, no esli ego net - domkrat vse ravno pozvolit pomenyat koleso i uekhat."""