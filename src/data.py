"""
Módulo de descarga y preparación de datos de precios usando yfinance.
"""

import yfinance as yf
import pandas as pd
import sys
from datetime import date, timedelta


def last_business_day_prev_month(reference: date | None = None) -> date:
    """
    Devuelve el último día hábil (lunes–viernes) del mes anterior a `reference`.

    Args:
        reference: fecha de referencia; si es None usa date.today().

    Returns:
        Último día hábil del mes anterior como objeto date.
    """
    if reference is None:
        reference = date.today()
    # Último día calendario del mes anterior
    last_cal = reference.replace(day=1) - timedelta(days=1)
    # Retroceder hasta encontrar un día hábil
    while last_cal.weekday() >= 5:   # 5=sábado, 6=domingo
        last_cal -= timedelta(days=1)
    return last_cal


def default_date_range(years: int = 3) -> tuple[str, str]:
    """
    Devuelve el rango de fechas por defecto: (inicio, fin).

    - Fin  : último día hábil del mes anterior a hoy.
    - Inicio: `years` años antes del fin.

    Returns:
        Tupla (start_str, end_str) en formato "YYYY-MM-DD".
    """
    end = last_business_day_prev_month()
    start = end.replace(year=end.year - years)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def download_prices(
    tickers: list[str],
    start: str,
    end: str,
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Descarga precios de cierre ajustado para una lista de tickers.

    Args:
        tickers: Lista de símbolos bursátiles (ej. ["AAPL", "MSFT"]).
        start: Fecha de inicio en formato "YYYY-MM-DD".
        end: Fecha de fin en formato "YYYY-MM-DD".
        interval: Intervalo de datos (default "1d").

    Returns:
        DataFrame con precios de cierre ajustado, columnas = tickers.
    """
    print(f"[INFO] Descargando datos para: {', '.join(tickers)}")
    print(f"[INFO] Periodo: {start} a {end}  |  Intervalo: {interval}")

    raw = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )

    if raw.empty:
        print("[ERROR] No se obtuvieron datos. Verifica los tickers y las fechas.")
        sys.exit(1)

    # Extraer columna Close (funciona tanto para 1 ticker como para varios)
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        prices = raw[["Close"]]
        prices.columns = tickers

    # Eliminar tickers sin datos
    missing = [t for t in tickers if t not in prices.columns or prices[t].isna().all()]
    if missing:
        print(f"[WARNING] No se encontraron datos para: {', '.join(missing)}")

    prices = prices.dropna(axis=1, how="all").dropna()

    if prices.shape[1] < 2:
        print("[ERROR] Se necesitan al menos 2 activos con datos válidos.")
        sys.exit(1)

    valid_tickers = prices.columns.tolist()
    print(f"[INFO] Activos válidos ({len(valid_tickers)}): {', '.join(valid_tickers)}")
    print(f"[INFO] Observaciones: {len(prices)} filas\n")

    return prices


def compute_returns(prices: pd.DataFrame, method: str = "simple") -> pd.DataFrame:
    """
    Calcula retornos a partir de precios.

    Args:
        prices: DataFrame de precios.
        method: "simple" para retornos aritméticos, "log" para logarítmicos.

    Returns:
        DataFrame de retornos sin valores NaN.
    """
    if method == "log":
        import numpy as np
        returns = np.log(prices / prices.shift(1)).dropna()
    else:
        returns = prices.pct_change().dropna()

    return returns


def load_portfolio_from_excel(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Carga un portafolio pre-formado desde un archivo Excel con dos hojas:
      - "Precios": primera columna = Fechas (índice DatetimeIndex),
                   columnas restantes = precios de cierre por instrumento.
      - "Pesos":   primera columna = tickers (índice),
                   segunda columna = pesos entre 0 y 1.

    Args:
        path: Ruta al archivo Excel (.xlsx).

    Returns:
        Tupla (returns, weights):
          - returns : DataFrame de retornos simples diarios (pct_change),
                      índice = DatetimeIndex, columnas = tickers.
          - weights : DataFrame de pesos, forma (n_assets, 1),
                      índice = tickers, columna única = "weights".

    Raises:
        ValueError: Si el archivo no existe, faltan hojas, los datos son
                    inválidos o los tickers de "Pesos" no están en "Precios".
    """
    # ── Abrir el archivo ─────────────────────────────────────────────────────
    try:
        xl = pd.ExcelFile(path)
    except FileNotFoundError:
        raise ValueError(f"No se encontró el archivo Excel: '{path}'")
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo Excel '{path}': {e}")

    # ── Validar hojas requeridas ──────────────────────────────────────────────
    missing_sheets = {"Precios", "Pesos"} - set(xl.sheet_names)
    if missing_sheets:
        raise ValueError(
            f"El archivo Excel no contiene las hojas requeridas: {sorted(missing_sheets)}. "
            f"Hojas encontradas: {xl.sheet_names}"
        )

    # ── Hoja "Precios" ────────────────────────────────────────────────────────
    prices_raw = xl.parse("Precios", index_col=0)
    if prices_raw.empty:
        raise ValueError("La hoja 'Precios' está vacía.")
    try:
        prices_raw.index = pd.to_datetime(prices_raw.index)
    except Exception as e:
        raise ValueError(
            f"No se pudo convertir la primera columna de 'Precios' a fechas: {e}"
        )
    prices_raw.index.name = "Date"
    prices_raw = prices_raw.apply(pd.to_numeric, errors="coerce")
    prices_raw = prices_raw.dropna(how="all", axis=1).dropna()
    if prices_raw.shape[1] < 1:
        raise ValueError("La hoja 'Precios' no contiene columnas de precios válidas.")
    if len(prices_raw) < 2:
        raise ValueError(
            "La hoja 'Precios' necesita al menos 2 filas con precios válidos para calcular retornos."
        )
    returns = prices_raw.pct_change().dropna()

    # ── Hoja "Pesos" ──────────────────────────────────────────────────────────
    weights_raw = xl.parse("Pesos", index_col=0)
    if weights_raw.empty:
        raise ValueError("La hoja 'Pesos' está vacía.")
    weights_raw = weights_raw.iloc[:, :1].copy()
    weights_raw.index = weights_raw.index.astype(str).str.strip()
    weights_raw.index.name = None
    weights_raw.columns = ["weights"]
    weights_raw["weights"] = pd.to_numeric(weights_raw["weights"], errors="coerce")
    weights_raw = weights_raw.dropna()
    if weights_raw.empty:
        raise ValueError(
            "La hoja 'Pesos' no contiene pesos numéricos válidos. "
            "Verifica que la segunda columna tenga valores entre 0 y 1."
        )

    # ── Validación cruzada de tickers ─────────────────────────────────────────
    missing_in_prices = set(weights_raw.index) - set(returns.columns)
    if missing_in_prices:
        raise ValueError(
            f"Los siguientes tickers de 'Pesos' no aparecen en 'Precios': "
            f"{sorted(missing_in_prices)}. "
            f"Tickers disponibles en 'Precios': {sorted(returns.columns)}"
        )

    # Reordenar columnas de returns para que coincidan con el orden de weights
    ticker_order = weights_raw.index.tolist()
    returns = returns[ticker_order]

    print(f"[INFO] Portafolio cargado desde: {path}")
    print(f"[INFO] Activos ({len(ticker_order)}): {', '.join(ticker_order)}")
    print(f"[INFO] Observaciones: {len(returns)} filas de retornos\n")

    return returns, weights_raw


def load_prices_from_excel(path: str) -> pd.DataFrame:
    """
    Carga la hoja 'Precios' de un Excel y retorna los retornos calculados.
    Usa solo la hoja 'Precios'; no requiere la hoja 'Pesos'.
    Indicado para cuando se quiere optimizar usando datos locales.

    Args:
        path: Ruta al archivo Excel (.xlsx).

    Returns:
        DataFrame de retornos simples diarios (pct_change),
        índice = DatetimeIndex, columnas = tickers.

    Raises:
        ValueError: Si el archivo no existe, falta la hoja 'Precios',
                    los datos son inválidos o hay menos de 2 activos.
    """
    try:
        xl = pd.ExcelFile(path)
    except FileNotFoundError:
        raise ValueError(f"No se encontró el archivo Excel: '{path}'")
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo Excel '{path}': {e}")

    if "Precios" not in xl.sheet_names:
        raise ValueError(
            f"El archivo Excel no contiene la hoja 'Precios'. "
            f"Hojas encontradas: {xl.sheet_names}"
        )

    prices_raw = xl.parse("Precios", index_col=0)
    if prices_raw.empty:
        raise ValueError("La hoja 'Precios' está vacía.")
    try:
        prices_raw.index = pd.to_datetime(prices_raw.index)
    except Exception as e:
        raise ValueError(
            f"No se pudo convertir la primera columna de 'Precios' a fechas: {e}"
        )
    prices_raw.index.name = "Date"
    prices_raw = prices_raw.apply(pd.to_numeric, errors="coerce")
    prices_raw = prices_raw.dropna(how="all", axis=1).dropna()
    if prices_raw.shape[1] < 2:
        raise ValueError(
            "La hoja 'Precios' necesita al menos 2 activos con datos válidos para optimizar."
        )
    if len(prices_raw) < 2:
        raise ValueError(
            "La hoja 'Precios' necesita al menos 2 filas con precios válidos para calcular retornos."
        )

    returns = prices_raw.pct_change().dropna()
    tickers = prices_raw.columns.tolist()

    print(f"[INFO] Precios cargados desde: {path}")
    print(f"[INFO] Activos ({len(tickers)}): {', '.join(tickers)}")
    print(f"[INFO] Observaciones: {len(returns)} filas de retornos\n")

    return returns
