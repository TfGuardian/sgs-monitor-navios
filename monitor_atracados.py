import io
from typing import Any

import pandas as pd

from config import ATRACADOS_URL
from monitor_aps import (
    HEADERS,
    TIMEOUT,
    _sessao_http,
    _valor,
    _verificacao_https_aps,
    buscar_coluna,
)

Registro = dict[str, Any]


def _ajustar_colunas(tabela: pd.DataFrame) -> pd.DataFrame:
  tabela = tabela.copy()
  if isinstance(tabela.columns, pd.MultiIndex):
    tabela.columns = [
        " ".join(str(c) for c in coluna if "Unnamed" not in str(c)).strip()
        for coluna in tabela.columns
    ]
  else:
    tabela.columns = [str(c).strip() for c in tabela.columns]
  return tabela


def extrair_navios_atracados(
    tabelas: list[pd.DataFrame],
) -> tuple[list[Registro], bool]:
  registros: list[Registro] = []
  encontrou_tabela = False
  for original in tabelas:
    tabela = _ajustar_colunas(original)
    col_navio = buscar_coluna(tabela, ["navio", "ship", "vessel", "buque"])
    col_local = buscar_coluna(tabela, ["local", "berco", "terminal"])
    if col_navio is None or col_local is None:
      continue
    encontrou_tabela = True
    col_carga = buscar_coluna(tabela, ["carga", "cargo"])
    for _, row in tabela.iterrows():
      nome = _valor(row, col_navio)
      if not nome:
        continue
      registros.append({
          "nome": nome,
          "local": _valor(row, col_local),
          "carga": _valor(row, col_carga),
          "evento": "ATRACADO",
          "fonte": "APS_ATRACADOS",
      })
  return registros, encontrou_tabela


def coletar_navios_atracados() -> list[Registro]:
  response = _sessao_http().get(
      ATRACADOS_URL,
      headers=HEADERS,
      timeout=TIMEOUT,
      verify=_verificacao_https_aps(),
  )
  response.raise_for_status()
  try:
    tabelas = pd.read_html(io.StringIO(response.text))
  except ValueError as exc:
    raise RuntimeError("A pagina de Atracados nao retornou tabelas HTML") from exc
  registros, encontrou_tabela = extrair_navios_atracados(tabelas)
  if not encontrou_tabela:
    raise RuntimeError("A pagina de Atracados nao retornou uma tabela reconhecida")
  return registros


if __name__ == "__main__":
  print(f"{len(coletar_navios_atracados())} navios atracados encontrados.")
