import io
from typing import Any

import pandas as pd

from config import ATRACACOES_PROGRAMADAS_URL
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


def _etb_programado(data: Any, hora: Any) -> str | None:
  partes = [str(valor).strip() for valor in (data, hora)
            if valor is not None and not pd.isna(valor) and str(valor).strip()]
  return " ".join(partes) or None


def extrair_atracacoes_programadas(
    tabelas: list[pd.DataFrame],
) -> tuple[list[Registro], bool]:
  registros: list[Registro] = []
  encontrou_tabela = False
  for original in tabelas:
    tabela = _ajustar_colunas(original)
    col_navio = buscar_coluna(tabela, ["navio", "ship", "vessel", "buque"])
    col_eta = buscar_coluna(tabela, ["eta"])
    if col_navio is None or col_eta is None:
      continue
    encontrou_tabela = True
    col_data = buscar_coluna(tabela, ["data", "date", "fecha"])
    col_hora = buscar_coluna(tabela, ["hora", "hour"])
    colunas = {
        "imo": buscar_coluna(tabela, ["imo"]),
        "eta": col_eta,
        "local": buscar_coluna(tabela, ["local", "place", "lugar", "berco"]),
        "evento": buscar_coluna(tabela, ["evento", "event", "status"]),
        "carga": buscar_coluna(tabela, ["carga", "cargo"]),
        "viagem": buscar_coluna(tabela, ["viagem", "voyage"]),
        "duv": buscar_coluna(tabela, ["duv"]),
    }
    for _, row in tabela.iterrows():
      nome = _valor(row, col_navio)
      if not nome:
        continue
      dados: Registro = {
          "nome": nome,
          "etb": _etb_programado(
              row.get(col_data) if col_data is not None else None,
              row.get(col_hora) if col_hora is not None else None,
          ),
          "fonte": "APS_ATRACACOES_PROGRAMADAS",
      }
      dados.update({campo: _valor(row, coluna)
                    for campo, coluna in colunas.items()})
      registros.append(dados)
  return registros, encontrou_tabela


def coletar_atracacoes_programadas() -> list[Registro]:
  response = _sessao_http().get(
      ATRACACOES_PROGRAMADAS_URL,
      headers=HEADERS,
      timeout=TIMEOUT,
      verify=_verificacao_https_aps(),
  )
  response.raise_for_status()
  try:
    tabelas = pd.read_html(io.StringIO(response.text))
  except ValueError as exc:
    raise RuntimeError(
        "Atracacoes Programadas nao retornou tabelas HTML"
    ) from exc
  registros, encontrou_tabela = extrair_atracacoes_programadas(tabelas)
  if not encontrou_tabela:
    raise RuntimeError(
        "Atracacoes Programadas nao retornou uma tabela reconhecida"
    )
  return registros


if __name__ == "__main__":
  print(f"{len(coletar_atracacoes_programadas())} atracacoes programadas encontradas.")
