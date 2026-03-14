"""
Módulo de integración con Ollama (qwen3.5) para el agente conversacional.
Gestiona el cliente, las definiciones de herramientas y la ejecución del loop ReAct.
"""

import sys
import io
from pathlib import Path
from typing import Any

import ollama

# ─────────────────────────────────────────────
# Definición de herramientas disponibles
# ─────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "optimize_portfolio",
            "description": (
                "Descarga precios históricos de Yahoo Finance y ejecuta una "
                "optimización de portafolio Mean-Variance con Riskfolio-Lib. "
                "Devuelve los pesos óptimos del portafolio y métricas de desempeño "
                "(retorno esperado, volatilidad y Sharpe Ratio anualizados). "
                "Usar cuando el usuario quiera optimizar una cartera de activos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Lista de símbolos bursátiles de Yahoo Finance, "
                            "p.ej. ['AAPL', 'MSFT', 'GOOGL']. Mínimo 2 activos."
                        ),
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Fecha de inicio del período de análisis en formato YYYY-MM-DD.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Fecha de fin del período de análisis en formato YYYY-MM-DD.",
                    },
                    "objective": {
                        "type": "string",
                        "enum": ["sharpe", "min_risk", "max_ret", "utility"],
                        "description": (
                            "Objetivo de optimización: "
                            "'sharpe' maximiza el Sharpe Ratio (default), "
                            "'min_risk' minimiza la varianza, "
                            "'max_ret' maximiza el retorno, "
                            "'utility' maximiza la utilidad cuadrática."
                        ),
                    },
                    "risk_measure": {
                        "type": "string",
                        "enum": ["MV", "MAD", "CVaR"],
                        "description": (
                            "Medida de riesgo: 'MV' varianza (default), "
                            "'MAD' desviación media absoluta, "
                            "'CVaR' valor en riesgo condicional."
                        ),
                    },
                    "risk_free_rate": {
                        "type": "number",
                        "description": (
                            "Tasa libre de riesgo anualizada en decimal. "
                            "Ej: 0.05 para 5%. Por defecto 0.0."
                        ),
                    },
                    "returns_method": {
                        "type": "string",
                        "enum": ["simple", "log"],
                        "description": "Método de cálculo de retornos: 'simple' (default) o 'log'.",
                    },
                    "allow_short": {
                        "type": "boolean",
                        "description": "Si true, permite posiciones cortas. Por defecto false.",
                    },
                    "max_weight": {
                        "type": "number",
                        "description": (
                            "Peso máximo permitido por activo, entre 0 y 1. "
                            "Ej: 0.3 para limitar a 30% por activo. Por defecto 0.5 (50%)."
                        ),
                    },
                    "output_dir": {
                        "type": "string",
                        "description": (
                            "Carpeta donde guardar los resultados: "
                            "portafolio.xlsx, riskfolio_report.xlsx, "
                            "portfolio_optimization.png y jupyter_report.png. "
                            "Si el usuario no indica carpeta, usar 'resultados/'. "
                            "Usar siempre que el usuario pida guardar, exportar o salvar "
                            "resultados, o cuando optimice un portafolio sin especificar carpeta. "
                            "Ej: 'resultados/', 'output/portafolio', 'mis_resultados/'."
                        ),
                    },
                },
                "required": ["tickers", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_summary",
            "description": (
                "Descarga precios históricos de Yahoo Finance y devuelve "
                "estadísticas descriptivas básicas: precio inicial, precio final, "
                "retorno total y volatilidad anualizada de cada activo. "
                "Usar cuando el usuario quiera explorar o comparar activos "
                "sin necesidad de optimizar un portafolio."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de símbolos bursátiles de Yahoo Finance.",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Fecha de inicio en formato YYYY-MM-DD.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Fecha de fin en formato YYYY-MM-DD.",
                    },
                },
                "required": ["tickers", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_existing_portfolio",
            "description": (
                "Analiza un portafolio pre-formado cargado desde un archivo Excel. "
                "El Excel debe contener dos hojas: "
                "'Precios' (primera columna = Fechas como índice, columnas restantes = "
                "precios de cada instrumento) y "
                "'Pesos' (primera columna = tickers, segunda columna = pesos entre 0 y 1). "
                "Genera dos archivos en output_dir: "
                "'riskfolio_report.xlsx' con métricas detalladas de riesgo/retorno y "
                "'jupyter_report.png' con la visualización del portafolio. "
                "NO realiza optimización: usa los pesos tal como están en el Excel. "
                "Usar cuando el usuario mencione un archivo Excel con su portafolio ya formado, "
                "diga 'analiza mis posiciones actuales', 'ya tengo los pesos', o similar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "excel_path": {
                        "type": "string",
                        "description": (
                            "Ruta al archivo Excel (.xlsx) con las hojas 'Precios' y 'Pesos'. "
                            "Ej: 'mi_portafolio.xlsx', 'datos/cartera_2024.xlsx'."
                        ),
                    },
                    "output_dir": {
                        "type": "string",
                        "description": (
                            "Carpeta donde guardar riskfolio_report.xlsx y jupyter_report.png. "
                            "Si el usuario no indica carpeta, usar 'resultados/'."
                        ),
                    },
                    "risk_free_rate": {
                        "type": "number",
                        "description": (
                            "Tasa libre de riesgo anualizada en decimal. "
                            "Ej: 0.05 para 5%. Por defecto 0.0."
                        ),
                    },
                    "risk_measure": {
                        "type": "string",
                        "enum": ["MV", "MAD", "CVaR"],
                        "description": (
                            "Medida de riesgo para el panel de contribución al riesgo "
                            "en jupyter_report.png: 'MV' varianza (default), "
                            "'MAD' desviación media absoluta, "
                            "'CVaR' valor en riesgo condicional."
                        ),
                    },
                },
                "required": ["excel_path"],
            },
        },
    },
]


# ─────────────────────────────────────────────
# Implementaciones de las herramientas
# ─────────────────────────────────────────────

def _tool_optimize_portfolio(args: dict) -> str:
    """Ejecuta la optimización y retorna un string con los resultados."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.data import download_prices, compute_returns, default_date_range
    from src.optimizer import build_portfolio, optimize, compute_metrics
    from src.report import save_to_excel, plot_portfolio, save_riskfolio_report, save_jupyter_report

    _start_def, _end_def = default_date_range(years=3)

    tickers = [t.upper() for t in args["tickers"]]
    start = args.get("start_date") or _start_def
    end   = args.get("end_date")   or _end_def
    objective = args.get("objective", "sharpe")
    risk_measure = args.get("risk_measure", "MV")
    rf = float(args.get("risk_free_rate", 0.0))
    returns_method = args.get("returns_method", "simple")
    allow_short = bool(args.get("allow_short", False))
    max_weight = float(args.get("max_weight", 0.5))
    output_dir = args.get("output_dir") or "resultados/"  # carpeta por defecto

    # Capturar los prints internos para incluirlos en la respuesta
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        prices = download_prices(tickers, start, end)
        returns = compute_returns(prices, method=returns_method)
        port = build_portfolio(returns)
        weights = optimize(
            port=port,
            objective=objective,
            risk_measure=risk_measure,
            risk_free_rate=rf,
            long_only=not allow_short,
            max_weight=max_weight,
        )
        metrics = compute_metrics(weights, returns, risk_free_rate=rf)
    except SystemExit as e:
        sys.stdout = old_stdout
        return f"ERROR al descargar datos: {buffer.getvalue()}"
    except RuntimeError as e:
        sys.stdout = old_stdout
        return f"ERROR en optimización: {e}"
    finally:
        sys.stdout = old_stdout

    logs = buffer.getvalue()
    saved_files: list[str] = []

    # Guardar Excel y gráfico en output_dir si se solicita
    if output_dir:
        from pathlib import Path as _Path
        out = _Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        excel_path = str(out / "portafolio.xlsx")
        try:
            save_to_excel(weights, metrics, returns, excel_path)
            saved_files.append(excel_path)
        except Exception as e:
            logs += f"\n[WARNING] No se pudo guardar Excel: {e}"

        try:
            plot_portfolio(weights, port, risk_measure, output_dir=str(out), show=False)
            saved_files.append(str(out / "portfolio_optimization.png"))
        except Exception as e:
            logs += f"\n[WARNING] No se pudo guardar gráfico: {e}"

        report_path = str(out / "riskfolio_report")
        try:
            save_riskfolio_report(weights, returns, report_path, risk_free_rate=rf)
            saved_files.append(report_path + ".xlsx")
        except Exception as e:
            logs += f"\n[WARNING] No se pudo generar reporte Riskfolio: {e}"

        jupyter_path = str(out / "jupyter_report.png")
        try:
            save_jupyter_report(weights, returns, jupyter_path, risk_free_rate=rf, risk_measure=risk_measure)
            saved_files.append(jupyter_path)
        except Exception as e:
            logs += f"\n[WARNING] No se pudo generar reporte visual Riskfolio: {e}"

    # Armar resultado como texto estructurado
    w_nonzero = weights[weights.iloc[:, 0] > 0.0001].copy()
    w_nonzero.columns = ["peso"]
    w_nonzero = w_nonzero.sort_values("peso", ascending=False)

    result_lines = [
        f"Optimización completada para: {', '.join(tickers)}",
        f"Período: {start} a {end}",
        f"Objetivo: {objective} | Medida de riesgo: {risk_measure}",
        f"Restricción: peso máximo por activo = {max_weight:.0%}",
        "",
        "PESOS ÓPTIMOS:",
    ]
    for ticker, row in w_nonzero.iterrows():
        result_lines.append(f"  {ticker}: {row['peso']*100:.4f}%")
    result_lines += [
        "",
        "MÉTRICAS ANUALIZADAS:",
        f"  Retorno esperado : {metrics['Retorno Esperado (anual)']:.4f} "
        f"({metrics['Retorno Esperado (anual)']:.2%})",
        f"  Volatilidad      : {metrics['Volatilidad (anual)']:.4f} "
        f"({metrics['Volatilidad (anual)']:.2%})",
        f"  Sharpe Ratio     : {metrics['Sharpe Ratio']:.4f}",
    ]
    if saved_files:
        result_lines.append("")
        result_lines.append("ARCHIVOS GUARDADOS:")
        for f in saved_files:
            result_lines.append(f"  {f}")

    return "\n".join(result_lines)


def _tool_get_price_summary(args: dict) -> str:
    """Descarga precios y retorna estadísticas descriptivas básicas."""
    import numpy as np
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.data import download_prices, compute_returns, default_date_range

    _start_def, _end_def = default_date_range(years=3)

    tickers = [t.upper() for t in args["tickers"]]
    start = args.get("start_date") or _start_def
    end   = args.get("end_date")   or _end_def

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        prices = download_prices(tickers, start, end)
        returns = compute_returns(prices, method="simple")
    except SystemExit:
        sys.stdout = old_stdout
        return "ERROR: No se pudieron descargar datos para los tickers indicados."
    finally:
        sys.stdout = old_stdout

    lines = [
        f"Resumen de activos ({start} a {end}):",
        "",
        f"  {'Ticker':<8}  {'Precio ini':>12}  {'Precio fin':>12}  "
        f"{'Ret. total':>11}  {'Volatilidad':>12}",
        "  " + "-" * 62,
    ]
    for ticker in prices.columns:
        p_ini = prices[ticker].iloc[0]
        p_fin = prices[ticker].iloc[-1]
        ret_total = (p_fin / p_ini) - 1
        vol_anual = returns[ticker].std() * np.sqrt(252)
        lines.append(
            f"  {ticker:<8}  {p_ini:>12.2f}  {p_fin:>12.2f}  "
            f"{ret_total:>10.2%}  {vol_anual:>11.2%}"
        )

    lines.append(f"\nObservaciones: {len(prices)} días de trading")
    return "\n".join(lines)


def _tool_analyze_existing_portfolio(args: dict) -> str:
    """Carga un portafolio pre-formado desde Excel y genera reportes Riskfolio."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.data import load_portfolio_from_excel
    from src.report import save_riskfolio_report, save_jupyter_report

    excel_path   = args["excel_path"]
    output_dir   = args.get("output_dir") or "resultados/"
    rf           = float(args.get("risk_free_rate", 0.0))
    risk_measure = args.get("risk_measure", "MV")

    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        returns, weights = load_portfolio_from_excel(excel_path)
    except ValueError as e:
        sys.stdout = old_stdout
        return f"ERROR al cargar el portafolio desde Excel: {e}"
    except Exception as e:
        sys.stdout = old_stdout
        return f"ERROR inesperado al leer '{excel_path}': {e}"
    finally:
        sys.stdout = old_stdout

    logs = buffer.getvalue()
    saved_files: list[str] = []

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    report_path = str(out / "riskfolio_report")
    try:
        save_riskfolio_report(weights, returns, report_path, risk_free_rate=rf)
        saved_files.append(report_path + ".xlsx")
    except Exception as e:
        logs += f"\n[WARNING] No se pudo generar riskfolio_report: {e}"

    jupyter_path = str(out / "jupyter_report.png")
    try:
        save_jupyter_report(
            weights, returns, jupyter_path,
            risk_free_rate=rf,
            risk_measure=risk_measure,
        )
        saved_files.append(jupyter_path)
    except Exception as e:
        logs += f"\n[WARNING] No se pudo generar jupyter_report: {e}"

    tickers = weights.index.tolist()
    result_lines = [
        f"Análisis completado para portafolio en: {excel_path}",
        f"Activos analizados ({len(tickers)}): {', '.join(tickers)}",
        f"Observaciones: {len(returns)} días de retornos",
        f"Tasa libre de riesgo: {rf:.2%}",
        f"Medida de riesgo (jupyter_report): {risk_measure}",
        "",
        "COMPOSICIÓN DEL PORTAFOLIO:",
    ]
    for ticker, row in weights.iterrows():
        result_lines.append(f"  {ticker}: {float(row['weights']) * 100:.4f}%")

    if saved_files:
        result_lines.append("")
        result_lines.append("ARCHIVOS GENERADOS:")
        for f in saved_files:
            result_lines.append(f"  {f}")

    return "\n".join(result_lines)


# ─────────────────────────────────────────────
# Dispatcher de herramientas
# ─────────────────────────────────────────────

_TOOL_HANDLERS: dict[str, Any] = {
    "optimize_portfolio":         _tool_optimize_portfolio,
    "get_price_summary":          _tool_get_price_summary,
    "analyze_existing_portfolio": _tool_analyze_existing_portfolio,
}


def execute_tool(name: str, arguments: dict) -> str:
    """Ejecuta la herramienta indicada y retorna el resultado como string."""
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return f"ERROR: Herramienta '{name}' no reconocida."
    try:
        return handler(arguments)
    except Exception as e:
        return f"ERROR ejecutando '{name}': {e}"


# ─────────────────────────────────────────────
# Cliente Ollama: loop de conversación
# ─────────────────────────────────────────────

def _build_system_prompt() -> str:
    """Genera el system prompt con las fechas por defecto calculadas en tiempo de ejecución."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.data import default_date_range
    start_default, end_default = default_date_range(years=3)

    return f"""Eres un asistente experto en análisis y optimización de portafolios financieros.
Tienes acceso a herramientas que te permiten:
- Descargar precios históricos de Yahoo Finance usando yfinance
- Optimizar portafolios con el modelo Mean-Variance de Markowitz usando Riskfolio-Lib
- Mostrar estadísticas descriptivas de activos financieros
- Analizar portafolios pre-formados cargados desde archivos Excel (sin optimizar)

Responde siempre en español. Sé conciso pero informativo al interpretar los resultados.
Cuando el usuario mencione activos, fechas u objetivos de inversión, usa las herramientas disponibles.
Si el usuario no especifica objetivo, usa 'sharpe' por defecto.
Tras recibir los resultados de una herramienta, interprétalos y explícalos claramente al usuario,
destacando qué activos tienen mayor peso, qué significa el Sharpe Ratio obtenido, y
cualquier observación relevante sobre el portafolio.

FECHAS POR DEFECTO (usar cuando el usuario no especifique fechas):
- Fecha de fin   : {end_default}  (último día hábil del mes anterior a hoy)
- Fecha de inicio: {start_default} (3 años antes del fin)

REGLAS PARA GUARDAR RESULTADOS:
- Siempre incluye el parámetro output_dir al llamar a optimize_portfolio o analyze_existing_portfolio.
- Si el usuario especifica una carpeta o ruta, úsala como output_dir.
- Si el usuario NO especifica carpeta, usa output_dir='resultados/' como valor por defecto.
- optimize_portfolio guarda: portafolio.xlsx, riskfolio_report.xlsx, portfolio_optimization.png, jupyter_report.png.
- analyze_existing_portfolio guarda: riskfolio_report.xlsx, jupyter_report.png.
- Ejemplos de rutas indicadas por el usuario:
    'guarda en mis_datos/' → output_dir='mis_datos/'
    'exporta a output/'    → output_dir='output/'
    'salva en análisis/'   → output_dir='análisis/'

CUÁNDO USAR analyze_existing_portfolio (en lugar de optimize_portfolio):
- Cuando el usuario mencione un archivo Excel con su portafolio ya formado.
- Cuando diga 'analiza mi portafolio', 'ya tengo los pesos', 'mis posiciones actuales'.
- Cuando indique una ruta .xlsx y pida análisis, reportes o métricas sin optimizar.
- Ejemplos: 'analiza el archivo cartera.xlsx', 'genera el reporte de mi portafolio en datos/portfolio.xlsx'."""


class OllamaAgent:
    """Agente conversacional basado en Ollama con soporte de herramientas."""

    # Opciones comunes para todas las llamadas al modelo:
    #   think=False  → desactiva el modo "thinking" de qwen3.5, que genera
    #                  miles de tokens <think>…</think> y desborda el contexto
    #                  cuando el historial ya incluye tool calls + resultados.
    #   num_ctx=8192 → ventana de contexto explícita; el default de Ollama
    #                  (2048 tokens) es insuficiente para el flujo de tools.
    _CHAT_OPTIONS: dict = {"num_ctx": 8192}

    def __init__(
        self,
        model: str = "qwen3.5:latest",
        host: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.client = ollama.Client(host=host)
        self.history: list[dict] = []

    def reset(self) -> None:
        """Limpia el historial de conversación."""
        self.history = []

    def chat(self, user_message: str) -> str:
        """
        Envía un mensaje al modelo y retorna la respuesta final (texto).
        Maneja automáticamente los ciclos de tool calling.
        """
        self.history.append({"role": "user", "content": user_message})

        messages = [{"role": "system", "content": _build_system_prompt()}] + self.history

        # Loop de tool calling (máximo 5 rondas para evitar bucles)
        for _ in range(5):
            response = self.client.chat(
                model=self.model,
                messages=messages,
                tools=TOOLS,
                think=False,          # evita tokens de thinking que desbordan ctx
                options=self._CHAT_OPTIONS,
            )

            msg = response.message

            # Sin tool calls: respuesta final de texto
            if not msg.tool_calls:
                final_text = msg.content or ""
                self.history.append({"role": "assistant", "content": final_text})
                return final_text

            # Con tool calls: ejecutar cada herramienta
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": msg.tool_calls,
            })

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = tool_call.function.arguments

                print(f"\n[HERRAMIENTA] Ejecutando: {fn_name}...")
                result = execute_tool(fn_name, fn_args)

                messages.append({
                    "role": "tool",
                    "name": fn_name,
                    "content": result,
                })

        # Si se agotaron los ciclos, devolver el último contenido disponible
        last_content = messages[-1].get("content", "No se pudo generar una respuesta.")
        self.history.append({"role": "assistant", "content": last_content})
        return last_content
