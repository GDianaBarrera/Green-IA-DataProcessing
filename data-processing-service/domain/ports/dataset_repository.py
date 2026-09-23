from abc import ABC, abstractmethod
from typing import Any


class DatasetRepository(ABC):
    """
    Puerto de salida para almacenar el dataset
    resultante del procesamiento.
    """

    @abstractmethod
    def save(self, data: Any) -> None:
        """
        Guarda el dataset procesado.
        """
        pass
    