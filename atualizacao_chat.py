"""Fila de atualizacoes solicitadas por administradores no WhatsApp."""
import os
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from consulta_navio import formatar_navio


def diagnostico_seguro(erro, etapa):
  """Registra somente metadados permitidos, nunca texto bruto da excecao."""
  dados = {"evento": "falha_resultado", "etapa": etapa,
           "tipo": type(erro).__name__}
  ausentes = [nome for nome in ("META_ACCESS_TOKEN", "META_PHONE_NUMBER_ID")
             if not os.getenv(nome, "").strip()]
  if ausentes:
    dados["configuracoes_ausentes"] = ausentes
  atual = erro
  vistos = set()
  while atual is not None and id(atual) not in vistos:
    vistos.add(id(atual))
    resposta = getattr(atual, "response", None)
    if resposta is not None:
      if isinstance(resposta.status_code, int):
        dados["http_status"] = resposta.status_code
      try:
        corpo = resposta.json()
        meta = corpo.get("error", {}) if isinstance(corpo, dict) else {}
        if isinstance(meta, dict):
          for campo in ("code", "error_subcode"):
            if isinstance(meta.get(campo), int):
              dados[campo] = meta[campo]
      except (ValueError, TypeError):
        pass
      break
    atual = atual.__cause__ or atual.__context__
  print(json.dumps(dados, ensure_ascii=True))


def ativo():
  return os.getenv("ATUALIZACAO_CHAT_ATIVA", "").strip().lower() in ("true", "1", "sim")


def disparar_github():
  import requests
  token = os.getenv("GH_ACTIONS_TOKEN", "").strip()
  if not token:
    print('disparo_github: nao_configurado')
    return False
  try:
    resposta = requests.post(
        "https://api.github.com/repos/TfGuardian/sgs-monitor-navios/actions/workflows/atualizar-chat.yml/dispatches",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2026-03-10",
                 "User-Agent": "sgs-monitor-navios"},
        json={"ref": "main"}, timeout=(2, 4), allow_redirects=False,
    )
    aceito = 200 <= resposta.status_code < 300
    print(json.dumps({"evento": "disparo_github", "http_status": resposta.status_code,
                      "resultado": "aceito" if aceito else "recusado"}))
    return aceito
  except requests.RequestException:
    print('disparo_github: falha_rede_ou_timeout')
    return False


def solicitar(cliente, numero):
  cliente.rpc("solicitar_atualizacao_chat", {"numero": numero}).execute()
  if disparar_github():
    return ("Atualizacao solicitada e acionamento aceito. Enviarei o resumo ao concluir. "
            "Pedidos durante a mesma coleta compartilham o resultado; o inicio depende da fila de execucao.")
  return ("Pedido de atualizacao salvo. Nao foi possivel confirmar o acionamento imediato. "
          "O pedido aguarda o executor automatico ou uma execucao manual pela equipe.")


def dividir(texto, limite=3800):
  partes = []
  while texto:
    fim = min(limite, len(texto))
    if fim < len(texto):
      quebra = texto.rfind("\n", 0, fim)
      if quebra > 0:
        fim = quebra + 1
    partes.append(texto[:fim])
    texto = texto[fim:]
  return ([f"Parte {i} de {len(partes)}\n\n{parte}"
           for i, parte in enumerate(partes, 1)] if len(partes) > 1 else partes)


def preparar_resultado(cliente, coletar, candidatos=None):
  from lista_monitoramento import montar_visao_monitorados
  try:
    coletar()
  except Exception:
    # O detalhe tecnico permanece no historico de coletas. Nao expor credenciais.
    return ["Nao foi possivel concluir a atualizacao. Os dados anteriores podem "
            "estar desatualizados. Use Resumo para consulta-los ou tente Atualizar novamente."], "falha"
  momento = datetime.now(timezone.utc).astimezone(
      ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")
  navios = montar_visao_monitorados(cliente)
  if candidatos is not None:
    candidatos.extend(candidatos_indisponiveis(navios))
  cabecalho = f"ATUALIZACAO CONCLUIDA — {momento} (Brasilia)"
  cabecalho += "\nAusencia nas fontes nao confirma saida do porto."
  texto = "\n\n".join(formatar_navio(n) for n in navios)
  return dividir(cabecalho + "\n\n" + (texto or "Nenhum navio acompanhado.")), "sucesso"


def candidatos_indisponiveis(navios):
  return [{"id": n["lista_monitoramento_id"], "nome": n.get("nome")}
          for n in navios if n.get("lista_monitoramento_id") is not None
          and str(n.get("situacao") or "indisponivel").lower() == "indisponivel"]


def oferecer_remocao(cliente, lote_id, item, enviar, salvar):
  proposta = cliente.rpc("oferecer_remocao_indisponiveis", {
      "lote": lote_id, "numero": item["telefone"],
  }).execute().data
  if not isinstance(proposta, dict) or not proposta.get("ids"):
    return
  texto = ("NAVIOS INDISPONIVEIS NA ATUALIZACAO\n\n" +
           "\n".join(f"- {nome}" for nome in proposta["nomes"]) +
           "\n\nDeseja remover esses navios da lista compartilhada? "
           "Responda CONFIRMAR ou SIM para remover; CANCELAR ou NAO para manter. "
           "A confirmacao vale por 10 minutos. Navios que voltarem a ter dados serao preservados.")
  perguntas = dividir(texto)
  for indice in range(item.get("proxima_pergunta", 0), len(perguntas)):
    enviar(item["telefone"], perguntas[indice])
    salvar({"proxima_pergunta": indice + 1})


def processar_fila(cliente, coletar, enviar, agora=None):
  lotes = cliente.rpc("reservar_atualizacao_chat", {}).execute().data or []
  if not lotes:
    print("Nenhuma atualizacao pendente ou outro executor ativo.")
    return
  lote = lotes[0]
  lote_id = lote["id"]
  try:
    paginas = lote.get("paginas")
    if lote["estado"] != "pronto":
      candidatos = []
      paginas, resultado = preparar_resultado(cliente, coletar, candidatos)
      cliente.table("atualizacoes_chat").update({"indisponiveis": candidatos}).eq("id", lote_id).execute()
      cliente.rpc("finalizar_coleta_chat", {
          "lote": lote_id, "conteudo": paginas, "resultado_coleta": resultado,
      }).execute()
    destinatarios = (cliente.table("atualizacoes_chat_destinatarios").select("*")
                     .eq("atualizacao_id", lote_id).eq("enviado", False)
                     .eq("expirado", False).execute().data or [])
    falhas = 0
    for item in destinatarios:
      def salvar(dados):
        (cliente.table("atualizacoes_chat_destinatarios").update(dados)
         .eq("atualizacao_id", lote_id).eq("telefone", item["telefone"]).execute())
      # Nao enviar texto livre depois da janela de atendimento de 24h.
      solicitado = datetime.fromisoformat(item["solicitado_em"].replace("Z", "+00:00"))
      if (agora or datetime.now(timezone.utc)) - solicitado >= timedelta(hours=23):
        salvar({"expirado": True})
        print("Solicitacao expirada; consulte Resumo ou envie novo Atualizar.")
        continue
      etapa = "enviar_whatsapp"
      try:
        for indice in range(item["proxima_pagina"], len(paginas)):
          etapa = "enviar_whatsapp"
          enviar(item["telefone"], paginas[indice])
          etapa = "salvar_progresso_supabase"
          salvar({"proxima_pagina": indice + 1})
        etapa = "oferecer_remocao_indisponiveis"
        oferecer_remocao(cliente, lote_id, item, enviar, salvar)
        etapa = "salvar_conclusao_supabase"
        salvar({"enviado": True})
      except Exception as erro:
        falhas += 1
        diagnostico_seguro(erro, etapa)
        print("Falha ao enviar resultado; nova tentativa na proxima execucao.")
    if falhas:
      raise RuntimeError("Entrega de resultados pendente; consulte a proxima execucao.")
    cliente.table("atualizacoes_chat").update({
        "estado": "concluido", "concluido_em": datetime.now(timezone.utc).isoformat(),
    }).eq("id", lote_id).execute()
  finally:
    cliente.table("atualizacoes_chat").update({"reserva_ate": None}).eq("id", lote_id).execute()


def executar():
  from config import criar_supabase
  from sincronizador import sincronizar
  from whatsapp import enviar_texto_whatsapp
  # O pedido individual nao dispara novamente os relatorios de todos os assinantes.
  os.environ["RELATORIO_WHATSAPP_ATIVO"] = "false"
  processar_fila(criar_supabase(administrativo=True), sincronizar, enviar_texto_whatsapp)


if __name__ == "__main__":
  executar()
