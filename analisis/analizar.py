"""Calcula las metricas de resiliencia de cada experimento.

Para cada carpeta resultados/<escenario>/rep<N>/ :

1. Curva de funcionalidad F(t)  (vista del usuario, segundo a segundo)
     F_bruta(t) = solicitudes "buenas" que empezaron en el segundo t / total
     buena = respuesta exitosa (2xx/3xx) y latencia <= SLO
     F(t)  = min(1, F_bruta(t) / F0),  F0 = promedio de F_bruta en la linea base
   Si en un segundo no termino ninguna solicitud, F = 0 (el sistema no respondio).

2. Metricas (t = 0 es el instante de la falla, H = horizonte):
     t_impacto   primer segundo con F < umbral                 [s]
     F_min       funcionalidad minima alcanzada                [0-1]
     TTR_usuario segundos hasta que F >= umbral por V segundos seguidos
     TTR_infra   segundos hasta que Kubernetes reporta cartservice disponible
     brecha      TTR_usuario - TTR_infra: tiempo en que Kubernetes "cree" que
                 ya se recupero pero el usuario todavia falla
     perdida     area entre F=1 y F(t) en [0, H]  (regla del trapecio)   [s]
     R           1 - perdida/H = funcionalidad promedio en el horizonte  [0-1]
                 (area bajo la curva normalizada, en la linea de Weisman et al.)
     fallidas    solicitudes fallidas en el horizonte

Complejidad: O(n) en el numero de solicitudes + O(H) en segundos.

Salidas:
  resultados/<esc>/rep<N>/curva.png, metricas.json
  resultados/resumen_repeticiones.csv, resumen_escenarios.csv
  resultados/curvas_<esc>.png (todas las repeticiones superpuestas)
  resultados/comparacion.txt (prueba de Mann-Whitney si hay 2 escenarios)

Uso:  python analisis/analizar.py  [--slo 1000] [--umbral 0.95] [--ventana 10]
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_trap = getattr(np, "trapezoid", None) or np.trapz

BASE = Path(__file__).resolve().parent.parent / "resultados"
CALENTAMIENTO = 20  # s iniciales de k6 que no cuentan para la linea base


def guardar(fig, ruta):
    """Guarda la figura; si el archivo esta abierto/bloqueado, avisa y sigue."""
    try:
        fig.savefig(ruta, dpi=150)
    except OSError:
        alt = ruta.with_name(ruta.stem + "_nuevo.png")
        try:
            fig.savefig(alt, dpi=150)
            print(f"   (aviso) {ruta.name} estaba abierto; se guardo como {alt.name}")
        except OSError:
            print(f"   (aviso) no se pudo guardar {ruta}; cierra el visor de imagenes y repite")
    finally:
        plt.close(fig)


def cargar_k6(ruta):
    df = pd.read_csv(ruta, low_memory=False)
    df = df[df["metric_name"] == "http_req_duration"].copy()
    df["lat_ms"] = df["metric_value"].astype(float)
    df["ok"] = df["expected_response"].astype(str).str.lower().eq("true")
    # k6 marca el FIN de la solicitud; la asignamos al segundo en que EMPEZO
    df["t_ini"] = df["timestamp"].astype(float) - df["lat_ms"] / 1000.0
    return df[["t_ini", "ok", "lat_ms", "name", "status"]]


def curva_funcionalidad(df, t0, t1, slo):
    seg = np.floor(df["t_ini"] - t0).astype(int)
    df = df.assign(seg=seg, buena=df["ok"] & (df["lat_ms"] <= slo))
    g = df.groupby("seg").agg(total=("buena", "size"), buenas=("buena", "sum"))
    idx = np.arange(0, int(np.ceil(t1 - t0)))
    g = g.reindex(idx, fill_value=0)
    g["F_bruta"] = np.where(g["total"] > 0, g["buenas"] / g["total"].clip(lower=1), 0.0)
    g["t_abs"] = t0 + g.index
    return g


def primer_sostenido(cond, desde, ventana):
    """Primer indice i >= desde tal que cond[i:i+ventana] es todo True."""
    c = np.asarray(cond, dtype=bool)
    for i in range(desde, len(c) - ventana + 1):
        if c[i:i + ventana].all():
            return i
    return None


def ttr_infra(ruta, t_falla):
    if not ruta.exists():
        return None, None
    inf = pd.read_csv(ruta)
    inf = inf[(inf["deployment"] == "cartservice") & (inf["t"] >= t_falla)].sort_values("t")
    caidas = inf[inf["disponibles"] < 1]
    if caidas.empty:
        return 0.0, inf  # Kubernetes nunca reporto indisponibilidad
    t_caida = caidas["t"].iloc[0]
    vuelta = inf[(inf["t"] > t_caida) & (inf["disponibles"] >= 1)]
    return (None if vuelta.empty else float(vuelta["t"].iloc[0] - t_falla)), inf


def analizar_rep(carpeta, a):
    ev = json.loads((carpeta / "eventos.json").read_text(encoding="utf-8"))
    df = cargar_k6(carpeta / "k6.csv")
    tf = ev["t_falla"]
    H = ev["parametros"]["horizonte_s"]
    t0 = ev["t_inicio_carga"]
    g = curva_funcionalidad(df, t0, tf + H, a.slo)

    i_falla = int(np.floor(tf - t0))
    base = g.loc[CALENTAMIENTO:i_falla - 1, "F_bruta"]
    F0 = float(base.mean()) if len(base) else 1.0
    g["F"] = (g["F_bruta"] / F0).clip(upper=1.0) if F0 > 0 else 0.0

    post = g.loc[i_falla:i_falla + H - 1]
    F = post["F"].to_numpy()
    t_rel = np.arange(len(F))

    bajo = F < a.umbral
    t_imp = int(np.argmax(bajo)) if bajo.any() else None
    if t_imp is None:
        ttr_u = 0.0
    else:
        k = primer_sostenido(F >= a.umbral, t_imp, a.ventana)
        ttr_u = None if k is None else float(k)

    perdida = float(_trap(1.0 - F, t_rel)) if len(F) > 1 else 0.0
    R = 1.0 - perdida / max(1, len(F) - 1)

    ttr_i, inf = ttr_infra(carpeta / "infra.csv", tf)
    brecha = (ttr_u - ttr_i) if (ttr_u is not None and ttr_i is not None) else None

    ventana_df = df[(df["t_ini"] >= tf) & (df["t_ini"] < tf + H)]
    m = {
        "escenario": ev["escenario"], "repeticion": ev["repeticion"],
        "F0_linea_base": round(F0, 4),
        "F0_desv": round(float(base.std()), 4) if len(base) > 1 else None,
        "t_impacto_s": t_imp, "F_min": round(float(F.min()), 4) if len(F) else None,
        "TTR_usuario_s": ttr_u, "TTR_infra_s": None if ttr_i is None else round(ttr_i, 1),
        "brecha_s": None if brecha is None else round(brecha, 1),
        "perdida_s": round(perdida, 2), "R": round(R, 4),
        "solicitudes": int(len(ventana_df)),
        "fallidas": int((~ventana_df["ok"]).sum()),
    }
    if ev.get("t_reconciliacion"):
        m["t_reconciliacion_s"] = round(ev["t_reconciliacion"] - tf, 1)
    (carpeta / "metricas.json").write_text(json.dumps(m, indent=2), encoding="utf-8")

    graficar_rep(carpeta, g, i_falla, H, m, inf, tf, ev, a)
    curva = pd.DataFrame({"t_rel": np.arange(-i_falla, len(g) - i_falla), "F": g["F"].to_numpy()})
    return m, curva


def graficar_rep(carpeta, g, i_falla, H, m, inf, tf, ev, a):
    x = np.arange(len(g)) - i_falla
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(x, g["F"], color="#2a6fdb", lw=1.4, label="F(t) usuario")
    m_post = x >= 0
    ax.fill_between(x[m_post], g["F"].to_numpy()[m_post], 1, color="#e4572e", alpha=.18,
                    label=f"Pérdida = {m['perdida_s']} s   R = {m['R']}")
    ax.axvline(0, color="#e4572e", ls="--", lw=1.2, label="Falla / ataque")
    if ev.get("t_reconciliacion"):
        ax.axvline(ev["t_reconciliacion"] - tf, color="#17a34a", ls="--", lw=1.2,
                   label="Reconciliación (estado deseado)")
    if m["TTR_usuario_s"] is not None and m["TTR_usuario_s"] > 0:
        ax.axvline(m["TTR_usuario_s"], color="#2a6fdb", ls=":", lw=1.2,
                   label=f"Recuperación usuario ({m['TTR_usuario_s']:.0f} s)")
    ax.axhline(a.umbral, color="gray", lw=.8, ls=":")
    if inf is not None and len(inf):
        ax2 = ax.twinx()
        ax2.step(inf["t"] - tf, inf["disponibles"], where="post", color="#7a5195",
                 lw=1, alpha=.7, label="Réplicas cartservice (Kubernetes)")
        ax2.set_ylim(-0.1, max(2, inf["disponibles"].max() + 1))
        ax2.set_ylabel("Réplicas disponibles")
        ax2.legend(loc="lower right", fontsize=8)
    ax.set_xlim(x[0], H)
    ax.set_ylim(-0.03, 1.05)
    ax.set_xlabel("Tiempo relativo a la falla [s]")
    ax.set_ylabel("Funcionalidad F(t)")
    ax.set_title(f"{m['escenario']} — repetición {m['repeticion']}")
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    guardar(fig, carpeta / "curva.png")


def resumen(metricas, curvas, a):
    df = pd.DataFrame(metricas).sort_values(["escenario", "repeticion"])
    df.to_csv(BASE / "resumen_repeticiones.csv", index=False)
    cols = ["F_min", "TTR_usuario_s", "TTR_infra_s", "brecha_s", "perdida_s", "R", "fallidas"]
    est = df.groupby("escenario")[cols].agg(["mean", "std", "count"]).round(3)
    est.to_csv(BASE / "resumen_escenarios.csv")
    print("\nResumen por escenario (media, desviación, n):\n", est.T.to_string())

    for esc, lista in curvas.items():
        fig, ax = plt.subplots(figsize=(10, 4))
        for i, c in enumerate(lista, 1):
            ax.plot(c["t_rel"], c["F"], lw=1, alpha=.6, label=f"rep {i}")
        todas = pd.concat(lista).groupby("t_rel")["F"].mean()
        ax.plot(todas.index, todas.values, color="black", lw=2, label="promedio")
        ax.axvline(0, color="#e4572e", ls="--")
        ax.set_xlabel("Tiempo relativo a la falla [s]")
        ax.set_ylabel("F(t)")
        ax.set_ylim(-0.03, 1.05)
        ax.set_title(f"Curvas de funcionalidad — {esc}")
        ax.legend(fontsize=8, ncol=3)
        fig.tight_layout()
        guardar(fig, BASE / f"curvas_{esc}.png")

    escs = sorted(df["escenario"].unique())
    if len(escs) == 2:
        try:
            from scipy.stats import mannwhitneyu
        except ImportError:
            return
        lineas = [f"Comparación {escs[0]} vs {escs[1]} (Mann-Whitney U, bilateral)"]
        for c in ["R", "perdida_s", "TTR_usuario_s", "brecha_s"]:
            x = df.loc[df.escenario == escs[0], c].dropna()
            y = df.loc[df.escenario == escs[1], c].dropna()
            if len(x) >= 2 and len(y) >= 2:
                u, p = mannwhitneyu(x, y, alternative="two-sided")
                lineas.append(f"  {c:15s} U={u:6.1f}  p={p:.4f}  medianas {x.median():.3f} vs {y.median():.3f}")
        texto = "\n".join(lineas)
        (BASE / "comparacion.txt").write_text(texto, encoding="utf-8")
        print("\n" + texto)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slo", type=float, default=1000, help="latencia máxima aceptable [ms]")
    ap.add_argument("--umbral", type=float, default=0.95, help="F mínima para considerar 'sano'")
    ap.add_argument("--ventana", type=int, default=10, help="segundos sanos seguidos para 'recuperado'")
    a = ap.parse_args()

    metricas, curvas = [], {}
    for carpeta in sorted(BASE.glob("*/rep*")):
        if not (carpeta / "eventos.json").exists():
            print(f"(omitida, incompleta) {carpeta}")
            continue
        m, c = analizar_rep(carpeta, a)
        metricas.append(m)
        curvas.setdefault(m["escenario"], []).append(c)
        print(f"{carpeta.parent.name}/{carpeta.name}: R={m['R']}  TTR_usuario={m['TTR_usuario_s']}  "
              f"TTR_infra={m['TTR_infra_s']}  brecha={m['brecha_s']}")
    if not metricas:
        print("No hay resultados. Ejecuta primero experimentos/experimento.py")
        return
    resumen(metricas, curvas, a)
    print(f"\nGráficos y tablas en: {BASE}")


if __name__ == "__main__":
    main()
