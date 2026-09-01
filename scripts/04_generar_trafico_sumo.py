import argparse
import pathlib
import subprocess
import sys

from comun import vtypes_carla_por_defecto, obtener_sumo_home, escribir_sumocfg


# Genera viajes aleatorios con randomTrips.py y valida las rutas resultantes.
def generar_trafico(
    fichero_red: pathlib.Path,
    prefijo_salida: pathlib.Path,
    tiempo_fin: float,
    periodo: float,
    semilla: int,
) -> tuple[pathlib.Path, pathlib.Path]:
    random_trips = obtener_sumo_home() / "tools" / "randomTrips.py"
    if not random_trips.exists():
        raise FileNotFoundError(f"No se encuentra randomTrips.py en {random_trips}")

    prefijo_salida.parent.mkdir(parents=True, exist_ok=True)
    fichero_viajes = prefijo_salida.with_suffix(".trips.xml")
    fichero_rutas = prefijo_salida.with_suffix(".rou.xml")

    comando = [
        sys.executable, str(random_trips),
        "-n", str(fichero_red),
        "-o", str(fichero_viajes),
        "-r", str(fichero_rutas),
        "--vehicle-class", "passenger",
        "-b", "0",
        "-e", str(tiempo_fin),
        "-p", str(periodo),
        "--seed", str(semilla),
        "--validate",
        "--remove-loops",
        "--fringe-factor", "5",
    ]
    subprocess.run(comando, check=True)
    print(f"Guardadas rutas validadas en: {fichero_rutas}")
    return fichero_viajes, fichero_rutas


# Interpreta los argumentos, genera el tráfico y escribe el .sumocfg.
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--net-file", type=pathlib.Path, required=True, help="Red de SUMO (.net.xml) de entrada")
    parser.add_argument("-o", "--out-prefix", type=pathlib.Path, required=True, help="Prefijo de salida (sin extensión) para .trips.xml/.rou.xml/.sumocfg")
    parser.add_argument("--end-time", type=float, default=600.0, help="Instante final de la simulación en segundos (default: 600)")
    parser.add_argument("--period", type=float, default=3.0, help="Periodo medio entre inserciones de vehículos, en segundos (default: 3.0, menor = más tráfico)")
    parser.add_argument("--seed", type=int, default=42, help="Semilla aleatoria (default: 42)")
    parser.add_argument("--carla-vtypes", type=pathlib.Path, default=None, help="Fichero de tipos de vehículo de CARLA a incluir en el .sumocfg (default: <CARLA_ROOT>/Co-Simulation/Sumo/examples/carlavtypes.rou.xml)")
    args = parser.parse_args()
    if args.carla_vtypes is None:
        args.carla_vtypes = vtypes_carla_por_defecto()

    _, fichero_rutas = generar_trafico(args.net_file, args.out_prefix, args.end_time, args.period, args.seed)
    ruta_sumocfg = args.out_prefix.with_suffix(".sumocfg")
    escribir_sumocfg(ruta_sumocfg, args.net_file, [args.carla_vtypes, fichero_rutas])


if __name__ == "__main__":
    main()
