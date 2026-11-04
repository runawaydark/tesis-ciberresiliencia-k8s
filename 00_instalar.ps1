# =====================================================================
# 00_instalar.ps1  -  Instala las herramientas del laboratorio (Windows 11)
# Ejecutar en PowerShell COMO ADMINISTRADOR, desde la carpeta kit-mvp.
# =====================================================================
$ErrorActionPreference = "Stop"

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
    "k6",                     # generador de carga
    "Python.Python.3.12"      # analisis de datos
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
     para que se carguen las rutas nuevas.
  3. En la carpeta kit-mvp ejecuta:
        python -m pip install -r requirements.txt
  4. Sigue con: .\01_laboratorio.ps1
"@
