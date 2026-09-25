"""Relatorio horario: snapshot por hora e progresso persistido por mensagem."""
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from atualizacao_chat import diagnostico_seguro
from consulta_navio import estado_operacional, etapa_evento, formatar_local

MODELO = """🚢 *Monitoramento de navios*
🕒 Coleta: {{1}} (Brasília) • Parte {{2}}

🚢 *{{3}}*
{{4}}
📍 Terminal: {{5}}
Chegada: {{6}}
Atracação: {{7}}

───────────────

🚢 *{{8}}*
{{9}}
📍 Terminal: {{10}}
Chegada: {{11}}
Atracação: {{12}}

Relatório solicitado por assinatura. Para cancelar, envie *Parar*."""


def linha(valor):
  return re.sub(r"\s+", " ", str(valor or "Não informado")).strip()


def campos(navio):
  if not navio:
    return ["Fim da lista", "—", "—", "—", "—"]
  nome = linha(navio.get("nome"))
  if str(navio.get("situacao") or "indisponivel").lower() == "indisponivel":
    return [nome, "⚪ Não localizado nesta coleta", "—", "—", "—"]
  emoji, estado = estado_operacional(navio)
  etb = ("✅ Já atracado / etapa posterior" if etapa_evento(navio.get("evento"))[0] >= 3
         else "⏳ Prevista: " + linha(navio.get("etb")))
  return [nome, f"{emoji} {linha(estado)}", linha(formatar_local(navio.get("local"))),
          linha(navio.get("eta")), etb]


def preparar_paginas(navios, momento=None):
  momento = momento or datetime.now(timezone.utc)
  horario = momento.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")
  grupos = [navios[i:i + 2] for i in range(0, len(navios), 2)] or [[]]
  paginas = []
  for i, grupo in enumerate(grupos, 1):
    primeiro = campos(grupo[0]) if grupo else ["Lista vazia", "⚪ Nenhum navio monitorado", "—", "—", "—"]
    valores = [horario, f"{i}/{len(grupos)}", *primeiro,
               *campos(grupo[1] if len(grupo) > 1 else None)]
    renderizado = re.sub(r"\{\{(\d+)\}\}", lambda m: valores[int(m[1]) - 1], MODELO)
    if len(renderizado) > 1024:
      raise ValueError("Relatorio excede o limite do modelo; nenhum dado foi cortado")
    paginas.append(valores)
  return paginas


def processar(cliente, coletar, enviar):
  reserva = cliente.rpc("reservar_relatorio_horario", {}).execute().data or []
  if not reserva:
    print("Relatorio da hora concluido ou executor ativo.")
    return
  lote = reserva[0]
  lote_id, token = lote["id"], lote["reserva_token"]
  def rpc(nome, **dados):
    return cliente.rpc(nome, {"lote": lote_id, "token": token, **dados}).execute().data
  falhas = 0
  try:
    if lote.get("paginas") is None:
      from lista_monitoramento import montar_visao_monitorados
      coletar()  # Falha de coleta nunca e apresentada como dado atualizado.
      paginas = preparar_paginas(montar_visao_monitorados(cliente))
      rpc("preparar_relatorio_horario", conteudo=paginas)
    itens = rpc("listar_entregas_horarias") or []
    for item in itens:
      if not rpc("iniciar_entrega_horaria", entrega=item["id"]):
        continue  # Cancelamento da assinatura ou entrega ja processada.
      try:
        message_id = enviar(item["telefone"], item["parametros"], item["id"])
      except Exception as erro:
        diagnostico_seguro(erro, "relatorio_horario")
        # Uma resposta HTTP de erro e uma rejeicao conhecida. Timeout/desconexao
        # pode acontecer depois de a Meta aceitar: nao repetir automaticamente.
        causa = erro
        rejeitado = False
        while causa is not None:
          resposta = getattr(causa, "response", None)
          if resposta is not None:
            rejeitado = 400 <= resposta.status_code < 500
            break
          causa = causa.__cause__ or causa.__context__
        rpc("finalizar_entrega_horaria", entrega=item["id"],
            resultado="falha" if rejeitado else "incerto", mensagem=None)
        falhas += 1
        continue
      # Se esta gravacao falhar, a entrega permanece 'enviando'. O callback
      # assinado da Meta pode reconciliar pelo id opaco, sem enviar novamente.
      rpc("finalizar_entrega_horaria", entrega=item["id"], resultado="aceito", mensagem=message_id)
    pendentes = rpc("concluir_relatorio_horario")
    if falhas or pendentes:
      raise RuntimeError("Relatorio horario com entregas pendentes; consulte o painel de entregas")
    print("Relatorio horario processado. Aceite da API nao confirma entrega ao telefone.")
  finally:
    rpc("liberar_relatorio_horario")


def executar():
  from config import criar_supabase
  from sincronizador import sincronizar
  from whatsapp import enviar_modelo_relatorio
  if os.getenv("RELATORIO_WHATSAPP_ATIVO", "").lower() != "true":
    print("Relatorio horario desativado.")
    return
  for nome in ("META_ACCESS_TOKEN", "META_PHONE_NUMBER_ID", "META_REPORT_TEMPLATE_NAME"):
    if not os.getenv(nome, "").strip():
      raise RuntimeError(f"Configuracao ausente: {nome}")
  os.environ["RELATORIO_WHATSAPP_ATIVO"] = "false"
  processar(criar_supabase(administrativo=True), sincronizar, enviar_modelo_relatorio)


if __name__ == "__main__":
  executar()
