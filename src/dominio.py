"""Modelo del dominio: el rango ideal de temperatura, humedad y CO2 de un cultivo."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RangoIdeal:
    """Condiciones ideales (inclusivas) para una etapa del cultivo.

    Atributos:
        nombre: etapa del cultivo (por ejemplo, "fructificacion").
        temp_min, temp_max: temperatura en grados Celsius.
        hum_min, hum_max: humedad relativa en porcentaje (0 a 100).
        co2_max: concentracion maxima de CO2 en ppm.
    """

    nombre: str
    temp_min: float
    temp_max: float
    hum_min: float
    hum_max: float
    co2_max: float

    def __post_init__(self):
        valores = (self.temp_min, self.temp_max, self.hum_min, self.hum_max, self.co2_max)
        if not all(math.isfinite(v) for v in valores):
            raise ValueError("Los limites deben ser numeros finitos")
        if self.temp_min >= self.temp_max:
            raise ValueError("temp_min debe ser menor que temp_max")
        if self.hum_min >= self.hum_max:
            raise ValueError("hum_min debe ser menor que hum_max")
        if self.hum_min < 0 or self.hum_max > 100:
            raise ValueError("La humedad debe estar entre 0 y 100")
        if self.co2_max <= 0:
            raise ValueError("co2_max debe ser positivo")

    def temperatura_ok(self, temperatura):
        return self.temp_min <= temperatura <= self.temp_max

    def humedad_ok(self, humedad):
        return self.hum_min <= humedad <= self.hum_max

    def co2_ok(self, co2):
        return co2 <= self.co2_max

    def evaluar(self, temperatura, humedad, co2):
        """Devuelve la lista de problemas (vacia si esta todo en rango)."""
        problemas = []
        if temperatura < self.temp_min:
            problemas.append("temperatura_baja")
        elif temperatura > self.temp_max:
            problemas.append("temperatura_alta")
        if humedad < self.hum_min:
            problemas.append("humedad_baja")
        elif humedad > self.hum_max:
            problemas.append("humedad_alta")
        if co2 > self.co2_max:
            problemas.append("co2_alto")
        return problemas


# Valores de EJEMPLO: deben confirmarse con el productor segun especie y etapa.
RANGOS = {
    "fructificacion": RangoIdeal("fructificacion", 15, 24, 80, 95, 1000),
    "incubacion": RangoIdeal("incubacion", 20, 27, 65, 80, 5000),
}
