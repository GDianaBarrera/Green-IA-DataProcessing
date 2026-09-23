from pathlib import Path
import sys

import pandas as pd


SERVICE_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(SERVICE_ROOT)
)


from infrastructure.adapters.output.csv_dataset_repository import (
    CsvDatasetRepository,
)


TEST_OUTPUT = (
    SERVICE_ROOT
    / "tests"
    / "temp"
    / "test_output.csv"
)


def test_repository():
    print("\n=== PRUEBA DEL REPOSITORIO CSV ===")

    # Dataset pequeño exclusivamente para la prueba
    test_data = pd.DataFrame({
        "hardware_id": [
            "HW001",
            "HW002"
        ],
        "cpu_utilization_pct": [
            45.5,
            72.3
        ]
    })

    repository = CsvDatasetRepository(
        TEST_OUTPUT
    )

    repository.save(
        test_data
    )

    # Verificar que el archivo fue creado
    assert TEST_OUTPUT.exists()

    # Volver a leerlo
    saved_data = pd.read_csv(
        TEST_OUTPUT
    )

    # Verificar cantidad de registros
    assert len(saved_data) == 2

    # Verificar columnas
    assert list(saved_data.columns) == [
        "hardware_id",
        "cpu_utilization_pct"
    ]

    print(
        "Archivo creado:",
        TEST_OUTPUT
    )

    print(
        "Registros guardados:",
        len(saved_data)
    )

    print(
        "Columnas:",
        len(saved_data.columns)
    )

    print(
        "Repositorio CSV funcionando correctamente."
    )

    # Eliminar archivo temporal
    TEST_OUTPUT.unlink()

    # Eliminar carpeta temporal si queda vacía
    if TEST_OUTPUT.parent.exists():
        TEST_OUTPUT.parent.rmdir()


if __name__ == "__main__":
    test_repository()