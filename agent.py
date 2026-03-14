#!/usr/bin/env python
"""
Agente de Optimización de Portafolios — Mean-Variance
======================================================
Descarga precios de Yahoo Finance y optimiza un portafolio
usando Riskfolio-Lib con el modelo clásico de Markowitz.

Uso básico
----------
python agent.py --tickers AAPL MSFT GOOGL AMZN META --start 2022-01-01 --end 2024-12-31

Argumentos clave
----------------
  --tickers          Símbolos bursátiles separados por espacio (mín. 2)
  --start            Fecha de inicio  (YYYY-MM-DD)
  --end              Fecha de fin     (YYYY-MM-DD)
  --portfolio-excel  Ruta a un Excel con hojas "Precios" y "Pesos"
                     para analizar un portafolio ya formado (excluye --tickers/--start)
  --objective        sharpe | min_risk | max_ret | utility  (default: sharpe)
  --risk-measure     MV | MAD | CVaR                        (default: MV)
  --rf               Tasa libre de riesgo anualizada        (default: 0.0)
  --returns-method   simple | log                           (default: simple)
  --no-plot          No mostrar gráficos
  --save-plot        Guardar gráficos en la carpeta indicada
  --export-excel     Ruta del archivo .xlsx para exportar resultados
"""

import argparse
import sys
from pathlib import Path

# Forzar UTF-8 en stdout/stderr para evitar errores de encoding en Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Agregar el directorio raíz al path para importar src/
sys.path.insert(0, str(Path(__file__).parent))

from src.data import (
    download_prices,
    compute_returns,
    default_date_range,
    load_portfolio_from_excel,
)
from src.optimizer import build_portfolio, optimize, compute_metrics
from src.report import print_weights, plot_portfolio, save_to_excel, save_riskfolio_report, save_jupyter_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agent.py",
        description="Agente de optimización de portafolios Mean-Variance con Riskfolio-Lib",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Datos
    parser.add_argument(
        "--tickers",
        nargs="+",
        required=False,
        default=None,
        metavar="TICKER",
        help="Lista de símbolos bursátiles (ej. AAPL MSFT GOOGL). "
             "Requerido cuando no se usa --portfolio-excel.",
    )
    parser.add_argument(
        "--start",
        required=False,
        default=None,
        metavar="YYYY-MM-DD",
        help="Fecha de inicio del período de análisis. "
             "Requerido cuando no se usa --portfolio-excel.",
    )
    parser.add_argument(
        "--end",
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "Fecha de fin del período (default: último día hábil del mes anterior)"
        ),
    )
    parser.add_argument(
        "--returns-method",
        default="simple",
        choices=["simple", "log"],
        help="Método de cálculo de retornos (default: simple)",
    )
    parser.add_argument(
        "--portfolio-excel",
        default=None,
        metavar="FILE.xlsx",
        help=(
            "Ruta a un Excel con hojas 'Precios' (fechas + precios) y "
            "'Pesos' (tickers + pesos). Genera riskfolio_report.xlsx y "
            "jupyter_report.png en --save-plot. "
            "Mutuamente excluyente con --tickers/--start."
        ),
    )

    # Optimización
    parser.add_argument(
        "--objective",
        default="sharpe",
        choices=["sharpe", "min_risk", "max_ret", "utility"],
        help="Objetivo de optimización (default: sharpe)",
    )
    parser.add_argument(
        "--risk-measure",
        default="MV",
        choices=["MV", "MAD", "CVaR"],
        help="Medida de riesgo (default: MV = Varianza)",
    )
    parser.add_argument(
        "--rf",
        type=float,
        default=0.0,
        metavar="RATE",
        help="Tasa libre de riesgo anualizada, ej. 0.05 para 5%% (default: 0.0)",
    )
    parser.add_argument(
        "--allow-short",
        action="store_true",
        help="Permitir posiciones cortas (default: solo largo)",
    )
    parser.add_argument(
        "--max-weight",
        type=float,
        default=0.5,
        metavar="FRAC",
        help="Peso máximo por activo entre 0 y 1, ej. 0.3 para 30%% (default: 0.5)",
    )

    # Salida
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="No mostrar gráficos",
    )
    parser.add_argument(
        "--save-plot",
        default="resultados/",
        metavar="DIR",
        help="Carpeta donde guardar los gráficos como PNG (default: resultados/)",
    )
    parser.add_argument(
        "--export-excel",
        default="resultados/portafolio.xlsx",
        metavar="FILE.xlsx",
        help="Exportar resultados a un archivo Excel (default: resultados/portafolio.xlsx)",
    )

    return parser.parse_args()


def _run_excel_portfolio(args: argparse.Namespace) -> None:
    """Modo análisis de portafolio pre-formado desde Excel."""
    print("\n" + "=" * 55)
    print("  ANÁLISIS DE PORTAFOLIO DESDE EXCEL")
    print("=" * 55)
    print(f"  Archivo       : {args.portfolio_excel}")
    print(f"  Tasa libre    : {args.rf:.2%}")
    print(f"  Carpeta salida: {args.save_plot}")
    print("=" * 55 + "\n")

    returns, weights = load_portfolio_from_excel(args.portfolio_excel)

    out_dir = Path(args.save_plot)
    out_dir.mkdir(parents=True, exist_ok=True)

    save_riskfolio_report(
        weights=weights,
        returns=returns,
        output_path=str(out_dir / "riskfolio_report"),
        risk_free_rate=args.rf,
    )
    save_jupyter_report(
        weights=weights,
        returns=returns,
        output_path=str(out_dir / "jupyter_report.png"),
        risk_free_rate=args.rf,
        risk_measure="MV",
    )
    print(f"\n[OK] Reportes generados en: {out_dir}/")


def main() -> None:
    args = parse_args()

    # ── Modo 1: Portafolio pre-formado desde Excel ────────────────────────────
    if args.portfolio_excel:
        if args.tickers or args.start:
            print(
                "[ERROR] --portfolio-excel es mutuamente excluyente con "
                "--tickers y --start."
            )
            sys.exit(1)
        try:
            _run_excel_portfolio(args)
        except ValueError as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
        return

    # ── Modo 2: Optimización (flujo existente) ────────────────────────────────
    if not args.tickers or not args.start:
        print(
            "[ERROR] Se requieren --tickers y --start cuando no se usa --portfolio-excel.\n"
            "Ejemplo: python agent.py --tickers AAPL MSFT GOOGL --start 2022-01-01"
        )
        sys.exit(1)

    tickers = [t.upper() for t in args.tickers]

    # Resolver fecha de fin: si no se indicó, usar el último día hábil del mes anterior
    _start_def, _end_def = default_date_range(years=3)
    end_date = args.end or _end_def

    print("\n" + "=" * 55)
    print("  AGENTE DE OPTIMIZACIÓN — MEAN-VARIANCE")
    print("=" * 55)
    print(f"  Objetivo      : {args.objective}")
    print(f"  Medida riesgo : {args.risk_measure}")
    print(f"  Tasa libre    : {args.rf:.2%}")
    print(f"  Peso max/activo: {args.max_weight:.0%}")
    print(f"  Solo largo    : {not args.allow_short}")
    print(f"  Período       : {args.start} a {end_date}")
    print("=" * 55 + "\n")

    # 1. Descargar precios
    prices = download_prices(
        tickers=tickers,
        start=args.start,
        end=end_date,
    )

    # 2. Calcular retornos
    returns = compute_returns(prices, method=args.returns_method)

    # 3. Construir portafolio y optimizar
    print("[INFO] Ejecutando optimización...\n")
    port = build_portfolio(returns)

    try:
        weights = optimize(
            port=port,
            objective=args.objective,
            risk_measure=args.risk_measure,
            risk_free_rate=args.rf,
            long_only=not args.allow_short,
            max_weight=args.max_weight,
        )
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # 4. Calcular métricas
    metrics = compute_metrics(
        weights=weights,
        returns=returns,
        risk_free_rate=args.rf,
    )

    # 5. Mostrar resultados en consola
    print_weights(weights, metrics)

    # 6. Exportar a Excel (default: resultados/portafolio.xlsx)
    if args.export_excel:
        save_to_excel(
            weights=weights,
            metrics=metrics,
            returns=returns,
            output_path=args.export_excel,
        )
        # Reporte detallado de Riskfolio en la misma carpeta
        report_dir = Path(args.export_excel).parent
        report_path = str(report_dir / "riskfolio_report")
        save_riskfolio_report(
            weights=weights,
            returns=returns,
            output_path=report_path,
            risk_free_rate=args.rf,
        )
        # Reporte visual (jupyter_report) en la misma carpeta
        jupyter_path = str(report_dir / "jupyter_report.png")
        save_jupyter_report(
            weights=weights,
            returns=returns,
            output_path=jupyter_path,
            risk_free_rate=args.rf,
            risk_measure=args.risk_measure,
        )

    # 7. Graficar (opcional)
    show_plot = not args.no_plot
    if show_plot or args.save_plot:
        plot_portfolio(
            weights=weights,
            port=port,
            risk_measure=args.risk_measure,
            output_dir=args.save_plot,
            show=show_plot,
        )


if __name__ == "__main__":
    main()
