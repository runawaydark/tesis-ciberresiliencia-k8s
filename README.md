# Kit MVP – Resiliencia de microservicios en Kubernetes (CINF200 · E2)

Laboratorio reproducible para medir la ciber-resiliencia de **Online Boutique** (11 microservicios) en **Minikube**, comparando la vista del **usuario** (curva F(t) medida con k6) con la vista de **Kubernetes** (réplicas disponibles).

## Qué mide y por qué (conexión con la tesis)

| Pieza | Rol en la tesis |
|---|---|
| Minikube + Online Boutique | Sistema estudiado |
| k6 (`carga/carga.js`) | Usuarios simulados; define la línea base y la curva F(t) |
| `experimento.py` | Protocolo línea base → falla → recuperación, con instantes registrados |
| `ataques/rbac-sa-comprometida.yaml` | Escenario de *ciber*seguridad: credencial con permisos excesivos |
| `analizar.py` | Métricas: F(t), pérdida (área), R, TTR usuario, TTR infra y **brecha** |

**Escenarios**

- `podkill` — se eliminan los pods de `cartservice`. Recupera el *self-healing* de Kubernetes.
- `ataque-rbac` — una cuenta de servicio comprometida borra el deployment `cartservice`. El self-healing **no** lo recupera; se recupera reaplicando el **estado deseado** declarativo (`manifiestos/estado-deseado.yaml`), como haría un controlador GitOps.

La **brecha** (TTR usuario − TTR infra) responde la pregunta de investigación: ¿cuánto tiempo Kubernetes reporta el servicio como sano mientras el usuario todavía falla?

## Requisitos

Windows 11, 16 GB RAM o más (recomendado 32 GB), ~20 GB libres.

## Paso a paso

**1. Instalar herramientas** (PowerShell **como administrador**, en esta carpeta):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\00_instalar.ps1
```

Si instala WSL, reinicia y ejecútalo de nuevo. Luego abre Docker Desktop y espera "Engine running".

**2. Librerías de Python** (PowerShell **nueva y normal**):

```powershell
python -m pip install -r requirements.txt
```

**3. Levantar el laboratorio** (10–15 min la primera vez):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\01_laboratorio.ps1
```

Debe terminar con todos los pods en `Running` y la línea `yes` (la cuenta comprometida puede borrar deployments).

**4. Prueba rápida** (≈ 6 min) — comprueba que todo funciona:

```powershell
python experimento.py --escenario podkill --reps 1
python analizar.py
```

Abre `resultados\podkill\rep1\curva.png`. Deberías ver F(t) cerca de 1, una caída en t = 0 y la recuperación.

**5. Experimento completo** (≈ 1 h 20 min en total; se puede dejar corriendo):

```powershell
python experimento.py --escenario podkill --reps 5 --desde 2
python experimento.py --escenario ataque-rbac --reps 5 --retardo 60
python analizar.py
```

No uses el computador para cosas pesadas mientras corre (afecta las latencias).

**6. (Opcional) Grafana para capturas:** `.\02_monitoreo_opcional.ps1`

## Resultados (`resultados\`)

- `<escenario>\repN\curva.png` — curva F(t) con falla, recuperación y réplicas
- `curvas_<escenario>.png` — todas las repeticiones superpuestas + promedio
- `resumen_repeticiones.csv`, `resumen_escenarios.csv` — tablas para el informe
- `comparacion.txt` — prueba de Mann-Whitney entre escenarios

## Parámetros (para justificar en la metodología)

| Parámetro | Valor | Dónde se cambia |
|---|---|---|
| Línea base | 120 s (se descartan los primeros 20 s) | `--base` |
| Horizonte tras la falla | 200 s | `--horizonte` |
| Carga | 5 clientes/s (≈ 20 solicitudes/s), tasa constante | `--tasa` |
| Timeout por solicitud | 5 s | `carga.js` |
| SLO de latencia | 1000 ms | `analizar.py --slo` |
| Umbral "sano" | F ≥ 0,95 durante 10 s seguidos | `--umbral`, `--ventana` |
| Retardo de reconciliación | 60 s | `--retardo` |

## Problemas frecuentes

- **`minikube start` falla:** Docker Desktop no está abierto, o asígnale más memoria en *Settings → Resources*.
- **Pods en `ImagePullBackOff`:** internet lento; espera y repite `kubectl get pods`.
- **`No se pudo conectar al frontend`:** otro programa usa el puerto 8080, o hay un `port-forward` abierto en otra ventana; ciérralo.
- **Una repetición quedó mal:** borra su carpeta y repítela con `--desde N --reps 1`.
- **Apagar todo:** `minikube stop -p tesis`. **Borrar todo:** `minikube delete -p tesis`.
