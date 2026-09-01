import argparse
import pathlib
import sys

import requests

URL_API_OSM = "https://api.openstreetmap.org/api/0.6/map"
URL_API_OVERPASS = "https://overpass-api.de/api/interpreter"


# Descarga el extracto OSM vía el endpoint de exportación estándar (límite ~50 000 nodos).
def descargar_osm(lon_min: float, lat_min: float, lon_max: float, lat_max: float, ruta_salida: pathlib.Path) -> None:
    bbox = f"{lon_min},{lat_min},{lon_max},{lat_max}"
    respuesta = requests.get(URL_API_OSM, params={"bbox": bbox}, timeout=60)

    if respuesta.status_code != 200:
        raise RuntimeError(
            f"La API de OSM devolvió {respuesta.status_code}: {respuesta.text[:300]}"
        )

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    ruta_salida.write_bytes(respuesta.content)
    print(f"Guardado extracto OSM ({len(respuesta.content) / 1024:.1f} KB) en: {ruta_salida}")


# Descarga el extracto OSM vía Overpass (solo vías highway=*, sin límite de nodos).
def descargar_osm_overpass(lon_min: float, lat_min: float, lon_max: float, lat_max: float, ruta_salida: pathlib.Path) -> None:
    # Overpass pide las coordenadas en otro orden que el resto del script: (lat_min, lon_min, lat_max, lon_max).
    consulta = f"""
    [out:xml][timeout:120];
    (
      way["highway"]({lat_min},{lon_min},{lat_max},{lon_max});
    );
    (._;>;);
    out meta;
    """
    # "out meta" hace falta porque netconvert luego exige version/timestamp en cada elemento.
    # Sin un User-Agent identificable, algunos espejos de Overpass devuelven 4xx.
    cabeceras = {"User-Agent": "TFG-gemelo-digital-UC3M/1.0 (contacto: davidbravo37192@gmail.com)"}
    respuesta = requests.post(URL_API_OVERPASS, data={"data": consulta}, headers=cabeceras, timeout=180)

    if respuesta.status_code != 200:
        raise RuntimeError(
            f"La API de Overpass devolvió {respuesta.status_code}: {respuesta.text[:300]}"
        )

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    ruta_salida.write_bytes(respuesta.content)
    print(f"Guardado extracto OSM vía Overpass ({len(respuesta.content) / 1024:.1f} KB) en: {ruta_salida}")


# Interpreta los argumentos y lanza la descarga (API estándar o Overpass).
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"),
        required=True,
        help="Bounding box en WGS84: lon_min lat_min lon_max lat_max",
    )
    parser.add_argument("-o", "--output", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent.parent / "data" / "osm" / "area.osm", help="Ruta del fichero .osm de salida")
    parser.add_argument("--overpass", action="store_true", help="Usar la API de Overpass (solo vías highway=*), para zonas que exceden el límite de 50k nodos")
    args = parser.parse_args()

    lon_min, lat_min, lon_max, lat_max = args.bbox
    if lon_min >= lon_max or lat_min >= lat_max:
        sys.exit("Bounding box inválida: comprueba el orden lon_min lat_min lon_max lat_max")

    if args.overpass:
        descargar_osm_overpass(lon_min, lat_min, lon_max, lat_max, args.output)
    else:
        descargar_osm(lon_min, lat_min, lon_max, lat_max, args.output)


if __name__ == "__main__":
    main()
