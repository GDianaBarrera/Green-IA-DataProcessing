from pathlib import Path
import sys


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVICE_ROOT.parent

sys.path.insert(
    0,
    str(SERVICE_ROOT)
)


from infrastructure.adapters.input.greenai_excel_adapter import (
    GreenAIExcelAdapter,
)


DATASET_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "raw"
    / "synthetic_greenai"
    / "BD_GreenAi.xlsx"
)


def test_adapter():
    adapter = GreenAIExcelAdapter(
        DATASET_PATH
    )

    data = adapter.extract()

    hardware = data["hardware"]
    logs = data["logs"]

    print("\n=== PRUEBA DEL ADAPTADOR ===")
    print("Servidores:", len(hardware))
    print("Logs:", len(logs))
    print(
        "Servidores únicos en Logs:",
        logs["hardware_id"].nunique()
    )

    assert len(hardware) == 50
    assert len(logs) == 100000
    assert logs["hardware_id"].nunique() == 50

    print("Adaptador funcionando correctamente.")


if __name__ == "__main__":
    test_adapter()