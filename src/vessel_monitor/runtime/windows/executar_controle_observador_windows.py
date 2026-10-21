"""Iniciador com log para a tarefa local de controle do observador."""

from __future__ import annotations

import os
import runpy
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from vessel_monitor.paths import PROJECT_ROOT, LOG_DIR


def main() -> None:
    raiz = PROJECT_ROOT
    os.chdir(raiz)
    caminho = LOG_DIR / "controle-observador.log"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8", buffering=1) as log:
        with redirect_stdout(log), redirect_stderr(log):
            runpy.run_module("vessel_monitor.runtime.windows.controle_observador", run_name="__main__")


if __name__ == "__main__":
    main()
