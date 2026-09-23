import re
from typing import Any

from consulta_navio import (
    formatar_navio,
    formatar_resumo,
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
  from atualizacao_chat import ativo
  texto = '🚢 *Monitor de Navios*\n\nDigite o *nome do navio* ou utilize os comandos abaixo.\n\n*Consultas*\n\n🔎 *Consultar NOME* — detalhes do navio\n📋 *Lista* — navios monitorados\n📊 *Resumo* — dados da última coleta'
  if admin and ativo():
    texto += "\n🔄 *Atualizar* — buscar dados novos"
  if admin:
    texto += '\n\n*Gerenciar a lista*\n\n➕ *Adicionar NOME* — incluir navio\n➖ *Remover NOME* — solicitar remoção\n✅ *Confirmar* — aprovar remoção\n↩️ *Cancelar* — cancelar solicitação'
  return texto + '\n\n*Relatórios*\n\n🔔 *Assinar* — receber relatórios\n🔕 *Parar* — suspender relatórios'


def _resultado_adicao(resultado: Registro) -> str:
  partes: list[str] = []
  adicionados = resultado.get("adicionados") or []
  existentes = resultado.get("existentes") or []
  ausentes = resultado.get("nao_encontrados") or []
  if adicionados:
    partes.append(("✅ *Navio adicionado*" if len(adicionados) == 1 else "✅ *Navios adicionados*") + "\n\n" + "\n".join(f"🚢 *{n}*" for n in adicionados) + "\n\nInclusão na *lista de monitoramento* realizada.")
  if existentes:
    partes.append(("ℹ️ *Navio já monitorado*" if len(existentes) == 1 else "ℹ️ *Navios já monitorados*") + "\n\n" + "\n".join(f"🚢 *{n}*" for n in existentes))
  for item in ausentes:
    trecho = f"🔎 *Navio não localizado nas fontes do porto*\n\n*{item['termo']}* não foi adicionado.\n\nConfira o nome e tente novamente."
    if item.get("sugestoes"):
      trecho += "\n\n*Nomes semelhantes*\n\n" + "\n".join(f"🚢 *{nome}*" for nome in item["sugestoes"])
    partes.append(trecho)
  return "\n\n".join(partes) or "🔎 *Informe o navio*\n\nEnvie o *nome completo* do navio."


def _consultar(texto: str, navios: list[Registro]) -> str:
  termos = separar_termos(texto)
  if not termos:
    return "🔎 *Informe o navio*\n\nEnvie *Consultar ECO CZAR* ou apenas *ECO CZAR*."
  respostas: list[str] = []
  for termo in termos:
    encontrados = localizar_navios(termo, navios)
    if len(encontrados) == 1:
      respostas.append(formatar_navio(encontrados[0]))
    elif len(encontrados) > 1:
      opcoes = "\n".join(f"🚢 *{n.get('nome')}*" for n in encontrados[:8])
      respostas.append(
          f'🔎 *Mais de um navio encontrado*\n\nResultados para *{termo}*:\n\n{opcoes}\n\n'
          "Envie o *nome completo* do navio desejado."
      )
    else:
      sugestoes = sugerir_navios(termo, navios)
      resposta = f'🔎 *Navio não encontrado*\n\n*{termo}* não consta na lista de monitoramento.\n\nEnvie *Lista* para consultar os nomes cadastrados.'
      if sugestoes:
        resposta += "\n\n*Nomes semelhantes*\n\n" + "\n".join(
            f"🚢 *{nome}*" for nome in sugestoes
        )
      respostas.append(resposta)
  return "\n\n───────────────\n\n".join(respostas)


def processar_chat(cliente, remetente: str, texto: str) -> str:
  mensagem = texto.strip()
  comando = normalizar(mensagem)
  admin = eh_administrador(cliente, remetente)

  if comando == "ATUALIZAR":
    if not admin:
      return "🔒 *Acesso restrito*\n\nEste comando está disponível apenas para *administradores*."
    from atualizacao_chat import ativo, solicitar
    if not ativo():
      return "ℹ️ *Atualização temporariamente indisponível*\n\nEnvie *Resumo* para consultar os dados da última coleta."
    from lista_monitoramento import normalizar_telefone
    return solicitar(cliente, normalizar_telefone(remetente))
  if comando in ("AJUDA", "MENU", "COMANDOS", "OI", "OLA", "BOM DIA", "BOA TARDE", "BOA NOITE"):
    return _ajuda(admin)
  if comando in ("ASSINAR", "RECEBER RELATORIO"):
    definir_relatorio(cliente, remetente, True)
    return "🔔 *Inscrição realizada*\n\nO recebimento de relatórios está habilitado para este número.\n\nOs relatórios serão enviados quando o *envio automático estiver ativo*."
  if comando in ("PARAR", "PARAR RELATORIO"):
    definir_relatorio(cliente, remetente, False)
    return "🔕 *Recebimento de relatórios desativado*\n\nPara reativar, envie *Assinar*."
  if comando == "RESUMO":
    navios = montar_visao_monitorados(cliente)
    cabecalho = "📊 *Resumo dos navios*\n\nInformações da *última coleta*."
    if not navios:
      return cabecalho + "\n\n📋 *Lista de monitoramento vazia*\n\nPara incluir um navio, um administrador deve enviar *Adicionar NOME*."
    return cabecalho + "\n\n" + "\n\n───────────────\n\n".join(
        formatar_resumo(navio) for navio in navios
    )
  if comando in ("LISTA", "LISTAR MONITORADOS"):
    navios = montar_visao_monitorados(cliente)
    from lista_monitoramento import normalizar_telefone
    cliente.table("listas_exibidas_chat").upsert({
        "telefone": normalizar_telefone(remetente),
        "itens": [n.get("lista_monitoramento_id") for n in navios],
    }, on_conflict="telefone").execute()
    if not navios:
      return "📋 *Lista de monitoramento vazia*\n\nPara incluir um navio, um administrador deve enviar *Adicionar NOME*."
    return "📋 *Navios monitorados*\n\n" + "\n".join(
        f"{indice}. *{navio.get('nome')}*"
        for indice, navio in enumerate(navios, start=1)
    ) + "\n\n🔎 Para consultar os detalhes, envie o *número da lista* ou o *nome do navio*."
  if comando in ("SIM", "CONFIRMAR"):
    if not admin:
      return "🔒 *Acesso restrito*\n\nEste comando está disponível apenas para *administradores*."
    removidos = confirmar_remocao(cliente, remetente)
    return (
        "✅ *Remoção concluída*\n\n" + "\n".join(f"🚢 *{nome}*" for nome in removidos) + "\n\nRemoção da *lista de monitoramento* realizada."
        if removidos else "ℹ️ *Nenhum navio removido*\n\nA solicitação não está mais válida ou os dados dos navios voltaram a ficar disponíveis.\n\nEnvie *Lista* para conferir o monitoramento atual."
    )
  if comando in ("NAO", "CANCELAR"):
    cancelar_confirmacao(cliente, remetente)
    return "↩️ *Solicitação cancelada*\n\nA lista de monitoramento foi *mantida*."
  if comando.startswith("ADICIONAR"):
    if not admin:
      return "🔒 *Inclusão restrita*\n\nApenas *administradores* podem adicionar navios à lista."
    termos = _argumentos(mensagem, "adicionar")
    if not termos:
      return '➕ *Informe o navio para adicionar*\n\nExemplo: *Adicionar ECO CZAR*\n\nPara vários navios, separe os nomes com *;*\n*Adicionar ECO CZAR; AETERNO*'
    from sincronizador import coletar_catalogo_completo
    try:
      catalogo, _, _, _ = coletar_catalogo_completo()
    except Exception:
      return "⚠️ *Cadastro não realizado*\n\nNão foi possível consultar as fontes do porto.\n\n*Nenhum navio foi adicionado.* Tente novamente em instantes."
    try:
      resultado = adicionar_navios(cliente, termos, remetente, catalogo)
    except Exception:
      return "⚠️ *Cadastro não concluído*\n\nParte do pedido pode ter sido salva.\n\nEnvie *Lista* para conferir antes de tentar novamente."
    return _resultado_adicao(resultado)
  if comando.startswith("REMOVER"):
    if not admin:
      return "🔒 *Remoção restrita*\n\nApenas *administradores* podem remover navios da lista."
    termos = _argumentos(mensagem, "remover")
    if not termos:
      return '➖ *Informe o navio para remover*\n\nExemplo: *Remover ECO CZAR*\n\nPara vários navios, separe os nomes com *;*\n*Remover ECO CZAR; AETERNO*'
    resultado = preparar_remocao(cliente, remetente, termos)
    selecionados = resultado.get("selecionados") or []
    if not selecionados:
      return "🔎 *Nenhum navio selecionado*\n\nOs nomes informados não foram encontrados na lista.\n\nEnvie *Lista* para conferir os nomes cadastrados."
    resposta = "🗑️ *Solicitação de remoção*\n\n" + "\n".join(
        f"🚢 *{nome}*" for nome in selecionados
    ) + "\n\n😺 Posso remover estes navios da lista?\n\n*Confirmar* — remover\n*Cancelar* — manter\n\n⏳ Confirmação válida por *10 minutos*."
    if resultado.get("nao_encontrados"):
      resposta += "\n\n*Nomes não encontrados na lista*\n\n" + ", ".join(resultado["nao_encontrados"]) + "\n\nA confirmação vale apenas para os navios selecionados acima."
    return resposta

  # Seven-digit input remains an IMO lookup; list positions use up to six digits.
  if re.fullmatch(r"[0-9]{1,6}", mensagem):
    from lista_monitoramento import normalizar_telefone
    registros = cliente.table("listas_exibidas_chat").select("itens").eq(
        "telefone", normalizar_telefone(remetente)).limit(1).execute().data or []
    if not registros or not registros[0]["itens"]:
      return "📋 *Lista necessária*\n\nEnvie *Lista* e depois o *número do navio* desejado."
    itens = registros[0]["itens"]
    posicao = int(mensagem)
    if not 1 <= posicao <= len(itens):
      return f"🔎 *Número fora da lista*\n\nDigite um número de *1 a {len(itens)}* ou envie *Lista* novamente."
    selecionado = next((n for n in montar_visao_monitorados(cliente)
                         if n.get("lista_monitoramento_id") is not None
                         and n["lista_monitoramento_id"] == itens[posicao - 1]), None)
    if selecionado is None:
      return "ℹ️ *Navio não monitorado*\n\nEste navio não está mais na lista. Envie *Lista* para consultar a relação atual."
    return formatar_navio(selecionado)

  consulta = (
      _argumentos(mensagem, "consultar")
      if comando.startswith("CONSULTAR")
      else separar_termos(mensagem)
  )
  return _consultar(";".join(consulta), montar_visao_monitorados(cliente))
