"""
Módulo de optimización Mean-Variance usando Riskfolio-Lib.
"""

import pandas as pd
import numpy as np
import riskfolio as rp

# Objetivos disponibles para la optimización
OBJECTIVES = {
    "sharpe": ("Sharpe", "MaxRet"),    # Máximo Sharpe Ratio
    "min_risk": ("MinRisk", "MinRisk"), # Mínima Varianza
    "max_ret": ("MaxRet", "MaxRet"),    # Máximo Retorno
    "utility": ("Utility", "MaxRet"),  # Máxima Utilidad
}

RISK_MEASURES = {
    "MV": "Varianza (MV)",
    "MAD": "Mean Absolute Deviation",
    "CVaR": "Conditional Value at Risk",
}


def build_portfolio(returns: pd.DataFrame) -> rp.Portfolio:
    """
    Construye un objeto Portfolio de Riskfolio con los retornos dados.

    Args:
        returns: DataFrame con retornos periódicos.

    Returns:
        Objeto rp.Portfolio con estadísticas calculadas.
    """
    port = rp.Portfolio(returns=returns)

    # Estimar estadísticas (media y covarianza)
    port.assets_stats(method_mu="hist", method_cov="hist")

    return port


def optimize(
    port: rp.Portfolio,
    objective: str = "sharpe",
    risk_measure: str = "MV",
    risk_free_rate: float = 0.0,
    long_only: bool = True,
    periods_per_year: int = 252,
    max_weight: float = 0.5,
) -> pd.DataFrame:
    """
    Ejecuta la optimización Mean-Variance.

    Args:
        port: Objeto rp.Portfolio ya inicializado.
        objective: Objetivo de optimización ("sharpe", "min_risk", "max_ret", "utility").
        risk_measure: Medida de riesgo ("MV", "MAD", "CVaR").
        risk_free_rate: Tasa libre de riesgo **anualizada** (ej. 0.05 para 5%).
        long_only: Si True, solo posiciones largas (pesos >= 0).
        periods_per_year: Períodos por año para convertir rf a diario (default 252).
        max_weight: Peso máximo permitido por activo entre 0 y 1 (default 0.5 = 50%).

    Returns:
        DataFrame con los pesos óptimos del portafolio.
    """
    if objective not in OBJECTIVES:
        raise ValueError(
            f"Objetivo '{objective}' no válido. Opciones: {list(OBJECTIVES.keys())}"
        )
    if not (0 < max_weight <= 1):
        raise ValueError(f"max_weight debe estar entre 0 y 1, recibido: {max_weight}")

    obj_code, _ = OBJECTIVES[objective]

    # Riskfolio-Lib espera rf en la misma periodicidad que los retornos (diario).
    # Convertir tasa anual → tasa del período con capitalización compuesta.
    rf_period = (1 + risk_free_rate) ** (1 / periods_per_year) - 1

    # Restricciones de pesos
    port.sht = not long_only
    port.uppersht = 0.2 if not long_only else 0
    port.upperlng = max_weight          # límite máximo por activo
    if long_only:
        port.lowerret = None

    weights = port.optimization(
        model="Classic",
        rm=risk_measure,
        obj=obj_code,
        rf=rf_period,
        l=2,           # parámetro lambda para Utility
        hist=True,
    )

    if weights is None:
        raise RuntimeError(
            "La optimización no convergió. "
            "Intenta con otro objetivo o verifica los datos."
        )

    return weights


def compute_metrics(
    weights: pd.DataFrame,
    returns: pd.DataFrame,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> dict:
    """
    Calcula métricas del portafolio optimizado.

    Args:
        weights: DataFrame con pesos óptimos (resultado de optimize).
        returns: DataFrame de retornos.
        risk_free_rate: Tasa libre de riesgo anualizada.
        periods_per_year: Cantidad de períodos por año (252 para diario).

    Returns:
        Diccionario con retorno esperado, volatilidad y Sharpe ratio anualizados.
    """
    w = weights.values.flatten()
    mu = returns.mean().values
    cov = returns.cov().values

    port_return = float(np.dot(w, mu)) * periods_per_year
    port_vol = float(np.sqrt(np.dot(w, np.dot(cov, w)))) * np.sqrt(periods_per_year)
    sharpe = (port_return - risk_free_rate) / port_vol if port_vol > 0 else 0.0

    return {
        "Retorno Esperado (anual)": port_return,
        "Volatilidad (anual)": port_vol,
        "Sharpe Ratio": sharpe,
    }


def efficient_frontier(
    port: rp.Portfolio,
    risk_measure: str = "MV",
    points: int = 50,
) -> pd.DataFrame:
    """
    Calcula la frontera eficiente.

    Args:
        port: Objeto rp.Portfolio.
        risk_measure: Medida de riesgo.
        points: Número de puntos en la frontera.

    Returns:
        DataFrame con puntos de la frontera eficiente.
    """
    frontier = port.efficient_frontier(
        model="Classic",
        rm=risk_measure,
        points=points,
        rf=0,
        hist=True,
    )
    return frontier
