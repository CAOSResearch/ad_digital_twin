import argparse
import logging
import os
import sys
import time

from comun import obtener_carla_root

if "SUMO_HOME" not in os.environ:
    sys.exit("Define la variable de entorno SUMO_HOME (instalación de SUMO).")
sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
sys.path.append(str(obtener_carla_root() / "Co-Simulation" / "Sumo"))

from sumo_integration.bridge_helper import BridgeHelper  # noqa: E402
from sumo_integration.carla_simulation import CarlaSimulation  # noqa: E402
from sumo_integration.sumo_simulation import SumoSimulation  # noqa: E402

import run_synchronization as rs  # noqa: E402  (aquí solo interesa su SimulationSynchronization)


# Sincroniza SUMO y CARLA paso a paso, forzando el offset de coordenadas a (0, 0).
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sumo_cfg_file", type=str, help="Fichero de configuración de SUMO (.sumocfg)")
    parser.add_argument("--carla-host", default="127.0.0.1")
    parser.add_argument("--carla-port", type=int, default=2000)
    parser.add_argument("--step-length", type=float, default=0.05)
    parser.add_argument("--tls-manager", choices=["none", "sumo", "carla"], default="sumo")
    parser.add_argument("--duration", type=float, default=None, help="Si se indica, detiene la co-simulación tras N segundos reales (para pruebas)")
    args = parser.parse_args()

    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

    simulacion_sumo = SumoSimulation(args.sumo_cfg_file, args.step_length, None, None, False, 1)
    simulacion_carla = CarlaSimulation(args.carla_host, args.carla_port, args.step_length)

    sincronizacion = rs.SimulationSynchronization(
        simulacion_sumo, simulacion_carla, tls_manager=args.tls_manager
    )

    # Mismo origen local en ambos mapas: no se debe reaplicar el netOffset de SUMO.
    BridgeHelper.offset = (0.0, 0.0)
    logging.info("Offset SUMO->CARLA forzado a (0.0, 0.0) (mismo origen local en ambos).")

    tiempo_inicio = time.time()
    try:
        while True:
            inicio_tick = time.time()
            sincronizacion.tick()
            transcurrido = time.time() - inicio_tick
            if transcurrido < args.step_length:
                time.sleep(args.step_length - transcurrido)
            if args.duration is not None and (time.time() - tiempo_inicio) > args.duration:
                logging.info("Duración máxima alcanzada, terminando.")
                break
    except KeyboardInterrupt:
        logging.info("Cancelado por el usuario.")
    finally:
        sincronizacion.close()


if __name__ == "__main__":
    main()
