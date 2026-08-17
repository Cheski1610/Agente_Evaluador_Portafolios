"""
Pantalla — Analizar u Optimizar un Excel propio.

Réplica de `_run_excel_portfolio` en agent.py, ambos submodos:
- Analizar: usa las hojas "Precios" y "Pesos" tal cual.
- Optimizar: usa solo la hoja "Precios" y calcula el portafolio óptimo.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.web_utils import capture_output
from src.data import load_portfolio_from_excel, load_prices_from_excel
from src.optimizer import build_portfolio, optimize, compute_metrics
from src.report import plot_portfolio, save_to_excel, save_riskfolio_report, save_jupyter_report

st.set_page_config(page_title="Analizar Excel", page_icon="📁", layout="wide")
st.title("📁 Analizar / Optimizar Excel propio")
st.caption(
    "Sube un Excel con hoja 'Precios' (y opcionalmente 'Pesos') para analizar "
    "un portafolio existente u optimizarlo usando esos precios."
)

if "excel_result" not in st.session_state:
    st.session_state.excel_result = None

uploaded_file = st.file_uploader("Sube tu Excel", type=["xlsx"])

modo = st.radio(
    "Modo",
    options=["Analizar (usar Pesos)", "Optimizar (usar solo Precios)"],
    horizontal=True,
)
is_optimize = modo == "Optimizar (usar solo Precios)"

if is_optimize:
    col3, col4 = st.columns(2)
    with col3:
        objective = st.selectbox(
            "Objetivo",
            options=["sharpe", "min_risk", "max_ret", "utility"],
            format_func=lambda o: {
                "sharpe": "Máximo Sharpe",
                "min_risk": "Mínima varianza",
                "max_ret": "Máximo retorno",
                "utility": "Máxima utilidad",
            }[o],
        )
    with col4:
        risk_measure = st.selectbox("Medida de riesgo", options=["MV", "MAD", "CVaR"])

    col6, col7, col8 = st.columns(3)
    with col6:
        rf_pct = st.number_input("Tasa libre de riesgo anual (%)", value=0.0, step=0.1)
    with col7:
        max_weight_pct = st.slider("Peso máximo por activo (%)", min_value=1, max_value=100, value=50)
    with col8:
        allow_short = st.checkbox("Permitir posiciones cortas", value=False)
else:
    rf_pct = st.number_input("Tasa libre de riesgo anual (%)", value=0.0, step=0.1)

output_dir = st.text_input("Carpeta de resultados", value="resultados/")

if st.button("Ejecutar"):
    if uploaded_file is None:
        st.error("Sube un archivo Excel antes de continuar.")
    else:
        try:
            uploaded_file.seek(0)
            with capture_output() as logs:
                out_dir = Path(output_dir)
                out_dir.mkdir(parents=True, exist_ok=True)

                if is_optimize:
                    returns = load_prices_from_excel(uploaded_file)

                    port = build_portfolio(returns)
                    weights = optimize(
                        port=port,
                        objective=objective,
                        risk_measure=risk_measure,
                        risk_free_rate=rf_pct / 100,
                        long_only=not allow_short,
                        max_weight=max_weight_pct / 100,
                    )
                    metrics = compute_metrics(weights, returns, risk_free_rate=rf_pct / 100)

                    excel_path = out_dir / "portafolio.xlsx"
                    save_to_excel(weights, metrics, returns, str(excel_path))

                    riskfolio_report_path = out_dir / "riskfolio_report"
                    save_riskfolio_report(
                        weights=weights,
                        returns=returns,
                        output_path=str(riskfolio_report_path),
                        risk_free_rate=rf_pct / 100,
                    )

                    jupyter_path = out_dir / "jupyter_report.png"
                    save_jupyter_report(
                        weights=weights,
                        returns=returns,
                        output_path=str(jupyter_path),
                        risk_free_rate=rf_pct / 100,
                        risk_measure=risk_measure,
                    )

                    plot_path = out_dir / "portfolio_optimization.png"
                    plot_portfolio(
                        weights=weights,
                        port=port,
                        risk_measure=risk_measure,
                        output_dir=str(out_dir),
                        show=False,
                    )
                else:
                    returns, weights = load_portfolio_from_excel(uploaded_file)
                    metrics = compute_metrics(weights, returns, risk_free_rate=rf_pct / 100)

                    excel_path = None
                    riskfolio_report_path = out_dir / "riskfolio_report"
                    save_riskfolio_report(
                        weights=weights,
                        returns=returns,
                        output_path=str(riskfolio_report_path),
                        risk_free_rate=rf_pct / 100,
                    )

                    jupyter_path = out_dir / "jupyter_report.png"
                    save_jupyter_report(
                        weights=weights,
                        returns=returns,
                        output_path=str(jupyter_path),
                        risk_free_rate=rf_pct / 100,
                        risk_measure="MV",
                    )
                    plot_path = None

            st.session_state.excel_result = {
                "weights": weights,
                "metrics": metrics,
                "excel_path": excel_path,
                "riskfolio_report_path": Path(f"{riskfolio_report_path}.xlsx"),
                "jupyter_path": jupyter_path,
                "plot_path": plot_path,
                "logs": logs.getvalue(),
            }
        except SystemExit:
            st.error("No se pudieron descargar los precios necesarios. Verifica el Excel.")
            st.session_state.excel_result = None
        except (ValueError, RuntimeError) as e:
            st.error(str(e))
            st.session_state.excel_result = None

result = st.session_state.excel_result
if result:
    st.success("Procesamiento completado.")

    w = result["weights"].copy()
    w.columns = ["Peso (%)"]
    w["Peso (%)"] = (w["Peso (%)"] * 100).round(4)
    w = w[w["Peso (%)"] > 0.001].sort_values("Peso (%)", ascending=False)
    st.dataframe(w, use_container_width=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("Retorno esperado (anual)", f"{result['metrics']['Retorno Esperado (anual)']:.2%}")
    m2.metric("Volatilidad (anual)", f"{result['metrics']['Volatilidad (anual)']:.2%}")
    m3.metric("Sharpe Ratio", f"{result['metrics']['Sharpe Ratio']:.4f}")

    if result["plot_path"]:
        st.image(str(result["plot_path"]), caption="Composición y frontera eficiente")
    st.image(str(result["jupyter_path"]), caption="Reporte visual Riskfolio")

    if result["excel_path"]:
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "Descargar portafolio.xlsx",
                data=Path(result["excel_path"]).read_bytes(),
                file_name="portafolio.xlsx",
            )
        with d2:
            st.download_button(
                "Descargar riskfolio_report.xlsx",
                data=result["riskfolio_report_path"].read_bytes(),
                file_name="riskfolio_report.xlsx",
            )
    else:
        st.download_button(
            "Descargar riskfolio_report.xlsx",
            data=result["riskfolio_report_path"].read_bytes(),
            file_name="riskfolio_report.xlsx",
        )

    with st.expander("Logs"):
        st.text(result["logs"])
