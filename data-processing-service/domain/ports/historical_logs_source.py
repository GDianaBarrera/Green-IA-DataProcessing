from abc import ABC, abstractmethod
from datetime import datetime


class HistoricalLogsSource(ABC):
    @abstractmethod
    def read_page(self, hardware_id: str, start: datetime, end: datetime,
                  limit: int, after: tuple[datetime, str] | None = None) -> list[dict]:
        """Read at most limit rows ordered by (timestamp, log_id), without writes."""
        raise NotImplementedError
