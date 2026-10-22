import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from fuentes import ErrorDatos, FuenteCSV, FuenteDatos, FuenteJSON  # noqa: E402


class PruebasFuentes(unittest.TestCase):
    def test_csv_caso_normal(self):
        filas = FuenteCSV(RAIZ / "data" / "mediciones.csv").cargar()
        self.assertEqual(len(filas), 8715)
        self.assertIn("co2_ppm", filas[0])

    def test_json_caso_normal(self):
        filas = FuenteJSON(RAIZ / "data" / "mediciones.json").cargar()
        self.assertEqual(len(filas), 8715)

    def test_archivo_inexistente_no_se_oculta(self):
        with self.assertRaises(FileNotFoundError):
            FuenteCSV(RAIZ / "data" / "no_existe.csv").cargar()

    def test_json_mal_formado(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "roto.json"
            ruta.write_text("[{'a': 1", encoding="utf-8")
            with self.assertRaises(ErrorDatos):
                FuenteJSON(ruta).cargar()

    def test_json_con_estructura_incorrecta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "objeto.json"
            ruta.write_text(json.dumps({"mediciones": []}), encoding="utf-8")
            with self.assertRaises(ErrorDatos):
                FuenteJSON(ruta).cargar()

    def test_la_clase_base_es_abstracta(self):
        with self.assertRaises(TypeError):
            FuenteDatos("x")


if __name__ == "__main__":
    unittest.main()
