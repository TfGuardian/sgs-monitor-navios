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


def provedor_whatsapp() -> str:
  provedor = os.getenv("WHATSAPP_PROVIDER", "").strip().lower() or "zapi"
  if provedor not in {"meta", "zapi"}:
    raise RuntimeError("WHATSAPP_PROVIDER deve ser 'meta' ou 'zapi'")
  return provedor


def _credenciais_zapi() -> tuple[str, str, str, str]:
  valores = _obrigatorias(
      (
          "ZAPI_INSTANCE_ID",
          "ZAPI_INSTANCE_TOKEN",
          "ZAPI_CLIENT_TOKEN",
          "ZAPI_PHONE",
      ),
      "Z-API",
  )
  return valores[0], valores[1], valores[2], valores[3]


def _url_zapi(recurso: str) -> tuple[str, dict[str, str], str]:
  instance_id, instance_token, client_token, phone = _credenciais_zapi()
  base = f"https://api.z-api.io/instances/{instance_id}/token/{instance_token}"
  headers = {"Client-Token": client_token, "Content-Type": "application/json"}
  return f"{base}/{recurso}", headers, phone


def verificar_zapi() -> bool:
  url, headers, _ = _url_zapi("me")
  response = requests.get(url, headers=headers, timeout=(5, 20))
  response.raise_for_status()
  dados = response.json()
  conectado = bool(dados.get("connected"))
  print(f"Z-API acessivel. Instancia conectada: {'sim' if conectado else 'nao'}")
  return conectado


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
  versao = os.getenv("META_GRAPH_API_VERSION", "").strip() or "v24.0"
  idioma = os.getenv("META_TEMPLATE_LANGUAGE", "").strip() or "pt_BR"
  if not versao.startswith("v"):
    raise RuntimeError("META_GRAPH_API_VERSION deve seguir o formato v24.0")
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


def formatar_alerta(navio: dict[str, Any]) -> str:
  return (
      "🚢 *MONITORAMENTO MARÍTIMO*\n\n"
      f"📌 *Navio:* {navio.get('nome', 'N/A')}\n"
      f"🔢 *IMO:* {navio.get('imo', 'N/A')}\n"
      f"📍 *Local:* {navio.get('local', 'N/A')}\n"
      f"📅 *ETA:* {navio.get('eta', 'N/A')}\n"
      f"⚓ *ETB:* {navio.get('etb', 'N/A')}\n"
      f"🏷️ *Evento:* {navio.get('evento', 'N/A')}\n"
      f"🏢 *Fonte:* {navio.get('fonte', 'N/A')}"
  )


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


def enviar_zapi(navio: dict[str, Any]) -> bool:
  url, headers, phone = _url_zapi("send-text")
  response = requests.post(
      url,
      headers=headers,
      json={"phone": phone, "message": formatar_alerta(navio)},
      timeout=TIMEOUT,
  )
  response.raise_for_status()
  dados = response.json()
  if not (dados.get("messageId") or dados.get("zaapId") or dados.get("id")):
    raise RuntimeError(f"Z-API nao confirmou o envio: {dados}")
  print("Alerta enviado ao WhatsApp pela Z-API.")
  return True


def verificar_whatsapp() -> bool:
  return verificar_meta() if provedor_whatsapp() == "meta" else verificar_zapi()


def enviar_alerta_whatsapp(navio: dict[str, Any]) -> bool:
  return enviar_meta(navio) if provedor_whatsapp() == "meta" else enviar_zapi(navio)
