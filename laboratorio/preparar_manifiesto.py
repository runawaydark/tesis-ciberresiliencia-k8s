"""Genera laboratorio/manifiestos/estado-deseado.yaml a partir del manifiesto oficial.

Quita el generador de carga interno de Online Boutique (loadgenerator), porque
la carga del experimento la controla k6. El archivo resultante es el
"estado deseado" declarativo del sistema: lo que se reaplica para recuperar
el servicio en el escenario de ataque (reconciliacion tipo GitOps).
"""
from pathlib import Path
import yaml

BASE = Path(__file__).parent / "manifiestos"
origen = BASE / "online-boutique-original.yaml"
destino = BASE / "estado-deseado.yaml"

docs = [d for d in yaml.safe_load_all(origen.read_text(encoding="utf-8")) if d]
filtrados = [d for d in docs if d.get("metadata", {}).get("name") != "loadgenerator"]

destino.write_text(yaml.safe_dump_all(filtrados, sort_keys=False), encoding="utf-8")
print(f"{len(docs)} recursos en el original, {len(filtrados)} en el estado deseado -> {destino}")
