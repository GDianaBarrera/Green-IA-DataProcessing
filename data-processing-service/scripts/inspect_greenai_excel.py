from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASET_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "raw"
    / "synthetic_greenai"
    / "BD_GreenAi.xlsx"
)


def main():
    print("=" * 60)
    print("INSPECCIÓN - BD GREEN AI")
    print("=" * 60)

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo:\n{DATASET_PATH}"
        )

    # Abrir el libro de Excel
    excel = pd.ExcelFile(DATASET_PATH)

    print(f"\nArchivo: {DATASET_PATH.name}")

    print("\nHojas encontradas:")
    print(excel.sheet_names)

    # Inspeccionar cada hoja
    for sheet_name in excel.sheet_names:

        print("\n" + "=" * 60)
        print(f"HOJA: {sheet_name}")
        print("=" * 60)

        df = pd.read_excel(
            DATASET_PATH,
            sheet_name=sheet_name
        )

        print(f"Filas: {len(df)}")
        print(f"Columnas: {len(df.columns)}")

        print("\nNombres de columnas:")
        for column in df.columns:
            print(f" - {column}")

        print("\nValores nulos:")
        print(df.isna().sum())

        print("\nDuplicados:")
        print(df.duplicated().sum())

        print("\nTipos de datos:")
        print(df.dtypes)


if __name__ == "__main__":
    main()