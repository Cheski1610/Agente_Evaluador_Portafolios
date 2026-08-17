"""
Pantalla — Crear Excel de portafolio.

Réplica del Modo 0 de agent.py / create_portfolio_excel: descarga precios para
una composición de portafolio (ticker + peso) y genera un Excel con hojas
"Precios" y "Pesos", listo para usarse en "Analizar Excel".
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.web_utils import capture_output
from src.data import create_portfolio_excel, default_date_range

st.set_page_config(page_title="Crear Excel", page_icon="🧾", layout="wide")
st.title("🧾 Crear Excel de portafolio")
st.caption(
    "Define una composición de portafolio (ticker + peso) y genera un Excel "
    "con precios históricos, listo para usar en 'Analizar Excel'."
)

_default_start, _default_end = default_date_range(years=3)

if "create_excel_result" not in st.session_state:
    st.session_state.create_excel_result = None

with st.form("form_crear_excel"):
    composition_df = st.data_editor(
        pd.DataFrame({"Ticker": ["AAPL", "MSFT"], "Peso": [0.4, 0.6]}),
        num_rows="dynamic",
        use_container_width=True,
        key="composition_editor",
    )

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Fecha de inicio", value=date.fromisoformat(_default_start))
    with col2:
        end_date = st.date_input("Fecha de fin", value=date.fromisoformat(_default_end))

    output_path = st.text_input("Ruta del archivo a generar", value="resultados/mi_portafolio.xlsx")

    submitted = st.form_submit_button("Crear Excel")

if submitted:
    rows = composition_df.dropna(subset=["Ticker", "Peso"])
    rows = rows[rows["Ticker"].astype(str).str.strip() != ""]

    if rows.empty:
        st.error("Agrega al menos un ticker con su peso.")
    elif start_date >= end_date:
        st.error("La fecha de inicio debe ser anterior a la fecha de fin.")
    else:
        composition = {
            str(t).strip().upper(): float(w)
            for t, w in zip(rows["Ticker"], rows["Peso"])
        }
        try:
            with capture_output() as logs:
                generated_path = create_portfolio_excel(
                    composition, start_date.isoformat(), end_date.isoformat(), output_path
                )
                preview_prices = pd.read_excel(generated_path, sheet_name="Precios", index_col=0)

            st.session_state.create_excel_result = {
                "composition": composition,
                "generated_path": Path(generated_path),
                "prices": preview_prices,
                "logs": logs.getvalue(),
            }
        except SystemExit:
            st.error("No se pudieron descargar los precios. Verifica los tickers y las fechas.")
            st.session_state.create_excel_result = None
        except ValueError as e:
            st.error(str(e))
            st.session_state.create_excel_result = None

result = st.session_state.create_excel_result
if result:
    st.success(f"Excel generado en: {result['generated_path']}")

    comp_df = pd.DataFrame(
        {"Peso (%)": [w * 100 for w in result["composition"].values()]},
        index=list(result["composition"].keys()),
    ).sort_values("Peso (%)", ascending=False)
    st.dataframe(comp_df, use_container_width=True)

    st.line_chart(result["prices"])

    st.download_button(
        f"Descargar {result['generated_path'].name}",
        data=result["generated_path"].read_bytes(),
        file_name=result["generated_path"].name,
    )

    with st.expander("Logs"):
        st.text(result["logs"])
