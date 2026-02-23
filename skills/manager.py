import logging
from typing import Dict, Any, List
from .base import EsterSkill
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

logger = logging.getLogger("EsterSkillManager")

class SkillManager:
    """
    Tsentralnaya nervnaya sistema instrumentov.
    Khranit reestr navykov i marshrutiziruet prikazy.
    """
    def __init__(self):
        self._skills: Dict[str, EsterSkill] = {}

    def register_skill(self, skill: EsterSkill):
        """Dobavlyaet navyk v arsenal"""
        if skill.name in self._skills:
            logger.warning(f"Skill {skill.name} overwritten!")
        self._skills[skill.name] = skill
        logger.info(f"Skill registered: {skill.name}")

    def add_skill(self, name: str, func, tags=None, description: str = ""):
        """
        Sovmestimost s register_all.py: registriruem funktsiyu kak navyk.
        """
        tags = tags or []

        class _FuncSkill(EsterSkill):
            @property
            def name(self) -> str:
                return name

            @property
            def description(self) -> str:
                return description or "Skill"

            @property
            def parameters(self) -> Dict[str, str]:
                return {"tags": ",".join(tags)}

            def execute(self, **kwargs) -> Dict[str, Any]:
                return func(**kwargs)

        self.register_skill(_FuncSkill())

    def add(self, skill_obj: Dict[str, Any]):
        """
        Fallback format: {"name","func","tags","description"}.
        """
        if not isinstance(skill_obj, dict):
            return
        self.add_skill(
            name=skill_obj.get("name") or "unnamed",
            func=skill_obj.get("func"),
            tags=skill_obj.get("tags") or [],
            description=skill_obj.get("description") or "",
        )

    def get_skill(self, name: str) -> EsterSkill:
        return self._skills.get(name)

    def get_descriptions_for_prompt(self) -> str:
        """Generiruet tekst instrumentov dlya sistemnogo prompta"""
        lines = []
        for name, skill in self._skills.items():
            lines.append(f"- {name}: {skill.description}")
        return "\n".join(lines)

    def execute_skill(self, skill_name: str, **kwargs) -> Dict[str, Any]:
        """Bezopasnoe vypolnenie navyka"""
        skill = self._skills.get(skill_name)
        if not skill:
            return {"status": "error", "error": f"Skill '{skill_name}' not found."}
        
        try:
            return skill.execute(**kwargs)
        except Exception as e:
            logger.error(f"Error executing {skill_name}: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}