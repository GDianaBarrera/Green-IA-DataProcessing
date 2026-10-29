"""Validate a running Data Processing container against the explicit Docker fixture."""
from datetime import datetime, timedelta, timezone
import sys
import time

import httpx


def run(base_url):
    with httpx.Client(base_url=base_url, timeout=5) as client:
        for attempt in range(30):
            try:
                if client.get("/api/v1/health").status_code == 200:
                    break
            except httpx.RequestError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Data Processing did not become healthy within 30 seconds")

        end = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=1)
        params = {"start": (end - timedelta(minutes=1)).isoformat(), "end": end.isoformat(),
                  "metric": "node.cpu.utilization", "cluster": "docker-fixture", "resourceId": "node-1"}
        response = client.get("/api/v1/metrics/history", params=params, headers={"X-Request-Id": "docker-smoke"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["unit"] == "ratio" and result["dataStatus"] == "partial"
        assert result["records"][0]["value"] == 0
        assert result["records"][1]["value"] is None
        assert result["records"][0]["origin"] == "simulated" and result["warnings"]
        assert response.headers["X-Request-Id"] == "docker-smoke"

        prediction = client.get("/api/v1/prediction/dataset", params={k: v for k, v in params.items() if k != "metric"})
        assert prediction.status_code == 200, prediction.text
        dataset = prediction.json()
        assert dataset["contractStatus"] == "provisional" and dataset["excludedSampleCount"] == 1
        assert dataset["features"][0]["cpu_utilization"] == 0
        historical = client.get("/api/v1/historical-logs", params={"start": params["start"], "end": params["end"], "hardwareId": "fixture"})
        assert historical.status_code == 503
        assert historical.json()["code"] == "SOURCE_NOT_CONFIGURED"
        invalid = client.get("/api/v1/metrics/history", params=params | {"stepSeconds": 1})
        assert invalid.status_code == 422
        assert client.get("/openapi.json").status_code == 200
    print("HTTP smoke passed: metadata, zero/null, correlation, provisional dataset, disabled Supabase.")


if __name__ == "__main__":
    run(sys.argv[1])
