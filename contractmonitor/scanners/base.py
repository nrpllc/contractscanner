from abc import ABC, abstractmethod

from contractmonitor.config import Config
from contractmonitor.models import Contract


class BaseScanner(ABC):
    """Base class for all contract source scanners."""

    name: str = "base"

    def __init__(self, config: Config):
        self.config = config

    @abstractmethod
    async def scan(self) -> list[Contract]:
        """Scan the source and return NYPD-related contracts."""
        ...

    def is_nypd(self, text: str) -> bool:
        """Check if text references NYPD."""
        text_upper = text.upper()
        for kw in self.config.agency_keywords:
            if kw.upper() in text_upper:
                return True
        return False
