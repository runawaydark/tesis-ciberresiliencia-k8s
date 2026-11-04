# Auditoría del MVP – 2 de noviembre de 2026

Revisión de los datos crudos de las 10 repeticiones (5 `podkill`, 5 `ataque-rbac`).

## Integridad de los datos

| Verificación | Resultado |
|---|---|
| Iteraciones de k6 por repetición | 1 700–1 701 (esperado: 5/s × 340 s = 1 700) |
| Iteraciones descartadas o interrumpidas | 0 en las 10 repeticiones |
| Advertencias o errores de k6 | 0 |
| Duración de la línea base | 120,0 s en todas |
| Retardo de reconciliación (ataque) | 60,1 s en todas |
| Muestreo de Kubernetes (`infra.csv`) | 341 muestras por repetición, cada 1,0 s, sin huecos |
| Fallas durante la línea base | 0 (las 0–16 registradas justo antes de la falla son solicitudes en curso al momento de la inyección; k6 guarda los tiempos en segundos enteros) |
| Latencia p95 en línea base | 21–73 ms |
| Tipo de falla durante la caída | 100 % HTTP 500 rápidos (≤ 96 ms): el frontend responde error, no hay timeouts |
| Reproducibilidad del análisis | Recalculado de forma independiente: diferencia 0,0 en todas las métricas |

## Incidentes durante la ejecución y su efecto

1. **Error al guardar `curva.png` (`analizar.py`).** El archivo estaba abierto en el visor de imágenes. Solo afectó la escritura del gráfico, no los datos. Corregido: el script ahora avisa y continúa. El análisis se volvió a ejecutar completo.
2. **Mensajes de error del `port-forward` manual.** Una ventana de `port-forward` abierta para ver la tienda quedó activa; el tráfico de k6 pasó por ella. Registra como error cada conexión que k6 cierra al terminar. Sin efecto en las mediciones: misma ruta hacia el frontend, línea base estable y 0 iteraciones perdidas. Protocolo: mantener cerrada esa ventana durante los experimentos.
3. **Texto "repetición 5/4".** Error cosmético del contador cuando se usa `--desde`. Los datos se guardaron en la carpeta correcta. Corregido.

## Conclusión

Los 10 experimentos son válidos y no requieren repetirse. El MVP funciona de punta a punta: despliegue → carga → inyección de falla/ataque → medición dual (usuario y Kubernetes) → métricas y pruebas estadísticas reproducibles.
