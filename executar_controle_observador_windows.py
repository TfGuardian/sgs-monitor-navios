"""Iniciador com log para a tarefa local de controle do observador."""

from __future__ import annotations

import os
import runpy
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


def main() -> None:
    raiz = Path(__file__).resolve().parent
    os.chdir(raiz)
    caminho = raiz / "tmp" / "controle-observador.log"
    caminho.parent.mkdir(exist_ok=True)
    with caminho.open("a", encoding="utf-8", buffering=1) as log:
        with redirect_stdout(log), redirect_stderr(log):
            runpy.run_path(str(raiz / "controle_observador.py"), run_name="__main__")


if __name__ == "__main__":
    main()
