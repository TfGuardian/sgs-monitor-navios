"""Inicia o observador local sem depender da política de scripts PowerShell.

Pode ser chamado diretamente pelo Agendador de Tarefas do Windows. Usa as
dependências locais já instaladas, lê o .env do projeto e grava um log simples.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from processos_observador import GrupoProcessos, memoria_disponivel_mb


class Espelho:
    """Mantém o log mesmo quando a janela do console não aceita um emoji."""

    def __init__(self, registro, console):
        self.registro = registro
        self.console = console

    def write(self, texto: str) -> int:
        self.registro.write(texto)
        if self.console is not None:
            try:
                self.console.write(texto)
            except UnicodeError:
                self.console.write(texto.encode("ascii", "backslashreplace").decode())
            except OSError:
                pass
        return len(texto)

    def flush(self) -> None:
        self.registro.flush()
        if self.console is not None:
            try:
                self.console.flush()
            except OSError:
                pass


def executar_filho(comando, ambiente, registro, console, *, proteger=False):
    """O watchdog pode encerrar o filho sem encerrar este supervisor.

    Usa arquivo em vez de pipe: um navegador descendente não pode manter
    o pipe aberto e impedir a detecção da saída do Python.
    """
    registro.flush()
    with open(registro.name, encoding="utf-8", errors="replace") as leitura:
        leitura.seek(0, 2)
        grupo = GrupoProcessos() if proteger else None
        processo = None
        try:
            processo = subprocess.Popen(comando, env=ambiente, stdout=registro,
                                       stderr=subprocess.STDOUT,
                                       stdin=subprocess.PIPE if proteger else None)
            if grupo:
                grupo.associar(processo.pid)
                processo.stdin.write(b"INICIAR\n")
                processo.stdin.flush()
                processo.stdin.close()
            while True:
                texto = leitura.read()
                if texto and console is not None:
                    try:
                        console.write(texto)
                        console.flush()
                    except (OSError, UnicodeError):
                        pass
                codigo = processo.poll()
                if codigo is not None:
                    restante = leitura.read()
                    if restante and console is not None:
                        try:
                            console.write(restante)
                            console.flush()
                        except (OSError, UnicodeError):
                            pass
                    return codigo
                time.sleep(0.5)
        finally:
            if grupo:
                grupo.fechar()
            if processo is not None and processo.poll() is None:
                processo.terminate()
                processo.wait(timeout=10)


def supervisionar(executar, esperar=time.sleep):
    while True:
        memoria = memoria_disponivel_mb()
        print(f"{datetime.now(timezone.utc).isoformat()} iniciando processo; "
              f"memoria_disponivel_mb={memoria}", flush=True)
        try:
            codigo = executar()
        except OSError as erro:
            print(f"Falha ao iniciar processo: {erro}", flush=True)
            codigo = 125
        if codigo == 0:
            return
        print(f"{datetime.now(timezone.utc).isoformat()} "
              f"observador encerrou com codigo={codigo}; reiniciando em 15s",
              flush=True)
        esperar(15)


def main() -> None:
    raiz = Path(__file__).resolve().parent
    dependencias = raiz / "tmp" / "praticagem-deps"
    if not dependencias.is_dir():
        raise RuntimeError("Dependências locais ausentes em tmp/praticagem-deps")
    sys.path.insert(0, str(dependencias))
    os.chdir(raiz)
    ambiente = os.environ.copy()
    ambiente["PYTHONPATH"] = str(dependencias) + os.pathsep + ambiente.get("PYTHONPATH", "")
    ambiente["PYTHONIOENCODING"] = "utf-8"

    caminho_log = raiz / "tmp" / "praticagem-worker.log"
    caminho_log.parent.mkdir(exist_ok=True)
    console_saida, console_erro = sys.stdout, sys.stderr
    for console in (console_saida, console_erro):
        if hasattr(console, "reconfigure"):
            try:
                console.reconfigure(encoding="utf-8", errors="backslashreplace")
            except OSError:
                pass
    with caminho_log.open("a", encoding="utf-8", buffering=1) as registro:
        with redirect_stdout(Espelho(registro, console_saida)), \
             redirect_stderr(Espelho(registro, console_erro)):
            print(f"{datetime.now(timezone.utc).isoformat()} observador iniciado",
                  flush=True)
            try:
                supervisionar(lambda: executar_filho(
                    [sys.executable, "-u", str(raiz / "iniciar_filho_observador.py"),
                     str(raiz / "praticagem_worker.py")],
                    ambiente, registro, console_saida, proteger=True))
            except KeyboardInterrupt:
                print("Supervisor interrompido pelo usuário.", flush=True)


if __name__ == "__main__":
    main()
