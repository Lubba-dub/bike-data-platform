from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EvidencePayload:
    offersCount: int = 0
    reviewsCount: int = 0
    confidence: float = 0.0
    coverage: str = "low"


@dataclass
class RenderPayload:
    status: str = "empty"
    fillValue: float | None = None
    fillColor: str = "#d9dde3"
    strokeOpacity: float = 0.45


@dataclass
class EnginePartPayload:
    partKey: str
    displayName: str
    templateLabels: list[str] = field(default_factory=list)
    componentName: str | None = None
    brandHint: str | None = None
    sourceType: str = "missing"
    evidence: EvidencePayload = field(default_factory=EvidencePayload)
    metrics: dict[str, float | None] = field(default_factory=dict)
    render: RenderPayload = field(default_factory=RenderPayload)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = asdict(self.evidence)
        payload["render"] = asdict(self.render)
        return payload


@dataclass
class EngineBikePayload:
    schemaVersion: str
    bikeId: str
    bikeName: str
    brand: str
    bikeType: str
    templateType: str
    views: dict[str, str | None]
    availableModes: list[str]
    defaultMode: str
    parts: list[EnginePartPayload] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "bikeId": self.bikeId,
            "bikeName": self.bikeName,
            "brand": self.brand,
            "bikeType": self.bikeType,
            "templateType": self.templateType,
            "views": self.views,
            "availableModes": self.availableModes,
            "defaultMode": self.defaultMode,
            "parts": [part.to_dict() for part in self.parts],
            "summary": self.summary,
            "meta": self.meta,
        }
