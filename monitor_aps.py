import io
import os
import re
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import certifi
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import APS_URL, criar_supabase

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SGS-Monitor-Navios/1.0)"}
TIMEOUT = (5, 30)
supabase = criar_supabase()
Registro = dict[str, Any]
_BUNDLE_APS: str | bool | None = None


def _verificacao_https_aps() -> str | bool:
  """Completa a cadeia Sectigo omitida pelo servidor da APS no Linux."""
  global _BUNDLE_APS
  if _BUNDLE_APS is not None:
    return _BUNDLE_APS
  if os.name == "nt":
    _BUNDLE_APS = True
    return _BUNDLE_APS

  intermediario = (
      Path(__file__).resolve().parent
      / "certs"
      / "SectigoPublicServerAuthenticationCAOVR36.pem"
  )
  bundle = Path(tempfile.gettempdir()) / "sgs-monitor-aps-ca-bundle.pem"
  bundle.write_bytes(
      Path(certifi.where()).read_bytes()
      + b"\n"
      + intermediario.read_bytes()
  )
  _BUNDLE_APS = str(bundle)
  return _BUNDLE_APS


def _sessao_http() -> requests.Session:
  sessao = requests.Session()
  retry = Retry(total=3, backoff_factor=1,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET",))
  sessao.mount("https://", HTTPAdapter(max_retries=retry))
  return sessao


def normalizar_texto(valor) -> str:
  texto = unicodedata.normalize("NFKD", str(valor))
  texto = "".join(c for c in texto if not unicodedata.combining(c))
  return re.sub(r"\s+", " ", texto).strip().upper()


def buscar_coluna(df, palavras_chave):
  for col in df.columns:
    col_normalizada = normalizar_texto(col)
    if any(normalizar_texto(p) in col_normalizada for p in palavras_chave):
      return col
  return None


def _valor(row, coluna):
  if coluna is None or pd.isna(row.get(coluna)):
    return None
  valor = str(row.get(coluna)).strip()
  return valor or None


def coletar_aps() -> list[Registro]:
  response = _sessao_http().get(
      APS_URL,
      headers=HEADERS,
      timeout=TIMEOUT,
      verify=_verificacao_https_aps(),
  )
  response.raise_for_status()
  tabelas = pd.read_html(io.StringIO(response.text))
  registros: list[Registro] = []
  for tabela in tabelas:
    if isinstance(tabela.columns, pd.MultiIndex):
      tabela.columns = [
          " ".join(str(c) for c in col if "Unnamed" not in str(c)).strip()
          for col in tabela.columns
      ]
    else:
      tabela.columns = [str(c).strip() for c in tabela.columns]
    col_navio = buscar_coluna(tabela, ["navio", "ship", "vessel", "buque"])
    if col_navio is None:
      continue
    colunas = {
        "imo": buscar_coluna(tabela, ["imo"]),
        "eta": buscar_coluna(tabela, ["eta"]),
        "etb": buscar_coluna(tabela, ["atracacao"]),
        "local": buscar_coluna(tabela, ["local", "berco", "terminal"]),
        "carga": buscar_coluna(tabela, ["carga", "cargo"]),
        "evento": buscar_coluna(tabela, ["evento", "event", "status"]),
        "viagem": buscar_coluna(tabela, ["viagem", "voyage"]),
        "duv": buscar_coluna(tabela, ["duv"]),
    }
    for _, row in tabela.iterrows():
      nome = _valor(row, col_navio)
      if not nome:
        continue
      dados: Registro = {"nome": nome, "fonte": "APS"}
      dados.update({campo: _valor(row, col) for campo, col in colunas.items()})
      registros.append(dados)
  if not registros:
    raise RuntimeError("A APS nao retornou nenhuma tabela reconhecida de navios")
  return registros


def _encontrar(registros: list[Registro], nome: str) -> Registro | None:
  procurado = normalizar_texto(nome)
  encontrados = [
      r for r in registros if normalizar_texto(r["nome"]) == procurado
  ]
  return max(encontrados, key=lambda r: _data_operacao(
      r.get("etb") or r.get("eta"))) \
      if encontrados else None


def _data_operacao(valor) -> datetime:
  if not valor:
    return datetime.min
  texto = str(valor).strip()
  formatos = (
      "%d/%m/%Y %H:%M:%S",
      "%d/%m/%y %H:%M:%S",
      "%Y-%m-%d %H:%M:%S",
  )
  for formato in formatos:
    try:
      return datetime.strptime(texto, formato)
    except ValueError:
      continue
  return datetime.min


def _mudou(anterior: Registro, novo: Registro) -> bool:
  return any((anterior.get(c) or None) != (novo.get(c) or None)
             for c in ("eta", "etb", "local", "evento", "fonte"))


def processar_navios(dry_run: bool = False) -> list[Registro]:
  registros_aps = coletar_aps()
  resposta = supabase.table("navios_monitorados").select("*").execute()
  monitorados = cast(list[Registro], resposta.data or [])
  alterados: list[Registro] = []
  for anterior in monitorados:
    # A Praticagem tem maior precedencia operacional e nao deve ser apagada
    # pela coleta APS seguinte.
    if anterior.get("fonte") == "SANTOS_PILOTS":
      continue
    encontrado = _encontrar(registros_aps, anterior.get("nome", ""))
    if not encontrado:
      continue
    data_nova = _data_operacao(encontrado.get("etb") or encontrado.get("eta"))
    data_anterior = _data_operacao(anterior.get("etb") or anterior.get("eta"))
    if data_nova < data_anterior:
      print(f"APS ignorada para {anterior['nome']}: operacao do painel e antiga")
      continue
    dados = {k: v for k, v in encontrado.items() if v is not None}
    if not _mudou(anterior, dados):
      continue
    if dry_run:
      alterados.append({**anterior, **dados})
      print(f"[SIMULACAO] APS alteraria {dados['nome']}")
      continue
    imo = anterior.get("imo")
    consulta = supabase.table("navios_monitorados").update(dados)
    consulta = (consulta.eq("imo", imo) if imo and imo != "N/A"
                else consulta.eq("nome", anterior["nome"]))
    resultado = consulta.execute()
    atualizados = cast(list[Registro], resultado.data or [])
    alterados.extend(atualizados or [{**anterior, **dados}])
    print(f"APS atualizada para {dados['nome']}")
  return alterados


def processar_e_salvar_navio(nome_navio):
  """Compatibilidade com integracoes antigas."""
  encontrado = _encontrar(coletar_aps(), nome_navio)
  return [encontrado] if encontrado else []


if __name__ == "__main__":
  processar_navios()
