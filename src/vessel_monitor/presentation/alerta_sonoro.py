"""Miado local para eventos novos, sem interromper a coleta em caso de erro."""
import os
import sys
from pathlib import Path
from vessel_monitor.paths import PROJECT_ROOT

ARQUIVO_SOM = PROJECT_ROOT / "assets" / "sounds" / "miado.wav"


def tocar_alerta():
    if os.getenv("PRATICAGEM_SOM_ATIVO", "true").strip().lower() in {"false", "0", "nao"}:
        return
    if sys.platform != "win32":
        return
    try:
        import winsound
        winsound.PlaySound(str(ARQUIVO_SOM), winsound.SND_FILENAME | winsound.SND_NODEFAULT)
    except Exception as erro:
        print(f"Aviso sonoro indisponível: {type(erro).__name__}",
              file=sys.stderr, flush=True)


if __name__ == "__main__":
    tocar_alerta()
