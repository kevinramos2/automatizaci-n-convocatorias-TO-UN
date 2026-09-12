"""Aplica estilos (encabezados, anchos de columna, ajuste de texto, formato

condicional por color) a las 5 hojas del Google Sheet. Solo llama a la API de
Google (gratuita) — no toca la API de Claude.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from pipeline.esquema_sheets import TODAS_LAS_HOJAS
from pipeline.sheets_client import abrir_spreadsheet, autenticar
from pipeline.sheets_estilos import aplicar_estilos_basicos, aplicar_estilos_maestro

RAIZ = Path(__file__).parent.parent


def main():
    client = autenticar(str(RAIZ / "service-account.json"))
    spreadsheet = abrir_spreadsheet(client, os.environ["GOOGLE_SHEETS_SPREADSHEET_ID"])

    for nombre_hoja, esquema in TODAS_LAS_HOJAS.items():
        ws = spreadsheet.worksheet(nombre_hoja)
        if nombre_hoja == "Maestro":
            aplicar_estilos_maestro(ws, esquema)
        else:
            aplicar_estilos_basicos(ws, esquema)
        print(f"Estilos aplicados: {nombre_hoja}")

    print(f"\nListo: {spreadsheet.url}")


if __name__ == "__main__":
    main()
