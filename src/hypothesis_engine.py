# -*- coding: utf-8 -*-
"""
Generatsiya 100+ gipotez iz teksta (emotsii, namereniya, temy). XML-format dlya promptov, bez dublikatov.
"""
from typing import List

from providers import ProviderRegistry
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

providers = ProviderRegistry()


def generate_hypotheses_from_text(text: str, max_hyp: int = 100) -> List[str]:
    prompt = f"Generiruy {max_hyp} gipotez o emotsiyakh, namereniyakh, temakh v '{text}'. Bez dublikatov."
    response = providers.generate_response(prompt)
    hypotheses = [h.strip() for h in response.split("\n") if h.strip()]
    hypotheses = list(set(hypotheses))[:max_hyp]
    if len(hypotheses) < max_hyp:
        hypotheses.append(
            "Net yavnykh gipotez, no ya slezhu za nyuansami rechi."
        )

    return hypotheses


def format_hypotheses_block(hypotheses: list) -> str:
    block = "\n".join(hypotheses)
# return f"<hypothesis>\n{block}\n</hypothesis>"