import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dominio import RangoIdeal  # noqa: E402


class PruebasRangoIdeal(unittest.TestCase):
    def setUp(self):
        self.rango = RangoIdeal("fructificacion", 15, 24, 80, 95, 1000)

    def test_medicion_en_rango(self):
        self.assertEqual(self.rango.evaluar(20, 85, 600), [])

    def test_limites_son_inclusivos(self):
        self.assertTrue(self.rango.temperatura_ok(24))
        self.assertTrue(self.rango.humedad_ok(80))
        self.assertTrue(self.rango.co2_ok(1000))
        self.assertFalse(self.rango.temperatura_ok(24.1))
        self.assertFalse(self.rango.humedad_ok(79.9))
        self.assertFalse(self.rango.co2_ok(1000.1))

    def test_detecta_cada_problema(self):
        self.assertEqual(self.rango.evaluar(26, 85, 600), ["temperatura_alta"])
        self.assertEqual(self.rango.evaluar(10, 85, 600), ["temperatura_baja"])
        self.assertEqual(self.rango.evaluar(20, 70, 600), ["humedad_baja"])
        self.assertEqual(self.rango.evaluar(20, 85, 1500), ["co2_alto"])
        self.assertEqual(self.rango.evaluar(26, 99, 1500),
                         ["temperatura_alta", "humedad_alta", "co2_alto"])

    def test_rangos_invalidos(self):
        with self.assertRaises(ValueError):
            RangoIdeal("x", 30, 20, 80, 95, 1000)         # temp_min >= temp_max
        with self.assertRaises(ValueError):
            RangoIdeal("x", 15, 24, 80, 120, 1000)        # humedad > 100
        with self.assertRaises(ValueError):
            RangoIdeal("x", 15, float("nan"), 80, 95, 1000)
        with self.assertRaises(ValueError):
            RangoIdeal("x", 15, 24, 80, 95, 0)            # co2_max no positivo


if __name__ == "__main__":
    unittest.main()
