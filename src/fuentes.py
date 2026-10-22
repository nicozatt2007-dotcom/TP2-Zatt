"""Fuentes de datos: una interfaz comun y dos lectores (CSV y JSON).

Ambos lectores devuelven una lista de diccionarios, uno por medicion.
El resto de la aplicacion no necesita saber de que formato vienen los datos.
"""
import csv
import json
from abc import ABC, abstractmethod
from pathlib import Path


class ErrorDatos(Exception):
    """El archivo de entrada no cumple la estructura esperada."""


class FuenteDatos(ABC):
    """Contrato comun: cargar() devuelve una lista de diccionarios."""

    def __init__(self, ruta):
        self._ruta = Path(ruta)

    @property
    def ruta(self):
        return self._ruta

    @abstractmethod
    def cargar(self):
        """Lee el archivo y devuelve una lista de diccionarios."""
        raise NotImplementedError


class FuenteCSV(FuenteDatos):
    """Lee un CSV con encabezados. Todos los valores llegan como texto."""

    def cargar(self):
        # Si el archivo no existe, open() lanza FileNotFoundError (no se oculta).
        with self._ruta.open(encoding="utf-8", newline="") as archivo:
            return [dict(fila) for fila in csv.DictReader(archivo)]


class FuenteJSON(FuenteDatos):
    """Lee un JSON cuya estructura es una lista de objetos (uno por fila)."""

    def cargar(self):
        with self._ruta.open(encoding="utf-8") as archivo:
            try:
                contenido = json.load(archivo)
            except json.JSONDecodeError as error:
                raise ErrorDatos(f"JSON mal formado en {self._ruta.name}: {error}")
        if not isinstance(contenido, list) or not all(
            isinstance(fila, dict) for fila in contenido
        ):
            raise ErrorDatos(
                "Se esperaba una lista de objetos JSON (uno por medicion)."
            )
        return contenido
