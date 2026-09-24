import json
from pathlib import Path


def test_prediction_contract_fixture_is_valid():
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "contracts"
        / "prediction-dataset-v1.example.json"
    )

    with fixture_path.open(encoding="utf-8") as file:
        dataset = json.load(file)

    assert dataset["schemaVersion"] == "1.0"
    assert dataset["datasetId"]

    assert dataset["resource"]["type"] == "node"
    assert dataset["resource"]["cluster"]
    assert dataset["resource"]["id"]

    assert dataset["period"]["start"]
    assert dataset["period"]["end"]

    assert dataset["features"]

    for feature in dataset["features"]:
        assert "timestamp" in feature
        assert "cpu_utilization" in feature
        assert "origin" in feature
        assert "quality" in feature

        assert feature["origin"] in {
            "observed",
            "simulated",
            "estimated",
            "unknown",
        }

        assert feature["quality"] in {
            "ok",
            "complete",
            "degraded",
            "warning",
        }

    assert dataset["dataStatus"] in {
        "complete",
        "partial",
        "incomplete",
    }