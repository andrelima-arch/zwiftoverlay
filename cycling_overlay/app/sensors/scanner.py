import logging
from dataclasses import dataclass

from app.sensors.compatibility import (
    detect_compatibility,
)

logger = logging.getLogger(__name__)


@dataclass
class ScannedDevice:
    address: str
    name: str
    services: list[str]
    service_type: str = ""
    compatibility_hint: str = ""
    compatibility_profile: str = ""

    @property
    def display_name(self) -> str:
        if self.name:
            return f"{self.name} ({self.address})"
        return self.address

    def detect_service_type(self) -> str:
        if self.service_type:
            return self.service_type
        match = detect_compatibility(self.name, self.services)
        self.compatibility_hint = self.compatibility_hint or match.hint
        self.compatibility_profile = self.compatibility_profile or match.profile
        return match.service_type


SERVICE_LABELS = {
    "hr": "Frequência Cardíaca",
    "power": "Potência",
    "csc": "Cadência",
    "ftms": "Rolo inteligente (FTMS)",
    "unknown": "Desconhecido",
}
