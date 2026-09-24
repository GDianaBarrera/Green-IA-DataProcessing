from __future__ import annotations

from typing import Any
from uuid import uuid4

import pandas as pd
import math
import json


class PreparePredictionDatasetUseCase:
    """
    Construye el contrato JSON v1 que Data Processing entrega
    a Prediction a partir de métricas de CPU procesadas.

    Reglas:
    - Prediction recibe cpu_utilization en porcentaje.
    - Monitoring entrega node.cpu.utilization como ratio.
    - Un valor válido de 0 debe conservarse como 0.
    - missing y non_finite no se convierten en cero.
    - Se conserva la procedencia de los datos.
    - No se inventan features opcionales que no estén disponibles.
    """

    SCHEMA_VERSION = "1.0"

    def execute(self, dataframe: pd.DataFrame) -> dict[str, Any]:
        if dataframe.empty:
            raise ValueError(
                "No se puede preparar un dataset de Prediction sin datos."
            )

        required_columns = {
            "metric",
            "resource_type",
            "cluster",
            "resource_id",
            "timestamp",
            "value",
            "quality",
            "origin",
            "data_status",
        }

        missing_columns = required_columns.difference(dataframe.columns)

        if missing_columns:
            raise ValueError(
                "Faltan columnas requeridas para preparar Prediction: "
                + ", ".join(sorted(missing_columns))
            )

        cpu_data = dataframe[
            dataframe["metric"] == "node.cpu.utilization"
        ].copy()

        if "unit" in cpu_data and not cpu_data["unit"].eq("ratio").all():
            raise ValueError("CPU de Monitoring debe tener unidad ratio.")
        if "labels" in cpu_data and cpu_data["labels"].map(lambda v: json.dumps(v, sort_keys=True)).nunique() > 1:
            raise ValueError("Prediction requiere una única serie de CPU.")
        if cpu_data["origin"].nunique(dropna=False) != 1:
            raise ValueError("No se pueden mezclar procedencias en Prediction.")

        if cpu_data.empty:
            raise ValueError(
                "El dataset no contiene la métrica node.cpu.utilization."
            )

        resources = cpu_data[
            ["resource_type", "cluster", "resource_id"]
        ].drop_duplicates()

        if len(resources) != 1:
            raise ValueError(
                "El dataset de Prediction debe corresponder a un único recurso."
            )

        resource_row = resources.iloc[0]

        cpu_data = cpu_data.sort_values("timestamp")
        if cpu_data["timestamp"].duplicated().any():
            raise ValueError("Prediction no admite timestamps duplicados.")

        features: list[dict[str, Any]] = []

        for _, row in cpu_data.iterrows():
            prediction_quality = self._map_quality(row["quality"])

            # Los registros no utilizables no deben transformarse
            # artificialmente en cero.
            if prediction_quality is None:
                continue

            value = row["value"]

            if pd.isna(value):
                continue

            cpu_percentage = float(value) * 100.0
            if not math.isfinite(cpu_percentage) or not 0 <= cpu_percentage <= 100:
                raise ValueError("CPU fuera del rango de ratio [0, 1].")

            features.append(
                {
                    "timestamp": self._to_rfc3339(row["timestamp"]),
                    "cpu_utilization": cpu_percentage,
                    "origin": row["origin"],
                    "quality": prediction_quality,
                }
            )

        if not features:
            raise ValueError(
                "No existen muestras de CPU válidas para Prediction."
            )

        origins = sorted(
            {
                feature["origin"]
                for feature in features
                if feature["origin"] is not None
            }
        )

        data_status_values = (
            cpu_data["data_status"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        data_status = (
            data_status_values[0]
            if len(data_status_values) == 1
            else "partial"
        )

        excluded = len(cpu_data) - len(features)
        warnings = list(dataframe.attrs.get("warnings", []))
        if excluded:
            warnings.append(f"Se excluyeron {excluded} muestras no utilizables; no se imputaron huecos.")
            data_status = "partial"
        return {
            "schemaVersion": self.SCHEMA_VERSION,
            "contractStatus": "provisional",
            "requestedPeriod": dataframe.attrs.get("requestedPeriod") or {
                "start": self._to_rfc3339(cpu_data.iloc[0]["timestamp"]),
                "end": self._to_rfc3339(cpu_data.iloc[-1]["timestamp"]),
            },
            "units": {"cpu_utilization": "%"},
            "excludedSampleCount": excluded,
            "datasetId": f"dataset-{uuid4()}",
            "period": {
                "start": features[0]["timestamp"],
                "end": features[-1]["timestamp"],
            },
            "resource": {
                "type": resource_row["resource_type"],
                "cluster": resource_row["cluster"],
                "id": resource_row["resource_id"],
            },
            "features": features,
            "origins": origins,
            "dataStatus": data_status,
            "warnings": warnings,
        }

    @staticmethod
    def _map_quality(quality: Any) -> str | None:
        """
        Traduce la calidad de Monitoring al vocabulario aceptado
        actualmente por Prediction.

        Solo las muestras válidas son utilizables para inferencia.
        Las muestras missing/non_finite se excluyen sin imputarlas.
        """
        mapping = {
            "valid": "ok",
        }

        return mapping.get(str(quality))

    @staticmethod
    def _to_rfc3339(timestamp: Any) -> str:
        parsed = pd.Timestamp(timestamp)

        if parsed.tzinfo is None:
            parsed = parsed.tz_localize("UTC")
        else:
            parsed = parsed.tz_convert("UTC")

        return parsed.isoformat().replace("+00:00", "Z")
