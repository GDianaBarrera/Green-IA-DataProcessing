from abc import ABC, abstractmethod
from typing import Any


class DatasetSource(ABC):
    """
    Puerto de salida que define el contrato para
    obtener datos desde una fuente externa.
    """

    @abstractmethod
    def extract(self) -> Any:
        """
        Extrae los datos desde la fuente configurada.
        """
        pass
    