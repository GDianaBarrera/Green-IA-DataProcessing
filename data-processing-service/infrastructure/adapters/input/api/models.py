from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

from domain.monitoring_contract import Metric, Origin, Quality, Status, Resource


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    code: str
    requestId: str


class Period(BaseModel):
    start: datetime
    end: datetime


class MetricRecord(BaseModel):
    metric: Metric
    unit: str
    aggregation: str
    window_seconds: int | None
    resource_type: Literal["node"]
    cluster: str
    resource_id: str
    labels: dict[str, str]
    timestamp: datetime
    value: float | None
    quality: Quality
    origin: Origin
    source: str
    data_status: Status


class ProcessedHistory(BaseModel):
    schemaVersion: Literal["1.0"] = "1.0"
    metric: Metric
    unit: str
    aggregation: str
    windowSeconds: int | None
    period: Period
    stepSeconds: int
    dataStatus: Status
    recordCount: int
    records: list[MetricRecord]
    warnings: list[str]


class HistoricalRecord(BaseModel):
    log_id: str
    hardware_id: str
    timestamp: datetime
    cpu_utilization_pct: float | None
    ram_utilization_pct: float | None
    temperatura_celsius: float | None
    energia_watts: float | None
    origin: Literal["unknown"]
    source: Literal["supabase"]
    quality: dict[str, Literal["valid", "missing", "non_finite", "out_of_range"]]


class HistoricalPage(BaseModel):
    schemaVersion: Literal["1.0"]
    hardwareId: str
    period: Period
    units: dict[str, str]
    dataStatus: Status
    recordCount: int
    records: list[HistoricalRecord]
    nextCursor: str | None
    warnings: list[str]


class PredictionFeature(BaseModel):
    timestamp: datetime
    cpu_utilization: float = Field(ge=0, le=100)
    origin: Origin
    quality: Literal["ok"]


class PredictionDataset(BaseModel):
    schemaVersion: Literal["1.0"]
    contractStatus: Literal["provisional"]
    datasetId: str
    requestedPeriod: Period
    period: Period
    resource: Resource
    features: list[PredictionFeature]
    units: dict[str, str]
    origins: list[Origin]
    dataStatus: Status
    excludedSampleCount: int
    warnings: list[str]
