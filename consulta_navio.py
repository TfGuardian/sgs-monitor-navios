import difflib
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from zoneinfo import ZoneInfo

Registro = dict[str, Any]
FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")


def normalizar(valor: Any) -> str:
  texto = unicodedata.normalize("NFKD", str(valor or ""))
  texto = "".join(c for c in texto if not unicodedata.combining(c))
  return re.sub(r"\s+", " ", texto).strip().upper()


def carregar_navios() -> list[Registro]:
  from config import criar_supabase
  from lista_monitoramento import montar_visao_monitorados
  # O console roda em ambiente controlado e usa a chave secreta para ler dados
  # protegidos por RLS. Essa chave nunca deve ser exposta em navegador ou chat.
  return montar_visao_monitorados(criar_supabase(administrativo=True))


def localizar_navios(termo: str, registros: list[Registro]) -> list[Registro]:
  """Busca pelo nome primeiro e tambem aceita o IMO."""
  procurado = normalizar(termo)
  if not procurado:
    return []

  nomes_exatos = [
      navio for navio in registros
      if normalizar(navio.get("nome")) == procurado
  ]
  if nomes_exatos:
    return nomes_exatos

  imos_exatos = [
      navio for navio in registros
      if normalizar(navio.get("imo")) == procurado
  ]
  if imos_exatos:
    return imos_exatos

  return [
      navio for navio in registros
      if procurado in normalizar(navio.get("nome"))
  ]


def sugerir_navios(
    termo: str,
    registros: list[Registro],
    limite: int = 5,
) -> list[str]:
  nomes_por_normalizado = {
      normalizar(navio.get("nome")): str(navio.get("nome", "")).strip()
      for navio in registros if navio.get("nome")
  }
  proximos = difflib.get_close_matches(
      normalizar(termo), nomes_por_normalizado.keys(), n=limite, cutoff=0.45
  )
  return [nomes_por_normalizado[nome] for nome in proximos]


def separar_termos(entrada: str) -> list[str]:
  return [termo.strip() for termo in re.split(r"[;\n]+", entrada) if termo.strip()]


def _data(valor: Any) -> datetime | None:
  if not valor:
    return None
  texto = str(valor).strip().replace("Z", "+00:00")
  try:
    data = datetime.fromisoformat(texto)
  except ValueError:
    return None
  if data.tzinfo is None:
    data = data.replace(tzinfo=timezone.utc)
  return data


def formatar_data(valor: Any) -> str:
  data = _data(valor)
  if data is None:
    return "N/A"
  return data.astimezone(FUSO_BRASILIA).strftime("%d/%m/%Y %H:%M")


def formatar_data_operacional(valor: Any) -> str:
  if valor in (None, ""):
    return "N/A"
  texto = str(valor).strip()
  for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%y %H:%M:%S",
                  "%d/%m/%Y %H:%M", "%d/%m/%y %H:%M",
                  "%Y-%m-%d %H:%M:%S"):
    try:
      return datetime.strptime(texto, formato).strftime("%d/%m/%Y %H:%M")
    except ValueError:
      continue
  return texto


def situacao_atual(navio: Registro, agora: datetime | None = None) -> str:
  situacao = normalizar(navio.get("situacao") or "INDISPONIVEL")
  ultima_consulta = _data(navio.get("ultima_consulta"))
  referencia = agora or datetime.now(timezone.utc)
  if referencia.tzinfo is None:
    referencia = referencia.replace(tzinfo=timezone.utc)
  if ultima_consulta and referencia - ultima_consulta > timedelta(hours=2):
    return "DESATUALIZADO"
  return situacao


def _exibir(valor: Any) -> str:
  return str(valor).strip() if valor not in (None, "") else "N/A"


def formatar_navio(navio: Registro, agora: datetime | None = None) -> str:
  return "\n".join((
      f"Nome: {_exibir(navio.get('nome'))}",
      f"IMO: {_exibir(navio.get('imo'))}",
      f"ETA: {formatar_data_operacional(navio.get('eta'))}",
      f"ETB: {formatar_data_operacional(navio.get('etb'))}",
      f"Local: {_exibir(navio.get('local'))}",
      f"Evento: {_exibir(navio.get('evento'))}",
      f"Fonte: {_exibir(navio.get('fonte'))}",
      f"Ultima consulta: {formatar_data(navio.get('ultima_consulta'))}",
      f"Ultima alteracao: {formatar_data(navio.get('ultima_alteracao'))}",
      f"Situacao: {situacao_atual(navio, agora)}",
  ))
