from consulta_navio import normalizar
from lista_monitoramento import carregar_lista


def registros_fora_da_lista(cliente) -> list[dict]:
  lista = carregar_lista(cliente)
  nomes = {normalizar(item.get("nome_confirmado")) for item in lista}
  imos = {normalizar(item.get("imo")) for item in lista if item.get("imo")}
  resposta = cliente.table("navios_monitorados").select("*").execute()
  return [
      navio for navio in (resposta.data or [])
      if navio.get("lista_monitoramento_id") is None
      and normalizar(navio.get("nome")) not in nomes
      and (not navio.get("imo") or normalizar(navio.get("imo")) not in imos)
  ]


def simular_limpeza(cliente) -> list[dict]:
  fora = registros_fora_da_lista(cliente)
  print(f"[SIMULACAO] {len(fora)} registro(s) seriam removidos.")
  for navio in fora[:20]:
    print(f"- {navio.get('nome')} (IMO: {navio.get('imo') or 'N/A'})")
  if len(fora) > 20:
    print(f"... e mais {len(fora) - 20} registro(s).")
  return fora


def executar_limpeza(cliente, confirmacao: str) -> int:
  if confirmacao.strip().upper() != "REMOVER":
    raise ValueError('Limpeza cancelada. Digite exatamente "REMOVER" para confirmar.')
  fora = registros_fora_da_lista(cliente)
  ids = [navio["id"] for navio in fora if navio.get("id") is not None]
  if ids:
    cliente.table("navios_monitorados").delete().in_("id", ids).execute()
  return len(ids)
