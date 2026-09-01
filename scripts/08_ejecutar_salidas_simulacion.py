import argparse
import json
import pathlib
import subprocess
import xml.etree.ElementTree as ET

from comun import buscar_herramienta_sumo


# Cuenta los vehículos definidos en los .rou.xml que referencia el .sumocfg.
def contar_vehiculos_totales(sumocfg: pathlib.Path) -> int:
    raiz_cfg = ET.parse(sumocfg).getroot()
    elemento_rutas = raiz_cfg.find("./input/route-files")
    if elemento_rutas is None:
        return 0
    total = 0
    for fichero_ruta in elemento_rutas.get("value", "").split(","):
        ruta_fichero = (sumocfg.parent / fichero_ruta.strip())
        if ruta_fichero.exists():
            total += len(ET.parse(ruta_fichero).getroot().findall("vehicle"))
    return total


# Calcula los estadísticos macroscópicos a partir de tripinfo.xml.
def resumir_macroscopico(ruta_tripinfo: pathlib.Path, vehiculos_totales: int) -> dict:
    raiz = ET.parse(ruta_tripinfo).getroot()
    viajes = raiz.findall("tripinfo")
    n = len(viajes)
    if n == 0:
        return {
            "vehiculos_totales": vehiculos_totales,
            "vehiculos_completados": 0,
            "porcentaje_completado": 0.0,
        }

    def media(atributo):
        return sum(float(v.get(atributo)) for v in viajes) / n

    # Promedia la razón routeLength/duration por viaje, para no sesgar la velocidad media hacia los viajes largos.
    velocidades = [float(v.get("routeLength")) / float(v.get("duration")) for v in viajes if float(v.get("duration")) > 0]
    return {
        "vehiculos_totales": vehiculos_totales,
        "vehiculos_completados": n,
        "porcentaje_completado": round(100.0 * n / vehiculos_totales, 2) if vehiculos_totales else None,
        "duracion_media_s": round(media("duration"), 2),
        "longitud_ruta_media_m": round(media("routeLength"), 2),
        "velocidad_media_ms": round(sum(velocidades) / len(velocidades), 2) if velocidades else None,
        "tiempo_espera_medio_s": round(media("waitingTime"), 2),
        "perdida_tiempo_media_s": round(media("timeLoss"), 2),
    }


# Ejecuta SUMO sobre el escenario calibrado y genera las tres salidas (micro, meso, macro).
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--sumocfg", type=pathlib.Path, required=True, help="Escenario de SUMO ya calibrado (.sumocfg)")
    parser.add_argument("-o", "--out-dir", type=pathlib.Path, required=True, help="Directorio donde escribir las tres salidas")
    parser.add_argument("--fcd-period", type=float, default=10.0, help="Periodo de muestreo (s) del nivel microscópico (default: 10)")
    args = parser.parse_args()

    sumo = buscar_herramienta_sumo("sumo")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    ruta_fcd = args.out_dir / "fcd.xml"
    ruta_edgedata = args.out_dir / "edgedata.xml"
    ruta_tripinfo = args.out_dir / "tripinfo.xml"
    ruta_summary = args.out_dir / "summary.xml"

    comando = [
        str(sumo),
        "-c", str(args.sumocfg),
        "--fcd-output", str(ruta_fcd),
        "--device.fcd.period", str(args.fcd_period),
        "--edgedata-output", str(ruta_edgedata),
        "--tripinfo-output", str(ruta_tripinfo),
        "--summary-output", str(ruta_summary),
        "--duration-log.statistics",
        "--no-step-log",
    ]
    print("Ejecutando SUMO...")
    subprocess.run(comando, check=True)

    vehiculos_totales = contar_vehiculos_totales(args.sumocfg)
    macro = resumir_macroscopico(ruta_tripinfo, vehiculos_totales)
    ruta_macro = args.out_dir / "resumen_macroscopico.json"
    ruta_macro.write_text(json.dumps(macro, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nNivel microscópico: {ruta_fcd}")
    print(f"Nivel mesoscópico:  {ruta_edgedata}")
    print(f"Nivel macroscópico: {ruta_macro}")
    print(json.dumps(macro, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
