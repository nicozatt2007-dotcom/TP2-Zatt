"""Flujo de procesamiento: validar -> limpiar -> seleccionar periodo -> resumir -> verificar -> guardar.

Las funciones de limpieza y resumen son puras: no leen ni escriben archivos
y no modifican los datos de entrada.
"""
import csv
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean

from fuentes import ErrorDatos

CAMPOS = ("sala", "fecha_hora", "temperatura_c", "humedad_pct", "co2_ppm")

# Las expresiones regulares validan solo la FORMA del texto.
PATRON_SALA = re.compile(r"SALA-[0-9]{2}")                       # SALA-01, SALA-02, ...
PATRON_FECHA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
PATRON_DIA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")           # para --desde / --hasta

# Limites de plausibilidad (no son los rangos ideales del cultivo).
TEMP_FISICA = (-10.0, 60.0)
CO2_SENSOR = (0.0, 5000.0)          # el MH-Z19B mide hasta 5000 ppm
HUM_SENSOR_MAX = 120.0              # el HTU21D puede informar hasta ~118 % al saturarse


class ErrorVerificacion(Exception):
    """El resultado no cumple una propiedad que deberia cumplir."""


def validar_esquema(filas):
    """Comprueba que haya registros y que existan todas las columnas."""
    if not filas:
        raise ErrorDatos("La entrada no tiene registros")
    presentes = set().union(*(fila.keys() for fila in filas))
    faltantes = [campo for campo in CAMPOS if campo not in presentes]
    if faltantes:
        raise ErrorDatos(f"Faltan columnas obligatorias: {', '.join(faltantes)}")


def _a_numero(valor):
    """Convierte a float finito. Lanza ValueError si falta o no es valido."""
    if valor is None or isinstance(valor, bool):
        raise ValueError("falta o no es numero")
    if isinstance(valor, str) and valor.strip() == "":
        raise ValueError("vacio")
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError("no finito")
    return numero


def _validar_fila(fila):
    """Devuelve (medicion_normalizada, None) o (None, motivo_de_rechazo)."""
    sala = str(fila.get("sala") or "")
    if not PATRON_SALA.fullmatch(sala):
        return None, "sala con formato invalido (se espera SALA-##)"

    texto_fecha = str(fila.get("fecha_hora") or "")
    if not PATRON_FECHA.fullmatch(texto_fecha):
        return None, "fecha_hora con formato invalido"
    try:
        # La regex no sabe de calendario: strptime rechaza 2026-02-30 o 25:00:00.
        fecha_hora = datetime.strptime(texto_fecha, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None, "fecha_hora inexistente en el calendario"

    numeros = {}
    for campo in ("temperatura_c", "humedad_pct", "co2_ppm"):
        try:
            numeros[campo] = _a_numero(fila.get(campo))
        except ValueError:
            return None, f"{campo} falta o no es un numero valido"
    temperatura, humedad, co2 = (numeros["temperatura_c"], numeros["humedad_pct"],
                                 numeros["co2_ppm"])

    if not TEMP_FISICA[0] <= temperatura <= TEMP_FISICA[1]:
        return None, "temperatura_c fuera del rango fisico (-10 a 60)"
    if not 0 <= humedad <= HUM_SENSOR_MAX:
        return None, "humedad_pct fuera del rango del sensor (0 a 120)"
    if not CO2_SENSOR[0] < co2 <= CO2_SENSOR[1]:
        return None, "co2_ppm fuera del rango del sensor (0 a 5000)"

    ajuste = None
    if humedad > 100:
        # Una humedad relativa no puede superar 100 %: es saturacion del sensor.
        # No se descarta la fila: se limita a 100 y se registra el ajuste.
        ajuste = f"humedad_pct {round(humedad, 2)} limitada a 100 (saturacion del sensor)"
        humedad = 100.0

    return {
        "sala": sala,
        "fecha_hora": fecha_hora,
        "fecha": fecha_hora.strftime("%Y-%m-%d"),
        "temperatura_c": temperatura,
        "humedad_pct": humedad,
        "co2_ppm": co2,
        "ajuste": ajuste,
    }, None


def limpiar_mediciones(filas):
    """Separa filas validas y rechazadas (con motivo). No modifica la entrada.

    Si (sala, fecha_hora) aparece mas de una vez, se rechazan TODAS las copias:
    no se elige una arbitrariamente.
    """
    repeticiones = Counter((str(f.get("sala")), str(f.get("fecha_hora"))) for f in filas)
    validos, rechazados = [], []
    for numero, fila in enumerate(filas, start=1):
        if repeticiones[(str(fila.get("sala")), str(fila.get("fecha_hora")))] > 1:
            medicion, motivo = None, "medicion duplicada (misma sala y fecha_hora)"
        else:
            medicion, motivo = _validar_fila(fila)
        if medicion is not None:
            validos.append(medicion)
        else:
            rechazados.append({"fila": numero, "motivo": motivo,
                               **{c: fila.get(c) for c in CAMPOS}})
    return validos, rechazados


def listar_ajustes(validos):
    """Filas que se aceptaron pero con un valor corregido (queda registrado)."""
    return [{"sala": m["sala"],
             "fecha_hora": m["fecha_hora"].strftime("%Y-%m-%d %H:%M:%S"),
             "ajuste": m["ajuste"]} for m in validos if m["ajuste"]]


def seleccionar_periodo(validos, desde=None, hasta=None):
    """Conserva las mediciones entre dos dias (AAAA-MM-DD), ambos inclusivos."""
    fechas = {}
    for nombre, valor in (("desde", desde), ("hasta", hasta)):
        if valor is None:
            continue
        if not PATRON_DIA.fullmatch(str(valor)):
            raise ValueError(f"'{nombre}' debe tener formato AAAA-MM-DD")
        try:
            datetime.strptime(valor, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"'{nombre}' no es una fecha valida: {valor}")
        fechas[nombre] = valor
    if "desde" in fechas and "hasta" in fechas and fechas["desde"] > fechas["hasta"]:
        raise ValueError("'desde' no puede ser posterior a 'hasta'")
    return [m for m in validos
            if ("desde" not in fechas or m["fecha"] >= fechas["desde"])
            and ("hasta" not in fechas or m["fecha"] <= fechas["hasta"])]


def resumir_por_dia_sala(validos, rango, min_mediciones=18):
    """Resumen por (fecha, sala): estadisticas, horas fuera de rango y cobertura."""
    grupos = defaultdict(list)
    for medicion in validos:
        grupos[(medicion["fecha"], medicion["sala"])].append(medicion)

    resumen = []
    for (fecha, sala), items in sorted(grupos.items()):
        temps = [m["temperatura_c"] for m in items]
        hums = [m["humedad_pct"] for m in items]
        co2s = [m["co2_ppm"] for m in items]
        fuera = sum(1 for m in items if rango.evaluar(
            m["temperatura_c"], m["humedad_pct"], m["co2_ppm"]))
        resumen.append({
            "fecha": fecha,
            "sala": sala,
            "mediciones": len(items),
            "temp_media": round(mean(temps), 2),
            "temp_min": round(min(temps), 2),
            "temp_max": round(max(temps), 2),
            "hum_media": round(mean(hums), 2),
            "hum_min": round(min(hums), 2),
            "hum_max": round(max(hums), 2),
            "co2_media": round(mean(co2s), 1),
            "co2_max": round(max(co2s), 1),
            "fuera_de_rango": fuera,
            "pct_en_rango": round(100 * (len(items) - fuera) / len(items), 1),
            "cobertura": "completa" if len(items) >= min_mediciones else "parcial",
        })
    return resumen


def generar_alertas(validos, rango):
    """Lista las mediciones validas que estan fuera del rango ideal."""
    alertas = []
    for m in validos:
        problemas = rango.evaluar(m["temperatura_c"], m["humedad_pct"], m["co2_ppm"])
        if problemas:
            alertas.append({
                "sala": m["sala"],
                "fecha_hora": m["fecha_hora"].strftime("%Y-%m-%d %H:%M:%S"),
                "temperatura_c": round(m["temperatura_c"], 2),
                "humedad_pct": round(m["humedad_pct"], 2),
                "co2_ppm": round(m["co2_ppm"], 1),
                "problemas": ";".join(problemas),
            })
    return alertas


def verificar_resumen(resumen, cantidad_validos):
    """Propiedad: la suma de mediciones del resumen es igual a las consideradas."""
    total = sum(fila["mediciones"] for fila in resumen)
    if total != cantidad_validos:
        raise ErrorVerificacion(
            f"El resumen cuenta {total} mediciones y hay {cantidad_validos} validas"
        )


def ejecutar_pipeline(fuente, rango, min_mediciones=18, desde=None, hasta=None):
    """Lee, valida, limpia, selecciona periodo, resume y verifica. No escribe archivos."""
    entrada = fuente.cargar()
    validar_esquema(entrada)
    validos, rechazados = limpiar_mediciones(entrada)
    if not validos:
        raise ErrorDatos("Ninguna medicion supero la validacion")
    en_periodo = seleccionar_periodo(validos, desde, hasta)
    if not en_periodo:
        raise ErrorDatos("No hay mediciones validas en el periodo solicitado")
    resumen = resumir_por_dia_sala(en_periodo, rango, min_mediciones)
    verificar_resumen(resumen, len(en_periodo))
    ajustes = listar_ajustes(en_periodo)
    return {
        "resumen": resumen,
        "rechazados": rechazados,
        "alertas": generar_alertas(en_periodo, rango),
        "ajustes": ajustes,
        "auditoria": {"entrada": len(entrada), "validos": len(validos),
                      "rechazados": len(rechazados), "en_periodo": len(en_periodo),
                      "ajustados": len(ajustes)},
    }


def _escribir_csv(ruta, filas, columnas):
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)


def guardar_resultados(directorio, resultado):
    """Escribe resumen_diario.csv, alertas.csv, rechazados.csv y ajustes.csv."""
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    resumen = resultado["resumen"]
    _escribir_csv(directorio / "resumen_diario.csv", resumen, list(resumen[0].keys()))
    _escribir_csv(directorio / "alertas.csv", resultado["alertas"],
                  ["sala", "fecha_hora", "temperatura_c", "humedad_pct",
                   "co2_ppm", "problemas"])
    _escribir_csv(directorio / "rechazados.csv", resultado["rechazados"],
                  ["fila", "motivo", *CAMPOS])
    _escribir_csv(directorio / "ajustes.csv", resultado["ajustes"],
                  ["sala", "fecha_hora", "ajuste"])
    return directorio
