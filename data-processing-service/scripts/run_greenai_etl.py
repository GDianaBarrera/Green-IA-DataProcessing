from pathlib import Path
import sys


# ============================================================
# CONFIGURACIÓN DE RUTAS
# ============================================================

SERVICE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVICE_ROOT.parent

sys.path.insert(
    0,
    str(SERVICE_ROOT)
)


# ============================================================
# IMPORTS DE LA ARQUITECTURA
# ============================================================

from application.use_cases.process_greenai_dataset import (
    ProcessGreenAIDatasetUseCase,
)

from infrastructure.adapters.input.greenai_excel_adapter import (
    GreenAIExcelAdapter,
)

from infrastructure.adapters.output.csv_dataset_repository import (
    CsvDatasetRepository,
)


# ============================================================
# RUTAS
# ============================================================

RAW_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "raw"
    / "synthetic_greenai"
    / "BD_GreenAi.xlsx"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "processed"
    / "dataset_green_ai_v2_hexagonal.csv"
)


# ============================================================
# COMPOSITION ROOT
# ============================================================

def main():

    print("=" * 60)
    print("GREEN AI - DATA PROCESSING SERVICE")
    print("ETL CON ARQUITECTURA HEXAGONAL")
    print("=" * 60)

    # Adaptador de entrada
    source = GreenAIExcelAdapter(
        RAW_PATH
    )

    # Adaptador de salida
    repository = CsvDatasetRepository(
        OUTPUT_PATH
    )

    # Inyección de dependencias
    use_case = ProcessGreenAIDatasetUseCase(
        source=source,
        repository=repository,
    )

    # Ejecución
    processed = use_case.execute()

    print("\n" + "=" * 60)
    print("PROCESAMIENTO FINALIZADO")
    print("=" * 60)

    print(
        f"Registros procesados: "
        f"{len(processed)}"
    )

    print(
        f"Servidores: "
        f"{processed['hardware_id'].nunique()}"
    )

    print(
        f"Columnas: "
        f"{len(processed.columns)}"
    )

    print(
        f"Archivo generado:\n"
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()