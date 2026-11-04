# =====================================================================
# instalacion/00_instalar.ps1  -  Instala las herramientas del laboratorio
# Windows 11. Ejecutar en PowerShell COMO ADMINISTRADOR:
#     .\instalacion\00_instalar.ps1
# =====================================================================
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)   # raiz del repositorio

Write-Host "`n[1/3] WSL2 (necesario para Docker Desktop)" -ForegroundColor Cyan
wsl --status 2>$null
if ($LASTEXITCODE -ne 0) {
    wsl --install --no-distribution
    Write-Host "WSL instalado. REINICIA el computador y vuelve a ejecutar este script." -ForegroundColor Yellow
    exit
}

Write-Host "`n[2/3] Herramientas (winget)" -ForegroundColor Cyan
$paquetes = @(
    "Docker.DockerDesktop",   # motor de contenedores
    "Kubernetes.minikube",    # cluster Kubernetes local
    "Kubernetes.kubectl",     # cliente de Kubernetes
    "Helm.Helm",              # gestor de paquetes (Grafana/Prometheus, opcional)
    "GrafanaLabs.k6",         # generador de carga
    "Python.Python.3.12",     # analisis de datos
    "Git.Git"                 # control de versiones
)
foreach ($p in $paquetes) {
    Write-Host "  -> $p"
    winget install --id $p --exact --accept-source-agreements --accept-package-agreements --silent
}

Write-Host "`n[3/3] Listo." -ForegroundColor Green
Write-Host @"
Pasos manuales:
  1. Abre Docker Desktop una vez y espera a que diga 'Engine running'.
  2. CIERRA esta ventana y abre una PowerShell nueva (normal, no admin)
     en la carpeta del repositorio, para que se carguen las rutas nuevas.
  3. Ejecuta:
        python -m pip install -r requirements.txt
  4. Sigue con: .\instalacion\01_laboratorio.ps1
"@
