import copy
import math
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from dominio import RangoIdeal  # noqa: E402
from fuentes import ErrorDatos, FuenteCSV, FuenteJSON  # noqa: E402
from pipeline import (ErrorVerificacion, ejecutar_pipeline, generar_alertas,  # noqa: E402
                      limpiar_mediciones, listar_ajustes, resumir_por_dia_sala,
                      seleccionar_periodo, validar_esquema, verificar_resumen)

RANGO = RangoIdeal("fructificacion", 15, 24, 80, 95, 1000)
CSV = RAIZ / "data" / "mediciones.csv"
JSON = RAIZ / "data" / "mediciones.json"


def fila(sala="SALA-01", fecha="2026-10-01 08:00:00", t=20.0, h=85.0, c=600.0):
    return {"sala": sala, "fecha_hora": fecha, "temperatura_c": t,
            "humedad_pct": h, "co2_ppm": c}


class PruebasLimpieza(unittest.TestCase):
    def test_caso_normal(self):
        validos, rechazados = limpiar_mediciones(
            [fila(), fila(fecha="2026-10-01 09:00:00", t="21.5")])
        self.assertEqual(len(validos), 2)
        self.assertEqual(rechazados, [])
        self.assertEqual(validos[1]["temperatura_c"], 21.5)   # texto -> numero

    def test_entradas_invalidas_con_motivo(self):
        casos = {
            "sala": fila(sala="X1"),
            "formato fecha": fila(fecha="01/10/2026"),
            "calendario": fila(fecha="2026-02-30 10:00:00"),
            "hora imposible": fila(fecha="2026-10-01 25:00:00"),
            "no numero": fila(t="abc"),
            "falta humedad": fila(h=None),
            "falta co2": fila(c=""),
            "infinito": fila(t=float("inf")),
            "nan": fila(h=float("nan")),
            "temperatura": fila(t=75),
            "humedad negativa": fila(h=-1),
            "humedad imposible": fila(h=120.1),
            "co2 cero": fila(c=0),
            "co2 excesivo": fila(c=6000),
        }
        for nombre, caso in casos.items():
            with self.subTest(nombre):
                validos, rechazados = limpiar_mediciones([caso])
                self.assertEqual(validos, [])
                self.assertEqual(len(rechazados), 1)
                self.assertTrue(rechazados[0]["motivo"])

    def test_humedad_sobre_100_se_ajusta_y_se_registra(self):
        validos, rechazados = limpiar_mediciones([fila(h=103.4)])
        self.assertEqual(rechazados, [])
        self.assertEqual(validos[0]["humedad_pct"], 100.0)
        ajustes = listar_ajustes(validos)
        self.assertEqual(len(ajustes), 1)
        self.assertIn("103.4", ajustes[0]["ajuste"])

    def test_limites_de_humedad_validos(self):
        validos, _ = limpiar_mediciones(
            [fila(h=0), fila(fecha="2026-10-01 09:00:00", h=100),
             fila(fecha="2026-10-01 10:00:00", h=120)])
        self.assertEqual(len(validos), 3)

    def test_duplicados_se_rechazan_todos(self):
        validos, rechazados = limpiar_mediciones(
            [fila(), fila(t=22), fila(fecha="2026-10-01 09:00:00")])
        self.assertEqual(len(validos), 1)
        self.assertEqual(len(rechazados), 2)

    def test_conservacion_entrada_igual_validos_mas_rechazados(self):
        entrada = FuenteCSV(CSV).cargar()
        validos, rechazados = limpiar_mediciones(entrada)
        self.assertEqual(len(entrada), len(validos) + len(rechazados))

    def test_no_modifica_la_entrada(self):
        entrada = [fila(h=105), fila(fecha="2026-10-01 09:00:00", t="abc")]
        copia = copy.deepcopy(entrada)
        limpiar_mediciones(entrada)
        self.assertEqual(entrada, copia)


class PruebasEsquemaYPeriodo(unittest.TestCase):
    def test_entrada_vacia(self):
        with self.assertRaises(ErrorDatos):
            validar_esquema([])

    def test_columna_faltante(self):
        with self.assertRaises(ErrorDatos):
            validar_esquema([{"sala": "SALA-01", "fecha_hora": "2026-10-01 08:00:00"}])

    def test_periodo_inclusivo(self):
        validos, _ = limpiar_mediciones(
            [fila(fecha=f"2026-10-0{d} 08:00:00") for d in (1, 2, 3, 4)])
        sel = seleccionar_periodo(validos, "2026-10-02", "2026-10-03")
        self.assertEqual([m["fecha"] for m in sel], ["2026-10-02", "2026-10-03"])

    def test_periodo_invalido(self):
        validos, _ = limpiar_mediciones([fila()])
        for desde, hasta in (("01/10/2026", None), ("2026-02-30", None),
                             ("2026-10-05", "2026-10-01")):
            with self.subTest(desde=desde, hasta=hasta):
                with self.assertRaises(ValueError):
                    seleccionar_periodo(validos, desde, hasta)


class PruebasResumen(unittest.TestCase):
    def test_resumen_con_valores_conocidos(self):
        validos, _ = limpiar_mediciones([
            fila(fecha="2026-10-01 08:00:00", t=20, h=80, c=500),
            fila(fecha="2026-10-01 09:00:00", t=22, h=90, c=700),
            fila(fecha="2026-10-01 10:00:00", t=30, h=85, c=600),   # temperatura alta
        ])
        resumen = resumir_por_dia_sala(validos, RANGO, min_mediciones=3)
        self.assertEqual(len(resumen), 1)
        r = resumen[0]
        self.assertEqual(r["mediciones"], 3)
        self.assertTrue(math.isclose(r["temp_media"], 24.0))
        self.assertTrue(math.isclose(r["hum_media"], 85.0))
        self.assertTrue(math.isclose(r["co2_media"], 600.0))
        self.assertEqual(r["fuera_de_rango"], 1)
        self.assertEqual(r["cobertura"], "completa")

    def test_cobertura_parcial(self):
        validos, _ = limpiar_mediciones([fila()])
        self.assertEqual(resumir_por_dia_sala(validos, RANGO)[0]["cobertura"], "parcial")

    def test_alertas_solo_fuera_de_rango(self):
        validos, _ = limpiar_mediciones(
            [fila(), fila(fecha="2026-10-01 09:00:00", c=1500)])
        alertas = generar_alertas(validos, RANGO)
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]["problemas"], "co2_alto")

    def test_verificacion_detecta_conteos_incoherentes(self):
        validos, _ = limpiar_mediciones([fila()])
        with self.assertRaises(ErrorVerificacion):
            verificar_resumen(resumir_por_dia_sala(validos, RANGO), cantidad_validos=5)


class PruebasFlujoCompleto(unittest.TestCase):
    def test_csv_y_json_equivalentes(self):
        a = ejecutar_pipeline(FuenteCSV(CSV), RANGO)
        b = ejecutar_pipeline(FuenteJSON(JSON), RANGO)
        self.assertEqual(a["resumen"], b["resumen"])
        self.assertEqual(a["auditoria"], b["auditoria"])
        self.assertEqual(a["alertas"], b["alertas"])
        # En los rechazados el CSV conserva texto y el JSON numeros: se comparan fila y motivo.
        self.assertEqual([(r["fila"], r["motivo"]) for r in a["rechazados"]],
                         [(r["fila"], r["motivo"]) for r in b["rechazados"]])

    def test_auditoria_de_los_datos_reales(self):
        r = ejecutar_pipeline(FuenteCSV(CSV), RANGO)
        self.assertEqual(r["auditoria"], {"entrada": 8715, "validos": 6841,
                                          "rechazados": 1874, "en_periodo": 6841,
                                          "ajustados": 566})

    def test_resumen_suma_las_mediciones_del_periodo(self):
        r = ejecutar_pipeline(FuenteCSV(CSV), RANGO, desde="2026-09-01", hasta="2026-09-30")
        total = sum(f["mediciones"] for f in r["resumen"])
        self.assertEqual(total, r["auditoria"]["en_periodo"])
        self.assertTrue(all("2026-09-01" <= f["fecha"] <= "2026-09-30"
                            for f in r["resumen"]))

    def test_periodo_sin_datos(self):
        with self.assertRaises(ErrorDatos):
            ejecutar_pipeline(FuenteCSV(CSV), RANGO, desde="2030-01-01")

    def test_es_reproducible(self):
        self.assertEqual(ejecutar_pipeline(FuenteCSV(CSV), RANGO),
                         ejecutar_pipeline(FuenteCSV(CSV), RANGO))


if __name__ == "__main__":
    unittest.main()
