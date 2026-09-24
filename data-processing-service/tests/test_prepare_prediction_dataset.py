import pandas as pd
import pytest

from application.use_cases.prepare_prediction_dataset import (
    PreparePredictionDatasetUseCase,
)


def build_cpu_dataframe() -> pd.DataFrame:
    """
    Fixture que representa datos ya procesados provenientes
    del Monitoring Service.
    """
    return pd.DataFrame(
        [
            {
                "metric": "node.cpu.utilization",
                "resource_type": "node",
                "cluster": "fixture-lab",
                "resource_id": "fixture-node-01",
                "timestamp": "2026-09-21T15:00:00Z",
                "value": 0.0,
                "quality": "valid",
                "origin": "simulated",
                "data_status": "partial",
            },
            {
                "metric": "node.cpu.utilization",
                "resource_type": "node",
                "cluster": "fixture-lab",
                "resource_id": "fixture-node-01",
                "timestamp": "2026-09-21T15:00:15Z",
                "value": 0.412,
                "quality": "valid",
                "origin": "simulated",
                "data_status": "partial",
            },
            {
                "metric": "node.cpu.utilization",
                "resource_type": "node",
                "cluster": "fixture-lab",
                "resource_id": "fixture-node-01",
                "timestamp": "2026-09-21T15:00:30Z",
                "value": None,
                "quality": "missing",
                "origin": "simulated",
                "data_status": "partial",
            },
            {
                "metric": "node.cpu.utilization",
                "resource_type": "node",
                "cluster": "fixture-lab",
                "resource_id": "fixture-node-01",
                "timestamp": "2026-09-21T15:00:45Z",
                "value": None,
                "quality": "non_finite",
                "origin": "simulated",
                "data_status": "partial",
            },
        ]
    )


def test_prepare_prediction_dataset_builds_contract_v1():
    use_case = PreparePredictionDatasetUseCase()

    result = use_case.execute(build_cpu_dataframe())

    assert result["schemaVersion"] == "1.0"
    assert result["datasetId"].startswith("dataset-")

    assert result["resource"] == {
        "type": "node",
        "cluster": "fixture-lab",
        "id": "fixture-node-01",
    }

    assert result["origins"] == ["simulated"]
    assert result["dataStatus"] == "partial"

    assert result["period"]["start"] == "2026-09-21T15:00:00Z"
    assert result["period"]["end"] == "2026-09-21T15:00:15Z"


def test_prepare_prediction_dataset_converts_cpu_ratio_to_percentage():
    use_case = PreparePredictionDatasetUseCase()

    result = use_case.execute(build_cpu_dataframe())

    features = result["features"]

    assert len(features) == 2

    # Un cero válido debe continuar siendo cero.
    assert features[0]["cpu_utilization"] == 0.0

    # Monitoring: 0.412 ratio -> Prediction: 41.2 %
    assert features[1]["cpu_utilization"] == pytest.approx(41.2)


def test_prepare_prediction_dataset_does_not_impute_missing_as_zero():
    use_case = PreparePredictionDatasetUseCase()

    result = use_case.execute(build_cpu_dataframe())

    features = result["features"]

    timestamps = [feature["timestamp"] for feature in features]

    # Las muestras missing/non_finite no deben llegar al modelo
    # convertidas artificialmente en cero.
    assert "2026-09-21T15:00:30Z" not in timestamps
    assert "2026-09-21T15:00:45Z" not in timestamps

    # El cero real sí debe conservarse.
    assert features[0]["cpu_utilization"] == 0.0


def test_prepare_prediction_dataset_maps_valid_quality_to_ok():
    use_case = PreparePredictionDatasetUseCase()

    result = use_case.execute(build_cpu_dataframe())

    assert all(
        feature["quality"] == "ok"
        for feature in result["features"]
    )


def test_prepare_prediction_dataset_rejects_multiple_resources():
    dataframe = build_cpu_dataframe()

    dataframe.loc[1, "resource_id"] = "fixture-node-02"

    use_case = PreparePredictionDatasetUseCase()

    with pytest.raises(
        ValueError,
        match="único recurso",
    ):
        use_case.execute(dataframe)


def test_prepare_prediction_dataset_rejects_empty_dataframe():
    use_case = PreparePredictionDatasetUseCase()

    with pytest.raises(
        ValueError,
        match="sin datos",
    ):
        use_case.execute(pd.DataFrame())