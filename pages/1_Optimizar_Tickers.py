"""
Pantalla — Optimizar desde Tickers.

Réplica del Modo 2 de agent.py: descarga precios de Yahoo Finance para una
lista de tickers y calcula el portafolio óptimo Mean-Variance.
"""

import sys
from datetime import date
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.web_utils import capture_output
from src.data import download_prices, compute_returns, default_date_range
from src.optimizer import build_portfolio, optimize, compute_metrics
from src.report import plot_portfolio, save_to_excel, save_riskfolio_report, save_jupyter_report

st.set_page_config(page_title="Optimizar Tickers", page_icon="📈", layout="wide")
st.title("📈 Optimizar desde Tickers")
st.caption("Descarga precios de Yahoo Finance y calcula el portafolio óptimo Mean-Variance.")

_default_start, _default_end = default_date_range(years=3)

if "tickers_result" not in st.session_state:
    st.session_state.tickers_result = None

with st.form("form_optimizar_tickers"):
    tickers_input = st.text_input(
        "Tickers (separados por espacio o coma)",
        value="AAPL MSFT GOOGL AMZN META",
        help="Símbolos bursátiles de Yahoo Finance, mínimo 2.",
    )

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Fecha de inicio", value=date.fromisoformat(_default_start))
    with col2:
        end_date = st.date_input("Fecha de fin", value=date.fromisoformat(_default_end))

    col3, col4, col5 = st.columns(3)
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
    with col5:
        returns_method = st.selectbox("Método de retornos", options=["simple", "log"])

    col6, col7, col8 = st.columns(3)
    with col6:
        rf_pct = st.number_input("Tasa libre de riesgo anual (%)", value=0.0, step=0.1)
    with col7:
        max_weight_pct = st.slider("Peso máximo por activo (%)", min_value=1, max_value=100, value=50)
    with col8:
        allow_short = st.checkbox("Permitir posiciones cortas", value=False)

    output_dir = st.text_input("Carpeta de resultados", value="resultados/")

    submitted = st.form_submit_button("Optimizar")

if submitted:
    tickers = [t.strip().upper() for t in tickers_input.replace(",", " ").split() if t.strip()]

    if len(tickers) < 2:
        st.error("Se necesitan al menos 2 tickers.")
    elif start_date >= end_date:
        st.error("La fecha de inicio debe ser anterior a la fecha de fin.")
    else:
        try:
            with capture_output() as logs:
                prices = download_prices(
                    tickers=tickers,
                    start=start_date.isoformat(),
                    end=end_date.isoformat(),
                )
                returns = compute_returns(prices, method=returns_method)

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

                out_dir = Path(output_dir)
                out_dir.mkdir(parents=True, exist_ok=True)

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

            st.session_state.tickers_result = {
                "weights": weights,
                "metrics": metrics,
                "excel_path": excel_path,
                "riskfolio_report_path": Path(f"{riskfolio_report_path}.xlsx"),
                "jupyter_path": jupyter_path,
                "plot_path": plot_path,
                "logs": logs.getvalue(),
            }
        except SystemExit:
            st.error("No se pudieron descargar los datos. Verifica los tickers y las fechas.")
            st.session_state.tickers_result = None
        except (ValueError, RuntimeError) as e:
            st.error(str(e))
            st.session_state.tickers_result = None

result = st.session_state.tickers_result
if result:
    st.success("Optimización completada.")

    w = (result["weights"] * 100).round(4)
    w.columns = ["Peso (%)"]
    w = w[w["Peso (%)"] > 0.001].sort_values("Peso (%)", ascending=False)
    st.dataframe(w, use_container_width=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("Retorno esperado (anual)", f"{result['metrics']['Retorno Esperado (anual)']:.2%}")
    m2.metric("Volatilidad (anual)", f"{result['metrics']['Volatilidad (anual)']:.2%}")
    m3.metric("Sharpe Ratio", f"{result['metrics']['Sharpe Ratio']:.4f}")

    st.image(str(result["plot_path"]), caption="Composición y frontera eficiente")
    st.image(str(result["jupyter_path"]), caption="Reporte visual Riskfolio")

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

    with st.expander("Logs"):
        st.text(result["logs"])
