import argparse


def executar() -> None:
  parser = argparse.ArgumentParser(description="Monitoramento de navios")
  grupo = parser.add_mutually_exclusive_group()
  grupo.add_argument(
      "--sincronizar", action="store_true",
      help="Coleta o Porto de Santos e sincroniza o Supabase",
  )
  grupo.add_argument(
      "--consultar", metavar="NAVIO_OU_IMO",
      help='Consulta um ou mais navios; separe varios nomes com ";"',
  )
  grupo.add_argument(
      "--console", action="store_true",
      help="Abre o modo de consultas continuas",
  )
  grupo.add_argument(
      "--status", action="store_true",
      help="Mostra a saude da ultima coleta",
  )
  grupo.add_argument(
      "--cadastrar-admin", metavar="TELEFONE",
      help="Cadastra o primeiro administrador do chat",
  )
  grupo.add_argument(
      "--simular-chat", metavar="TELEFONE",
      help="Abre o chat local simulando o numero informado",
  )
  grupo.add_argument(
      "--simular-limpeza", action="store_true",
      help="Mostra registros fora da lista sem remove-los",
  )
  grupo.add_argument(
      "--executar-limpeza", action="store_true",
      help="Remove dados fora da lista apos confirmacao interativa",
  )
  grupo.add_argument(
      "--check-whatsapp", action="store_true",
      help="Verifica a integracao Meta sem enviar mensagem",
  )
  grupo.add_argument(
      "--test-whatsapp", action="store_true",
      help="Envia uma mensagem de teste pela Meta",
  )
  parser.add_argument(
      "--dry-run", action="store_true",
      help="Simula a sincronizacao sem modificar o Supabase",
  )
  argumentos = parser.parse_args()

  if argumentos.consultar:
    from console import consultar_entrada
    consultar_entrada(argumentos.consultar)
  elif argumentos.console:
    from console import executar_console
    executar_console()
  elif argumentos.status:
    from sincronizador import exibir_status
    exibir_status()
  elif argumentos.cadastrar_admin:
    from config import criar_supabase
    from lista_monitoramento import cadastrar_administrador
    numero = cadastrar_administrador(
        criar_supabase(administrativo=True), argumentos.cadastrar_admin
    )
    print(f"Administrador cadastrado: {numero}")
  elif argumentos.simular_chat:
    from simulador_chat import executar_simulador
    executar_simulador(argumentos.simular_chat)
  elif argumentos.simular_limpeza:
    from config import criar_supabase
    from limpeza import simular_limpeza
    simular_limpeza(criar_supabase(administrativo=True))
  elif argumentos.executar_limpeza:
    from config import criar_supabase
    from limpeza import executar_limpeza, simular_limpeza
    cliente = criar_supabase(administrativo=True)
    simular_limpeza(cliente)
    confirmacao = input('\nDigite "REMOVER" para confirmar a limpeza: ')
    removidos = executar_limpeza(cliente, confirmacao)
    print(f"Limpeza concluida: {removidos} registro(s) removido(s).")
  elif argumentos.check_whatsapp:
    from whatsapp import verificar_whatsapp
    verificar_whatsapp()
  elif argumentos.test_whatsapp:
    from whatsapp import enviar_alerta_whatsapp, verificar_whatsapp
    verificar_whatsapp()
    enviar_alerta_whatsapp({
        "nome": "NAVIO TESTE", "imo": "0000000", "local": "PORTO DE SANTOS",
        "eta": "TESTE", "etb": "TESTE", "evento": "VALIDACAO DO SISTEMA",
        "fonte": "SGS MONITOR NAVIOS",
    })
  else:
    from sincronizador import sincronizar
    sincronizar(dry_run=argumentos.dry_run)


if __name__ == "__main__":
  executar()
