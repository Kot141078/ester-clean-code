from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class EsterSkill(ABC):
    """
    Bazovyy kontrakt dlya lyubogo navyka Ester.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unikalnoe imya navyka (naprimer, 'read_local_file')"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Opisanie dlya System Prompt"""
        pass

    @property
    def parameters(self) -> Dict[str, str]:
        """Opisanie argumentov (dlya JSON skhemy)"""
        return {}

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Logika vypolneniya."""
        pass