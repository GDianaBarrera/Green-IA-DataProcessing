from datetime import datetime, timezone

import httpx

from infrastructure.adapters.input.monitoring_http_adapter import (
    MonitoringHttpAdapter,
)


def test_monitoring_adapter_configuration():
    adapter = MonitoringHttpAdapter(
        base_url="http://monitoring:8080/",
        timeout_seconds=10,
    )

    assert adapter.base_url == "http://monitoring:8080"
    assert adapter.timeout_seconds == 10


def test_get_history_preserves_monitoring_response(monkeypatch):
    monitoring_response = {
        "metric": "node.memory.used",
        "unit": "bytes",
        "aggregation": "instant",
        "windowSeconds": None,
        "start": "2026-09-23T20:00:00Z",
        "end": "2026-09-23T21:00:00Z",
        "stepSeconds": 60,
        "warnings": [],
        "dataStatus": "partial",
        "series": [
            {
                "resource": {
                    "type": "node",
                    "cluster": "test-lab",
                    "id": "host:9100",
                },
                "origin": "simulated",
                "labels": {},
                "source": "prometheus",
                "samples": [
                    {
                        "timestamp": "2026-09-23T20:00:00Z",
                        "value": 0,
                        "quality": "valid",
                    },
                    {
                        "timestamp": "2026-09-23T20:01:00Z",
                        "value": None,
                        "quality": "missing",
                    },
                    {
                        "timestamp": "2026-09-23T20:02:00Z",
                        "value": None,
                        "quality": "non_finite",
                    },
                ],
            }
        ],
    }

    captured_request = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return monitoring_response

    class FakeClient:
        def __init__(self, timeout):
            captured_request["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

        def get(self, url, params):
            captured_request["url"] = url
            captured_request["params"] = params
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    adapter = MonitoringHttpAdapter(
        base_url="http://monitoring:8080",
        timeout_seconds=10,
    )

    result = adapter.get_history(
        metric="node.memory.used",
        start=datetime(
            2026, 9, 23, 20, 0, tzinfo=timezone.utc
        ),
        end=datetime(
            2026, 9, 23, 21, 0, tzinfo=timezone.utc
        ),
        cluster="test-lab",
        resource_id="host:9100",
        step_seconds=60,
    )

    assert captured_request["url"] == (
        "http://monitoring:8080/api/v1/metrics/history"
    )

    assert captured_request["params"]["metric"] == "node.memory.used"
    assert captured_request["params"]["cluster"] == "test-lab"
    assert captured_request["params"]["resourceId"] == "host:9100"
    assert captured_request["params"]["stepSeconds"] == 60

    assert result["dataStatus"] == "partial"

    samples = result["series"][0]["samples"]

    assert samples[0]["value"] == 0
    assert samples[0]["quality"] == "valid"

    assert samples[1]["value"] is None
    assert samples[1]["quality"] == "missing"

    assert samples[2]["value"] is None
    assert samples[2]["quality"] == "non_finite"

def test_get_history_raises_value_error_for_invalid_query(monkeypatch):

    class FakeResponse:
        status_code = 400
        text = '{"code":"INVALID_PARAMETER"}'

        def raise_for_status(self):
            request = httpx.Request(
                "GET",
                "http://monitoring:8080/api/v1/metrics/history",
            )

            response = httpx.Response(
                status_code=400,
                request=request,
                text=self.text,
            )

            raise httpx.HTTPStatusError(
                "Bad Request",
                request=request,
                response=response,
            )

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

        def get(self, url, params):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    adapter = MonitoringHttpAdapter(
        base_url="http://monitoring:8080",
    )

    try:
        adapter.get_history(
            metric="invalid.metric",
            start=datetime(
                2026, 9, 23, 20, 0, tzinfo=timezone.utc
            ),
            end=datetime(
                2026, 9, 23, 21, 0, tzinfo=timezone.utc
            ),
        )

        assert False, "Se esperaba ValueError"

    except ValueError as exc:
        assert "400" in str(exc)


def test_get_history_raises_runtime_error_when_monitoring_unavailable(
    monkeypatch,
):

    class FakeResponse:
        status_code = 503
        text = '{"code":"METRICS_SOURCE_UNAVAILABLE"}'

        def raise_for_status(self):
            request = httpx.Request(
                "GET",
                "http://monitoring:8080/api/v1/metrics/history",
            )

            response = httpx.Response(
                status_code=503,
                request=request,
                text=self.text,
            )

            raise httpx.HTTPStatusError(
                "Service Unavailable",
                request=request,
                response=response,
            )

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

        def get(self, url, params):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    adapter = MonitoringHttpAdapter(
        base_url="http://monitoring:8080",
    )

    try:
        adapter.get_history(
            metric="node.memory.used",
            start=datetime(
                2026, 9, 23, 20, 0, tzinfo=timezone.utc
            ),
            end=datetime(
                2026, 9, 23, 21, 0, tzinfo=timezone.utc
            ),
        )

        assert False, "Se esperaba RuntimeError"

    except RuntimeError as exc:
        assert "503" in str(exc)
