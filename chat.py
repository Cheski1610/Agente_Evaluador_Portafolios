#!/usr/bin/env python
"""
Agente conversacional de optimización de portafolios.
Usa qwen3.5 vía Ollama para interpretar peticiones en lenguaje natural
y ejecutar optimizaciones con Riskfolio-Lib / yfinance.

Uso:
    python -X utf8 chat.py
    python -X utf8 chat.py --model qwen3.5:latest
    python -X utf8 chat.py --host http://localhost:11434
"""

import argparse
import sys
from pathlib import Path

# Encoding UTF-8 en Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

from src.llm import OllamaAgent

BANNER = """
╔══════════════════════════════════════════════════════════╗
║   AGENTE DE PORTAFOLIOS — qwen3.5 + Riskfolio-Lib       ║
╠══════════════════════════════════════════════════════════╣
║  Escribe tu consulta en lenguaje natural. Ejemplos:      ║
║                                                          ║
║  > Optimiza un portafolio con AAPL, MSFT y GOOGL         ║
║  > Compara AMZN, META y NVDA desde 2023                  ║
║  > Quiero minimizar riesgo con bancos mexicanos          ║
║  > Muéstrame las estadísticas de TSLA y NVDA en 2024     ║
║                                                          ║
║  Comandos especiales:                                    ║
║    /reset   → limpiar historial de conversación          ║
║    /salir   → terminar el programa                       ║
╚══════════════════════════════════════════════════════════╝
"""

SEPARATOR = "─" * 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="chat.py",
        description="Agente conversacional de portafolios con Ollama",
    )
    parser.add_argument(
        "--model",
        default="qwen3.5:latest",
        help="Nombre del modelo Ollama a usar (default: qwen3.5:latest)",
    )
    parser.add_argument(
        "--host",
        default="http://localhost:11434",
        help="URL del servidor Ollama (default: http://localhost:11434)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(BANNER)
    print(f"Modelo  : {args.model}")
    print(f"Servidor: {args.host}")
    print(SEPARATOR)

    agent = OllamaAgent(model=args.model, host=args.host)

    while True:
        try:
            user_input = input("\nTú: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n[Agente finalizado]")
            break

        if not user_input:
            continue

        # Comandos especiales
        if user_input.lower() in ("/salir", "/exit", "/quit", "salir", "exit"):
            print("\n[Agente finalizado]")
            break

        if user_input.lower() == "/reset":
            agent.reset()
            print("[Historial de conversación limpiado]")
            continue

        # Enviar al agente
        print()
        try:
            response = agent.chat(user_input)
        except Exception as e:
            print(f"[ERROR] No se pudo conectar con Ollama: {e}")
            print("Verifica que el servidor esté corriendo en", args.host)
            continue

        print(f"\n{SEPARATOR}")
        print("Agente:")
        print(response)
        print(SEPARATOR)


if __name__ == "__main__":
    main()
