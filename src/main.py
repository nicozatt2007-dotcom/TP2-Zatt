"""Punto de entrada: monitoreo de temperatura, humedad y CO2 de un cultivo de hongos.

Ejemplos (desde la raiz del proyecto):
    python src/main.py
    python src/main.py --entrada data/mediciones.json --etapa incubacion
    python src/main.py --desde 2026-09-01 --hasta 2026-09-30
"""
import argparse
import sys
from pathlib import Path

from dominio import RANGOS
from fuentes import ErrorDatos, FuenteCSV, FuenteJSON
from pipeline import ejecutar_pipeline, guardar_resultados

RAIZ = Path(__file__).resolve().parents[1]
FUENTES = {".csv": FuenteCSV, ".json": FuenteJSON}


def crear_fuente(ruta):
    """Elige la clase concreta segun la extension del archivo."""
    extension = Path(ruta).suffix.lower()
    if extension not in FUENTES:
        raise ErrorDatos(f"Formato no soportado: '{extension}' (use .csv o .json)")
    return FUENTES[extension](ruta)


def leer_argumentos():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--entrada", default=str(RAIZ / "data" / "mediciones.csv"),
                        help="archivo .csv o .json con las mediciones")
    parser.add_argument("--salida", default=str(RAIZ / "outputs"),
                        help="carpeta donde se guardan los resultados")
    parser.add_argument("--etapa", choices=sorted(RANGOS), default="fructificacion",
                        help="etapa del cultivo (define el rango ideal)")
    parser.add_argument("--desde", help="primer dia a analizar (AAAA-MM-DD)")
    parser.add_argument("--hasta", help="ultimo dia a analizar (AAAA-MM-DD)")
    parser.add_argument("--min-mediciones", type=int, default=18,
                        help="minimo de mediciones horarias por dia para cobertura completa")
    parser.add_argument("--mostrar", type=int, default=10,
                        help="cantidad de dias recientes que se muestran en pantalla")
    return parser.parse_args()


def mostrar_resumen(resumen, cantidad):
    print(f"{'fecha':<11}{'sala':<9}{'horas':>6}{'temp':>8}{'hum':>8}{'co2':>8}"
          f"{'fuera':>7}{'% ok':>7}  cobertura")
    for f in resumen[-cantidad:]:
        print(f"{f['fecha']:<11}{f['sala']:<9}{f['mediciones']:>6}"
              f"{f['temp_media']:>8.2f}{f['hum_media']:>8.2f}{f['co2_media']:>8.1f}"
              f"{f['fuera_de_rango']:>7}{f['pct_en_rango']:>7.1f}  {f['cobertura']}")


def main():
    args = leer_argumentos()
    try:
        fuente = crear_fuente(args.entrada)
        resultado = ejecutar_pipeline(fuente, RANGOS[args.etapa], args.min_mediciones,
                                      args.desde, args.hasta)
    except (FileNotFoundError, ErrorDatos, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    carpeta = guardar_resultados(args.salida, resultado)
    a, resumen = resultado["auditoria"], resultado["resumen"]
    horas = sum(f["mediciones"] for f in resumen)
    fuera = sum(f["fuera_de_rango"] for f in resumen)
    print(f"Etapa: {args.etapa} | filas de entrada: {a['entrada']} | validas: {a['validos']} "
          f"| rechazadas: {a['rechazados']} | ajustadas: {a['ajustados']}")
    print(f"Periodo analizado: {resumen[0]['fecha']} a {resumen[-1]['fecha']} "
          f"({len(resumen)} dias, {horas} horas)")
    print(f"Horas en rango ideal: {horas - fuera} de {horas} "
          f"({100 * (horas - fuera) / horas:.1f} %)\n")
    mostrar_resumen(resumen, args.mostrar)
    print(f"\nResultados guardados en: {carpeta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
