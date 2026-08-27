import argparse

import monitor_aps
import monitor_praticagem
from whatsapp import enviar_alerta_whatsapp, verificar_whatsapp, verificar_zapi


def main(dry_run: bool = False) -> None:
  modo = " (SIMULACAO)" if dry_run else ""
  print(f"Iniciando ciclo de monitoramento maritimo{modo}...")
  alterados = monitor_aps.processar_navios(dry_run=dry_run)
  alterados.extend(monitor_praticagem.processar_praticagem(dry_run=dry_run))
  if not dry_run:
    for navio in alterados:
      enviar_alerta_whatsapp(navio)
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
      help="Verifica diretamente a instancia Z-API (compatibilidade)",
  )
  parser.add_argument(
      "--check-whatsapp",
      action="store_true",
      help="Verifica o provedor WhatsApp configurado sem enviar mensagem",
  )
  parser.add_argument(
      "--test-whatsapp",
      action="store_true",
      help="Envia uma mensagem real pelo provedor configurado",
  )
  argumentos = parser.parse_args()
  if argumentos.check_zapi:
    verificar_zapi()
  elif argumentos.check_whatsapp:
    verificar_whatsapp()
  elif argumentos.test_whatsapp:
    verificar_whatsapp()
    enviar_alerta_whatsapp({
        "nome": "NAVIO TESTE",
        "imo": "0000000",
        "local": "PORTO DE SANTOS",
        "eta": "TESTE",
        "etb": "TESTE",
        "evento": "VALIDACAO DO SISTEMA",
        "fonte": "SGS MONITOR NAVIOS",
    })
  else:
    main(dry_run=argumentos.dry_run)
