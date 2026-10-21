"""Mostra no console avisos de exemplo, sem site, Supabase ou WhatsApp."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from vessel_monitor.paths import STATE_DIR

from vessel_monitor.application.praticagem_observador import montar_pacote
from vessel_monitor.sources.praticagem.praticagem_normalizador import normalizar_captura
from vessel_monitor.domain.praticagem_snapshot import construir_snapshot
from vessel_monitor.domain.praticagem_transicoes import formatar_alerta


IMO_FICTICIO = "9999999"
QUANTIDADES_FICTICIAS = {"movimentos": 1, "previstas": 1,
                         "atracados": 1, "fundeados": 1}
PEDIDO_OBSERVADOR = STATE_DIR / "praticagem-teste.flag"
PEDIDO_TOXOTIS = STATE_DIR / "praticagem-teste-toxotis.flag"
IMO_TOXOTIS = "9563419"


def estado(fase: str | None = None, *, horario: str = "09/10 14:00",
           local: str = "13/14", fundeado: bool = False) -> dict:
    manobras = []
    if fase:
        manobras.append({"chave": "manobra-exemplo", "mv": "S", "fase": fase,
                         "pob": horario, "local1": local, "local2": "",
                         "passag": ""})
    return {"imo": IMO_FICTICIO, "nome": "NAVIO EXEMPLO",
            "manobras": manobras, "fundeado": fundeado, "atracado": False}


def gerar_cenarios() -> list[tuple[str, list[str]]]:
    """Passa os dados fictícios pela mesma comparação usada pelo observador."""
    casos = [
        ("Primeira leitura", estado()),
        ("Nova previsão", estado("previsao")),
        ("Confirmação", estado("confirmada")),
        ("Andamento com horário e local alterados",
         estado("andamento", horario="09/10 14:30", local="15")),
        ("Fundeio", estado("andamento", horario="09/10 14:30",
                           local="15", fundeado=True)),
        ("Releitura igual", estado("andamento", horario="09/10 14:30",
                                   local="15", fundeado=True)),
    ]
    anterior = {}
    resultado = []
    for titulo, atual in casos:
        estados, eventos = montar_pacote(
            {"quantidades": QUANTIDADES_FICTICIAS, "navios": [deepcopy(atual)]},
            {IMO_FICTICIO: "NAVIO EXEMPLO"}, anterior, [])
        resultado.append((titulo, [formatar_alerta(evento) for evento in eventos]))
        anterior = {IMO_FICTICIO: estados[0]}
    return resultado


def simular_proxima_etapa_toxotis(captura: dict) -> str:
    """Compara o TOXOTIS real a uma próxima fase hipotética, só em memória."""
    normalizado = normalizar_captura(captura)
    snapshot = construir_snapshot(normalizado, {})
    atuais = [n for n in snapshot["navios"] if n["imo"] == IMO_TOXOTIS]
    if len(atuais) != 1:
        raise ValueError("TOXOTIS não encontrado de forma única na captura atual")
    atual = atuais[0]
    observacoes = [o for o in normalizado["observacoes"]
                   if o["imo"] == IMO_TOXOTIS]
    fundeios = [o["fundeio"] for o in observacoes if o["tabela"] == "fundeados"]
    manobras = atual["manobras"]
    if len(manobras) > 1:
        raise ValueError("TOXOTIS tem mais de uma manobra; próxima fase ambígua")
    proximo = deepcopy(atual)
    fases = {"previsao": "confirmada", "confirmada": "andamento",
             "andamento": "encerrada"}
    if manobras:
        fase_atual = manobras[0]["fase"]
        if fase_atual not in fases:
            raise ValueError("Manobra do TOXOTIS já encerrada; sem próxima fase")
        proximo["manobras"][0]["fase"] = fases[fase_atual]
        situacao = f"Manobra em {fase_atual}"
    else:
        proximo["manobras"] = [{
            "chave": "teste-toxotis-previsao", "mv": "", "fase": "previsao",
            "pob": "", "passag": "", "local1": "", "local2": "",
        }]
        situacao = "Fundeado" if atual["fundeado"] else (
            "Atracado" if atual["atracado"] else "Sem manobra visível")
    _, eventos = montar_pacote(
        {"quantidades": snapshot["quantidades"], "navios": [proximo]},
        {IMO_TOXOTIS: atual["nome"]}, {IMO_TOXOTIS: atual}, [])
    if len(eventos) != 1:
        raise ValueError("A simulação não produziu um alerta único")
    linhas = ["=== TESTE TOXOTIS COM CAPTURA REAL; NÃO GRAVADO / NÃO ENVIADO ===",
              f"Coleta: {normalizado['coletado_em'] or 'N/A'}",
              f"Situação observada no portal: {situacao}"]
    if fundeios:
        linhas.append(f"Fundeio informado: {fundeios[0] or 'N/A'}")
    linhas.extend(["Próxima etapa HIPOTÉTICA (teste):",
                   formatar_alerta(eventos[0]),
                   "Horário e local da nova etapa: N/A (não observados)",
                   "=== FIM DO TESTE TOXOTIS ==="])
    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulação isolada da Praticagem")
    parser.add_argument("--observador", action="store_true",
                        help="Pede que a tarefa em execução mostre os exemplos no próximo ciclo")
    parser.add_argument("--toxotis", action="store_true",
                        help="Com --observador, testa a próxima etapa do TOXOTIS com captura real")
    args = parser.parse_args()
    if args.toxotis and not args.observador:
        parser.error("--toxotis requer --observador")
    if args.observador:
        pedido = PEDIDO_TOXOTIS if args.toxotis else PEDIDO_OBSERVADOR
        pedido.parent.mkdir(parents=True, exist_ok=True)
        pedido.touch()
        print("Teste solicitado ao observador. Aguarde o próximo ciclo no console ou log.")
        return

    print("SIMULAÇÃO LOCAL — NAVIO FICTÍCIO; NADA SERÁ ENVIADO OU GRAVADO\n")
    for titulo, mensagens in gerar_cenarios():
        print(f"--- {titulo} ---")
        if mensagens:
            for mensagem in mensagens:
                print(mensagem)
        else:
            print("Nenhum aviso")
        print()


if __name__ == "__main__":
    main()
