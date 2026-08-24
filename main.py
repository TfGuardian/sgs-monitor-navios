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