import pandas as pd

from application.use_cases.process_metrics import (
    ProcessMetricsUseCase,
)


def test_process_metrics_preserves_quality_and_series_identity():

    monitoring_response = {
        "metric": "node.filesystem.used",
        "unit": "bytes",
        "aggregation": "instant",
        "windowSeconds": None,
        "dataStatus": "partial",
        "series": [
            {
                "resource": {
                    "type": "node",
                    "cluster": "fixture-lab",
                    "id": "fixture-node-01",
                },
                "labels": {
                    "device": "/dev/fixture-a",
                    "mountpoint": "/",
                    "fstype": "ext4",
                },
                "origin": "simulated",
                "source": "fixture",
                "samples": [
                    {
                        "timestamp": "2026-09-21T15:00:00Z",
                        "value": 0,
                        "quality": "valid",
                    },
                    {
                        "timestamp": "2026-09-21T15:00:15Z",
                        "value": None,
                        "quality": "missing",
                    },
                    {
                        "timestamp": "2026-09-21T15:00:30Z",
                        "value": None,
                        "quality": "non_finite",
                    },
                ],
            }
        ],
    }

    use_case = ProcessMetricsUseCase()

    dataframe = use_case.execute(
        monitoring_response
    )

    assert len(dataframe) == 3

    # Contrato de la métrica
    assert dataframe.iloc[0]["metric"] == "node.filesystem.used"
    assert dataframe.iloc[0]["unit"] == "bytes"
    assert dataframe.iloc[0]["aggregation"] == "instant"
    assert pd.isna(dataframe.iloc[0]["window_seconds"])

    # Identidad del recurso
    assert dataframe.iloc[0]["resource_type"] == "node"
    assert dataframe.iloc[0]["cluster"] == "fixture-lab"
    assert dataframe.iloc[0]["resource_id"] == "fixture-node-01"

    # Identidad de la serie
    assert dataframe.iloc[0]["labels"] == {
        "device": "/dev/fixture-a",
        "mountpoint": "/",
        "fstype": "ext4",
    }

    # Cero real: debe seguir siendo cero
    assert dataframe.iloc[0]["value"] == 0
    assert dataframe.iloc[0]["quality"] == "valid"

    # Ausencia: NO debe transformarse en cero
    assert dataframe.iloc[1]["quality"] == "missing"
    assert pd.isna(dataframe.iloc[1]["value"])

    # Valor no finito: tampoco debe transformarse en cero
    assert dataframe.iloc[2]["quality"] == "non_finite"
    assert pd.isna(dataframe.iloc[2]["value"])

    # Procedencia
    assert dataframe.iloc[0]["origin"] == "simulated"
    assert dataframe.iloc[0]["source"] == "fixture"
    assert dataframe.iloc[0]["data_status"] == "partial"

    # Timestamp normalizado en UTC
    assert str(dataframe.iloc[0]["timestamp"]) == (
        "2026-09-21 15:00:00+00:00"
    )


def test_process_metrics_keeps_different_series_separated():

    monitoring_response = {
        "metric": "node.filesystem.used",
        "unit": "bytes",
        "aggregation": "instant",
        "windowSeconds": None,
        "dataStatus": "complete",
        "series": [
            {
                "resource": {
                    "type": "node",
                    "cluster": "fixture-lab",
                    "id": "fixture-node-01",
                },
                "labels": {
                    "device": "/dev/fixture-a",
                    "mountpoint": "/",
                    "fstype": "ext4",
                },
                "origin": "simulated",
                "source": "fixture",
                "samples": [
                    {
                        "timestamp": "2026-09-21T15:00:00Z",
                        "value": 100,
                        "quality": "valid",
                    }
                ],
            },
            {
                "resource": {
                    "type": "node",
                    "cluster": "fixture-lab",
                    "id": "fixture-node-01",
                },
                "labels": {
                    "device": "/dev/fixture-b",
                    "mountpoint": "/data",
                    "fstype": "xfs",
                },
                "origin": "simulated",
                "source": "fixture",
                "samples": [
                    {
                        "timestamp": "2026-09-21T15:00:00Z",
                        "value": 200,
                        "quality": "valid",
                    }
                ],
            },
        ],
    }

    use_case = ProcessMetricsUseCase()

    dataframe = use_case.execute(
        monitoring_response
    )

    assert len(dataframe) == 2

    first_labels = dataframe.iloc[0]["labels"]
    second_labels = dataframe.iloc[1]["labels"]

    assert first_labels["device"] == "/dev/fixture-a"
    assert first_labels["mountpoint"] == "/"
    assert first_labels["fstype"] == "ext4"

    assert second_labels["device"] == "/dev/fixture-b"
    assert second_labels["mountpoint"] == "/data"
    assert second_labels["fstype"] == "xfs"

    assert first_labels != second_labels


def test_process_metrics_handles_no_data_without_error():

    monitoring_response = {
        "metric": "node.filesystem.used",
        "unit": "bytes",
        "dataStatus": "no_data",
        "series": [],
    }

    use_case = ProcessMetricsUseCase()

    dataframe = use_case.execute(
        monitoring_response
    )

    assert dataframe.empty