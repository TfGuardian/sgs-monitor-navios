from consulta_navio import (
    Registro,
    carregar_navios,
    formatar_navio,
    localizar_navios,
    separar_termos,
    sugerir_navios,
)


def _escolher(encontrados: list[Registro]) -> Registro | None:
  print("Foram encontrados varios navios:\n")
  for indice, navio in enumerate(encontrados, start=1):
    imo = navio.get("imo") or "N/A"
    print(f"{indice}. {navio.get('nome', 'N/A')} (IMO: {imo})")
  escolha = input("\nEscolha o numero desejado ou Enter para cancelar: ").strip()
  if not escolha.isdigit() or not 1 <= int(escolha) <= len(encontrados):
    print("Consulta cancelada.")
    return None
  return encontrados[int(escolha) - 1]


def consultar_entrada(entrada: str, registros: list[Registro] | None = None) -> bool:
  termos = separar_termos(entrada)
  if not termos:
    print("Informe pelo menos um nome ou IMO.")
    return False
  navios = registros if registros is not None else carregar_navios()
  encontrou_algum = False

  for posicao, termo in enumerate(termos):
    if posicao:
      print("\n" + "-" * 50 + "\n")
    encontrados = localizar_navios(termo, navios)
    if not encontrados:
      print(f'Navio "{termo}" nao encontrado.')
      sugestoes = sugerir_navios(termo, navios)
      if sugestoes:
        print("\nVoce quis dizer:")
        for indice, nome in enumerate(sugestoes, start=1):
          print(f"{indice}. {nome}")
      continue

    escolhido = encontrados[0] if len(encontrados) == 1 else _escolher(encontrados)
    if escolhido:
      print(formatar_navio(escolhido))
      encontrou_algum = True
  return encontrou_algum


def executar_console() -> None:
  print("Consulta de navios - Porto de Santos")
  print('Digite um ou mais nomes separados por ";". Digite "sair" para encerrar.')
  while True:
    entrada = input("\nNavio(s): ").strip()
    if entrada.lower() == "sair":
      print("Consulta encerrada.")
      return
    try:
      consultar_entrada(entrada)
    except Exception as exc:
      print(f"Nao foi possivel consultar o banco: {exc}")
