import monitor_aps
import monitor_praticagem

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

  print("\n🏁 Ciclo concluído!")

  import os
  import urllib.parse
  import requests


  def enviar_alerta_whatsapp(mensagem: str):
    phone = os.getenv("WHATSAPP_PHONE")
    api_key = os.getenv("WHATSAPP_API_KEY")

    if not phone or not api_key:
      print("⚠️ Credenciais do WhatsApp não configuradas no ambiente.")
      return

    # Formata o texto para ser aceito em URL
    texto_encoded = urllib.parse.quote(mensagem)
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={texto_encoded}&apikey={api_key}"

    try:
      response = requests.get(url, timeout=15)
      if response.status_code == 200:
        print("✅ Alerta enviado com sucesso para o WhatsApp!")
      else:
        print(f"⚠️ Erro ao enviar WhatsApp: Status {response.status_code}")
    except Exception as e:
      print(f"❌ Erro ao conectar com o serviço do WhatsApp: {e}")