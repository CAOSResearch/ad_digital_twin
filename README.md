# Creación de Gemelos Digitales para la Simulación de Alta Fidelidad en Conducción Autónoma

El objetivo principal de este proyecto es integrar las herramientas de Carla para la simulación de alta fidelidad con las herramientas de Sumo para la generación de tráfico realista. El propósito es estudiar, analizar y desarrollar el flujo de trabajo necesario para generar automáticamente, a partir de una ubicación real específica —preferiblemente en España—, un mundo simulado fiel a la realidad (un gemelo digital) en aspectos como las carreteras, la señalización, el tráfico, etc.

Para ello, será necesario contar con conocimientos generales sobre simuladores, herramientas GIS para el tratamiento de datos geográficos y un sistema de cartografía como OpenStreetMap.

# Gemelo Digital — Guía de ejecución

Este repositorio contiene el código necesario para ejecutar el pipeline del gemelo digital urbano desarrollado en el TFG.

## 1. Requisitos

* Windows 10/11 64 bits
* Python 3.12
* CARLA 0.9.16
* SUMO 1.27.1
* Git


## 2. Ejecución

Hay dos recorridos posibles: el de "tráfico sintético" (más rápido, sirve para comprobar que todo el sistema funciona) y el de "tráfico calibrado con datos reales" (el que reproduce el tráfico real de la zona).

### 2.1. Pasos comunes: construir el entorno

Paso 1 — Descargar la cartografía

```bash
python 01_descargar_osm.py --bbox -3.7100 40.4100 -3.6900 40.4300 -o ../data/osm/madrid_centro.osm
```

| Argumento | Descripción |
|---|---|
| `--bbox LON_MIN LAT_MIN LON_MAX LAT_MAX` | Área de estudio en WGS84 (obligatorio) |
| `-o, --output` | Fichero `.osm` de salida |
| `--overpass` | Usa la API de Overpass en vez del exportador estándar. Necesario en zonas densas, ya que el exportador estándar tiene un límite de unos 50 000 nodos |

Paso 2 — Convertir a OpenDRIVE y a red de SUMO

```bash
python 02_osm_a_xodr.py -i ../data/osm/madrid_centro.osm \
    -o ../data/xodr/madrid_centro.xodr \
    --net-output ../data/sumo/madrid_centro.net.xml
```

| Argumento | Descripción |
|---|---|
| `-i, --input` | Fichero `.osm` de entrada (obligatorio) |
| `-o, --output` | Fichero `.xodr` de salida (obligatorio) |
| `--net-output` | Exporta además la red nativa de SUMO (`.net.xml`), necesaria para generar tráfico |
| `--junctions-join-dist` | Distancia máxima (m) para fusionar uniones próximas mal digitalizadas (defecto: 15.0) |
| `--geometry-min-radius` | Radio de giro mínimo (m) antes de corregir la geometría (defecto: 5.0) |
| `--geo-boundary` | Recorta la red a una bounding box concreta |
| `--signal-height` | Altura escrita en el `zOffset` de cada semáforo (defecto: 0.0, para que el poste apoye en el suelo) |

Generar el `.xodr` y el `.net.xml` en la misma llamada garantiza que ambas representaciones de la red sean coherentes entre sí.

Paso 3 — Cargar el mapa en CARLA

Primero hay que arrancar el servidor de CARLA (`CarlaUE4.exe` en Windows) y dejarlo en marcha. Después:

```bash
python 03_cargar_en_carla.py -x ../data/xodr/madrid_centro.xodr
```

| Argumento | Descripción |
|---|---|
| `-x, --xodr` | Fichero `.xodr` a cargar (obligatorio) |
| `--host` / `--port` | Dirección del servidor CARLA (defecto: `127.0.0.1:2000`) |
| `--timeout` | Tiempo máximo de espera en segundos (defecto: 180; generar la malla de una red grande tarda) |

### 2.2. Recorrido A: tráfico sintético

Paso 4 — Generar el tráfico aleatorio

```bash
python 04_generar_trafico_sumo.py -n ../data/sumo/madrid_centro.net.xml \
    -o ../data/sumo/sintetico \
    --end-time 3600 --period 2.5 --seed 42
```

| Argumento | Descripción |
|---|---|
| `-n, --net-file` | Red de SUMO de entrada (obligatorio) |
| `-o, --out-prefix` | Prefijo de salida, sin extensión (obligatorio) |
| `--end-time` | Duración de la simulación en segundos (defecto: 600) |
| `--period` | Segundos entre inserciones de vehículos (defecto: 3.0; menor valor = más tráfico) |
| `--seed` | Semilla aleatoria, para poder reproducir la misma simulación (defecto: 42) |

Genera `sintetico.rou.xml` y `sintetico.sumocfg`, listos para simular.

### 2.3. Recorrido B: tráfico calibrado con datos reales

Paso 4 — Descargar y transformar los datos de aforo

Descarga de [datos.madrid.es](https://datos.madrid.es/) los ficheros `Datos_estaciones.csv` (ubicación de las estaciones) y `Datos_completos.csv` (intensidades horarias), y conviértelos al formato canónico del sistema:

```bash
python 06_transformar_datos_trafico.py \
    --estaciones ../data/madrid/Datos_estaciones.csv \
    --aforos ../data/madrid/Datos_completos.csv \
    -o ../data/canonico
```

Produce `estaciones.csv` y `aforos.csv` en el directorio indicado.

Paso 5 — Calibrar el tráfico contra los aforos reales

```bash
python 07_generar_trafico_desde_aforos.py \
    -n ../data/sumo/madrid_centro.net.xml \
    --estaciones ../data/canonico/estaciones.csv \
    --aforos ../data/canonico/aforos.csv \
    --date 2025-01-15 --hour-start 8 --hour-end 9 \
    --scale 0.1 \
    -o ../data/sumo/real_08_09
```

| Argumento | Descripción |
|---|---|
| `-n, --net-file` | Red de SUMO (obligatorio) |
| `--estaciones` / `--aforos` | Ficheros canónicos del paso anterior (obligatorios) |
| `--date` | Fecha a reproducir, en formato `AAAA-MM-DD` (obligatorio) |
| `--hour-start` / `--hour-end` | Franja horaria; la hora final es exclusiva (obligatorios) |
| `--scale` | Factor de escala sobre los conteos reales (defecto: 0.1). Con `1.0` se reproduce la intensidad real completa, inviable de renderizar en tiempo real en un equipo de sobremesa |
| `--radius` | Radio (m) de búsqueda de arcos alrededor de cada estación (defecto: 60) |
| `--max-bearing-diff` | Diferencia angular máxima (grados) entre el sentido medido y el del arco, para no asignar la estación al sentido contrario (defecto: 60) |
| `--candidates` | Número de rutas candidatas a generar antes del muestreo (defecto: 4000) |
| `-o, --out-prefix` | Prefijo de salida (obligatorio) |

### 2.4. Ejecutar la simulación

Opción 1 — Co-simulación CARLA–SUMO (visual)

Con el servidor de CARLA en marcha y el mapa ya cargado (paso 3):

```bash
python 05_ejecutar_cosimulacion_trafico.py ../data/sumo/real_08_09.sumocfg
```

| Argumento | Descripción |
|---|---|
| `sumo_cfg_file` | Fichero `.sumocfg` a simular (argumento posicional obligatorio) |
| `--carla-host` / `--carla-port` | Dirección del servidor CARLA (defecto: `127.0.0.1:2000`) |
| `--step-length` | Paso temporal de la co-simulación en segundos (defecto: 0.05) |
| `--tls-manager` | Quién gestiona los semáforos: `sumo`, `carla` o `none` (defecto: `sumo`) |
| `--duration` | Detiene la co-simulación tras N segundos reales (útil para pruebas) |

Se detiene con `Ctrl+C`.

Opción 2 — Solo SUMO, para generar las salidas de datos

```bash
python 08_ejecutar_salidas_simulacion.py -c ../data/sumo/real_08_09.sumocfg \
    -o ../data/salidas/real_08_09
```

Genera las tres salidas del gemelo digital:

- `fcd.xml` — nivel microscópico: posición, velocidad y carril de cada vehículo (muestreado cada 10 s por defecto, ajustable con `--fcd-period`)
- `edgedata.xml` — nivel mesoscópico: estadísticos agregados por arco
- `resumen_macroscopico.json` — nivel macroscópico: velocidad media, duración media del viaje, tiempo de espera y porcentaje de viajes completados

### 2.5. Validar frente a los datos reales

Solo aplicable al recorrido B (tráfico calibrado):

```bash
python 09_validar_contra_datos_reales.py \
    -n ../data/sumo/madrid_centro.net.xml \
    --edgedata ../data/salidas/real_08_09/edgedata.xml \
    --estaciones ../data/canonico/estaciones.csv \
    --aforos ../data/canonico/aforos.csv \
    --date 2025-01-15 --hour-start 8 --hour-end 9 \
    --scale 0.1 \
    -o ../data/validacion/real_08_09.csv
```

El valor de `--scale` debe ser el mismo que se usó en el paso de calibración (script 07), ya que los conteos simulados se expanden por el inverso de esa escala antes de compararse con los reales.

Produce un CSV con la comparación estación a estación (conteo real, conteo simulado, GEH y error relativo) y un `_resumen.json` con los agregados: GEH medio, GEH máximo, porcentaje de estaciones con GEH < 5, error relativo medio y correlación de Pearson.

Un GEH por debajo de 5 en un arco individual es el criterio de aceptación habitual en ingeniería de tráfico.
