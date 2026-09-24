from datetime import datetime
from typing import Any

import httpx
from domain.ports.metrics_source import MetricsSource


class MonitoringHttpAdapter(MetricsSource):
    """
    Adaptador HTTP para consultar métricas históricas
    del Green AI Monitoring Service.

    Su responsabilidad es únicamente la comunicación HTTP.
    No limpia, imputa ni transforma las métricas recibidas.
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_history(
        self,
        metric: str,
        start: datetime,
        end: datetime,
        resource_type: str | None = None,
        cluster: str | None = None,
        resource_id: str | None = None,
        step_seconds: int | None = None,
    ) -> dict[str, Any]:

        url = f"{self.base_url}/api/v1/metrics/history"

        params: dict[str, str | int] = {
            "metric": metric,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

        if resource_type is not None:
            params["resourceType"] = resource_type

        if cluster is not None:
            params["cluster"] = cluster

        if resource_id is not None:
            params["resourceId"] = resource_id

        if step_seconds is not None:
            params["stepSeconds"] = step_seconds

        try:
            with httpx.Client(
                timeout=self.timeout_seconds
            ) as client:
                response = client.get(
                    url,
                    params=params,
                )

                response.raise_for_status()

                data = response.json()

                if not isinstance(data, dict):
                    raise RuntimeError(
                        "Monitoring devolvió una respuesta JSON inválida."
                    )

                return data

        except httpx.TimeoutException as exc:
            raise RuntimeError(
                "Monitoring no respondió dentro del tiempo establecido."
            ) from exc

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code

            if status in (400, 422):
                raise ValueError(
                    f"Consulta inválida enviada a Monitoring ({status}): "
                    f"{exc.response.text}"
                ) from exc

            if status in (502, 503, 504):
                raise RuntimeError(
                    f"Monitoring o su fuente de métricas no está disponible "
                    f"({status}): {exc.response.text}"
                ) from exc

            raise RuntimeError(
                f"Monitoring respondió con error HTTP {status}: "
                f"{exc.response.text}"
            ) from exc

        except httpx.RequestError as exc:
            raise RuntimeError(
                "No fue posible establecer comunicación con Monitoring."
            ) from exc