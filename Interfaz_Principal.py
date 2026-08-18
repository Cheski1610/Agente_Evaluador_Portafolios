"""
Interfaz web — Agente de Optimización de Portafolios (Riskfolio-Lib).

Punto de entrada de la app Streamlit. Usar:
    streamlit run Interfaz_Principal.py
"""

import streamlit as st

st.set_page_config(
    page_title="Agente de Portafolios",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Agente de Optimización de Portafolios")
st.markdown(
    """
Interfaz web para el agente de optimización de portafolios basado en
**Riskfolio-Lib** (modelo Mean-Variance / Markowitz). Usa el menú de la
izquierda para navegar entre las pantallas disponibles.
"""
)

st.subheader("Pantallas disponibles")

st.markdown(
    """
- **📈 Optimizar Tickers** — Descarga precios de Yahoo Finance para una lista
  de tickers y calcula el portafolio óptimo (Sharpe, mínima varianza, máximo
  retorno o utilidad).
- **📁 Analizar Portafolio** — Sube un Excel propio con hoja `Precios` (y
  opcionalmente `Pesos`) para analizar un portafolio existente u optimizarlo
  usando esos precios.
- **🧾 Crear Portafolio** — Genera un archivo Excel con hojas `Precios`/`Pesos` a
  partir de una composición de portafolio (ticker + peso) que definas, listo
  para usarse luego en "Analizar Portafolio".
- **💬 Chat** — Conversa con el agente vía lenguaje natural (requiere
  [Ollama](https://ollama.com) corriendo localmente con el modelo `qwen3.5` o personalizable con otros modelos y despliegues de Ollama en la nube).
"""
)

st.info(
    "Todos los resultados se muestran embebidos en la app y además se guardan "
    "como archivos (Excel/PNG) en la carpeta `resultados/` por defecto."
)
