"""
Pantalla — Chat conversacional con el agente (Ollama + qwen3.5).

Envuelve OllamaAgent (src/llm.py): mismo flujo de tool-calling que chat.py,
pero con la conversación embebida en la interfaz web.
"""

import shutil
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm import OllamaAgent

st.set_page_config(page_title="Chat", page_icon="💬", layout="wide")
st.title("💬 Chat conversacional")
st.caption(
    "Conversa en lenguaje natural con el agente. Requiere Ollama corriendo "
    "localmente con el modelo configurado o desplegado en la nube (runpod)."
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
        shutil.rmtree(Path("resultados") / "uploads", ignore_errors=True)
        st.session_state.uploaded_excel_path = None
        st.session_state.uploaded_excel_name = None
        st.rerun()

if "agent" not in st.session_state:
    st.session_state.agent = OllamaAgent(model=model, host=host)

agent = st.session_state.agent

for msg in agent.history:
    st.chat_message(msg["role"]).write(msg["content"])

if st.session_state.get("uploaded_excel_path"):
    col1, col2 = st.columns([0.92, 0.08])
    col1.caption(f"📄 Archivo activo: {st.session_state.uploaded_excel_name}")
    if col2.button("✕", key="remove_excel", help="Quitar archivo"):
        st.session_state.uploaded_excel_path = None
        st.session_state.uploaded_excel_name = None
        st.rerun()

prompt = st.chat_input(
    "Escribe tu consulta (ej. 'Optimiza un portafolio con AAPL y MSFT')",
    accept_file=True,
    file_type=["xlsx"],
)

if prompt:
    user_input = prompt.text

    if prompt.files:
        uploaded_file = prompt.files[0]
        upload_dir = Path("resultados") / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_path = upload_dir / uploaded_file.name
        saved_path.write_bytes(uploaded_file.getvalue())
        st.session_state.uploaded_excel_path = str(saved_path)
        st.session_state.uploaded_excel_name = uploaded_file.name
        if not user_input.strip():
            user_input = f"Analiza el archivo {uploaded_file.name}."

    message_to_send = user_input
    if st.session_state.get("uploaded_excel_path"):
        message_to_send += (
            f"\n\n📎 Archivo adjunto: {st.session_state.uploaded_excel_name} "
            f"(ruta: {st.session_state.uploaded_excel_path})"
        )

    st.chat_message("user").write(message_to_send)
    with st.spinner("Pensando..."):
        try:
            response = agent.chat(message_to_send)
        except Exception as e:
            st.error(f"No se pudo conectar con Ollama: {e}. Verifica que el servidor esté corriendo en {host}.")
            response = None

    if response is not None:
        st.chat_message("assistant").write(response)
