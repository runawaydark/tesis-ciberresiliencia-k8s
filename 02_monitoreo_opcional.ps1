# =====================================================================
# 02_monitoreo_opcional.ps1  -  Prometheus + Grafana (OPCIONAL)
# No es necesario para medir: experimento.py ya registra los datos.
# Sirve para capturas de pantalla de dashboards para el informe.
# =====================================================================
$ErrorActionPreference = "Stop"

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack `
    --namespace monitoring --create-namespace `
    --set prometheus.prometheusSpec.scrapeInterval=5s `
    --set grafana.adminPassword=tesis2026

kubectl wait --for=condition=available deployment --all -n monitoring --timeout=600s

Write-Host @"

Grafana listo. Abre otra PowerShell y ejecuta:
    kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80
Navegador: http://localhost:3000   usuario: admin   clave: tesis2026
Dashboard util: 'Kubernetes / Compute Resources / Namespace (Pods)', namespace default.
"@ -ForegroundColor Green
