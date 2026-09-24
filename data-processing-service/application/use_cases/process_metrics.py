from typing import Any

import pandas as pd


class ProcessMetricsUseCase:
    """
    Transforma la respuesta histórica del Monitoring Service
    en una estructura tabular preparada para procesamiento posterior.

    Reglas importantes:
    - Un valor 0 válido debe conservarse como 0.
    - Los valores missing y non_finite permanecen ausentes.
    - Se conserva la identidad de cada serie mediante sus labels.
    - Se conserva la procedencia de los datos.
    """

    def execute(self, monitoring_response: dict[str, Any]) -> pd.DataFrame:
        metric = monitoring_response.get("metric")
        unit = monitoring_response.get("unit")
        aggregation = monitoring_response.get("aggregation")
        window_seconds = monitoring_response.get("windowSeconds")
        data_status = monitoring_response.get("dataStatus", "unknown")

        series = monitoring_response.get("series", [])
        rows: list[dict[str, Any]] = []

        for metric_series in series:
            resource = metric_series.get("resource", {})
            labels = metric_series.get("labels", {})
            samples = metric_series.get("samples", [])

            for sample in samples:
                row = {
                    "metric": metric,
                    "unit": unit,
                    "aggregation": aggregation,
                    "window_seconds": window_seconds,

                    "resource_type": resource.get("type"),
                    "cluster": resource.get("cluster"),
                    "resource_id": resource.get("id"),

                    "labels": labels,

                    "timestamp": sample.get("timestamp"),
                    "value": sample.get("value"),
                    "quality": sample.get("quality"),

                    "origin": metric_series.get("origin"),
                    "source": metric_series.get("source"),
                    "data_status": data_status,
                }

                rows.append(row)

        dataframe = pd.DataFrame(rows)

        if dataframe.empty:
            return dataframe

        dataframe["timestamp"] = pd.to_datetime(
            dataframe["timestamp"],
            utc=True,
            errors="coerce",
        )

        return dataframe