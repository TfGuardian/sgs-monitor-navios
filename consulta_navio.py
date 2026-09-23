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


def etapa_evento(valor):
  evento = re.sub(r"[^A-Z0-9 ]", " ", normalizar(valor))
  evento = re.sub(r"\s+", " ", evento).strip()
  if evento in ("SAIDA CONFIRMADA", "SAIU"):
    return 7, "🚢", "Saída confirmada"
  if evento == "DESATRACADO":
    return 6, "🚢", "Desatracado"
  if evento in ("DESATRACANDO", "EM DESATRACACAO"):
    return 6, "🚢", "Desatracando"
  if evento in ("AG DESATRACACAO", "AGUARDANDO DESATRACACAO", "AGUARD DESATRACACAO", "AGUAR DESATRACACAO"):
    return 5, "🟢", "Aguardando desatracação"
  if evento in ("OPERANDO", "OPERANDO BOMBEANDO", "EM OPERACAO"):
    return 4, "🟢", "Operando"
  if evento == "ATRACADO":
    return 3, "🟢", "Atracado"
  if evento in ("ATRACANDO", "EM ATRACACAO"):
    return 2, "🚢", "Atracando"
  if evento == "FUNDEADO":
    return 1, "⚓", "Fundeado"
  if evento in ("ATRACACAO", "ATRACACAO PROGRAMADA", "PROGRAMADO", "AGUARDANDO ATRACACAO"):
    return 0, "🟡", "Atracação programada"
  return 0, "⚪", str(valor or "Situação não informada")


def estado_operacional(navio: Registro) -> tuple[str, str]:
  if normalizar(navio.get("evento")) == "SITUACAO_EM_VERIFICACAO":
    return "⚠️", "Situação em verificação"
  rank, emoji, estado = etapa_evento(navio.get("evento"))
  fontes = str(navio.get("fonte") or "").split(" + ")
  if rank < 3 and "APS_ATRACADOS" in fontes:
    return "🟢", "Atracado"
  if not navio.get("evento") and "APS_ATRACACOES_PROGRAMADAS" in fontes:
    return "🟡", "Atracação programada"
  return emoji, estado


def _formatar(navio: Registro, agora: datetime | None, completo: bool) -> str:
  blocos = (["🔎 *Detalhes do navio*"] if completo else [])
  identidade = f"🚢 *{_exibir(navio.get('nome'))}*"
  if completo and navio.get("imo"):
    identidade += f"\n*IMO:* {navio['imo']}"
  blocos.append(identidade)
  indisponivel = normalizar(navio.get("situacao") or "indisponivel") == "INDISPONIVEL"
  antigo = situacao_atual(navio, agora) == "DESATUALIZADO"
  if indisponivel:
    blocos.extend(["⚪ *Dados indisponíveis*", "Não localizado nas fontes consultadas nesta coleta."])
  else:
    emoji, estado = estado_operacional(navio)
    if antigo:
      blocos.extend(["⚠️ *Dados desatualizados*", "As informações abaixo correspondem à última consulta disponível."])
    status = f"*Última situação registrada:* {estado}" if antigo else f"{emoji} *{estado}*"
    if navio.get("local") and navio["local"] != "N/A":
      status += f"\n📍 *{'Terminal previsto' if emoji in ('🟡', '⚓') else 'Local'}:* {navio['local']}"
    blocos.append(status)
    previsoes = []
    for campo, rotulo in (("eta", "Chegada (ETA)"), ("etb", "Atracado" if emoji == "🟢" else "Atracação prevista")):
      if campo == "etb" and etapa_evento(navio.get("evento"))[0] >= 3:
        continue
      if navio.get(campo) and navio[campo] != "N/A":
        previsoes.append(f"{('✅ ' if emoji == '🟢' else '⏳ ') if campo == 'etb' else ''}*{rotulo}:* {formatar_data_operacional(navio[campo])}")
    if previsoes:
      blocos.append(("*Datas*\n\n" if completo else "") + "\n".join(previsoes))
  dados = []
  if navio.get("ultima_consulta"):
    dados.append(f"🕒 *{'Última consulta' if completo else 'Consulta'}:* {formatar_data(navio['ultima_consulta'])}")
  if completo:
    if navio.get("ultima_alteracao"):
      dados.append(f"*Última alteração:* {formatar_data(navio['ultima_alteracao'])}")
    if navio.get("fonte"):
      fonte = str(navio['fonte']).replace("APS_ATRACACOES_PROGRAMADAS", "Atracações programadas").replace("APS_FUNDEADOS", "Navios fundeados").replace("APS_ATRACADOS", "Navios atracados").replace("APS_PAINEL", "Painel do porto")
      dados.append(f"*Fonte:* {fonte}")
  if dados:
    blocos.append(("*Atualização dos dados*\n\n" if completo else "") + "\n".join(dados))
  return "\n\n".join(blocos)


def formatar_resumo(navio: Registro, agora: datetime | None = None) -> str:
  return _formatar(navio, agora, False)


def formatar_navio(navio: Registro, agora: datetime | None = None) -> str:
  return _formatar(navio, agora, True)
