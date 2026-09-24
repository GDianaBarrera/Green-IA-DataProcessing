from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Query, Request

from application.use_cases.process_metrics import ProcessMetricsUseCase
from application.use_cases.prepare_prediction_dataset import PreparePredictionDatasetUseCase
from application.use_cases.read_historical_logs import ReadHistoricalLogsUseCase
from domain.errors import InvalidQuery, SourceNotConfigured
from domain.monitoring_contract import Metric
from infrastructure.adapters.input.monitoring_http_adapter import MonitoringHttpAdapter
from infrastructure.adapters.input.supabase_historical_logs_adapter import SupabaseHistoricalLogsAdapter
from infrastructure.adapters.input.api.models import HistoricalPage, PredictionDataset, ProcessedHistory, Problem

ERRORS = {status: {"description": description,
    "content": {"application/problem+json": {"schema": Problem.model_json_schema()}},
    "headers": {"X-Request-Id": {"schema": {"type": "string"}}},
} for status, description in {
    422: "Consulta inválida o límite excedido", 502: "Respuesta upstream inválida",
    503: "Fuente ausente, sin permisos o indisponible", 504: "Timeout de la fuente", 500: "Error interno",
}.items()}
router = APIRouter()
IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


def monitoring_data(request, metric, start, end, resource_type, cluster, resource_id, step_seconds):
    settings = request.app.state.settings
    adapter = MonitoringHttpAdapter(settings.monitoring_url, settings.timeout, request.state.request_id)
    payload = adapter.get_history(metric, start, end, resource_type, cluster, resource_id, step_seconds)
    return payload, ProcessMetricsUseCase().execute(payload)


@router.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "service": "data-processing-service", "project": "Green AI"}


@router.get("/metrics/history", response_model=ProcessedHistory, responses=ERRORS, tags=["Monitoring"])
def get_processed_metric_history(
    request: Request, metric: Metric, start: datetime, end: datetime,
    resource_type: Literal["node"] = Query("node", alias="resourceType"),
    cluster: str | None = Query(None, pattern=IDENTIFIER),
    resource_id: str | None = Query(None, alias="resourceId", pattern=IDENTIFIER),
    step_seconds: int = Query(15, alias="stepSeconds", ge=15, le=3600),
):
    """Histórico de Monitoring: zona explícita, segundos enteros, máximo 24h, sin imputación."""
    payload, frame = monitoring_data(request, metric, start, end, resource_type, cluster, resource_id, step_seconds)
    records = frame.astype(object).where(frame.notna(), None).to_dict(orient="records")
    status = payload["dataStatus"]
    if not records and status != "partial":
        status = "no_data"
    return {"schemaVersion": "1.0", "metric": payload["metric"], "unit": payload["unit"],
            "aggregation": payload["aggregation"], "windowSeconds": payload["windowSeconds"],
            "period": {"start": payload["start"], "end": payload["end"]},
            "stepSeconds": payload["stepSeconds"], "dataStatus": status,
            "recordCount": len(records), "records": records, "warnings": frame.attrs.get("warnings", [])}


@router.get("/historical-logs", response_model=HistoricalPage, responses=ERRORS, tags=["Supabase"])
def get_historical_logs(
    request: Request, start: datetime, end: datetime,
    hardware_id: str = Query(..., alias="hardwareId", min_length=1, max_length=20),
    limit: int = Query(100, ge=1, le=500), cursor: str | None = Query(None, max_length=2048),
):
    """Solo lectura de logs. Máximo 31 días; UTC conserva fracciones. Seguir nextCursor hasta página vacía.

    hardwareId es un filtro, no autorización por usuario. Publicar únicamente detrás del Gateway autorizado.
    """
    settings = request.app.state.settings
    if not settings.supabase_enabled:
        raise SourceNotConfigured("La lectura de Supabase no está configurada.")
    adapter = SupabaseHistoricalLogsAdapter(settings.supabase_url, settings.supabase_key,
        settings.supabase_token, settings.timeout, request.state.request_id)
    return ReadHistoricalLogsUseCase(adapter, settings.historical_page_size).execute(hardware_id, start, end, limit, cursor)


@router.get("/prediction/dataset", response_model=PredictionDataset, responses=ERRORS, tags=["Prediction (provisional)"])
def get_prediction_dataset(
    request: Request, start: datetime, end: datetime,
    cluster: str = Query(..., pattern=IDENTIFIER),
    resource_id: str = Query(..., alias="resourceId", pattern=IDENTIFIER),
    step_seconds: int = Query(15, alias="stepSeconds", ge=15, le=3600),
):
    """Prepara CPU (%) de un recurso desde Monitoring. Contrato provisional; no ejecuta inferencia.

    Se excluyen missing/non_finite; no se mezclan orígenes ni se imputan huecos.
    """
    _, frame = monitoring_data(request, "node.cpu.utilization", start, end, "node", cluster, resource_id, step_seconds)
    try:
        return PreparePredictionDatasetUseCase().execute(frame)
    except ValueError as exc:
        raise InvalidQuery(str(exc)) from exc
