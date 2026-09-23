from pathlib import Path
import sys

import pandas as pd
import pytest


# ============================================================
# CONFIGURACIÓN DE IMPORTS
# ============================================================

SERVICE_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(SERVICE_ROOT)
)


from application.use_cases.process_greenai_dataset import (
    ProcessGreenAIDatasetUseCase,
)


# ============================================================
# DATOS BASE PARA LAS PRUEBAS
# ============================================================

def create_valid_hardware():
    """
    Crea un Hardware válido para utilizarlo
    en las diferentes pruebas.
    """

    return pd.DataFrame({
        "hardware_id": ["HW001"],
        "hostname": ["srv-green-001"],
        "cpu_cores": [32],
        "ram_gb": [64],
        "max_watts": [600],
        "ubicacion_rack": ["Rack-01"],
        "estado": ["Activo"],
    })


def create_valid_logs():
    """
    Crea un Log válido para utilizarlo
    en las diferentes pruebas.
    """

    return pd.DataFrame({
        "log_id": ["LOG001"],
        "hardware_id": ["HW001"],
        "timestamp": ["2026-09-18 10:00:00"],
        "cpu_utilization_pct": [50.0],
        "ram_utilization_pct": [60.0],
        "temperatura_celsius": [40.0],
        "energia_watts": [300.0],
        "cumple_sla": [True],
    })


def create_use_case():
    """
    Para probar únicamente la transformación no
    necesitamos conectarnos al Excel ni al CSV.
    """

    return ProcessGreenAIDatasetUseCase(
        source=None,
        repository=None,
    )


# ============================================================
# TEST 1
# DATOS CORRECTOS
# ============================================================

def test_valid_data_is_processed():

    use_case = create_use_case()

    hardware = create_valid_hardware()
    logs = create_valid_logs()

    result = use_case._transform(
        hardware,
        logs,
    )

    assert len(result) == 1

    assert (
        result.iloc[0]["hardware_id"]
        == "HW001"
    )

    assert (
        "estimated_power_watts"
        in result.columns
    )

    assert (
        "energia_watts"
        not in result.columns
    )


# ============================================================
# TEST 2
# COLUMNA OBLIGATORIA AUSENTE
# ============================================================

def test_missing_required_column_raises_error():

    use_case = create_use_case()

    hardware = create_valid_hardware()
    logs = create_valid_logs()

    # Eliminamos intencionalmente CPU
    logs = logs.drop(
        columns=["cpu_utilization_pct"]
    )

    with pytest.raises(
        ValueError,
        match="Faltan columnas",
    ):
        use_case._transform(
            hardware,
            logs,
        )


# ============================================================
# TEST 3
# CPU MAYOR A 100
# ============================================================

def test_cpu_above_100_is_rejected():

    use_case = create_use_case()

    hardware = create_valid_hardware()
    logs = create_valid_logs()

    logs.loc[
        0,
        "cpu_utilization_pct"
    ] = 150.0

    result = use_case._transform(
        hardware,
        logs,
    )

    assert len(result) == 0


# ============================================================
# TEST 4
# RAM MAYOR A 100
# ============================================================

def test_ram_above_100_is_rejected():

    use_case = create_use_case()

    hardware = create_valid_hardware()
    logs = create_valid_logs()

    logs.loc[
        0,
        "ram_utilization_pct"
    ] = 125.0

    result = use_case._transform(
        hardware,
        logs,
    )

    assert len(result) == 0


# ============================================================
# TEST 5
# POTENCIA NEGATIVA
# ============================================================

def test_negative_power_is_rejected():

    use_case = create_use_case()

    hardware = create_valid_hardware()
    logs = create_valid_logs()

    logs.loc[
        0,
        "energia_watts"
    ] = -100.0

    result = use_case._transform(
        hardware,
        logs,
    )

    assert len(result) == 0


# ============================================================
# TEST 6
# HARDWARE INEXISTENTE
# ============================================================

def test_unknown_hardware_is_not_joined():

    use_case = create_use_case()

    hardware = create_valid_hardware()
    logs = create_valid_logs()

    # Hardware que no existe en la tabla Hardware
    logs.loc[
        0,
        "hardware_id"
    ] = "HW999"

    result = use_case._transform(
        hardware,
        logs,
    )

    assert len(result) == 0