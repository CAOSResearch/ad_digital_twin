import argparse
import pathlib
import re
import subprocess

from comun import buscar_herramienta_sumo

# Para evitar semáforos flotando
ALTURA_SEMAFOROS_POR_DEFECTO = 0.0


# Reescribe el zOffset para que el poste generado por CARLA apoye en el suelo en vez de quedar suspendido en el aire.
def corregir_altura_semaforos(ruta_xodr: pathlib.Path, altura: float) -> int:
    contenido = ruta_xodr.read_text(encoding="utf-8")
    contenido_corregido, num_cambios = re.subn(
        r'(<signal\b[^>]*\bzOffset=")[^"]*(")',
        rf'\g<1>{altura}\g<2>',
        contenido,
    )
    if num_cambios:
        ruta_xodr.write_text(contenido_corregido, encoding="utf-8")
    return num_cambios


# Convierte el .osm a OpenDRIVE (y opcionalmente a .net.xml) invocando netconvert.
def convertir(
    ruta_entrada: pathlib.Path,
    ruta_salida: pathlib.Path,
    distancia_fusion_uniones: float,
    radio_minimo_geometria: float,
    ruta_red_salida: pathlib.Path | None = None,
    limite_geografico: list[float] | None = None,
    altura_semaforos: float = ALTURA_SEMAFOROS_POR_DEFECTO,
) -> None:
    netconvert = buscar_herramienta_sumo("netconvert")
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    comando = [
        str(netconvert),
        "--osm-files", str(ruta_entrada),
        "--opendrive-output", str(ruta_salida),
        "--keep-edges.by-vclass", "passenger",
    ]
    if limite_geografico is not None:
        lon_min, lat_min, lon_max, lat_max = limite_geografico
        comando += ["--keep-edges.in-geo-boundary", f"{lon_min},{lat_min},{lon_max},{lat_max}"]
    comando += [
        "--junctions.join",
        "--junctions.join-dist", str(distancia_fusion_uniones),
        "--geometry.remove",
        "--geometry.min-radius", str(radio_minimo_geometria),
        "--geometry.min-radius.fix",
        "--tls.guess",
        "--tls.guess-signals",
        "--remove-edges.isolated",
        "--no-turnarounds",
    ]
    if ruta_red_salida is not None:
        ruta_red_salida.parent.mkdir(parents=True, exist_ok=True)
        comando += ["--output-file", str(ruta_red_salida)]

    subprocess.run(comando, check=True)

    num_semaforos = corregir_altura_semaforos(ruta_salida, altura_semaforos)
    if num_semaforos:
        print(f"Corregida la altura de {num_semaforos} semáforos a {altura_semaforos} m")

    print(f"Guardado fichero OpenDRIVE en: {ruta_salida}")
    if ruta_red_salida is not None:
        print(f"Guardada red nativa de SUMO en: {ruta_red_salida}")


# Interpreta los argumentos y ejecuta la conversión.
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", type=pathlib.Path, required=True, help="Fichero .osm de entrada")
    parser.add_argument("-o", "--output", type=pathlib.Path, required=True, help="Fichero .xodr de salida")
    parser.add_argument("--junctions-join-dist", type=float, default=15.0, help="Distancia máxima (m) para fusionar uniones cercanas")
    parser.add_argument("--geometry-min-radius", type=float, default=5.0, help="Radio de giro mínimo (m) antes de corregir la geometría")
    parser.add_argument("--net-output", type=pathlib.Path, default=None, help="Si se indica, además exporta la red nativa de SUMO (.net.xml) para generación de tráfico")
    parser.add_argument(
        "--geo-boundary",
        nargs=4,
        type=float,
        metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"),
        default=None,
        help="Si se indica, recorta la red a esta bounding box WGS84 (p. ej. la zona que engloba las estaciones de aforo)",
    )
    parser.add_argument("--signal-height", type=float, default=ALTURA_SEMAFOROS_POR_DEFECTO, help="Altura (m) que se escribe en el zOffset de cada semáforo, para que el poste 3D de CARLA apoye en el suelo (default 0.0)")
    args = parser.parse_args()

    convertir(args.input, args.output, args.junctions_join_dist, args.geometry_min_radius, args.net_output, args.geo_boundary, args.signal_height)


if __name__ == "__main__":
    main()
