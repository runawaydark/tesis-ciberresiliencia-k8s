# Medición cuantitativa de ciberresiliencia en infraestructuras basadas en contenedores y Kubernetes

*Análisis de métricas para degradación, continuidad y recuperación de microservicios*

Tesis de pregrado · Ingeniería Civil Informática · Universidad Andrés Bello · Curso CINF200

**Pregunta de investigación:** ¿En qué medida las métricas cuantitativas actuales representan adecuadamente la ciberresiliencia operacional de aplicaciones de microservicios desplegadas en Kubernetes frente a eventos de degradación y recuperación?

Este repositorio contiene un laboratorio reproducible que despliega **Online Boutique** (11 microservicios) en **Minikube**, genera carga de usuarios con **k6**, inyecta fallas y ataques, y mide en paralelo la recuperación desde dos perspectivas: la del **usuario** (curva de funcionalidad F(t)) y la de **Kubernetes** (réplicas disponibles).

**Equipo:** Elías Gabriel Pérez Uribe · Uriel Esteban Navarrete Cadima
**Profesor:** Rodrigo Hernán Díaz Miranda

---

## Estructura del repositorio

| Carpeta | Qué contiene |
|---|---|
| `instalacion/` | Scripts de PowerShell para instalar las herramientas y levantar el laboratorio |
| `laboratorio/` | Definición del sistema bajo estudio: manifiestos de Kubernetes (versión congelada) y escenarios de ataque |
| `carga/` | Script de k6 que simula usuarios comprando en la tienda |
| `experimentos/` | Orquestador del protocolo experimental (línea base → perturbación → recuperación) |
| `analisis/` | Cálculo de métricas de resiliencia, gráficos y pruebas estadísticas |
| `resultados/` | Resultados de cada repetición, organizados por escenario |
| `docs/` | Entregas del curso y auditorías de los datos |

```
.
├── instalacion/
│   ├── 00_instalar.ps1
│   ├── 01_laboratorio.ps1
│   └── 02_monitoreo_opcional.ps1
├── laboratorio/
│   ├── manifiestos/          online-boutique-original.yaml · estado-deseado.yaml
│   ├── ataques/              rbac-sa-comprometida.yaml
│   └── preparar_manifiesto.py
├── carga/                    carga.js
├── experimentos/             experimento.py
├── analisis/                 analizar.py
├── resultados/
│   ├── podkill/rep1..rep5/
│   ├── ataque-rbac/rep1..rep5/
│   └── resumen_*.csv · curvas_*.png · comparacion.txt
├── docs/
│   ├── entregas/             E1, E2, E3...
│   └── auditorias/
├── requirements.txt
└── .gitignore
```

## Escenarios

| Escenario | Perturbación | Mecanismo de recuperación |
|---|---|---|
| `podkill` | Se eliminan los pods de `cartservice` | *Self-healing* de Kubernetes |
| `ataque-rbac` | Una cuenta de servicio con permisos excesivos borra el *deployment* `cartservice` | Reaplicar el estado deseado declarativo (tipo GitOps) |

## Cómo reproducir

Todos los comandos se ejecutan **desde la carpeta raíz del repositorio**, en PowerShell (Windows 11, 16 GB de RAM o más).

**1. Instalar herramientas** (PowerShell como administrador):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\instalacion\00_instalar.ps1
```

Si instala WSL, reinicia y ejecútalo otra vez. Luego abre Docker Desktop y espera "Engine running".

**2. Librerías de Python** (PowerShell nueva y normal):

```powershell
python -m pip install -r requirements.txt
```

**3. Levantar el laboratorio:**

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\instalacion\01_laboratorio.ps1
```

**4. Ejecutar una campaña y analizarla:**

```powershell
python experimentos\experimento.py --escenario podkill --reps 5
python experimentos\experimento.py --escenario ataque-rbac --reps 5 --retardo 60
python analisis\analizar.py
```

Cada repetición dura unos 7 minutos. Durante la campaña no debe haber otra ventana con `kubectl port-forward` abierta.

## Métricas

| Métrica | Significado |
|---|---|
| F(t) | Fracción de solicitudes exitosas y dentro del SLO (1 000 ms) por segundo, normalizada por la línea base |
| TTR usuario | Segundos hasta que F(t) ≥ 0,95 durante 10 s seguidos |
| TTR infra | Segundos hasta que Kubernetes reporta el servicio disponible |
| Brecha | TTR usuario − TTR infra |
| Pérdida L | Área entre F = 1 y F(t) tras la perturbación (segundos de servicio perdidos) |
| R | 1 − L/H: funcionalidad promedio en el horizonte observado |

## Datos crudos

Los registros de cada solicitud (`k6.csv`, ~6 MB por repetición) no se versionan en el repositorio. Se publican comprimidos en la sección **Releases**, uno por campaña experimental.

## Versiones

| Etiqueta | Contenido |
|---|---|
| `v-E2` | MVP: laboratorio operativo y campaña de 10 repeticiones (02-11-2026) |

## Referencia principal

Weisman, M. J., Kott, A., et al. (2025). Quantitative measurement of cyber resilience: Modeling and experimentation. *ACM Transactions on Cyber-Physical Systems, 9*(1). https://doi.org/10.1145/3703159
