from application.use_cases.process_metrics import ProcessMetricsUseCase
from application.use_cases.prepare_prediction_dataset import (
    PreparePredictionDatasetUseCase,
)


def test_monitoring_response_can_be_prepared_for_prediction():
    """
    Verifica el flujo interno:

    Monitoring JSON
        -> ProcessMetricsUseCase
        -> DataFrame
        -> PreparePredictionDatasetUseCase
        -> Prediction contract v1
    """

    monitoring_response = {
        "metric": "node.cpu.utilization",
        "unit": "ratio",
        "aggregation": "mean_non_idle",
        "windowSeconds": 60,
        "dataStatus": "partial",
        "series": [
            {
                "resource": {
                    "type": "node",
                    "cluster": "fixture-lab",
                    "id": "fixture-node-01",
                },
                "labels": {},
                "origin": "simulated",
                "source": "fixture",
                "samples": [
                    {
                        "timestamp": "2026-09-21T15:00:00Z",
                        "value": 0.0,
                        "quality": "valid",
                    },
                    {
                        "timestamp": "2026-09-21T15:00:15Z",
                        "value": 0.42,
                        "quality": "valid",
                    },
                    {
                        "timestamp": "2026-09-21T15:00:30Z",
                        "value": None,
                        "quality": "missing",
                    },
                    {
                        "timestamp": "2026-09-21T15:00:45Z",
                        "value": None,
                        "quality": "non_finite",
                    },
                ],
            }
        ],
    }

    process_metrics = ProcessMetricsUseCase()
    prepare_prediction = PreparePredictionDatasetUseCase()

    dataframe = process_metrics.execute(monitoring_response)

    result = prepare_prediction.execute(dataframe)

    # Contrato general
    assert result["schemaVersion"] == "1.0"
    assert result["datasetId"].startswith("dataset-")

    # Recurso
    assert result["resource"] == {
        "type": "node",
        "cluster": "fixture-lab",
        "id": "fixture-node-01",
    }

    # Procedencia
    assert result["origins"] == ["simulated"]

    # Estado heredado de Monitoring
    assert result["dataStatus"] == "partial"

    # Solo deben llegar las dos muestras válidas.
    assert len(result["features"]) == 2

    first_sample = result["features"][0]
    second_sample = result["features"][1]

    # 0 ratio sigue siendo 0 %
    assert first_sample["cpu_utilization"] == 0.0

    # 0.42 ratio -> 42 %
    assert second_sample["cpu_utilization"] == 42.0

    # Vocabulario de Prediction
    assert first_sample["quality"] == "ok"
    assert second_sample["quality"] == "ok"

    # Procedencia conservada
    assert first_sample["origin"] == "simulated"
    assert second_sample["origin"] == "simulated"

    # Los registros missing y non_finite no deben llegar
    # artificialmente convertidos a cero.
    timestamps = [
        feature["timestamp"]
        for feature in result["features"]
    ]

    assert "2026-09-21T15:00:30Z" not in timestamps
    assert "2026-09-21T15:00:45Z" not in timestamps