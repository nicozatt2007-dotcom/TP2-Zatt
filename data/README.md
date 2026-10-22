# Datos

Mediciones **reales** de temperatura, humedad y CO2 de un cultivo de hongos comestibles de un
microemprendimiento familiar, registradas con un Raspberry Pi y el software
[Mycodo](https://kylegabriel.com/projects/).

## Fuente y procedencia
- **Sensores:** HTU21D (temperatura y humedad relativa) y MH-Z19B (CO2).
- **Origen:** exportaciones CSV de Mycodo (*Data -> Export Measurements*): una lectura de temperatura y
  humedad cada ~15 s y una de CO2 cada ~60 s.
- **Responsable:** el productor (datos propios, no sensibles; publicados con su autorizacion).
- **Periodo:** 22/10/2025 al 22/10/2026. **Fecha de consulta/exportacion:** 22/10/2026.
- **Licencia/condiciones:** datos propios del emprendimiento, de uso libre para este trabajo.

## Como se obtuvo la muestra de este repositorio
Los CSV crudos pesan unos 118 MB y mas de 1,6 millones de filas, asi que **no se incluyen**. Se resumieron a
**promedios por hora** con:

```bash
python src/preparar_datos.py --temperatura RUTA_temp.csv --humedad RUTA_hum.csv --co2 RUTA_co2.csv
```
Esto genera `mediciones.csv` y `mediciones.json` (contenido equivalente). La hora se paso de UTC a hora de
Argentina (UTC-3). El script solo resume: la validacion y limpieza las hace la aplicacion.

## Unidad de analisis
Cada fila es **el promedio de una hora** de una sala.

## Variables
| Campo | Descripcion |
|---|---|
| `sala` | Sala de cultivo, formato `SALA-##` (etiqueta asignada al preparar los datos) |
| `fecha_hora` | Inicio de la hora, `AAAA-MM-DD HH:MM:SS`, hora de Argentina |
| `temperatura_c` | Temperatura media de la hora, en grados Celsius |
| `humedad_pct` | Humedad relativa media de la hora, en % |
| `co2_ppm` | Concentracion media de CO2 de la hora, en ppm |

## Contenido
8.715 filas horarias. En 1.874 horas faltan temperatura y humedad (el sensor HTU21D estuvo sin registrar,
por ejemplo unas 550 horas entre octubre y noviembre de 2025 y unas 850 en abril de 2026); en esas horas el
CO2 si tiene dato y la fila queda vacia en las otras dos columnas.

## Limitaciones
- Una sola sala y un solo punto de medicion: no representa todo el cultivo.
- El HTU21D informa humedad por encima de 100 % cuando se satura (566 horas, maximo 117,6 %).
- El promedio horario oculta variaciones dentro de la hora.
- Se desconoce la especie y la etapa del cultivo en cada momento; los rangos ideales usados son de ejemplo.
