from datetime import datetime
from typing import Any

import httpx

from domain.errors import InvalidQuery, InvalidResponse, ServiceError, SourceTimeout
from domain.monitoring_contract import validate_payload
from domain.ports.metrics_source import MetricsSource
from domain.validation import interval, timestamp
from infrastructure.settings import validate_timeout, validate_url


class MonitoringHttpAdapter(MetricsSource):
    def __init__(self, base_url: str, timeout_seconds: float = 10.0, request_id: str | None = None):
        self.base_url = validate_url(base_url)
        self.timeout_seconds = validate_timeout(timeout_seconds)
        self.request_id = request_id

    def get_history(self, metric: str, start: datetime, end: datetime,
                    resource_type: str | None = None, cluster: str | None = None,
                    resource_id: str | None = None, step_seconds: int | None = None) -> dict[str, Any]:
        start, end = interval(start, end, monitoring=True)
        step = 15 if step_seconds is None else step_seconds
        if isinstance(step, bool) or not isinstance(step, int) or not 15 <= step <= 3600:
            raise InvalidQuery("stepSeconds debe estar entre 15 y 3600.")
        params = {"metric": metric, "start": timestamp(start), "end": timestamp(end), "stepSeconds": step}
        for name, value in (("resourceType", resource_type), ("cluster", cluster), ("resourceId", resource_id)):
            if value is not None:
                params[name] = value
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                kwargs = {"params": params}
                if self.request_id:
                    kwargs["headers"] = {"X-Request-Id": self.request_id}
                response = client.get(f"{self.base_url}/api/v1/metrics/history", **kwargs)
                response.raise_for_status()
                try:
                    data = response.json()
                except ValueError as exc:
                    raise InvalidResponse("Monitoring devolvió JSON inválido.") from exc
                parsed = validate_payload(data, envelope=True)
                if (parsed.metric != metric or parsed.start != start or parsed.end != end
                        or parsed.stepSeconds != step):
                    raise InvalidResponse("Monitoring devolvió un periodo o métrica diferente al solicitado.")
                for series in parsed.series:
                    if ((resource_type and series.resource.type != resource_type)
                            or (cluster and series.resource.cluster != cluster)
                            or (resource_id and series.resource.id != resource_id)):
                        raise InvalidResponse("Monitoring devolvió recursos fuera de los filtros.")
                return parsed.model_dump(mode="json")
        except httpx.TimeoutException as exc:
            raise SourceTimeout("Monitoring no respondió a tiempo.") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (400, 422):
                raise InvalidQuery(f"Monitoring rechazó la consulta ({status}). Revise filtros, rango y paso; reduzca series o aumente stepSeconds.") from exc
            if status == 502:
                raise InvalidResponse("Monitoring recibió una respuesta inválida de su fuente (502).") from exc
            if status == 504:
                raise SourceTimeout("La fuente de Monitoring excedió el tiempo permitido (504).") from exc
            raise ServiceError(f"Monitoring no está disponible ({status}).") from exc
        except httpx.RequestError as exc:
            raise ServiceError("No fue posible comunicarse con Monitoring.") from exc
