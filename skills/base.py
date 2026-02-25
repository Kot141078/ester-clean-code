from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class EsterSkill(ABC):
    """Basic contract for any Esther skill."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unikalnoe imya navyka (naprimer, 'read_local_file')"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description for System Prompt"""
        pass

    @property
    def parameters(self) -> Dict[str, str]:
        """Description of the arguments (for the JSCN scheme)"""
        return {}

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Logika vypolneniya."""
        pass