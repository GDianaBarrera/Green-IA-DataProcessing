from fastapi import APIRouter

import os
from datetime import datetime

from fastapi import HTTPException, Query

from application.use_cases.process_metrics import ProcessMetricsUseCase
from infrastructure.adapters.input.monitoring_http_adapter import (
    MonitoringHttpAdapter,
)


router = APIRouter()


@router.get(
    "/health",
    tags=["Health"],
    summary="Verificar estado del servicio",
)
def health_check():
    """
    Comprueba que el Data Processing Service
    se encuentra disponible.
    """

    return {
        "status": "healthy",
        "service": "data-processing-service",
        "project": "Green AI",
    }

@router.get("/metrics/history")
def get_processed_metric_history(
    metric: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    resource_type: str | None = Query(None, alias="resourceType"),
    cluster: str | None = Query(None),
    resource_id: str | None = Query(None, alias="resourceId"),
    step_seconds: int | None = Query(None, alias="stepSeconds"),
):
    """
    Consulta métricas históricas desde Monitoring y las
    prepara mediante Data Processing.
    """

    monitoring_url = os.getenv(
        "MONITORING_BASE_URL",
        "http://localhost:8080",
    )

    timeout_seconds = float(
        os.getenv("REQUEST_TIMEOUT_SECONDS", "10")
    )

    adapter = MonitoringHttpAdapter(
        base_url=monitoring_url,
        timeout_seconds=timeout_seconds,
    )

    use_case = ProcessMetricsUseCase()

    try:
        monitoring_response = adapter.get_history(
            metric=metric,
            start=start,
            end=end,
            resource_type=resource_type,
            cluster=cluster,
            resource_id=resource_id,
            step_seconds=step_seconds,
        )

        dataframe = use_case.execute(
            monitoring_response
        )

        records = (
            dataframe
            .astype(object)
            .where(dataframe.notna(), None)
            .to_dict(orient="records")
        )

        return {
            "metric": metric,
            "dataStatus": monitoring_response.get(
                "dataStatus",
                "unknown",
            ),
            "recordCount": len(records),
            "records": records,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc