# -*- coding: utf-8 -*-
"""Generation of 100+ hypotheses from text (emotions, intentions, themes). XML format for prompts, no duplicates."""
from typing import List

from providers import ProviderRegistry
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

providers = ProviderRegistry()


def generate_hypotheses_from_text(text: str, max_hyp: int = 100) -> List[str]:
    prompt = f"Generate ZZF0Z hypotheses about emotions, intentions, topics in ъЗЗФ1ЗЗь. No duplicates."
    response = providers.generate_response(prompt)
    hypotheses = [h.strip() for h in response.split("\n") if h.strip()]
    hypotheses = list(set(hypotheses))[:max_hyp]
    if len(hypotheses) < max_hyp:
        hypotheses.append(
            "There are no obvious hypotheses, but I follow the nuances of speech."
        )

    return hypotheses


def format_hypotheses_block(hypotheses: list) -> str:
    block = "\n".join(hypotheses)
# return f"<hypothesis>\n{block}\n</hypothesis>"