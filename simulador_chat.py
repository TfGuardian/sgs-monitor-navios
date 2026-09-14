from chat import processar_chat


def executar_simulador(telefone: str) -> None:
  from config import criar_supabase
  from lista_monitoramento import normalizar_telefone, telefone_valido

  numero = normalizar_telefone(telefone)
  if not telefone_valido(numero):
    raise ValueError("Informe o telefone com DDI e DDD, somente numeros.")
  cliente = criar_supabase(administrativo=True)
  print("Simulador do chat - Monitor de Navios")
  print('Digite "ajuda" para ver os comandos ou "sair" para encerrar.')
  while True:
    mensagem = input("\nVoce: ").strip()
    if mensagem.lower() == "sair":
      print("Simulacao encerrada.")
      return
    try:
      print("\nBot:\n" + processar_chat(cliente, numero, mensagem))
    except Exception as exc:
      print(f"\nBot:\nNao foi possivel processar a mensagem: {exc}")
