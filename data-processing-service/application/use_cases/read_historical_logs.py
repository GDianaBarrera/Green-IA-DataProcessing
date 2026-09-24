import base64
from datetime import datetime
import json
import math

from domain.errors import InvalidQuery, InvalidResponse
from domain.ports.historical_logs_source import HistoricalLogsSource
from domain.validation import interval, timestamp, utc

UNITS = {"cpu_utilization_pct": "%", "ram_utilization_pct": "%",
         "temperatura_celsius": "degC", "energia_watts": "W"}


def context(hardware_id, start, end):
    return {"hardwareId": hardware_id, "start": timestamp(start), "end": timestamp(end)}


def decode_cursor(cursor, scope):
    if not cursor:
        return None
    try:
        if len(cursor) > 2048:
            raise ValueError()
        data = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        if data["scope"] != scope or data["version"] != 1:
            raise ValueError()
        instant = utc(datetime.fromisoformat(data["timestamp"]))
        log_id = data["logId"]
        if not isinstance(log_id, str) or not 1 <= len(log_id) <= 20:
            raise ValueError()
        if not datetime.fromisoformat(scope["start"]) <= instant <= datetime.fromisoformat(scope["end"]):
            raise ValueError()
        return instant, log_id
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise InvalidQuery("Cursor inválido o perteneciente a otro periodo/hardware.") from exc


class ReadHistoricalLogsUseCase:
    def __init__(self, source: HistoricalLogsSource, max_page_size=500):
        self.source = source
        self.max_page_size = max_page_size

    def execute(self, hardware_id, start, end, limit=100, cursor=None):
        start, end = interval(start, end)
        if not isinstance(hardware_id, str) or not 1 <= len(hardware_id) <= 20:
            raise InvalidQuery("hardwareId debe tener entre 1 y 20 caracteres.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= self.max_page_size:
            raise InvalidQuery(f"limit debe estar entre 1 y {self.max_page_size}.")
        scope = context(hardware_id, start, end)
        after = decode_cursor(cursor, scope)
        rows = self.source.read_page(hardware_id, start, end, limit, after)
        if len(rows) > limit:
            raise InvalidResponse("Supabase excedió el tamaño de página.")
        records, warnings, seen = [], ["Procedencia de los históricos no confirmada; origin=unknown."], set()
        previous_time = after[0] if after else start
        for row in rows:
            try:
                log_id = row["log_id"]
                instant = utc(datetime.fromisoformat(row["timestamp"]))
                if (not isinstance(log_id, str) or not 1 <= len(log_id) <= 20
                        or row["hardware_id"] != hardware_id or not start <= instant <= end
                        or instant < previous_time or log_id in seen
                        or (after and (instant, log_id) == after)):
                    raise ValueError()
                seen.add(log_id)
                previous_time = instant
                record = {"log_id": log_id, "hardware_id": hardware_id,
                          "timestamp": timestamp(instant), "origin": "unknown", "source": "supabase", "quality": {}}
                for field in UNITS:
                    value = row[field]
                    quality = "valid"
                    if value is None:
                        quality = "missing"
                    elif isinstance(value, bool) or not isinstance(value, (int, float)):
                        raise ValueError()
                    elif not math.isfinite(value):
                        value, quality = None, "non_finite"
                    elif (field.endswith("_pct") and not 0 <= value <= 100) or (field == "energia_watts" and value < 0):
                        value, quality = None, "out_of_range"
                    record[field] = value
                    record["quality"][field] = quality
                    if quality != "valid":
                        warnings.append(f"Registro {log_id}: {field} marcado {quality}, sin imputación.")
                records.append(record)
            except (ValueError, TypeError, KeyError) as exc:
                raise InvalidResponse("Supabase devolvió registros incompatibles con el contrato.") from exc
        # A full page MAY have more data, including server-side caps. Continue
        # after any nonempty page; only an empty page proves exhaustion.
        next_cursor = None
        if records:
            last = records[-1]
            payload = {"version": 1, "scope": scope, "timestamp": last["timestamp"], "logId": last["log_id"]}
            next_cursor = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
            warnings.append("Página acotada; continúe con nextCursor hasta una página vacía. No es un snapshot transaccional.")
        return {"schemaVersion": "1.0", "hardwareId": hardware_id,
                "period": {"start": timestamp(start), "end": timestamp(end)}, "units": UNITS,
                "dataStatus": "partial" if records else "no_data", "recordCount": len(records),
                "records": records, "nextCursor": next_cursor, "warnings": warnings}
