import math
import os
import pathlib
import shutil


# Lee la variable de entorno SUMO_HOME.
def obtener_sumo_home() -> pathlib.Path:
    carpeta_sumo = os.environ.get("SUMO_HOME")
    if not carpeta_sumo:
        raise EnvironmentError("La variable de entorno SUMO_HOME no está definida. Instala SUMO.")
    return pathlib.Path(carpeta_sumo)


# Busca un ejecutable de SUMO en el PATH o, si no está ahí, en <SUMO_HOME>/bin.
def buscar_herramienta_sumo(nombre: str) -> pathlib.Path:
    encontrado = shutil.which(nombre)
    if encontrado:
        return pathlib.Path(encontrado)
    candidato = obtener_sumo_home() / "bin" / f"{nombre}.exe"
    if candidato.exists():
        return candidato
    raise FileNotFoundError(f"No se encuentra {nombre}.exe. Instala SUMO o define SUMO_HOME.")


# Lee la variable de entorno CARLA_ROOT.
def obtener_carla_root() -> pathlib.Path:
    carpeta_carla = os.environ.get("CARLA_ROOT")
    if not carpeta_carla:
        raise EnvironmentError("La variable de entorno CARLA_ROOT no está definida. Instala CARLA.")
    return pathlib.Path(carpeta_carla)


# Ruta por defecto del fichero de tipos de vehículo de CARLA para SUMO, dentro de CARLA_ROOT.
def vtypes_carla_por_defecto() -> pathlib.Path:
    return obtener_carla_root() / "Co-Simulation" / "Sumo" / "examples" / "carlavtypes.rou.xml"


# Escribe un .sumocfg mínimo con la red y los ficheros de rutas indicados (en orden).
def escribir_sumocfg(ruta_sumocfg: pathlib.Path, fichero_red: pathlib.Path, ficheros_rutas: list) -> None:
    # Rutas absolutas: un .sumocfg con rutas relativas deja de funcionar si se invoca desde otro directorio.
    ruta_red_abs = pathlib.Path(fichero_red).resolve()
    rutas_unidas = ",".join(str(pathlib.Path(r).resolve()) for r in ficheros_rutas)
    contenido = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="{ruta_red_abs}"/>
        <route-files value="{rutas_unidas}"/>
    </input>
</configuration>
"""
    ruta_sumocfg.parent.mkdir(parents=True, exist_ok=True)
    ruta_sumocfg.write_text(contenido, encoding="utf-8")
    print(f"Guardado fichero de configuración SUMO en: {ruta_sumocfg}")


# Rumbo brújula (0=N, 90=E) del arco, de su primer a su último punto.
def rumbo_arco(arco) -> float:
    trazado = arco.getShape()
    (x1, y1), (x2, y2) = trazado[0], trazado[-1]
    return (math.degrees(math.atan2(x2 - x1, y2 - y1)) + 360.0) % 360.0


# Diferencia angular mínima entre dos rumbos.
def diferencia_angular(angulo1: float, angulo2: float) -> float:
    diferencia = abs(angulo1 - angulo2) % 360.0
    return min(diferencia, 360.0 - diferencia)


# Devuelve un diccionario station_id -> edge_id con las estaciones que caen dentro de la red.
def asignar_estaciones_a_arcos(red, estaciones: list, radio: float, diferencia_rumbo_maxima: float) -> dict:
    asignacion = {}
    for estacion in estaciones:
        x, y = red.convertLonLat2XY(float(estacion["lon"]), float(estacion["lat"]))
        cercanos = red.getNeighboringEdges(x, y, radio)
        cercanos = [
            (distancia, arco) for arco, distancia in cercanos
            if arco.allows("passenger")
        ]
        if not cercanos:
            print(f"  [fuera de red] {estacion['station_id']} ({estacion['name']})")
            continue

        rumbo = estacion.get("bearing_deg", "")
        elegido = None
        if rumbo != "":
            rumbo = float(rumbo)
            # Descarta arcos cuyo rumbo no encaje con el sentido medido en la estación.
            compatibles = [
                (distancia, arco) for distancia, arco in cercanos
                if diferencia_angular(rumbo_arco(arco), rumbo) <= diferencia_rumbo_maxima
            ]
            if compatibles:
                elegido = min(compatibles, key=lambda c: c[0])
            else:
                print(f"  [sin arco con rumbo compatible] {estacion['station_id']} ({estacion['name']}, rumbo {rumbo:.0f})")
                continue
        else:
            elegido = min(cercanos, key=lambda c: c[0])

        distancia, arco = elegido
        asignacion[estacion["station_id"]] = arco.getID()
        print(f"  [ok] {estacion['station_id']} ({estacion['name']}) -> arco {arco.getID()} (a {distancia:.1f} m, rumbo arco {rumbo_arco(arco):.0f})")
    return asignacion


# Suma, arco a arco, los conteos que caen dentro de la franja [hora_inicio, hora_fin).
def recopilar_conteos(ruta_aforos: pathlib.Path, asignacion: dict, fecha, hora_inicio: int, hora_fin: int) -> dict:
    import csv
    import datetime

    inicio_franja = datetime.datetime.combine(fecha, datetime.time(hour=hora_inicio))
    fin_franja = datetime.datetime.combine(fecha, datetime.time(hour=hora_fin))
    conteos_por_arco: dict = {}
    with open(ruta_aforos, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            if fila["station_id"] not in asignacion:
                continue
            inicio_medicion = datetime.datetime.fromisoformat(fila["timestamp_start"])
            fin_medicion = datetime.datetime.fromisoformat(fila["timestamp_end"])
            if inicio_medicion >= inicio_franja and fin_medicion <= fin_franja:
                id_arco = asignacion[fila["station_id"]]
                conteos_por_arco[id_arco] = conteos_por_arco.get(id_arco, 0) + int(fila["count"])
    return conteos_por_arco
