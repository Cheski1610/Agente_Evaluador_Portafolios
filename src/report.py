"""
Módulo de visualización y reporte de resultados del portafolio.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import riskfolio as rp
import warnings
from pathlib import Path


def print_weights(weights: pd.DataFrame, metrics: dict) -> None:
    """Imprime pesos y métricas en consola con formato tabular."""
    print("\n" + "=" * 55)
    print("  PORTAFOLIO ÓPTIMO — ASIGNACIÓN DE PESOS")
    print("=" * 55)

    w = weights.copy()
    w.columns = ["Peso (%)"]
    w["Peso (%)"] = (w["Peso (%)"] * 100).round(4)
    w = w[w["Peso (%)"] > 0.001].sort_values("Peso (%)", ascending=False)

    col_w = max(len(str(i)) for i in w.index) + 2
    print(f"  {'Activo':<{col_w}}  {'Peso (%)':>10}")
    print("  " + "-" * (col_w + 13))
    for ticker, row in w.iterrows():
        print(f"  {ticker:<{col_w}}  {row['Peso (%)']:>10.4f}")
    print("  " + "-" * (col_w + 13))
    print(f"  {'TOTAL':<{col_w}}  {w['Peso (%)'].sum():>10.4f}")

    print("\n" + "=" * 55)
    print("  MÉTRICAS (ANUALIZADAS)")
    print("=" * 55)
    for k, v in metrics.items():
        print(f"  {k:<30}  {v:>8.4f}")
    print("=" * 55 + "\n")


def plot_portfolio(
    weights: pd.DataFrame,
    port: rp.Portfolio,
    risk_measure: str = "MV",
    output_dir: str | None = None,
    show: bool = True,
) -> None:
    """
    Genera gráficos del portafolio: pie de pesos y frontera eficiente.

    Args:
        weights: Pesos óptimos.
        port: Objeto rp.Portfolio.
        risk_measure: Medida de riesgo.
        output_dir: Carpeta donde guardar las imágenes (None = no guardar).
        show: Si True, muestra los gráficos en pantalla.
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Optimización de Portafolio — Mean-Variance", fontsize=14, fontweight="bold")

    # --- Gráfico 1: Pie de pesos ---
    ax_pie = axes[0]
    w = weights.copy()
    w = w[w.iloc[:, 0] > 0.001]
    labels = w.index.tolist()
    sizes = w.iloc[:, 0].values

    ax_pie.pie(
        sizes,
        labels=labels,
        autopct="%1.2f%%",
        startangle=90,
        pctdistance=0.82,
    )
    ax_pie.set_title("Composición del Portafolio", fontsize=12)

    # --- Gráfico 2: Frontera Eficiente ---
    ax_ef = axes[1]
    try:
        frontier = port.efficient_frontier(
            model="Classic",
            rm=risk_measure,
            points=50,
            rf=0,
            hist=True,
        )

        mu = port.mu
        cov = port.cov
        n_assets = len(weights)
        periods = 252

        # Calcular retorno y volatilidad de la frontera
        rets = []
        vols = []
        for col in frontier.columns:
            w_arr = frontier[col].values
            r = float(np.dot(w_arr, mu.values.flatten())) * periods
            v = float(np.sqrt(np.dot(w_arr, np.dot(cov.values, w_arr)))) * np.sqrt(periods)
            rets.append(r)
            vols.append(v)

        ax_ef.plot(vols, rets, "b-", linewidth=2, label="Frontera Eficiente")

        # Punto del portafolio óptimo
        w_opt = weights.values.flatten()
        r_opt = float(np.dot(w_opt, mu.values.flatten())) * periods
        v_opt = float(np.sqrt(np.dot(w_opt, np.dot(cov.values, w_opt)))) * np.sqrt(periods)
        ax_ef.scatter(v_opt, r_opt, color="red", zorder=5, s=100, label="Portafolio Óptimo")

        ax_ef.set_xlabel("Volatilidad (anual)", fontsize=11)
        ax_ef.set_ylabel("Retorno Esperado (anual)", fontsize=11)
        ax_ef.set_title("Frontera Eficiente", fontsize=12)
        ax_ef.legend()
        ax_ef.grid(True, alpha=0.3)
        ax_ef.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.1%}"))
        ax_ef.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.1%}"))

    except Exception as e:
        ax_ef.text(0.5, 0.5, f"No se pudo calcular\nla frontera eficiente\n{e}",
                   ha="center", va="center", transform=ax_ef.transAxes)

    plt.tight_layout()

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "portfolio_optimization.png"
        plt.savefig(path, dpi=150, bbox_inches="tight")
        print(f"[INFO] Gráfico guardado en: {path}")

    if show:
        plt.show()
    else:
        plt.close()


def save_riskfolio_report(
    weights: pd.DataFrame,
    returns: pd.DataFrame,
    output_path: str,
    risk_free_rate: float = 0.0,
    alpha: float = 0.05,
) -> None:
    """
    Genera el reporte estándar de Riskfolio-Lib en formato Excel.

    El reporte incluye múltiples hojas con métricas de riesgo/retorno
    (CAGR, Sharpe, VaR, CVaR, EVaR, MaxDrawdown, etc.), retornos acumulados,
    drawdowns y composición del portafolio.

    Args:
        weights: Pesos óptimos del portafolio (n_assets x 1).
        returns: DataFrame de retornos diarios (n_days x n_assets).
        output_path: Ruta de salida SIN extensión .xlsx (se añade automáticamente).
        risk_free_rate: Tasa libre de riesgo anualizada en decimal (ej. 0.05 = 5%).
        alpha: Nivel de significancia para medidas de cola (VaR, CVaR, etc.).
    """
    # Riskfolio espera la tasa en unidades del período (daily)
    rf_daily = (1 + risk_free_rate) ** (1 / 252) - 1

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # EVaR/EDaR requieren cono exponencial (CVXPY). Con los solvers disponibles
    # (CLARABEL + SCS) el resultado puede ser OPTIMAL_INACCURATE: numéricamente
    # aceptable pero CVXPY emite un UserWarning redundante. Se suprime aquí porque
    # el cálculo sigue siendo correcto y no hay solver más preciso instalado.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Solution may be inaccurate",
            category=UserWarning,
        )
        rp.excel_report(
            returns=returns,
            w=weights,
            rf=rf_daily,
            alpha=alpha,
            t_factor=252,
            ini_days=1,
            days_per_year=252,
            name=output_path,
        )
    print(f"[INFO] Reporte Riskfolio guardado en: {output_path}.xlsx")


def save_jupyter_report(
    weights: pd.DataFrame,
    returns: pd.DataFrame,
    output_path: str,
    risk_free_rate: float = 0.0,
    alpha: float = 0.05,
    risk_measure: str = "MV",
) -> None:
    """
    Genera el reporte visual de Riskfolio-Lib (jupyter_report) y lo guarda como PNG.

    El reporte incluye 5 paneles: tabla de métricas, composición (pie), histograma
    de retornos, drawdown y contribución al riesgo por activo.

    Args:
        weights: Pesos óptimos del portafolio (n_assets x 1).
        returns: DataFrame de retornos diarios (n_days x n_assets).
        output_path: Ruta del archivo PNG a generar.
        risk_free_rate: Tasa libre de riesgo anualizada en decimal (ej. 0.05 = 5%).
        alpha: Nivel de significancia para medidas de cola (VaR, CVaR, etc.).
        risk_measure: Medida de riesgo para el panel de contribución al riesgo (ej. 'MV', 'CVaR').
    """
    rf_daily = (1 + risk_free_rate) ** (1 / 252) - 1

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Mismo motivo que en save_riskfolio_report: EVaR/EDaR con SCS puede producir
    # OPTIMAL_INACCURATE → UserWarning redundante. Se suprime localmente.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Solution may be inaccurate",
            category=UserWarning,
        )
        ax = rp.jupyter_report(
            returns=returns,
            w=weights,
            rm=risk_measure,
            rf=rf_daily,
            alpha=alpha,
            t_factor=252,
            ini_days=1,
            days_per_year=252,
        )

    fig = ax[0].get_figure() if hasattr(ax, "__len__") else ax.get_figure()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[INFO] Reporte visual Riskfolio guardado en: {output_path}")


def save_to_excel(
    weights: pd.DataFrame,
    metrics: dict,
    returns: pd.DataFrame,
    output_path: str,
) -> None:
    """
    Exporta resultados a un archivo Excel.

    Args:
        weights: Pesos óptimos.
        metrics: Métricas del portafolio.
        returns: DataFrame de retornos.
        output_path: Ruta del archivo .xlsx a generar.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        # Hoja 1: Pesos
        w_out = (weights * 100).round(4)
        w_out.columns = ["Peso (%)"]
        w_out.to_excel(writer, sheet_name="Pesos")

        # Hoja 2: Métricas
        metrics_df = pd.DataFrame.from_dict(
            metrics, orient="index", columns=["Valor"]
        )
        metrics_df.to_excel(writer, sheet_name="Métricas")

        # Hoja 3: Retornos
        returns.to_excel(writer, sheet_name="Retornos")

    print(f"[INFO] Resultados exportados a: {output_path}")
