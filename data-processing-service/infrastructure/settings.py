from dataclasses import dataclass, field
import math
import os
from urllib.parse import urlsplit


def validate_url(value, *, secure=False):
    parts = urlsplit(value)
    if (parts.scheme not in (("https",) if secure else ("http", "https"))
            or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment):
        raise ValueError("URL de servicio inválida; use HTTP(S) sin credenciales ni query.")
    return value.rstrip("/")


def validate_timeout(value):
    if not math.isfinite(value) or not 0 < value <= 120:
        raise ValueError("REQUEST_TIMEOUT_SECONDS debe estar entre 0 y 120.")
    return value


@dataclass(frozen=True)
class Settings:
    monitoring_url: str
    timeout: float
    supabase_enabled: bool = False
    supabase_url: str = ""
    supabase_key: str = field(default="", repr=False)
    supabase_token: str = field(default="", repr=False)
    historical_page_size: int = 500

    @classmethod
    def from_env(cls):
        enabled = os.getenv("SUPABASE_ENABLED", "false").lower()
        if enabled not in ("true", "false"):
            raise ValueError("SUPABASE_ENABLED debe ser true o false.")
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_API_KEY", "")
        token = os.getenv("SUPABASE_READ_TOKEN", "")
        if enabled == "true":
            validate_url(url, secure=True)
            if not key or not token:
                raise ValueError("Supabase habilitado requiere API key y token de lectura dedicado.")
        size = int(os.getenv("HISTORICAL_MAX_PAGE_SIZE", "500"))
        if not 1 <= size <= 500:
            raise ValueError("HISTORICAL_MAX_PAGE_SIZE debe estar entre 1 y 500.")
        return cls(
            validate_url(os.getenv("MONITORING_BASE_URL", "http://localhost:8080")),
            validate_timeout(float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))),
            enabled == "true", url.rstrip("/"), key, token, size,
        )
