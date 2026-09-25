import os
from typing import Any

import requests

TIMEOUT = (5, 30)


def _obrigatorias(nomes: tuple[str, ...], contexto: str) -> tuple[str, ...]:
  valores = tuple(os.getenv(nome, "").strip() for nome in nomes)
  ausentes = [nome for nome, valor in zip(nomes, valores) if not valor]
  if ausentes:
    raise RuntimeError(f"Configuracao {contexto} ausente: {', '.join(ausentes)}")
  return valores


def _configuracao_meta() -> tuple[str, str, str, str, str, str]:
  token, phone_number_id, destinatario, template = _obrigatorias(
      (
          "META_ACCESS_TOKEN",
          "META_PHONE_NUMBER_ID",
          "META_RECIPIENT_PHONE",
          "META_TEMPLATE_NAME",
      ),
      "Meta WhatsApp",
  )
  versao = os.getenv("META_GRAPH_API_VERSION", "").strip() or "v26.0"
  idioma = os.getenv("META_TEMPLATE_LANGUAGE", "").strip() or "pt_BR"
  if not versao.startswith("v"):
    raise RuntimeError("META_GRAPH_API_VERSION deve seguir o formato v26.0")
  return token, phone_number_id, destinatario, template, versao, idioma


def _resposta_meta(response: requests.Response, acao: str) -> dict[str, Any]:
  try:
    response.raise_for_status()
  except requests.HTTPError as exc:
    detalhe = response.text[:600]
    raise RuntimeError(f"Meta recusou {acao}: {detalhe}") from exc
  dados = response.json()
  if not isinstance(dados, dict):
    raise RuntimeError(f"Resposta inesperada da Meta ao {acao}")
  return dados


def verificar_meta() -> bool:
  token, phone_number_id, _, _, versao, _ = _configuracao_meta()
  response = requests.get(
      f"https://graph.facebook.com/{versao}/{phone_number_id}",
      headers={"Authorization": f"Bearer {token}"},
      params={"fields": "display_phone_number,verified_name"},
      timeout=TIMEOUT,
  )
  dados = _resposta_meta(response, "validar o numero")
  numero = dados.get("display_phone_number", phone_number_id)
  nome = dados.get("verified_name", "sem nome verificado")
  print(f"Meta WhatsApp acessivel. Numero: {numero}; nome: {nome}.")
  return True


def enviar_texto_whatsapp(destinatario: str, texto: str) -> bool:
  token, phone_number_id = _obrigatorias(
      ("META_ACCESS_TOKEN", "META_PHONE_NUMBER_ID"), "Meta WhatsApp"
  )
  versao = os.getenv("META_GRAPH_API_VERSION", "").strip() or "v26.0"
  numero = "".join(c for c in destinatario if c.isdigit())
  if not numero:
    raise ValueError("Destinatario do WhatsApp invalido")
  response = requests.post(
      f"https://graph.facebook.com/{versao}/{phone_number_id}/messages",
      headers={
          "Authorization": f"Bearer {token}",
          "Content-Type": "application/json",
      },
      json={
          "messaging_product": "whatsapp",
          "recipient_type": "individual",
          "to": numero,
          "type": "text",
          "text": {"preview_url": False, "body": texto[:4096]},
      },
      timeout=TIMEOUT,
  )
  dados = _resposta_meta(response, "enviar o relatorio")
  mensagens = dados.get("messages") or []
  if not mensagens or not mensagens[0].get("id"):
    raise RuntimeError(f"Meta nao confirmou o envio do relatorio: {dados}")
  return True


def enviar_relatorio_whatsapp(destinatario: str, texto: str) -> bool:
  """Impede uso acidental do modelo antigo, que truncava o relatorio."""
  raise RuntimeError("Use relatorio_horario.py com o modelo de 12 parametros")


def enviar_modelo_relatorio(destinatario: str, parametros: list[str], entrega_id: str) -> str:
  """Modelo de 12 parametros; retorna o ID de aceite, nao uma entrega confirmada."""
  token, phone_id, modelo = _obrigatorias(
      ("META_ACCESS_TOKEN", "META_PHONE_NUMBER_ID", "META_REPORT_TEMPLATE_NAME"),
      "relatorio horario")
  if len(parametros) != 12 or any(not isinstance(p, str) or not p or
                                  any(c in p for c in "\n\r\t") for p in parametros):
    raise ValueError("Parametros invalidos para o modelo horario")
  numero = "".join(c for c in destinatario if c.isdigit())
  if not 10 <= len(numero) <= 15:
    raise ValueError("Destinatario invalido")
  versao = os.getenv("META_GRAPH_API_VERSION", "").strip() or "v26.0"
  resposta = requests.post(
      f"https://graph.facebook.com/{versao}/{phone_id}/messages",
      headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT,
      json={"messaging_product": "whatsapp", "to": numero,
            "biz_opaque_callback_data": "relatorio_horario:" + entrega_id,
            "type": "template", "template": {
                "name": modelo,
                "language": {"code": os.getenv("META_REPORT_TEMPLATE_LANGUAGE") or "pt_BR"},
                "components": [{"type": "body", "parameters": [
                    {"type": "text", "text": p} for p in parametros]}]}})
  dados = _resposta_meta(resposta, "enviar relatorio horario")
  mensagens = dados.get("messages") or []
  if not mensagens or not mensagens[0].get("id"):
    raise RuntimeError("Meta nao retornou identificador da mensagem")
  return mensagens[0]["id"]


def _parametro_template(valor: Any) -> dict[str, str]:
  texto = str(valor).strip() if valor not in (None, "") else "N/A"
  return {"type": "text", "text": texto}


def enviar_meta(navio: dict[str, Any]) -> bool:
  token, phone_number_id, destinatario, template, versao, idioma = (
      _configuracao_meta()
  )
  campos = ("nome", "imo", "local", "eta", "etb", "evento", "fonte")
  payload = {
      "messaging_product": "whatsapp",
      "recipient_type": "individual",
      "to": destinatario,
      "type": "template",
      "template": {
          "name": template,
          "language": {"code": idioma},
          "components": [
              {
                  "type": "body",
                  "parameters": [
                      _parametro_template(navio.get(campo)) for campo in campos
                  ],
              }
          ],
      },
  }
  response = requests.post(
      f"https://graph.facebook.com/{versao}/{phone_number_id}/messages",
      headers={
          "Authorization": f"Bearer {token}",
          "Content-Type": "application/json",
      },
      json=payload,
      timeout=TIMEOUT,
  )
  dados = _resposta_meta(response, "enviar a mensagem")
  mensagens = dados.get("messages") or []
  if not mensagens or not mensagens[0].get("id"):
    raise RuntimeError(f"Meta nao confirmou o envio: {dados}")
  print("Alerta enviado pelo WhatsApp Cloud da Meta.")
  return True


def verificar_whatsapp() -> bool:
  return verificar_meta()


def enviar_alerta_whatsapp(navio: dict[str, Any]) -> bool:
  return enviar_meta(navio)
