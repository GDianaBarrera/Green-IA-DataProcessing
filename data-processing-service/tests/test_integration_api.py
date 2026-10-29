from copy import deepcopy
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from application.use_cases.process_metrics import ProcessMetricsUseCase
from domain.errors import InvalidResponse
from infrastructure.adapters.input.monitoring_http_adapter import MonitoringHttpAdapter

START = "2026-09-21T15:00:00Z"
END = "2026-09-21T16:00:00Z"
PARAMS = {"metric": "node.cpu.utilization", "start": START, "end": END}


def payload():
    return {"metric": "node.cpu.utilization", "unit": "ratio", "aggregation": "mean_non_idle",
        "windowSeconds": 60, "start": START, "end": END, "stepSeconds": 15, "dataStatus": "partial",
        "warnings": ["coverage incomplete"], "series": [{
            "resource": {"type": "node", "cluster": "lab", "id": "node-1"}, "labels": {},
            "source": "prometheus", "origin": "simulated", "samples": [
                {"timestamp": START, "value": 0, "quality": "valid"},
                {"timestamp": "2026-09-21T15:00:15Z", "value": None, "quality": "missing"},
            ]}]}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SUPABASE_ENABLED", "false")
    with TestClient(app) as client:
        yield client


def mock_upstream(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


def test_history_preserves_metadata_and_correlation(client, monkeypatch):
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=payload())
    mock_upstream(monkeypatch, respond)
    response = client.get("/api/v1/metrics/history", params=PARAMS, headers={"X-Request-Id": "test-123"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["unit"] == "ratio" and result["windowSeconds"] == 60
    assert result["period"] == {"start": START, "end": END}
    assert result["warnings"] == ["coverage incomplete"]
    assert result["records"][0]["value"] == 0
    assert result["records"][1]["value"] is None
    assert response.headers["X-Request-Id"] == requests[0].headers["X-Request-Id"] == "test-123"
    assert requests[0].url.params["start"] == START
    assert requests[0].url.params["stepSeconds"] == "15"


@pytest.mark.parametrize("change", [
    {"start": "2026-09-21T15:00:00"}, {"start": "2026-09-21T15:00:00.123Z"},
    {"end": START}, {"start": "2026-09-19T15:00:00Z"},
    {"end": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()},
    {"stepSeconds": 14}, {"stepSeconds": 3601}, {"metric": "not-a-metric"},
])
def test_bad_query_never_calls_source(client, monkeypatch, change):
    def unexpected(request):
        pytest.fail("Invalid query reached source")
    mock_upstream(monkeypatch, unexpected)
    result = client.get("/api/v1/metrics/history", params=PARAMS | change)
    assert result.status_code == 422
    assert result.json()["code"] == "INVALID_QUERY"
    assert result.headers["X-Request-Id"]


def test_offsets_are_serialized_as_utc(client, monkeypatch):
    def respond(request):
        assert request.url.params["start"] == START
        return httpx.Response(200, json=payload())
    mock_upstream(monkeypatch, respond)
    response = client.get("/api/v1/metrics/history", params=PARAMS | {"start": "2026-09-21T10:00:00-05:00"})
    assert response.status_code == 200


@pytest.mark.parametrize("status,expected", [(400,422), (422,422), (401,503), (500,503), (502,502), (503,503), (504,504)])
def test_source_errors_are_safe(client, monkeypatch, status, expected):
    mock_upstream(monkeypatch, lambda request: httpx.Response(status, text="secret-internal-sql-token"))
    response = client.get("/api/v1/metrics/history", params=PARAMS)
    assert response.status_code == expected
    assert "secret-internal" not in response.text
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize("failure,expected", [(httpx.ReadTimeout,504), (httpx.ConnectError,503)])
def test_transport_errors(client, monkeypatch, failure, expected):
    def respond(request):
        raise failure("internal detail", request=request)
    mock_upstream(monkeypatch, respond)
    assert client.get("/api/v1/metrics/history", params=PARAMS).status_code == expected


def test_broken_json_is_502(client, monkeypatch):
    mock_upstream(monkeypatch, lambda request: httpx.Response(200, text="not-json"))
    assert client.get("/api/v1/metrics/history", params=PARAMS).status_code == 502


@pytest.mark.parametrize("mutation", [
    lambda p: p.pop("unit"), lambda p: p.update(series={}),
    lambda p: p["series"][0]["samples"][0].update(value=None),
    lambda p: p["series"][0]["samples"][0].update(value=float("inf")),
    lambda p: p["series"][0]["samples"][0].update(timestamp="broken"),
    lambda p: p["series"][0]["samples"][0].update(timestamp="2026-09-21T15:00:00"),
    lambda p: p["series"][0]["samples"][1].update(value=0),
])
def test_invalid_samples_are_rejected(mutation):
    data = payload()
    mutation(data)
    with pytest.raises(InvalidResponse):
        ProcessMetricsUseCase().execute(data)


def test_empty_response_keeps_metadata_and_partial(client, monkeypatch):
    data = payload()
    data["series"] = []
    mock_upstream(monkeypatch, lambda request: httpx.Response(200, json=data))
    response = client.get("/api/v1/metrics/history", params=PARAMS).json()
    assert response["records"] == [] and response["recordCount"] == 0
    assert response["dataStatus"] == "partial" and response["unit"] == "ratio"
    data["dataStatus"] = "no_data"
    assert client.get("/api/v1/metrics/history", params=PARAMS).json()["dataStatus"] == "no_data"


def test_duplicates_preserve_identity_and_reject_conflicts():
    data = payload()
    series = data["series"][0]
    series["samples"].append(deepcopy(series["samples"][0]))
    frame = ProcessMetricsUseCase().execute(data)
    assert len(frame) == 2 and len(frame.attrs["warnings"]) == 2
    series["samples"][-1]["value"] = 0.7
    with pytest.raises(InvalidResponse):
        ProcessMetricsUseCase().execute(data)


def test_prediction_route_is_provisional_and_explains_exclusions(client, monkeypatch):
    mock_upstream(monkeypatch, lambda request: httpx.Response(200, json=payload()))
    response = client.get("/api/v1/prediction/dataset", params={"start": START, "end": END, "cluster": "lab", "resourceId": "node-1"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["contractStatus"] == "provisional" and data["excludedSampleCount"] == 1
    assert data["features"][0]["cpu_utilization"] == 0 and data["units"] == {"cpu_utilization": "%"}
    assert data["requestedPeriod"]["end"] == END and data["period"]["end"] == START
    assert "coverage incomplete" in data["warnings"]


def test_supabase_disabled_does_not_break_monitoring(client, monkeypatch):
    mock_upstream(monkeypatch, lambda request: httpx.Response(200, json=payload()))
    response = client.get("/api/v1/historical-logs", params={"hardwareId":"hw-1", "start":START,"end":END})
    assert response.status_code == 503 and response.json()["code"] == "SOURCE_NOT_CONFIGURED"
    assert client.get("/api/v1/metrics/history", params=PARAMS).status_code == 200


def test_invalid_request_id_replaced(client):
    response = client.get("/api/v1/health", headers={"X-Request-Id": "x" * 129})
    assert len(response.headers["X-Request-Id"]) == 36


def test_supabase_route_with_configured_read_identity(monkeypatch):
    from tests.test_historical_logs import row
    monkeypatch.setenv("SUPABASE_ENABLED", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_API_KEY", "fixture-key")
    monkeypatch.setenv("SUPABASE_READ_TOKEN", "fixture-token")
    with TestClient(app) as client:
        mock_upstream(monkeypatch, lambda request: httpx.Response(200, json=[row()]))
        response = client.get("/api/v1/historical-logs", params={"hardwareId":"hw-1", "start":START,"end":END})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["records"][0]["cpu_utilization_pct"] == 0
    assert result["units"]["energia_watts"] == "W" and result["nextCursor"]
    assert "password" not in response.text and "fixture-token" not in response.text


def test_response_filter_mismatch_rejected(client, monkeypatch):
    data = payload()
    data["metric"] = "node.memory.used"
    data.update(unit="bytes", aggregation="instant", windowSeconds=None)
    mock_upstream(monkeypatch, lambda request: httpx.Response(200, json=data))
    assert client.get("/api/v1/metrics/history", params=PARAMS).status_code == 502


def test_openapi_export_matches_live_schema():
    import json
    from pathlib import Path
    saved = json.loads((Path(__file__).parents[1] / "contracts/data-processing-v1.openapi.json").read_text(encoding="utf-8"))
    assert saved == app.openapi()
    response = saved["paths"]["/api/v1/historical-logs"]["get"]["responses"]["503"]
    assert "application/problem+json" in response["content"]
