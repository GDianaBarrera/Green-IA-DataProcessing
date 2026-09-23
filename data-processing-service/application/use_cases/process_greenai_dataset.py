import pandas as pd

from domain.ports.dataset_source import DatasetSource
from domain.ports.dataset_repository import DatasetRepository


class ProcessGreenAIDatasetUseCase:
    """
    Caso de uso encargado de ejecutar el procesamiento
    del dataset sintético Green AI.

    Flujo:
    Extract -> Validate -> Transform -> Join -> Load
    """

    HARDWARE_COLUMNS = [
        "hardware_id",
        "hostname",
        "cpu_cores",
        "ram_gb",
        "max_watts",
        "ubicacion_rack",
        "estado",
    ]

    LOG_COLUMNS = [
        "log_id",
        "hardware_id",
        "timestamp",
        "cpu_utilization_pct",
        "ram_utilization_pct",
        "temperatura_celsius",
        "energia_watts",
        "cumple_sla",
    ]

    def __init__(
        self,
        source: DatasetSource,
        repository: DatasetRepository,
    ):
        self.source = source
        self.repository = repository

    # ========================================================
    # VALIDACIÓN DEL ESQUEMA
    # ========================================================

    @staticmethod
    def _validate_columns(
        df: pd.DataFrame,
        required_columns: list[str],
        dataset_name: str,
    ) -> None:

        missing_columns = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Faltan columnas en {dataset_name}: "
                f"{missing_columns}"
            )

    # ========================================================
    # TRANSFORM
    # ========================================================

    def _transform(
        self,
        hardware: pd.DataFrame,
        logs: pd.DataFrame,
    ) -> pd.DataFrame:

        hardware = hardware.copy()
        logs = logs.copy()

        # ----------------------------------------------------
        # 1. Validar estructura
        # ----------------------------------------------------

        self._validate_columns(
            hardware,
            self.HARDWARE_COLUMNS,
            "Hardware",
        )

        self._validate_columns(
            logs,
            self.LOG_COLUMNS,
            "Logs",
        )

        # ----------------------------------------------------
        # 2. Seleccionar columnas necesarias
        # ----------------------------------------------------

        hardware = hardware[
            self.HARDWARE_COLUMNS
        ].copy()

        logs = logs[
            self.LOG_COLUMNS
        ].copy()

        # ----------------------------------------------------
        # 3. Corregir semántica de potencia
        # ----------------------------------------------------

        logs = logs.rename(
            columns={
                "energia_watts":
                "estimated_power_watts"
            }
        )

        # ----------------------------------------------------
        # 4. Normalizar timestamp
        # ----------------------------------------------------

        logs["timestamp"] = pd.to_datetime(
            logs["timestamp"],
            errors="coerce",
        )

        # ----------------------------------------------------
        # 5. Eliminar registros incompletos
        # ----------------------------------------------------

        hardware = hardware.dropna()
        logs = logs.dropna()

        # ----------------------------------------------------
        # 6. Eliminar duplicados
        # ----------------------------------------------------

        hardware = hardware.drop_duplicates()
        logs = logs.drop_duplicates()

        # ----------------------------------------------------
        # 7. Validar rangos
        # ----------------------------------------------------

        logs = logs[
            logs["cpu_utilization_pct"].between(
                0,
                100,
            )
            & logs["ram_utilization_pct"].between(
                0,
                100,
            )
            & (
                logs["estimated_power_watts"]
                >= 0
            )
        ].copy()

        # ----------------------------------------------------
        # 8. JOIN Logs + Hardware
        # ----------------------------------------------------

        processed = logs.merge(
            hardware,
            on="hardware_id",
            how="inner",
            validate="many_to_one",
        )

        # ----------------------------------------------------
        # 9. Orden temporal
        # ----------------------------------------------------

        processed = processed.sort_values(
            by=[
                "timestamp",
                "hardware_id",
            ]
        )

        processed = processed.reset_index(
            drop=True
        )

        return processed

    # ========================================================
    # EJECUTAR CASO DE USO
    # ========================================================

    def execute(self) -> pd.DataFrame:

        print("\n[APPLICATION] Procesando dataset...")

        # EXTRACT
        data = self.source.extract()

        hardware = data["hardware"]
        logs = data["logs"]

        print(
            f"Hardware recibido: {len(hardware)}"
        )

        print(
            f"Logs recibidos: {len(logs)}"
        )

        # TRANSFORM
        processed = self._transform(
            hardware,
            logs,
        )

        print(
            f"Registros procesados: "
            f"{len(processed)}"
        )

        print(
            f"Servidores: "
            f"{processed['hardware_id'].nunique()}"
        )

        # LOAD
        self.repository.save(
            processed
        )

        print(
            "Dataset almacenado correctamente."
        )

        return processed