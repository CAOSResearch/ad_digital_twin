import argparse
import csv
import datetime
import json
import math
import pathlib
import sys
import xml.etree.ElementTree as ET

from comun import recopilar_conteos, obtener_sumo_home, asignar_estaciones_a_arcos

sys.path.append(str(obtener_sumo_home() / "tools"))
import sumolib  # noqa: E402


# Lee edgedata.xml y devuelve el conteo simulado por arco.
def analizar_conteos_edgedata(ruta_edgedata: pathlib.Path) -> dict:
    raiz = ET.parse(ruta_edgedata).getroot()
    conteos = {}
    for arco in raiz.iter("edge"):
        entrados = arco.get("entered")
        if entrados is not None:
            conteos[arco.get("id")] = int(entrados)
    return conteos


# Estadístico GEH entre el conteo simulado y el real.
def geh(simulado: float, real: float) -> float:
    if simulado + real == 0:
        return 0.0
    return math.sqrt(2 * (simulado - real) ** 2 / (simulado + real))


# Coeficiente de correlación de Pearson entre dos series.
def coeficiente_pearson(xs: list, ys: list):
    n = len(xs)
    if n < 2:
        return None
    media_x, media_y = sum(xs) / n, sum(ys) / n
    covarianza = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys))
    varianza_x = sum((x - media_x) ** 2 for x in xs)
    varianza_y = sum((y - media_y) ** 2 for y in ys)
    if varianza_x == 0 or varianza_y == 0:
        return None
    return covarianza / math.sqrt(varianza_x * varianza_y)


# Reasigna estaciones a arcos y compara, estación a estación, los conteos simulados con los reales.
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--net-file", type=pathlib.Path, required=True)
    parser.add_argument("--edgedata", type=pathlib.Path, required=True, help="edgedata.xml generado por 08_ejecutar_salidas_simulacion.py")
    parser.add_argument("--estaciones", type=pathlib.Path, required=True)
    parser.add_argument("--aforos", type=pathlib.Path, required=True)
    parser.add_argument("--date", type=str, required=True)
    parser.add_argument("--hour-start", type=int, required=True)
    parser.add_argument("--hour-end", type=int, required=True)
    parser.add_argument("--scale", type=float, required=True, help="Misma escala usada en 07_generar_trafico_desde_aforos.py")
    parser.add_argument("--radius", type=float, default=60.0)
    parser.add_argument("--max-bearing-diff", type=float, default=60.0)
    parser.add_argument("-o", "--out-csv", type=pathlib.Path, required=True)
    args = parser.parse_args()

    fecha = datetime.date.fromisoformat(args.date)

    print("Cargando red y reasignando estaciones a arcos (misma lógica que la calibración)...")
    red = sumolib.net.readNet(str(args.net_file))

    with open(args.estaciones, encoding="utf-8") as f:
        estaciones = list(csv.DictReader(f))
    asignacion = asignar_estaciones_a_arcos(red, estaciones, args.radius, args.max_bearing_diff)

    conteos_reales = recopilar_conteos(args.aforos, asignacion, fecha, args.hour_start, args.hour_end)
    conteos_simulados = analizar_conteos_edgedata(args.edgedata)

    estacion_por_id = {e["station_id"]: e for e in estaciones}
    filas = []
    for id_estacion, id_arco in asignacion.items():
        if id_arco not in conteos_reales:
            continue
        real = conteos_reales[id_arco]
        simulado = conteos_simulados.get(id_arco, 0)
        simulado_expandido = simulado / args.scale
        filas.append({
            "station_id": id_estacion,
            "name": estacion_por_id[id_estacion]["name"],
            "edge_id": id_arco,
            "conteo_real": real,
            "conteo_simulado": simulado,
            "conteo_simulado_expandido": round(simulado_expandido, 1),
            "geh": round(geh(simulado_expandido, real), 2),
            "error_relativo_pct": round(100.0 * (simulado_expandido - real) / real, 1) if real else None,
        })

    if not filas:
        sys.exit("Ninguna estación con conteo real coincide con arcos con datos simulados: revisa fecha/franja/zona.")

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"Guardado: {args.out_csv} ({len(filas)} estaciones)")

    valores_geh = [fila["geh"] for fila in filas]
    reales = [fila["conteo_real"] for fila in filas]
    simulados = [fila["conteo_simulado_expandido"] for fila in filas]
    r_pearson = coeficiente_pearson(reales, simulados)
    resumen = {
        "n_estaciones": len(filas),
        "geh_medio": round(sum(valores_geh) / len(valores_geh), 2),
        "geh_maximo": round(max(valores_geh), 2),
        "pct_estaciones_geh_menor_5": round(100.0 * sum(1 for g in valores_geh if g < 5) / len(valores_geh), 1),
        "error_relativo_medio_pct": round(sum(fila["error_relativo_pct"] for fila in filas) / len(filas), 1),
        "correlacion_pearson_r": round(r_pearson, 3) if r_pearson is not None else None,
    }
    ruta_resumen = args.out_csv.with_name(args.out_csv.stem + "_resumen.json")
    ruta_resumen.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Guardado: {ruta_resumen}")
    print(json.dumps(resumen, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
