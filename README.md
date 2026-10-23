#Monitor de temperatura, humedad y CO2 para un cultivo de hongos

**Autor:** Nicolas Santiago Zatt Reyt &nbsp;|&nbsp; Programacion Orientada a Datos - UCA - TP2 individual

#Problema, usuario y solucion
Un microemprendimiento familiar produce hongos comestibles y registra la temperatura, la humedad y el CO2
de su sala con sensores conectados a un Raspberry Pi. Son millones de lecturas: revisarlas a mano para saber
cuantas horas el cultivo estuvo en condiciones ideales es inviable.

**Usuario:** el productor. **Solucion:** una aplicacion de consola que lee las mediciones horarias (CSV o
JSON), valida cada fila, descarta o corrige lo que corresponda dejando todo registrado, y genera un resumen
por dia, una lista de alertas (horas fuera del rango ideal) y los archivos de rechazos y ajustes.

**Alcance de la primera version:** *monitorea y alerta* sobre datos ya registrados. No lee sensores en vivo
ni controla equipos (humidificador, ventilacion); eso queda fuera.

#Funcionalidades y modo de uso
- Lee `.csv` o `.json` (se elige por extension).
- Valida cada medicion y registra las rechazadas con su motivo y las corregidas con su ajuste.
- Permite elegir un periodo (`--desde`, `--hasta`) y la etapa del cultivo (`fructificacion` o `incubacion`).
- Resume por dia: horas con dato, medias, minimos y maximos de temperatura, humedad y CO2, horas fuera de
  rango, porcentaje en rango y cobertura (`completa` si tiene al menos 18 horas con dato, `parcial` si no).

#Datos
Mediciones reales de un ano (22/10/2025 al 22/10/2026), resumidas a promedios por hora: 8.715 filas.
Fuente, sensores, licencia, unidad de analisis (una fila = una hora), variables y limitaciones en
[`data/README.md`](data/README.md). Los CSV crudos (118 MB) no se incluyen; ahi se explica como regenerar la
muestra con `src/preparar_datos.py`.

#Instalacion y ejecucion
Requiere Python 3.9 o superior. No hay dependencias externas.

```bash
git clone URL_DEL_REPOSITORIO
cd TP2-Zatt
python src/main.py                                  # usa data/mediciones.csv
python src/main.py --entrada data/mediciones.json   # mismo resultado desde JSON
python src/main.py --desde 2026-09-01 --hasta 2026-09-30
python src/main.py --etapa incubacion --mostrar 20
python src/main.py --help
```
En macOS/Linux puede ser `python3`. Los resultados se guardan en `outputs/`.

#Pruebas
```bash
python -m unittest discover -s tests -v
```
Cubren: caso normal, entradas invalidas (14 casos), limites, duplicados, humedad saturada, esquema incompleto,
archivo inexistente, JSON mal formado, periodos invalidos, no modificacion de la entrada y las propiedades
*entrada = validas + rechazadas*, *suma del resumen = horas del periodo* y *CSV y JSON dan el mismo resultado*.

#Organizacion del codigo
| Archivo | Responsabilidad |
|---|---|
| `src/fuentes.py` | `FuenteDatos` (clase abstracta), `FuenteCSV`, `FuenteJSON`, `ErrorDatos` |
| `src/dominio.py` | Clase `RangoIdeal` (limites de temperatura, humedad y CO2 y su evaluacion) |
| `src/pipeline.py` | Validacion, limpieza (regex), seleccion de periodo, resumen, alertas, verificacion y guardado |
| `src/main.py` | Argumentos de consola y coordinacion del flujo |
| `src/preparar_datos.py` | Resume las exportaciones crudas de Mycodo a promedios por hora |
| `tests/` | Pruebas con `unittest` |

Flujo: `leer -> validar esquema -> limpiar -> seleccionar periodo -> resumir -> verificar -> guardar`.
La lectura y escritura (efectos secundarios) estan en los bordes; limpiar y resumir son funciones puras que no
modifican la entrada.

**Por que esta jerarquia:** `FuenteCSV` y `FuenteJSON` heredan de `FuenteDatos` y ambas devuelven una lista de
diccionarios, asi el resto del programa no depende del formato. `RangoIdeal` agrupa los limites y la regla de
evaluacion en un solo lugar.

**Expresiones regulares:** `SALA-[0-9]{2}` (sala), `AAAA-MM-DD HH:MM:SS` (fecha y hora) y `AAAA-MM-DD`
(argumentos `--desde` y `--hasta`). Validan solo la *forma*; que la fecha exista en el calendario
(2026-02-30, 25:00:00) lo comprueba `datetime.strptime`.

#Decisiones de limpieza
Cada fila rechazada queda en `outputs/rechazados.csv` con su motivo:
1. Formato invalido de sala o fecha (regex) o fecha inexistente en el calendario.
2. Falta alguna de las tres variables, no es numerica, es infinita o NaN. Se exigen las tres: una hora con
   solo CO2 no permite evaluar el cultivo.
3. Fuera del rango del sensor: temperatura de -10 a 60 C, humedad de 0 a 120 %, CO2 de 0 a 5000 ppm.
4. Misma sala y fecha_hora repetidas: se rechazan **todas** las copias (no se elige una arbitrariamente).

**Humedad mayor a 100 %:** el sensor HTU21D informa hasta ~118 % cuando se satura. Una humedad relativa no
puede superar 100 %, pero descartar esas horas (566, el 8 % de las validas) eliminaria justo los momentos
de mayor humedad. Se **limita a 100** y cada correccion queda en `outputs/ajustes.csv`.

Una medicion fuera del rango *ideal* del cultivo **no se descarta**: es un dato valido y es lo que debe
generar una alerta. Tampoco se eliminan los picos de CO2 (hasta 4.673 ppm): pueden ser reales.

#Ejemplo de resultado
`python src/main.py --desde 2026-09-01 --hasta 2026-09-30 --mostrar 6`
```
Etapa: fructificacion | filas de entrada: 8715 | validas: 6841 | rechazadas: 1874 | ajustadas: 72
Periodo analizado: 2026-09-01 a 2026-09-29 (28 dias, 637 horas)
Horas en rango ideal: 405 de 637 (63.6 %)

fecha      sala      horas    temp     hum     co2  fuera   % ok  cobertura
2026-09-23 SALA-01      24   19.35   91.60   516.2      0  100.0  completa
2026-09-24 SALA-01      20   20.23   94.25   519.3      5   75.0  completa
2026-09-26 SALA-01      10   20.05   93.89   536.9      4   60.0  parcial
2026-09-27 SALA-01      24   20.61   99.86   498.1     24    0.0  completa
2026-09-28 SALA-01      24   21.21  100.00   535.1     24    0.0  completa
2026-09-29 SALA-01       7   21.14  100.00   553.9      7    0.0  parcial
```
Las 1.874 filas rechazadas del ano completo se deben a la falta de temperatura y humedad (huecos del sensor).

#Interpretacion y limitaciones
- Con los rangos de ejemplo (15-24 C, 80-95 % de humedad, CO2 hasta 1000 ppm), solo el 28,9 % de las horas
  del ano estuvo en rango ideal. La causa principal es la temperatura alta (2.835 alertas) y se concentra
  entre noviembre y marzo, cuando casi ninguna hora esta en rango; desde abril mejora (43 % a 64 % en mayo-septiembre; en los
  meses siguientes).
- Los dias `27` y `28` de septiembre muestran 0 % en rango con temperatura normal: la humedad quedo saturada
  (100 %) y supera el maximo de 95 %. Conviene revisar si ese maximo es el adecuado.
- Un dia `parcial` (pocas horas con dato) no permite concluir sobre ese dia.
- Los rangos ideales de `dominio.py` son **valores de ejemplo**: deben confirmarse con el productor segun
  especie y etapa, que ademas varia a lo largo del ano.
- Una sola sala y un solo punto de medicion; el promedio horario oculta variaciones internas.
- No lee sensores en vivo ni controla equipos.
