import re
from typing import Any

from consulta_navio import (
    formatar_navio,
    localizar_navios,
    normalizar,
    separar_termos,
    sugerir_navios,
)
from lista_monitoramento import (
    adicionar_navios,
    cancelar_confirmacao,
    confirmar_remocao,
    definir_relatorio,
    eh_administrador,
    montar_visao_monitorados,
    preparar_remocao,
)

Registro = dict[str, Any]


def _argumentos(texto: str, comando: str) -> list[str]:
  restante = re.sub(
      rf"^\s*{comando}\s*:?", "", texto, count=1, flags=re.IGNORECASE
  ).strip()
  return separar_termos(restante)


def _ajuda(admin: bool) -> str:
  comandos = [
      "Envie o nome do navio para consultar.",
      "Consultar: NAVIO A; NAVIO B",
      "Lista",
      "Resumo",
      "Assinar",
      "Parar",
      "Cancelar",
  ]
  if admin:
    from atualizacao_chat import ativo
    if ativo():
      comandos.append("Atualizar")
    comandos.extend((
        "Adicionar: NAVIO A; NAVIO B",
        "Remover: NAVIO A; NAVIO B",
        "Confirmar",
    ))
  return "COMANDOS DISPONIVEIS\n\n" + "\n".join(f"- {item}" for item in comandos)


def _resultado_adicao(resultado: Registro) -> str:
  partes: list[str] = []
  adicionados = resultado.get("adicionados") or []
  existentes = resultado.get("existentes") or []
  ausentes = resultado.get("nao_encontrados") or []
  if adicionados:
    partes.append("Adicionados:\n" + "\n".join(f"- {n}" for n in adicionados))
  if existentes:
    partes.append("Ja acompanhados:\n" + "\n".join(f"- {n}" for n in existentes))
  for item in ausentes:
    trecho = f"Nao encontrado: {item['termo']}"
    if item.get("sugestoes"):
      trecho += "\nVoce quis dizer: " + ", ".join(item["sugestoes"])
    partes.append(trecho)
  return "\n\n".join(partes) or "Nenhum navio foi informado."


def _consultar(texto: str, navios: list[Registro]) -> str:
  termos = separar_termos(texto)
  if not termos:
    return "Informe o nome do navio que deseja consultar."
  respostas: list[str] = []
  for termo in termos:
    encontrados = localizar_navios(termo, navios)
    if len(encontrados) == 1:
      respostas.append(formatar_navio(encontrados[0]))
    elif len(encontrados) > 1:
      opcoes = "\n".join(f"- {n.get('nome')}" for n in encontrados[:8])
      respostas.append(
          f'Encontrei mais de um resultado para "{termo}":\n{opcoes}\n'
          "Informe o nome completo."
      )
    else:
      sugestoes = sugerir_navios(termo, navios)
      resposta = f'O navio "{termo}" nao esta na lista de acompanhamento.'
      if sugestoes:
        resposta += "\n\nVoce quis dizer:\n" + "\n".join(
            f"- {nome}" for nome in sugestoes
        )
      respostas.append(resposta)
  return "\n\n--------------------\n\n".join(respostas)


def processar_chat(cliente, remetente: str, texto: str) -> str:
  mensagem = texto.strip()
  comando = normalizar(mensagem)
  admin = eh_administrador(cliente, remetente)

  if comando == "ATUALIZAR":
    if not admin:
      return "Seu numero nao possui permissao administrativa."
    from atualizacao_chat import ativo, solicitar
    if not ativo():
      return "Atualizacao sob demanda ainda nao esta ativa. Use Resumo."
    from lista_monitoramento import normalizar_telefone
    return solicitar(cliente, normalizar_telefone(remetente))
  if comando in ("AJUDA", "MENU", "COMANDOS"):
    return _ajuda(admin)
  if comando in ("ASSINAR", "RECEBER RELATORIO"):
    definir_relatorio(cliente, remetente, True)
    return "Inscricao realizada. O recebimento depende da rotina de envio estar ativa."
  if comando in ("PARAR", "PARAR RELATORIO"):
    definir_relatorio(cliente, remetente, False)
    return "Envio do relatorio cancelado."
  if comando == "RESUMO":
    navios = montar_visao_monitorados(cliente)
    cabecalho = "RESUMO — ultimos dados salvos; este comando nao faz nova coleta."
    if not navios:
      return cabecalho + "\n\nNenhum navio esta sendo acompanhado."
    return cabecalho + "\n\n" + "\n\n--------------------\n\n".join(
        formatar_navio(navio) for navio in navios
    )
  if comando in ("LISTA", "LISTAR MONITORADOS"):
    navios = montar_visao_monitorados(cliente)
    if not navios:
      return "Nenhum navio esta sendo acompanhado."
    return "NAVIOS ACOMPANHADOS\n\n" + "\n".join(
        f"{indice}. {navio.get('nome')}"
        for indice, navio in enumerate(navios, start=1)
    )
  if comando in ("SIM", "CONFIRMAR"):
    if not admin:
      return "Seu numero nao possui permissao administrativa."
    removidos = confirmar_remocao(cliente, remetente)
    return (
        "Removidos:\n" + "\n".join(f"- {nome}" for nome in removidos)
        if removidos else "Nenhum navio removido. A confirmacao pode ter expirado, ja ter sido respondida ou os navios voltaram a ter dados."
    )
  if comando in ("NAO", "CANCELAR"):
    cancelar_confirmacao(cliente, remetente)
    return "Operacao cancelada."
  if comando.startswith("ADICIONAR"):
    if not admin:
      return "Seu numero nao possui permissao para adicionar navios."
    termos = _argumentos(mensagem, "adicionar")
    if not termos:
      return 'Use: Adicionar: NAVIO A; NAVIO B'
    from sincronizador import coletar_catalogo_completo
    catalogo, _, _, _ = coletar_catalogo_completo()
    resultado = adicionar_navios(
        cliente, termos, remetente, catalogo
    )
    return _resultado_adicao(resultado)
  if comando.startswith("REMOVER"):
    if not admin:
      return "Seu numero nao possui permissao para remover navios."
    termos = _argumentos(mensagem, "remover")
    if not termos:
      return 'Use: Remover: NAVIO A; NAVIO B'
    resultado = preparar_remocao(cliente, remetente, termos)
    selecionados = resultado.get("selecionados") or []
    if not selecionados:
      return "Nenhum dos navios informados esta na lista."
    resposta = "Confirma a remocao?\n\n" + "\n".join(
        f"- {nome}" for nome in selecionados
    ) + "\n\nResponda SIM para confirmar ou NAO para cancelar."
    if resultado.get("nao_encontrados"):
      resposta += "\n\nNao encontrados: " + ", ".join(resultado["nao_encontrados"])
    return resposta

  consulta = (
      _argumentos(mensagem, "consultar")
      if comando.startswith("CONSULTAR")
      else separar_termos(mensagem)
  )
  return _consultar(";".join(consulta), montar_visao_monitorados(cliente))
