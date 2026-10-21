"""Caminhos compartilhados, independentes da pasta de execução."""
from pathlib import Path
import os


def localizar_raiz() -> Path:
    configurada = os.getenv("VESSEL_MONITOR_ROOT", "").strip()
    if configurada:
        return Path(configurada).expanduser().resolve()
    for pasta in Path(__file__).resolve().parents:
        if (pasta / "supabase").is_dir() and (pasta / "assets").is_dir():
            return pasta
    atual = Path.cwd().resolve()
    if (atual / "supabase").is_dir() and (atual / "assets").is_dir():
        return atual
    raise RuntimeError("Defina VESSEL_MONITOR_ROOT com a pasta do projeto")


PROJECT_ROOT = localizar_raiz()
LOG_DIR = PROJECT_ROOT / "var" / "logs"
STATE_DIR = PROJECT_ROOT / "var" / "state"
