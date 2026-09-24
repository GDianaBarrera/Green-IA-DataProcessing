from datetime import datetime, timedelta, timezone

from domain.errors import InvalidQuery


def utc(value: datetime, whole_seconds: bool = False) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidQuery("La fecha debe incluir zona horaria.")
    if whole_seconds and value.microsecond:
        raise InvalidQuery("Monitoring requiere segundos enteros, sin fracciones.")
    return value.astimezone(timezone.utc)


def interval(start, end, *, monitoring=False):
    start, end = utc(start, monitoring), utc(end, monitoring)
    if start >= end:
        raise InvalidQuery("start debe ser anterior a end.")
    if end > datetime.now(timezone.utc):
        raise InvalidQuery("end no puede estar en el futuro.")
    if end - start > timedelta(days=1 if monitoring else 31):
        raise InvalidQuery("El rango máximo es 24 horas para Monitoring y 31 días para históricos.")
    return start, end


def timestamp(value):
    return utc(value).isoformat().replace("+00:00", "Z")
