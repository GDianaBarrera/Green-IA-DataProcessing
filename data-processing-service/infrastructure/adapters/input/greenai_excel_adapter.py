from pathlib import Path

import pandas as pd

from domain.ports.dataset_source import DatasetSource


class GreenAIExcelAdapter(DatasetSource):
    """
    Adaptador de infraestructura encargado de extraer
    Hardware y Logs desde BD_GreenAi.xlsx.
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def extract(self) -> dict[str, pd.DataFrame]:
        if not self.file_path.exists():
            raise FileNotFoundError(
                f"No se encontró el dataset:\n{self.file_path}"
            )

        hardware = pd.read_excel(
            self.file_path,
            sheet_name="Hardware"
        )

        logs = pd.read_excel(
            self.file_path,
            sheet_name="Logs"
        )

        return {
            "hardware": hardware,
            "logs": logs
        }