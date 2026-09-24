from datetime import datetime
import httpx
import pytest

from application.use_cases.read_historical_logs import ReadHistoricalLogsUseCase
from domain.errors import InvalidQuery, InvalidResponse, SourceForbidden, SourceTimeout
from infrastructure.adapters.input.supabase_historical_logs_adapter import SupabaseHistoricalLogsAdapter, COLUMNS
from infrastructure.settings import Settings

START = datetime.fromisoformat("2026-09-21T15:00:00Z")
END = datetime.fromisoformat("2026-09-21T16:00:00Z")


def row(log_id="log-1"):
    return {"log_id": log_id, "hardware_id": "hw-1", "timestamp": "2026-09-21T15:00:00.123456Z",
            "cpu_utilization_pct": 0, "ram_utilization_pct": 42, "temperatura_celsius": 30,
            "energia_watts": 120.5, "password": "must-never-be-returned"}


class Pages:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.requests = []

    def read_page(self, *args):
        self.requests.append(args)
        value = next(self.pages)
        if isinstance(value, Exception):
            raise value
        return value


def test_same_timestamp_cursor_and_no_secret_columns():
    source = Pages([[row()], [row("log-2")], []])
    use_case = ReadHistoricalLogsUseCase(source)
    first = use_case.execute("hw-1", START, END, 1)
    second = use_case.execute("hw-1", START, END, 1, first["nextCursor"])
    last = use_case.execute("hw-1", START, END, 1, second["nextCursor"])
    assert first["records"][0]["cpu_utilization_pct"] == 0
    assert first["records"][0]["ram_utilization_pct"] == 42
    assert first["records"][0]["energia_watts"] == 120.5
    assert first["records"][0]["timestamp"].endswith(".123456Z")
    assert "password" not in first["records"][0]
    assert first["records"][0]["origin"] == "unknown"
    assert first["units"]["energia_watts"] == "W"
    assert first["dataStatus"] == "partial"
    assert source.requests[1][-1] == (datetime.fromisoformat(row()["timestamp"]), "log-1")
    assert last["nextCursor"] is None and last["dataStatus"] == "no_data"


def test_short_server_page_does_not_claim_complete():
    page = ReadHistoricalLogsUseCase(Pages([[row()]])).execute("hw-1", START, END, 100)
    assert page["nextCursor"] and page["dataStatus"] == "partial"


def test_cursor_bound_to_hardware_and_period():
    use_case = ReadHistoricalLogsUseCase(Pages([[row()]]))
    page = use_case.execute("hw-1", START, END, 1)
    with pytest.raises(InvalidQuery):
        use_case.execute("hw-2", START, END, 1, page["nextCursor"])
    with pytest.raises(InvalidQuery):
        use_case.execute("hw-1", START, END, 1, "not-a-cursor")


def test_failure_on_next_page_is_not_hidden():
    use_case = ReadHistoricalLogsUseCase(Pages([[row()], SourceTimeout("timeout")]))
    first = use_case.execute("hw-1", START, END, 1)
    with pytest.raises(SourceTimeout):
        use_case.execute("hw-1", START, END, 1, first["nextCursor"])


@pytest.mark.parametrize("field,value,quality", [
    ("cpu_utilization_pct", 101, "out_of_range"), ("ram_utilization_pct", -1, "out_of_range"),
    ("energia_watts", float("inf"), "non_finite"), ("energia_watts", None, "missing"),
])
def test_historical_quality(field, value, quality):
    data = row()
    data[field] = value
    record = ReadHistoricalLogsUseCase(Pages([[data]])).execute("hw-1", START, END)["records"][0]
    assert record[field] is None and record["quality"][field] == quality


@pytest.mark.parametrize("change", [{"hardware_id": "other"}, {"timestamp": "broken"}, {"cpu_utilization_pct": "42"}])
def test_invalid_source_rows(change):
    with pytest.raises(InvalidResponse):
        ReadHistoricalLogsUseCase(Pages([[row() | change]])).execute("hw-1", START, END)


def adapter():
    return SupabaseHistoricalLogsAdapter("https://test.supabase.co", "fake-key", "fake-read-token", request_id="test-id")


def test_adapter_filters_in_source_and_only_gets(monkeypatch):
    original = httpx.Client
    def respond(request):
        assert request.method == "GET"
        assert request.url.path == "/rest/v1/logs"
        assert request.url.params["select"] == COLUMNS
        assert request.url.params.get_list("timestamp") == ["gte.2026-09-21T15:00:00Z", "lte.2026-09-21T16:00:00Z"]
        assert request.url.params["order"] == "timestamp.asc,log_id.asc"
        assert 'log_id.gt."log-1"' in request.url.params["or"]
        assert request.headers["X-Request-Id"] == "test-id"
        return httpx.Response(200, json=[])
    monkeypatch.setattr(httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    assert adapter().read_page("hw-1", START, END, 10, (START, "log-1")) == []


@pytest.mark.parametrize("status,error", [(401,SourceForbidden), (403,SourceForbidden), (404,InvalidResponse), (504,SourceTimeout)])
def test_adapter_error_classification(monkeypatch, status, error):
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(lambda req: httpx.Response(status, text="private-details")), **kw))
    with pytest.raises(error) as caught:
        adapter().read_page("hw-1", START, END, 10)
    assert "private-details" not in str(caught.value)


@pytest.mark.parametrize("name,value", [("REQUEST_TIMEOUT_SECONDS","nan"), ("REQUEST_TIMEOUT_SECONDS","0"),
    ("MONITORING_BASE_URL","file:///tmp"), ("HISTORICAL_MAX_PAGE_SIZE","501"), ("SUPABASE_ENABLED","yes")])
def test_configuration_rejected_at_startup(monkeypatch, name, value):
    monkeypatch.setenv("SUPABASE_ENABLED", "false")
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        Settings.from_env()


@pytest.mark.parametrize("token", ["<TU_ACCESS_TOKEN>", "TU_ACCESS_TOKEN", " ", "sb_publishable_example", "sb_secret_example", "token with spaces"])
def test_placeholder_or_api_key_is_not_a_read_token(monkeypatch, token):
    monkeypatch.setenv("SUPABASE_ENABLED", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_API_KEY", "fixture-key")
    monkeypatch.setenv("SUPABASE_READ_TOKEN", token)
    with pytest.raises(ValueError) as error:
        Settings.from_env()
    assert token.strip() not in str(error.value) if token.strip() else True
