from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from consulta_navio import formatar_resumo

Registro = dict[str, Any]
FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")


def _valor(valor: Any) -> str:
  return str(valor).strip() if valor not in (None, "") else "N/A"


def bloco_navio(navio: Registro, indice: int) -> str:
  return formatar_resumo(navio)


def montar_relatorio(navios: list[Registro], limite: int = 3800) -> list[str]:
  horario = datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y %H:%M")
  cabecalho = f"🚢 *Relatório de navios*\n\n🕒 *Emitido em:* {horario}\nHorário de Brasília."
  if not navios:
    return [cabecalho + "\n\nA lista de monitoramento está *vazia*."]

  blocos = [bloco_navio(navio, indice)
            for indice, navio in enumerate(navios, start=1)]
  paginas: list[str] = []
  # Reserva para o rodape, inclusive quando um unico bloco precisa ser dividido.
  capacidade = limite - len(cabecalho) - 2 - 60
  if capacidade < 20:
    raise ValueError("Limite insuficiente para o cabecalho do relatorio")
  trechos = []
  for bloco in blocos:
    while len(bloco) > capacidade:
      fim = bloco.rfind("\n", 0, capacidade + 1)
      if fim <= 0:
        fim = capacidade
      trechos.append(bloco[:fim])
      bloco = bloco[fim:].lstrip("\n")
    if bloco:
      trechos.append(bloco)
  atual = cabecalho
  for bloco in trechos:
    candidato = atual + "\n\n" + bloco
    if len(candidato) > limite - 60 and atual != cabecalho:
      paginas.append(atual)
      atual = cabecalho + "\n\n" + bloco
    else:
      atual = candidato
  paginas.append(atual)

  if len(paginas) > 1:
    total = len(paginas)
    paginas = [f"{pagina}\n\n📄 *Parte {indice} de {total}*"
               for indice, pagina in enumerate(paginas, start=1)]
  return paginas
