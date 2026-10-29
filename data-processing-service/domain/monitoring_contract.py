from datetime import datetime
from typing import Literal
import math

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from domain.validation import utc
from domain.errors import InvalidResponse

Metric = Literal["node.cpu.utilization", "node.memory.used", "node.network.receive", "node.network.transmit", "node.filesystem.used"]
Origin = Literal["observed", "simulated", "estimated", "unknown"]
Status = Literal["complete", "partial", "no_data"]
Quality = Literal["valid", "missing", "non_finite"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Resource(Contract):
    type: Literal["node"]
    cluster: str
    id: str


class Sample(Contract):
    timestamp: datetime
    value: float | None = Field(strict=True)
    quality: Quality

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_time(cls, value):
        if not isinstance(value, (str, datetime)):
            raise ValueError("timestamp debe ser RFC3339")
        return value

    @field_validator("timestamp")
    @classmethod
    def zoned_time(cls, value):
        return utc(value)

    @model_validator(mode="after")
    def quality_matches(self):
        if self.quality == "valid":
            if self.value is None or not math.isfinite(self.value):
                raise ValueError("valid requiere un número finito")
        elif self.value is not None:
            raise ValueError("missing/non_finite requieren null")
        return self


class Series(Contract):
    resource: Resource
    labels: dict[str, str]
    source: Literal["fixture", "prometheus"]
    origin: Origin
    samples: list[Sample] = Field(min_length=1, max_length=5761)


class MetricsPayload(Contract):
    metric: Metric
    unit: Literal["ratio", "bytes", "bytes/s"]
    aggregation: Literal["instant", "rate", "mean_non_idle"]
    windowSeconds: Literal[60] | None
    dataStatus: Status
    series: list[Series] = Field(max_length=100)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def semantics(self):
        expected = ("ratio", "mean_non_idle", 60) if self.metric == "node.cpu.utilization" else (
            ("bytes/s", "rate", 60) if self.metric.startswith("node.network.") else ("bytes", "instant", None)
        )
        if (self.unit, self.aggregation, self.windowSeconds) != expected:
            raise ValueError("Unidad o agregación incompatible con la métrica")
        if sum(len(s.samples) for s in self.series) > 10000:
            raise ValueError("Más de 10000 muestras")
        if self.dataStatus == "no_data" and self.series:
            raise ValueError("no_data no puede contener series")
        return self


class MonitoringResponse(MetricsPayload):
    start: datetime
    end: datetime
    stepSeconds: int = Field(strict=True, ge=15, le=3600)
    warnings: list[str]

    @field_validator("start", "end")
    @classmethod
    def zoned_time(cls, value):
        return utc(value, True)

    @model_validator(mode="after")
    def bounds(self):
        if self.start >= self.end:
            raise ValueError("Periodo inválido")
        for series in self.series:
            for sample in series.samples:
                if not self.start <= sample.timestamp <= self.end:
                    raise ValueError("Muestra fuera del periodo")
        return self


def validate_payload(data, *, envelope=False):
    try:
        model = MonitoringResponse if envelope else MetricsPayload
        if not envelope and isinstance(data, dict):
            data = {k: v for k, v in data.items() if k not in ("start", "end", "stepSeconds")}
        return model.model_validate(data)
    except (ValueError, TypeError) as exc:
        raise InvalidResponse("Monitoring devolvió un contrato inválido.") from exc
