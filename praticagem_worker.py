"""Observador contínuo da Praticagem, sem entrega de mensagens ao WhatsApp.

Requer um executor sempre ligado. As coletas, eventos e alertas simulados são
persistidos pelo observador no Supabase; uma falha recria a sessão do navegador.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from praticagem_observador import executar
from praticagem_portal import SessaoPraticagem
from praticagem_transicoes import formatar_alerta
from alerta_sonoro import tocar_alerta
from vos_integration import sync_safely
from simular_praticagem import (PEDIDO_OBSERVADOR, PEDIDO_TOXOTIS,
                               gerar_cenarios, simular_proxima_etapa_toxotis)


INTERVALO_MINIMO = 60
RECUO_MAXIMO = 120
LIMITE_CICLO_S = 165


def vigiar_ciclos(inicio_atual: list[float | None], parar: threading.Event) -> None:
    """Libera a tarefa para reinício se uma operação externa não retornar."""
    while not parar.wait(5):
        inicio = inicio_atual[0]
        if inicio is not None and time.monotonic() - inicio > LIMITE_CICLO_S:
            print(f"{datetime.now(timezone.utc).isoformat()} "
                  f"ciclo excedeu {LIMITE_CICLO_S}s; "
                  "encerrando processo para reinício automático",
                  file=sys.stderr, flush=True)
            os._exit(124)


def espera_ate_proximo_ciclo(inicio: float, agora: float, intervalo: int,
                             falhas: int) -> float:
    """Mantém a cadência e reduz carga sobre a fonte durante falhas."""
    alvo = max(intervalo, min(RECUO_MAXIMO, intervalo * 2 ** min(falhas, 3)))
    return max(0.0, inicio + alvo - agora)


def mostrar_teste_pendente(arquivo: Path | None) -> bool:
    """Consome um pedido local; nenhum dado fictício chega ao Supabase."""
    if arquivo is None:
        return False
    try:
        arquivo.unlink()
    except FileNotFoundError:
        return False
    print("=== TESTE LOCAL NO OBSERVADOR; NAVIO FICTÍCIO; "
          "NÃO GRAVADO / NÃO ENVIADO ===", flush=True)
    for titulo, mensagens in gerar_cenarios():
        print(f"--- {titulo} ---", flush=True)
        for mensagem in mensagens:
            print(mensagem, flush=True)
        if not mensagens:
            print("Nenhum aviso", flush=True)
    print("=== FIM DO TESTE LOCAL ===", flush=True)
    return True


def observar_continuamente(cliente: Any, criar_sessao: Callable[[], Any],
                           *, intervalo: int = INTERVALO_MINIMO,
                           max_ciclos: int | None = None,
                           arquivo_teste: Path | None = None,
                           arquivo_toxotis: Path | None = None,
                           arquivo_som: Path | None = None) -> None:
    if intervalo < INTERVALO_MINIMO:
        raise ValueError("O intervalo mínimo é de 60 segundos")
    sessao = None
    falhas = 0
    ciclos = 0
    ultimo_inicio: float | None = None
    inicio_atual: list[float | None] = [None]
    parar_vigia = threading.Event()
    threading.Thread(target=vigiar_ciclos, args=(inicio_atual, parar_vigia),
                     daemon=True, name="vigia-praticagem").start()
    try:
        while max_ciclos is None or ciclos < max_ciclos:
            inicio = time.monotonic()
            inicio_atual[0] = inicio
            intervalo_real = (None if ultimo_inicio is None
                              else round(inicio - ultimo_inicio, 1))
            ultimo_inicio = inicio
            print(f"{datetime.now(timezone.utc).isoformat()} ciclo iniciado; "
                  f"intervalo_desde_anterior_s={intervalo_real if intervalo_real is not None else 'N/A'}",
                  flush=True)
            try:
                if arquivo_som is not None and arquivo_som.exists():
                    arquivo_som.unlink()
                    print("=== TESTE SONORO; NAVIO FICTÍCIO; NÃO GRAVADO / NÃO ENVIADO ===", flush=True)
                    print(formatar_alerta({"nome": "NAVIO TESTE", "mudancas": [
                        {"campo": "fase", "antes": "previsao", "depois": "andamento"}]}), flush=True)
                    tocar_alerta()
                    print("=== FIM DO TESTE SONORO ===", flush=True)
                mostrar_teste_pendente(arquivo_teste)
            except Exception as exc:
                print(f"Falha no teste local: {type(exc).__name__}",
                      file=sys.stderr, flush=True)
            try:
                registrados: list[dict[str, Any]] = []
                capturas: list[dict[str, Any]] = []

                def coletar() -> dict[str, Any]:
                    nonlocal sessao
                    # A reserva no banco é solicitada por executar antes de
                    # chamar este callback. Não abra o Edge quando outro ciclo
                    # ainda detém a reserva.
                    if sessao is None:
                        print(f"{datetime.now(timezone.utc).isoformat()} "
                              "reserva obtida; abrindo Edge", flush=True)
                        nova_sessao = criar_sessao()
                        nova_sessao.__enter__()
                        sessao = nova_sessao
                    print(f"{datetime.now(timezone.utc).isoformat()} "
                          "leitura do portal iniciada", flush=True)
                    captura = sessao.capturar()
                    capturas.append(captura)
                    return captura

                eventos = executar(cliente, coletar, registrados)
                falhas = 0
                if capturas:
                    print(f"{datetime.now(timezone.utc).isoformat()} "
                          f"coleta concluída; duracao_s={time.monotonic()-inicio:.1f}; "
                          f"eventos simulados={eventos}", flush=True)
                else:
                    print(f"{datetime.now(timezone.utc).isoformat()} "
                          f"ciclo sem coleta; duracao_s={time.monotonic()-inicio:.1f}; "
                          "reserva em uso", flush=True)
                if arquivo_toxotis is not None and arquivo_toxotis.exists():
                    try:
                        # Após reinício, uma reserva antiga pode impedir a coleta
                        # normal por alguns minutos. Só neste teste, leia o portal
                        # diretamente sem registrar qualquer dado dessa leitura.
                        captura_teste = capturas[0] if capturas else coletar()
                        aviso_teste = simular_proxima_etapa_toxotis(captura_teste)
                        print(aviso_teste, flush=True)
                        arquivo_toxotis.unlink()
                    except Exception as exc:
                        print(f"Falha no teste TOXOTIS: {type(exc).__name__}: {exc}",
                              file=sys.stderr, flush=True)
                for evento in registrados:
                    print("--- AVISO SIMULADO; NÃO ENVIADO ---", flush=True)
                    print(formatar_alerta(evento), flush=True)
                    tocar_alerta()
            except Exception as exc:
                falhas += 1
                print(f"{datetime.now(timezone.utc).isoformat()} "
                      f"falha na coleta: {type(exc).__name__}; "
                      f"duracao_s={time.monotonic()-inicio:.1f}; "
                      f"falhas consecutivas={falhas}", file=sys.stderr, flush=True)
                traceback.print_exc(file=sys.stderr)
                if sessao is not None:
                    try:
                        sessao.__exit__(None, None, None)
                    except Exception:
                        pass
                    sessao = None
            sync_safely(cliente)
            inicio_atual[0] = None
            ciclos += 1
            if max_ciclos is None or ciclos < max_ciclos:
                time.sleep(espera_ate_proximo_ciclo(
                    inicio, time.monotonic(), intervalo, falhas))
    finally:
        parar_vigia.set()
        if sessao is not None:
            sessao.__exit__(None, None, None)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consulta a Praticagem continuamente e registra alertas simulados")
    parser.add_argument("--intervalo", type=int, default=INTERVALO_MINIMO,
                        help="Segundos entre inícios de coleta (mínimo 60)")
    parser.add_argument("--visivel", action="store_true",
                        help="Mostra o navegador localmente")
    parser.add_argument("--canal", choices=("msedge", "chrome", "chromium"),
                        help="Canal do navegador; padrão msedge no Windows")
    args = parser.parse_args()

    from config import criar_supabase

    usuario = os.getenv("SPPILOTS_USUARIO", "")
    senha = os.getenv("SPPILOTS_SENHA", "")
    if not usuario or not senha:
        parser.error("Configure SPPILOTS_USUARIO e SPPILOTS_SENHA no ambiente")
    cliente = criar_supabase(administrativo=True)
    try:
        observar_continuamente(
            cliente,
            lambda: SessaoPraticagem(usuario, senha, headless=not args.visivel,
                                      canal=args.canal),
            intervalo=args.intervalo,
            arquivo_teste=PEDIDO_OBSERVADOR if os.name == "nt" else None,
            arquivo_toxotis=PEDIDO_TOXOTIS if os.name == "nt" else None,
            arquivo_som=Path(__file__).resolve().parent / "tmp" / "praticagem-teste-som.flag"
            if os.name == "nt" else None,
        )
    except KeyboardInterrupt:
        print("Observador interrompido.")


if __name__ == "__main__":
    main()
