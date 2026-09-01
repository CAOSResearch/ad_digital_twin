import argparse
import pathlib

import carla


# Genera el mundo 3D de CARLA a partir de los datos OpenDRIVE dados.
def cargar_mapa_opendrive(cliente: carla.Client, ruta_xodr: pathlib.Path, distancia_vertices: float = 2.0) -> None:
    datos_xodr = ruta_xodr.read_text(encoding="utf-8")

    parametros = carla.OpendriveGenerationParameters(
        vertex_distance=distancia_vertices,
        max_road_length=500.0,
        wall_height=0.0,
        additional_width=0.6,
        smooth_junctions=True,
        enable_mesh_visibility=True,
        enable_pedestrian_navigation=False,
    )

    print("Generando mundo a partir del OpenDRIVE (puede tardar unos segundos)...")
    cliente.generate_opendrive_world(datos_xodr, parametros)
    print("Mapa cargado en CARLA.")


# Conecta con el servidor CARLA y carga el .xodr indicado.
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-x", "--xodr", type=pathlib.Path, required=True, help="Fichero .xodr a cargar")
    parser.add_argument("--host", default="127.0.0.1", help="Host del servidor CARLA")
    parser.add_argument("--port", type=int, default=2000, help="Puerto del servidor CARLA")
    parser.add_argument("--timeout", type=float, default=180.0, help="Timeout en segundos (la generación de la malla de una red grande puede tardar)")
    args = parser.parse_args()

    cliente = carla.Client(args.host, args.port)
    cliente.set_timeout(args.timeout)

    cargar_mapa_opendrive(cliente, args.xodr)


if __name__ == "__main__":
    main()
