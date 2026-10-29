from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class MetricsSource(ABC):
    """
    Puerto de entrada para consultar métricas.

    Define el contrato que debe cumplir cualquier fuente
    de métricas utilizada por Data Processing.
    """

    @abstractmethod
    def get_history(
        self,
        metric: str,
        start: datetime,
        end: datetime,
        resource_type: str | None = None,
        cluster: str | None = None,
        resource_id: str | None = None,
        step_seconds: int | None = None,
    ) -> dict[str, Any]:
        """
        Obtiene métricas históricas desde una fuente externa.
        """
        raise NotImplementedError