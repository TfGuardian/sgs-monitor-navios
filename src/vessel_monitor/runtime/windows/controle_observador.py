"""Recebe pedidos administrativos do WhatsApp e aciona a tarefa local fixa.

Deve rodar em uma tarefa do Windows separada do observador. Só lê comandos
predefinidos na fila; nunca executa texto recebido pelo WhatsApp.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from vessel_monitor.paths import PROJECT_ROOT
from typing import Any, Callable


TAREFA_OBSERVADOR = "SGS Praticagem Observador"
INTERVALO_S = 15


def registrar(mensagem: str) -> None:
    print(f"{datetime.now(timezone.utc).isoformat()} {mensagem}", flush=True)


def reiniciar_tarefa(executor: Callable[..., Any] = subprocess.run) -> str:
    # Somente o nome fixo da tarefa entra neste script. O pedido remoto não
    # contém parâmetros capazes de alterar o comando executado no computador.
    script = r"""
$ErrorActionPreference = 'Stop'
$nome = 'SGS Praticagem Observador'
$tarefa = Get-ScheduledTask -TaskName $nome
if ($tarefa.State -eq 'Running') {
  Stop-ScheduledTask -TaskName $nome
  for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 250
    if ((Get-ScheduledTask -TaskName $nome).State -ne 'Running') { break }
  }
}
Start-ScheduledTask -TaskName $nome
Start-Sleep -Seconds 2
$estado = (Get-ScheduledTask -TaskName $nome).State
if ($estado -ne 'Running') { throw "A tarefa ficou em estado $estado" }
Write-Output 'Observador em execucao'
"""
    resultado = executor(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=25, check=False,
    )
    if resultado.returncode:
        detalhe = (resultado.stderr or resultado.stdout or "falha no Agendador").strip()
        raise RuntimeError(detalhe[-500:])
    return "Observador iniciado/reiniciado no Agendador de Tarefas"


def processar_uma_vez(cliente: Any,
                      acionar: Callable[[], str] = reiniciar_tarefa) -> bool:
    dados = cliente.rpc("reservar_pedido_observador").execute().data or []
    if not dados:
        return False
    pedido = dados[0]
    identificador, token = pedido["pedido_id"], pedido["token"]
    try:
        resultado = acionar()
        sucesso = True
    except Exception as erro:
        resultado = f"{type(erro).__name__}: {erro}"[:500]
        sucesso = False
    resposta = cliente.rpc("concluir_pedido_observador", {
        "pedido": identificador, "token": token,
        "sucesso": sucesso, "detalhe": resultado,
    }).execute().data
    if resposta is not True:
        raise RuntimeError("Não foi possível confirmar o resultado do pedido")
    registrar(f"pedido {identificador}: {'concluido' if sucesso else 'falha'}; {resultado}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uma-vez", action="store_true",
                        help="Verifica a fila uma vez e encerra")
    argumentos = parser.parse_args()
    raiz = PROJECT_ROOT
    dependencias = raiz / "tmp" / "praticagem-deps"
    if dependencias.is_dir():
        sys.path.insert(0, str(dependencias))
    os.chdir(raiz)
    from vessel_monitor.config import criar_supabase
    cliente = criar_supabase(administrativo=True)
    registrar("controlador do observador iniciado")
    while True:
        espera = INTERVALO_S
        try:
            processar_uma_vez(cliente)
        except Exception as erro:
            registrar(f"falha no controlador: {type(erro).__name__}: {erro}")
            espera = 60
            if argumentos.uma_vez:
                raise
        if argumentos.uma_vez:
            return
        time.sleep(espera)


if __name__ == "__main__":
    main()
