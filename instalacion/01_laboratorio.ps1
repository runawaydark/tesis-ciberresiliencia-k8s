# =====================================================================
# instalacion/01_laboratorio.ps1  -  Levanta el cluster y despliega Online Boutique
# Ejecutar en PowerShell normal, con Docker Desktop abierto:
#     .\instalacion\01_laboratorio.ps1
# =====================================================================
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)   # raiz del repositorio
$ManifiestoURL = "https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/main/release/kubernetes-manifests.yaml"
$Original = "laboratorio\manifiestos\online-boutique-original.yaml"

Write-Host "`n[1/5] Iniciando cluster Minikube (6 CPU, 12 GB)" -ForegroundColor Cyan
minikube start --driver=docker --cpus=6 --memory=12288 --profile=tesis
kubectl config use-context tesis

Write-Host "`n[2/5] Manifiesto de Online Boutique" -ForegroundColor Cyan
if (Test-Path $Original) {
    # Se usa la copia versionada en el repositorio: garantiza que todos
    # los experimentos usen exactamente la misma version de la aplicacion.
    Write-Host "  Usando la version congelada del repositorio ($Original)"
} else {
    New-Item -ItemType Directory -Force -Path laboratorio\manifiestos | Out-Null
    Invoke-WebRequest -Uri $ManifiestoURL -OutFile $Original
    Write-Host "  Descargado desde GitHub. Recuerda versionarlo (git add)."
}

Write-Host "`n[3/5] Generando el 'estado deseado' (sin el generador de carga interno)" -ForegroundColor Cyan
python laboratorio\preparar_manifiesto.py

Write-Host "`n[4/5] Desplegando (la primera vez tarda 5-10 min en bajar imagenes)" -ForegroundColor Cyan
kubectl apply -f laboratorio\manifiestos\estado-deseado.yaml
kubectl apply -f laboratorio\ataques\rbac-sa-comprometida.yaml
kubectl wait --for=condition=available deployment --all -n default --timeout=900s

Write-Host "`n[5/5] Verificacion" -ForegroundColor Cyan
kubectl get pods -n default
kubectl auth can-i delete deployments --as=system:serviceaccount:default:sa-comprometida -n default

Write-Host @"

Laboratorio listo. Para ver la tienda en el navegador:
    kubectl port-forward svc/frontend 8080:80
y abre http://localhost:8080   (Ctrl+C para cerrar el port-forward
ANTES de correr experimentos)

Siguiente paso: python experimentos\experimento.py --escenario podkill --reps 1
"@ -ForegroundColor Green
