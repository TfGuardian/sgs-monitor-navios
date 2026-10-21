"""Entrada de compatibilidade; a implementação está no pacote src/."""
from pathlib import Path
import sys

_raiz = Path(__file__).resolve().parent
for _pasta in (_raiz / "tmp" / "praticagem-deps", _raiz / "src"):
    if _pasta.is_dir():
        sys.path.insert(0, str(_pasta))

if __name__ == "__main__":
    from vessel_monitor.runtime.worker import main
    main()
