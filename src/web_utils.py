"""
Utilidades compartidas por las páginas de la interfaz web (Streamlit).
"""

import io
import sys
from contextlib import contextmanager
from pathlib import Path


def ensure_root_on_path() -> None:
    """Agrega la raíz del proyecto a sys.path para poder importar `src.*`."""
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)


@contextmanager
def capture_output():
    """
    Context manager que captura todo lo impreso por stdout (logs [INFO]/[WARNING]
    de src/data.py y src/report.py) y lo expone como un buffer de texto.

    Uso:
        with capture_output() as buf:
            ...
        st.expander("Logs").text(buf.getvalue())
    """
    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer
    try:
        yield buffer
    finally:
        sys.stdout = old_stdout
