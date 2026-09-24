from datetime import datetime
import httpx

from domain.errors import InvalidResponse, ServiceError, SourceForbidden, SourceTimeout
from domain.ports.historical_logs_source import HistoricalLogsSource
from domain.validation import timestamp
from infrastructure.settings import validate_timeout, validate_url

COLUMNS = "log_id,hardware_id,timestamp,cpu_utilization_pct,ram_utilization_pct,temperatura_celsius,energia_watts"


def quoted(value):
    # PostgREST quoted filter literals, then httpx handles URL encoding.
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


class SupabaseHistoricalLogsAdapter(HistoricalLogsSource):
    def __init__(self, base_url, api_key, read_token, timeout_seconds=10, request_id=None):
        self.base_url = validate_url(base_url, secure=True)
        self.api_key = api_key
        self.read_token = read_token
        self.timeout_seconds = validate_timeout(timeout_seconds)
        self.request_id = request_id

    def read_page(self, hardware_id: str, start: datetime, end: datetime,
                  limit: int, after: tuple[datetime, str] | None = None) -> list[dict]:
        if not 1 <= limit <= 500:
            raise ValueError("Límite de lectura inválido")
        params = [
            ("select", COLUMNS), ("hardware_id", "eq." + quoted(hardware_id)),
            ("timestamp", "gte." + timestamp(start)), ("timestamp", "lte." + timestamp(end)),
            ("order", "timestamp.asc,log_id.asc"), ("limit", str(limit)),
        ]
        if after:
            instant = timestamp(after[0])
            params.append(("or", f"(timestamp.gt.{instant},and(timestamp.eq.{instant},log_id.gt.{quoted(after[1])}))"))
        headers = {"apikey": self.api_key, "Authorization": f"Bearer {self.read_token}", "Accept": "application/json"}
        if self.request_id:
            headers["X-Request-Id"] = self.request_id
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(f"{self.base_url}/rest/v1/logs", params=params, headers=headers)
                response.raise_for_status()
                try:
                    rows = response.json()
                except ValueError as exc:
                    raise InvalidResponse("Supabase devolvió JSON inválido.") from exc
                if not isinstance(rows, list) or len(rows) > limit or any(not isinstance(r, dict) for r in rows):
                    raise InvalidResponse("Supabase devolvió una página inválida.")
                return rows
        except httpx.TimeoutException as exc:
            raise SourceTimeout("Supabase no respondió a tiempo.") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                raise SourceForbidden("La identidad de lectura no tiene acceso a los históricos.") from exc
            if exc.response.status_code == 504:
                raise SourceTimeout("Supabase no respondió a tiempo.") from exc
            if exc.response.status_code in (400, 404, 406, 416):
                raise InvalidResponse("El contrato de históricos no está disponible en la fuente.") from exc
            raise ServiceError("Supabase no está disponible.") from exc
        except httpx.RequestError as exc:
            raise ServiceError("No fue posible comunicarse con Supabase.") from exc
