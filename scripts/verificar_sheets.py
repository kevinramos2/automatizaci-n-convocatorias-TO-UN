"""Verifica la conexión con Google Sheets y crea las 5 hojas si no existen.

Uso: python scripts/verificar_sheets.py <SPREADSHEET_ID>
Requiere service-account.json en la raíz del proyecto (ver instrucciones de configuración).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.sheets_client import abrir_spreadsheet, asegurar_hojas, autenticar, correo_cuenta_de_servicio

RAIZ = Path(__file__).parent.parent
CREDENCIALES = RAIZ / "service-account.json"


def main():
    if len(sys.argv) != 2:
        print("Uso: python scripts/verificar_sheets.py <SPREADSHEET_ID>")
        sys.exit(1)
    spreadsheet_id = sys.argv[1]

    if not CREDENCIALES.exists():
        print(f"No se encontró {CREDENCIALES}. Sigue los pasos de configuración primero.")
        sys.exit(1)

    print(f"Cuenta de servicio: {correo_cuenta_de_servicio(str(CREDENCIALES))}")
    print("(si no compartiste el Sheet con este correo como Editor, el siguiente paso fallará)\n")

    client = autenticar(str(CREDENCIALES))
    spreadsheet = abrir_spreadsheet(client, spreadsheet_id)
    print(f"Conectado a: {spreadsheet.title}")

    hojas = asegurar_hojas(spreadsheet)
    print("\nHojas listas:")
    for nombre, ws in hojas.items():
        print(f"  - {nombre} ({len(ws.row_values(1))} columnas)")

    print(f"\nURL: {spreadsheet.url}")


if __name__ == "__main__":
    main()
