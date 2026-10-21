"""Relação oficial de fundeados; chegada não é previsão nem data de atualização."""
import io
import re
import pandas as pd
from config import FUNDEADOS_URL
from monitor_aps import HEADERS, TIMEOUT, _sessao_http, _valor, _verificacao_https_aps, buscar_coluna
from monitor_atracados import _ajustar_colunas


def extrair_navios_fundeados(tabelas):
  registros, reconhecida = [], False
  for original in tabelas:
    tabela = _ajustar_colunas(original)
    nome = buscar_coluna(tabela, ["navio", "ship"])
    chegada = buscar_coluna(tabela, ["cheg", "arrival"])
    terminal = buscar_coluna(tabela, ["terminal"])
    if nome is None or chegada is None or terminal is None:
      continue
    reconhecida = True
    campos = {c: buscar_coluna(tabela, [c]) for c in ("imo", "viagem", "duv")}
    for _, row in tabela.iterrows():
      n = _valor(row, nome)
      if not n:
        continue
      # PROGRAMADO é uma anotação da página, não parte do nome do navio.
      n = re.sub(r"\s+PROGRAMADO$", "", n, flags=re.I).strip()
      registros.append(dict(nome=n, evento="FUNDEADO", fonte="APS_FUNDEADOS",
        **{c: _valor(row, col) for c, col in campos.items()}))
  return registros, reconhecida


def coletar_navios_fundeados():
  resposta = _sessao_http().get(FUNDEADOS_URL, headers=HEADERS, timeout=TIMEOUT,
                                verify=_verificacao_https_aps())
  resposta.raise_for_status()
  try:
    tabelas = pd.read_html(io.StringIO(resposta.text))
  except ValueError as exc:
    raise RuntimeError("Fundeados: página sem tabela reconhecida") from exc
  registros, reconhecida = extrair_navios_fundeados(tabelas)
  if not reconhecida:
    raise RuntimeError("Fundeados: formato não reconhecido")
  return registros
