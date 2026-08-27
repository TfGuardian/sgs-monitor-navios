import argparse
import os

import requests

import monitor_aps
import monitor_praticagem


def _credenciais_zapi() -> tuple[str, str, str, str]:
  nomes = (
      "ZAPI_INSTANCE_ID",
      "ZAPI_INSTANCE_TOKEN",
      "ZAPI_CLIENT_TOKEN",
      "ZAPI_PHONE",
  )
  valores = tuple(os.getenv(nome, "").strip() for nome in nomes)
  ausentes = [nome for nome, valor in zip(nomes, valores) if not valor]
  if ausentes:
    raise RuntimeError(f"Configuracao Z-API ausente: {', '.join(ausentes)}")
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


def enviar_alerta_whatsapp(mensagem: str) -> bool:
  url, headers, phone = _url_zapi("send-text")
  response = requests.post(
      url,
      headers=headers,
      json={"phone": phone, "message": mensagem},
      timeout=(5, 30),
  )
  response.raise_for_status()
  dados = response.json()
  if not (dados.get("messageId") or dados.get("zaapId") or dados.get("id")):
    raise RuntimeError(f"Z-API nao confirmou o envio: {dados}")
  print("Alerta enviado ao WhatsApp pela Z-API.")
  return True


def formatar_alerta(navio: dict) -> str:
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


def main(dry_run: bool = False) -> None:
  modo = " (SIMULACAO)" if dry_run else ""
  print(f"Iniciando ciclo de monitoramento maritimo{modo}...")
  alterados = monitor_aps.processar_navios(dry_run=dry_run)
  alterados.extend(monitor_praticagem.processar_praticagem(dry_run=dry_run))
  if not dry_run:
    for navio in alterados:
      enviar_alerta_whatsapp(formatar_alerta(navio))
  print(f"Ciclo concluido: {len(alterados)} alteracao(oes).")


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Monitoramento maritimo")
  parser.add_argument(
      "--dry-run",
      action="store_true",
      help="Executa sem alterar o Supabase nem enviar WhatsApp",
  )
  parser.add_argument(
      "--check-zapi",
      action="store_true",
      help="Verifica credenciais e conexao da instancia sem enviar mensagem",
  )
  parser.add_argument(
      "--test-whatsapp",
      action="store_true",
      help="Envia uma mensagem real de teste pela Z-API",
  )
  argumentos = parser.parse_args()
  if argumentos.check_zapi:
    verificar_zapi()
  elif argumentos.test_whatsapp:
    if not verificar_zapi():
      raise RuntimeError("Conecte a instancia Z-API ao WhatsApp antes do teste")
    enviar_alerta_whatsapp("✅ Teste do SGS Monitor Navios realizado com sucesso.")
  else:
    main(dry_run=argumentos.dry_run)
