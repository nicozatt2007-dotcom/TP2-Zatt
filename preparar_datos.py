"""Prepara la muestra de datos: resume las exportaciones crudas de Mycodo a promedios por hora.

Entrada: tres CSV exportados desde Mycodo (Data -> Export Measurements), con el formato
    timestamp (UTC),<nombre del sensor y la medicion>
    1761114903.805991,18.77
Salida: data/mediciones.csv y data/mediciones.json (contenido equivalente), una fila por hora.

Uso (desde la raiz del proyecto):
    python src/preparar_datos.py --temperatura RUTA.csv --humedad RUTA.csv --co2 RUTA.csv

La hora se pasa de UTC a hora de Argentina (UTC-3, sin horario de verano).
Este script SOLO resume: la validacion y la limpieza las hace la aplicacion (pipeline.py).
Si en una hora falta alguna de las tres variables, el campo queda vacio y la aplicacion
rechaza esa fila registrando el motivo.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

DESPLAZAMIENTO_SEGUNDOS = -3 * 3600          # UTC-3 (Argentina)
ORIGEN = datetime(1970, 1, 1)
CAMPOS = ["sala", "fecha_hora", "temperatura_c", "humedad_pct", "co2_ppm"]


def promedios_por_hora(ruta):
    """Lee un CSV de Mycodo y devuelve {indice_de_hora_local: promedio}."""
    suma, cuenta = defaultdict(float), defaultdict(int)
    with Path(ruta).open(encoding="utf-8", newline="") as archivo:
        lector = csv.reader(archivo)
        next(lector)                                   # encabezado
        for marca, valor in lector:
            if valor.strip() == "":
                continue
            hora = (int(float(marca)) + DESPLAZAMIENTO_SEGUNDOS) // 3600
            suma[hora] += float(valor)
            cuenta[hora] += 1
    return {hora: suma[hora] / cuenta[hora] for hora in suma}


def construir_filas(temperatura, humedad, co2, sala):
    horas = sorted(set(temperatura) | set(humedad) | set(co2))
    filas = []
    for hora in horas:
        texto = (ORIGEN + timedelta(hours=hora)).strftime("%Y-%m-%d %H:%M:%S")
        filas.append({
            "sala": sala,
            "fecha_hora": texto,
            "temperatura_c": round(temperatura[hora], 2) if hora in temperatura else None,
            "humedad_pct": round(humedad[hora], 2) if hora in humedad else None,
            "co2_ppm": round(co2[hora], 1) if hora in co2 else None,
        })
    return filas


def escribir(filas, carpeta):
    carpeta.mkdir(parents=True, exist_ok=True)
    with (carpeta / "mediciones.csv").open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS)
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({k: ("" if v is None else v) for k, v in fila.items()})
    with (carpeta / "mediciones.json").open("w", encoding="utf-8") as f:
        json.dump(filas, f, indent=1, ensure_ascii=False)


def main():
    raiz = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--temperatura", required=True, help="CSV crudo de temperatura")
    parser.add_argument("--humedad", required=True, help="CSV crudo de humedad")
    parser.add_argument("--co2", required=True, help="CSV crudo de CO2")
    parser.add_argument("--sala", default="SALA-01", help="etiqueta de la sala (SALA-##)")
    parser.add_argument("--salida", default=str(raiz / "data"), help="carpeta de salida")
    args = parser.parse_args()

    filas = construir_filas(promedios_por_hora(args.temperatura),
                            promedios_por_hora(args.humedad),
                            promedios_por_hora(args.co2), args.sala)
    escribir(filas, Path(args.salida))
    print(f"Se escribieron {len(filas)} filas horarias en {args.salida}")


if __name__ == "__main__":
    main()
