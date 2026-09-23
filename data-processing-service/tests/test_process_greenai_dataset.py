from pathlib import Path
import sys

import pandas as pd


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVICE_ROOT.parent

sys.path.insert(
    0,
    str(SERVICE_ROOT)
)


from application.use_cases.process_greenai_dataset import (
    ProcessGreenAIDatasetUseCase,
)

from infrastructure.adapters.input.greenai_excel_adapter import (
    GreenAIExcelAdapter,
)

from infrastructure.adapters.output.csv_dataset_repository import (
    CsvDatasetRepository,
)


RAW_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "raw"
    / "synthetic_greenai"
    / "BD_GreenAi.xlsx"
)

TEST_OUTPUT = (
    SERVICE_ROOT
    / "tests"
    / "temp"
    / "greenai_processed_test.csv"
)


def test_process_greenai_dataset():

    print("\n=== PRUEBA ETL HEXAGONAL ===")

    # Adaptador de entrada
    source = GreenAIExcelAdapter(
        RAW_PATH
    )

    # Adaptador de salida
    repository = CsvDatasetRepository(
        TEST_OUTPUT
    )

    # Caso de uso
    use_case = ProcessGreenAIDatasetUseCase(
        source=source,
        repository=repository,
    )

    # Ejecutar ETL
    processed = use_case.execute()

    # ========================================================
    # ASSERTS
    # ========================================================

    assert len(processed) == 100000

    assert (
        processed["hardware_id"].nunique()
        == 50
    )

    assert len(processed.columns) == 14

    assert (
        "estimated_power_watts"
        in processed.columns
    )

    assert (
        "energia_watts"
        not in processed.columns
    )

    assert (
        "prediccion_watts"
        not in processed.columns
    )

    assert (
        "accion_recomendada"
        not in processed.columns
    )

    assert TEST_OUTPUT.exists()

    # Verificar persistencia
    saved = pd.read_csv(
        TEST_OUTPUT
    )

    assert len(saved) == 100000

    print("\n=== RESULTADOS ===")

    print(
        "Registros:",
        len(processed)
    )

    print(
        "Servidores:",
        processed["hardware_id"].nunique()
    )

    print(
        "Columnas:",
        len(processed.columns)
    )

    print(
        "Potencia:",
        "estimated_power_watts"
        in processed.columns
    )

    print(
        "\nETL hexagonal funcionando correctamente."
    )

    # Limpiar archivo de prueba
    TEST_OUTPUT.unlink()

    if TEST_OUTPUT.parent.exists():
        TEST_OUTPUT.parent.rmdir()


if __name__ == "__main__":
    test_process_greenai_dataset()