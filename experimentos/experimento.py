"""Ejecuta experimentos de resiliencia sobre Online Boutique.

Cada repeticion sigue el protocolo:  LINEA BASE -> FALLA -> RECUPERACION
y guarda en resultados/<escenario>/rep<N>/ :
  k6.csv        cada solicitud de los usuarios simulados (vista del USUARIO)
  infra.csv     replicas disponibles por deployment cada ~1 s (vista de KUBERNETES)
  eventos.json  instantes de inicio, falla y reconciliacion + parametros
  k6_resumen.txt salida de k6

Escenarios:
  podkill      Falla: se eliminan los pods de cartservice.
               Recuperacion: self-healing de Kubernetes (automatica).
  ataque-rbac  Ataque: una cuenta de servicio con permisos excesivos borra el
               deployment cartservice. El self-healing NO lo recupera (el objeto
               ya no existe). Recuperacion: reaplicar el estado deseado
               declarativo (reconciliacion tipo GitOps) tras --retardo segundos.
               Con --retardo -1 no hay reconciliacion durante la medicion.

Uso:
  python experimentos/experimento.py --escenario podkill --reps 5
  python experimentos/experimento.py --escenario ataque-rbac --reps 5 --retardo 60
"""
import argparse
import csv
import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent          # carpeta raiz del repositorio
MANIFIESTO = RAIZ / "laboratorio" / "manifiestos" / "estado-deseado.yaml"
CARGA = RAIZ / "carga" / "carga.js"
RESULTADOS = RAIZ / "resultados"
NS = "default"
OBJETIVO = "cartservice"
SA = f"system:serviceaccount:{NS}:sa-comprometida"
VIGILADOS = ["cartservice", "frontend", "redis-cart"]


def kubectl(*args, check=True):
    cmd = ["kubectl", *args]
    print("   $", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"Error en kubectl:\n{r.stderr}")
    return r


def esperar_sistema_sano():
    kubectl("wait", "--for=condition=available", "deployment", "--all",
            "-n", NS, "--timeout=600s")


def abrir_port_forward():
    pf = subprocess.Popen(
        ["kubectl", "port-forward", "-n", NS, "svc/frontend", "8080:80"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            urllib.request.urlopen("http://localhost:8080/_healthz", timeout=2)
            return pf
        except Exception:
            time.sleep(1)
    pf.terminate()
    sys.exit("No se pudo conectar al frontend en http://localhost:8080")


class MuestreadorInfra(threading.Thread):
    """Registra cada ~1 s cuantas replicas disponibles tiene cada deployment."""

    def __init__(self, ruta):
        super().__init__(daemon=True)
        self.ruta, self.activo = ruta, True

    def run(self):
        with open(self.ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t", "deployment", "disponibles", "deseadas"])
            while self.activo:
                t = time.time()
                r = subprocess.run(["kubectl", "get", "deployments", "-n", NS, "-o", "json"],
                                   capture_output=True, text=True)
                estado = {}
                if r.returncode == 0:
                    for d in json.loads(r.stdout).get("items", []):
                        estado[d["metadata"]["name"]] = (
                            d.get("status", {}).get("availableReplicas", 0) or 0,
                            d.get("spec", {}).get("replicas", 0) or 0)
                for nombre in VIGILADOS:
                    disp, des = estado.get(nombre, (0, 0))  # borrado => 0
                    w.writerow([f"{t:.3f}", nombre, disp, des])
                f.flush()
                time.sleep(max(0.0, 1.0 - (time.time() - t)))


def inyectar(escenario):
    if escenario == "podkill":
        kubectl("delete", "pod", "-n", NS, "-l", f"app={OBJETIVO}", "--wait=false")
    elif escenario == "ataque-rbac":
        kubectl("delete", "deployment", OBJETIVO, "-n", NS, f"--as={SA}", "--wait=false")


def reconciliar():
    """Reaplica el estado deseado (lo que haria un controlador GitOps)."""
    kubectl("apply", "-f", str(MANIFIESTO))


def una_repeticion(a, rep):
    carpeta = RESULTADOS / a.escenario / f"rep{rep}"
    carpeta.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {a.escenario}  repeticion {rep} (ultima: {a.desde + a.reps - 1})  ->  {carpeta}")

    esperar_sistema_sano()
    print(f"   enfriamiento {a.enfriamiento}s ...")
    time.sleep(a.enfriamiento)

    pf = abrir_port_forward()
    infra = MuestreadorInfra(carpeta / "infra.csv")
    infra.start()

    duracion = a.base + a.horizonte + 20
    ev = {"escenario": a.escenario, "repeticion": rep,
          "parametros": {"linea_base_s": a.base, "horizonte_s": a.horizonte,
                         "tasa_clientes_s": a.tasa, "retardo_reconciliacion_s": a.retardo,
                         "duracion_carga_s": duracion},
          "t_reconciliacion": None}
    with open(carpeta / "k6_resumen.txt", "w", encoding="utf-8") as salida:
        k6 = subprocess.Popen(
            ["k6", "run", "--out", f"csv={carpeta / 'k6.csv'}",
             "-e", "BASE_URL=http://localhost:8080", "-e", f"TASA={a.tasa}",
             "-e", f"DURACION={duracion}s", str(CARGA)],
            stdout=salida, stderr=subprocess.STDOUT)
        ev["t_inicio_carga"] = time.time()

        print(f"   linea base {a.base}s ...")
        time.sleep(a.base)
        ev["t_falla"] = time.time()
        print("   >>> INYECTANDO FALLA")
        inyectar(a.escenario)

        if a.escenario == "ataque-rbac" and a.retardo >= 0:
            time.sleep(a.retardo)
            ev["t_reconciliacion"] = time.time()
            print("   >>> RECONCILIANDO estado deseado")
            reconciliar()

        print("   esperando fin de la carga ...")
        k6.wait()
    ev["t_fin"] = time.time()

    infra.activo = False
    infra.join(timeout=5)
    pf.terminate()

    # deja el laboratorio sano para la siguiente repeticion
    if a.escenario == "ataque-rbac":
        reconciliar()
    (carpeta / "eventos.json").write_text(json.dumps(ev, indent=2), encoding="utf-8")
    print("   ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--escenario", required=True, choices=["podkill", "ataque-rbac"])
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--desde", type=int, default=1, help="numero de la primera repeticion")
    ap.add_argument("--base", type=int, default=120, help="segundos de linea base")
    ap.add_argument("--horizonte", type=int, default=200, help="segundos medidos tras la falla")
    ap.add_argument("--tasa", type=int, default=5, help="clientes por segundo")
    ap.add_argument("--retardo", type=int, default=60,
                    help="ataque-rbac: segundos hasta reconciliar (-1 = no reconciliar)")
    ap.add_argument("--enfriamiento", type=int, default=30)
    a = ap.parse_args()
    if a.retardo >= a.horizonte:
        sys.exit("--retardo debe ser menor que --horizonte")
    for rep in range(a.desde, a.desde + a.reps):
        una_repeticion(a, rep)
    print("\nListo. Ahora: python analisis/analizar.py")


if __name__ == "__main__":
    main()
