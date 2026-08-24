from datetime import datetime
import os
import urllib.parse
from dotenv import load_dotenv
import requests

# Módulos do projeto
import monitor_aps
import monitor_praticagem

# Carrega as variáveis do arquivo .env
load_dotenv()


def enviar_alerta_whatsapp(mensagem: str):
  phone = os.getenv("WHATSAPP_PHONE")
  api_key = os.getenv("WHATSAPP_API_KEY")

  if not phone or not api_key:
    print("⚠️ Credenciais do WhatsApp não configuradas no arquivo .env.")
    return

  # Formata o texto para ser aceito na URL
  texto_encoded = urllib.parse.quote(mensagem)
  url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={texto_encoded}&apikey={api_key}"

  try:
    response = requests.get(url, timeout=15)
    # Considera 200 (Sucesso) e 208 (Enfileirado/Processado) como envio correto
    if response.status_code in [200, 208]:
      print("✅ Alerta enviado/processado com sucesso no WhatsApp!")
    else:
      print(f"⚠️ Erro ao enviar WhatsApp: Status {response.status_code}")
  except Exception as e:
    print(f"❌ Erro ao conectar com o serviço do WhatsApp: {e}")


if __name__ == "__main__":
  print("🚀 Iniciando ciclo de monitoramento marítimo...\n")

  # 1. Executa atualização via APS
  try:
    res = monitor_aps.supabase.table("navios_monitorados").select("nome").execute()
    for item in res.data:
      monitor_aps.processar_e_salvar_navio(item["nome"])
  except Exception as e:
    print(f"Erro APS: {e}")

  # 2. Executa atualização via Santos Pilots
  try:
    monitor_praticagem.processar_praticagem()
  except Exception as e:
    print(f"Erro Praticagem: {e}")

  if __name__ == "__main__":
    print("🚀 Iniciando ciclo de monitoramento marítimo...\n")

    # 1. Executa atualização via APS e captura os dados retornados
    try:
      res = monitor_aps.supabase.table("navios_monitorados").select("nome").execute()
      for item in res.data:
        # Captura os dados processados do navio
        retorno = monitor_aps.processar_e_salvar_navio(item["nome"])

        # Se retornou dados do banco, formata e envia a notificação detalhada
        if retorno and len(retorno) > 0:
          navio = retorno[0]
          msg_navio = (
            f"🚢 *MONITORAMENTO MARÍTIMO*\n\n"
            f"📌 *Navio:* {navio.get('nome')}\n"
            f"🔢 *IMO:* {navio.get('imo')}\n"
            f"📍 *Local:* {navio.get('local')}\n"
            f"📅 *ETA:* {navio.get('eta')}\n"
            f"🏷️ *Evento:* {navio.get('evento')}\n"
            f"🏢 *Fonte:* {navio.get('fonte')}"
          )
          enviar_alerta_whatsapp(msg_navio)
    except Exception as e:
      print(f"Erro APS: {e}")

    # 2. Executa atualização via Santos Pilots
    try:
      monitor_praticagem.processar_praticagem()
    except Exception as e:
      print(f"Erro Praticagem: {e}")

    print("\n🏁 Ciclo concluído!")