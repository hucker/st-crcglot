"""Entry-point shim for Streamlit Cloud.

The real Streamlit app lives at ``src/streamlit_app.py`` (along with
``src/ui.py`` and ``src/crc_lib.py``) -- this file exists only so
Streamlit Cloud's default "main file at repo root" expectation keeps
working after the src/ layout move.

Adds ``src/`` to ``sys.path`` so the real app's sibling imports
(``from ui import ...``, ``from crc_lib import ...``) resolve, then
hands control to the real entry point via :func:`runpy.run_path`
with ``run_name="__main__"`` so any ``if __name__ == "__main__":``
guards inside the real app fire the same way they would under
``streamlit run src/streamlit_app.py``.
"""

import runpy
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(_SRC))
runpy.run_path(str(_SRC / "streamlit_app.py"), run_name="__main__")
