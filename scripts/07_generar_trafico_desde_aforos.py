import argparse
import csv
import datetime
import pathlib
import subprocess
import sys

from comun import vtypes_carla_por_defecto, recopilar_conteos, obtener_sumo_home, asignar_estaciones_a_arcos, escribir_sumocfg

sys.path.append(str(obtener_sumo_home() / "tools"))  # sumolib no está en PyPI, vive en <SUMO_HOME>/tools
import sumolib  # noqa: E402


# Asigna estaciones a arcos, genera rutas candidatas y calibra el tráfico con routeSampler.
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--net-file", type=pathlib.Path, required=True)
    parser.add_argument("--estaciones", type=pathlib.Path, required=True)
    parser.add_argument("--aforos", type=pathlib.Path, required=True)
    parser.add_argument("--date", type=str, required=True, help="Fecha de la medición a reproducir (AAAA-MM-DD)")
    parser.add_argument("--hour-start", type=int, required=True, help="Hora inicial de la franja (0-23)")
    parser.add_argument("--hour-end", type=int, required=True, help="Hora final exclusiva de la franja (1-24)")
    parser.add_argument("--scale", type=float, default=0.1, help="Factor de escala sobre los conteos reales (default 0.1; 1.0 = intensidad real, muy costosa de renderizar)")
    parser.add_argument("--radius", type=float, default=60.0, help="Radio (m) de búsqueda de arcos alrededor de cada estación")
    parser.add_argument("--max-bearing-diff", type=float, default=60.0, help="Diferencia angular máxima (grados) entre rumbo medido y rumbo del arco")
    parser.add_argument("--candidates", type=int, default=4000, help="Número de rutas candidatas a generar para el muestreo")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--carla-vtypes", type=pathlib.Path, default=None, help="Fichero de tipos de vehículo de CARLA a incluir en el .sumocfg (default: <CARLA_ROOT>/Co-Simulation/Sumo/examples/carlavtypes.rou.xml)")
    parser.add_argument("-o", "--out-prefix", type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.carla_vtypes is None:
        args.carla_vtypes = vtypes_carla_por_defecto()

    fecha = datetime.date.fromisoformat(args.date)
    duracion = (args.hour_end - args.hour_start) * 3600
    herramientas_sumo = obtener_sumo_home() / "tools"

    print("Cargando red...")
    red = sumolib.net.readNet(str(args.net_file))

    print("Asignando estaciones a arcos de la red...")
    with open(args.estaciones, encoding="utf-8") as f:
        estaciones = list(csv.DictReader(f))
    asignacion = asignar_estaciones_a_arcos(red, estaciones, args.radius, args.max_bearing_diff)
    print(f"Estaciones asignadas: {len(asignacion)} de {len(estaciones)}")
    if not asignacion:
        sys.exit("Ninguna estación cae dentro de la red: comprueba la zona.")

    conteos_por_arco = recopilar_conteos(args.aforos, asignacion, fecha, args.hour_start, args.hour_end)
    print(f"Arcos con conteo en la franja {args.hour_start}:00-{args.hour_end}:00 de {fecha}: {len(conteos_por_arco)}")
    total_real = sum(conteos_por_arco.values())
    print(f"Vehículos reales contados en la franja: {total_real} (se aplicará escala {args.scale})")

    args.out_prefix.parent.mkdir(parents=True, exist_ok=True)

    # routeSampler necesita el objetivo por arco en formato edgedata.
    ruta_edgedata = args.out_prefix.with_suffix(".edgedata.xml")
    with open(ruta_edgedata, "w", encoding="utf-8") as f:
        f.write('<data>\n')
        f.write(f'  <interval id="aforo" begin="0" end="{duracion}">\n')
        for id_arco, conteo in sorted(conteos_por_arco.items()):
            escalado = max(1, round(conteo * args.scale))
            f.write(f'    <edge id="{id_arco}" entered="{escalado}"/>\n')
        f.write('  </interval>\n')
        f.write('</data>\n')
    print(f"Guardado: {ruta_edgedata}")

    # Genera muchas rutas candidatas por toda la red; routeSampler elegirá un subconjunto.
    ruta_candidatas = args.out_prefix.parent / (args.out_prefix.name + "_candidatas.rou.xml")
    ruta_viajes = args.out_prefix.parent / (args.out_prefix.name + "_candidatas.trips.xml")
    periodo = duracion / args.candidates
    print(f"Generando {args.candidates} rutas candidatas...")
    subprocess.run([
        sys.executable, str(herramientas_sumo / "randomTrips.py"),
        "-n", str(args.net_file),
        "-o", str(ruta_viajes),
        "-r", str(ruta_candidatas),
        "--vehicle-class", "passenger",
        "-b", "0", "-e", str(duracion),
        "-p", str(periodo),
        "--seed", str(args.seed),
        "--validate", "--remove-loops",
        "--fringe-factor", "5",
    ], check=True)

    # routeSampler elige el subconjunto que mejor reproduce los conteos reales.
    ruta_muestreada = args.out_prefix.with_suffix(".rou.xml")
    print("Ejecutando routeSampler...")
    subprocess.run([
        sys.executable, str(herramientas_sumo / "routeSampler.py"),
        "-r", str(ruta_candidatas),
        "--edgedata-files", str(ruta_edgedata),
        "--edgedata-attribute", "entered",
        "-o", str(ruta_muestreada),
        "--seed", str(args.seed),
    ], check=True)
    print(f"Guardado: {ruta_muestreada}")

    ruta_sumocfg = args.out_prefix.with_suffix(".sumocfg")
    escribir_sumocfg(ruta_sumocfg, args.net_file, [args.carla_vtypes, ruta_muestreada])


if __name__ == "__main__":
    main()
