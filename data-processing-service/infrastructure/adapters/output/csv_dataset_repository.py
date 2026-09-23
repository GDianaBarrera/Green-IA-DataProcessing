from pathlib import Path

import pandas as pd

from domain.ports.dataset_repository import DatasetRepository


class CsvDatasetRepository(DatasetRepository):
    """
    Adaptador de salida encargado de almacenar
    el dataset procesado en formato CSV.
    """

    def __init__(self, output_path: Path):
        self.output_path = output_path

    def save(self, data: pd.DataFrame) -> None:
        # Crear la carpeta de salida si no existe
        self.output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        # Guardar dataset sin índice adicional
        data.to_csv(
            self.output_path,
            index=False
        )