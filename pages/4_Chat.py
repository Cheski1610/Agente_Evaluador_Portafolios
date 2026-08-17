"""
Pantalla — Chat conversacional con el agente (Ollama + qwen3.5).

Envuelve OllamaAgent (src/llm.py): mismo flujo de tool-calling que chat.py,
pero con la conversación embebida en la interfaz web.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm import OllamaAgent

st.set_page_config(page_title="Chat", page_icon="💬", layout="wide")
st.title("💬 Chat conversacional")
st.caption(
    "Conversa en lenguaje natural con el agente. Requiere Ollama corriendo "
    "localmente con el modelo configurado."
)

with st.sidebar:
    st.subheader("Configuración del modelo")
    model = st.text_input("Modelo", value="qwen3.5:latest")
    host = st.text_input("Servidor Ollama", value="http://localhost:11434")

    if st.button("Aplicar"):
        st.session_state.agent = OllamaAgent(model=model, host=host)
        st.success("Agente recreado con la nueva configuración.")

    if st.button("Reiniciar conversación"):
        if "agent" in st.session_state:
            st.session_state.agent.reset()
        st.rerun()

if "agent" not in st.session_state:
    st.session_state.agent = OllamaAgent(model=model, host=host)

agent = st.session_state.agent

for msg in agent.history:
    st.chat_message(msg["role"]).write(msg["content"])

user_input = st.chat_input("Escribe tu consulta (ej. 'Optimiza un portafolio con AAPL y MSFT')")

if user_input:
    st.chat_message("user").write(user_input)
    with st.spinner("Pensando..."):
        try:
            response = agent.chat(user_input)
        except Exception as e:
            st.error(f"No se pudo conectar con Ollama: {e}. Verifica que el servidor esté corriendo en {host}.")
            response = None

    if response is not None:
        st.chat_message("assistant").write(response)
