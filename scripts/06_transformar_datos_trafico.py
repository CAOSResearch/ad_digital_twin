import argparse
import csv
import datetime
import pathlib

# Traduce la orientación de texto de la fuente ('S-N', 'O-E'...) a un rumbo en grados brújula.
ORIENTACION_A_RUMBO = {
    "S-N": 0.0,
    "O-E": 90.0,
    "N-S": 180.0,
    "E-O": 270.0,
}


# Convierte un número con coma decimal (formato de la fuente) a float.
def analizar_decimal(valor: str) -> float:
    return float(valor.strip().replace(",", "."))


# Lee Datos_estaciones.csv y produce el diccionario de estaciones en formato canónico.
def transformar_estaciones(ruta: pathlib.Path) -> dict[str, dict]:
    estaciones: dict[str, dict] = {}
    descartadas = 0
    with open(ruta, encoding="utf-8-sig") as f:
        lector = csv.reader(f, delimiter=";")
        next(lector)  # la primera fila es la cabecera, no un dato
        for fila in lector:
            if len(fila) < 6 or not fila[0].strip():
                continue
            est, nombre, lat, lon, sentido, orient = (c.strip() for c in fila[:6])
            if not sentido or orient not in ORIENTACION_A_RUMBO:
                descartadas += 1
                continue
            id_estacion = f"ES{int(est):02d}-{sentido}"
            estaciones[id_estacion] = {
                "station_id": id_estacion,
                "name": nombre,
                "lat": analizar_decimal(lat),
                "lon": analizar_decimal(lon),
                "bearing_deg": ORIENTACION_A_RUMBO[orient],
            }
    print(f"Estaciones transformadas: {len(estaciones)} (descartadas por sentido/orientación vacíos: {descartadas})")
    return estaciones


# Lee Datos_completos.csv y produce las filas de aforos en formato canónico.
def transformar_conteos(ruta: pathlib.Path, estaciones: dict[str, dict]) -> list[dict]:
    filas_salida: list[dict] = []
    estaciones_omitidas = 0
    with open(ruta, encoding="utf-8-sig") as f:
        lector = csv.reader(f, delimiter=";")
        next(lector)  # la primera fila es la cabecera, no un dato
        for fila in lector:
            if len(fila) < 15 or not fila[0].strip():
                continue
            fdia, fest, fsen = fila[0].strip(), fila[1].strip(), fila[2].strip()
            if len(fsen) != 2 or fsen[1] not in "-=":
                continue
            sentido, mitad = fsen[0], fsen[1]
            id_estacion = f"{fest}-{sentido}"
            if id_estacion not in estaciones:
                estaciones_omitidas += 1
                continue
            fecha = datetime.datetime.strptime(fdia, "%d/%m/%Y").date()
            hora_base = 0 if mitad == "-" else 12
            for i, celda in enumerate(fila[3:15]):
                celda = celda.strip()
                if not celda:
                    continue
                inicio = datetime.datetime.combine(fecha, datetime.time(hour=hora_base + i))
                fin = inicio + datetime.timedelta(hours=1)
                filas_salida.append({
                    "station_id": id_estacion,
                    "timestamp_start": inicio.isoformat(),
                    "timestamp_end": fin.isoformat(),
                    "count": int(celda),
                })
    print(f"Mediciones horarias transformadas: {len(filas_salida)} (filas de estación desconocida: {estaciones_omitidas})")
    return filas_salida


# Interpreta los argumentos, transforma ambos ficheros y guarda los CSV canónicos.
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--estaciones", type=pathlib.Path, required=True, help="Datos_estaciones.csv de la fuente Madrid")
    parser.add_argument("--aforos", type=pathlib.Path, required=True, help="Datos_completos.csv de la fuente Madrid")
    parser.add_argument("-o", "--out-dir", type=pathlib.Path, required=True, help="Directorio de salida para estaciones.csv y aforos.csv canónicos")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    estaciones = transformar_estaciones(args.estaciones)
    conteos = transformar_conteos(args.aforos, estaciones)

    ruta_estaciones = args.out_dir / "estaciones.csv"
    with open(ruta_estaciones, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=["station_id", "name", "lat", "lon", "bearing_deg"])
        escritor.writeheader()
        escritor.writerows(estaciones.values())
    print(f"Guardado: {ruta_estaciones}")

    ruta_aforos = args.out_dir / "aforos.csv"
    with open(ruta_aforos, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=["station_id", "timestamp_start", "timestamp_end", "count"])
        escritor.writeheader()
        escritor.writerows(conteos)
    print(f"Guardado: {ruta_aforos}")


if __name__ == "__main__":
    main()
