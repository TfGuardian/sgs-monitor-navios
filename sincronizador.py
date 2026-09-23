from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import sleep
from typing import Any, Callable, cast

from consulta_navio import formatar_data_operacional, normalizar

Registro = dict[str, Any]
CAMPOS_DADOS = (
    "lista_monitoramento_id", "nome", "imo", "eta", "etb", "local",
    "evento", "fonte",
)
CAMPOS_ALTERACAO = ("eta", "etb", "local", "evento")
MINIMO_REGISTROS_PAINEL = 50


@dataclass
class Atualizacao:
  anterior: Registro
  dados: Registro
  alteracao_operacional: bool = False
  localizado: bool = True
  alteracao_dados: bool = False


@dataclass
class PlanoSincronizacao:
  inserir: list[Registro] = field(default_factory=list)
  atualizar: list[Atualizacao] = field(default_factory=list)
  remover: list[Registro] = field(default_factory=list)

  @property
  def quantidade_alterados(self) -> int:
    return sum(item.alteracao_operacional for item in self.atualizar)


def _imo(valor: Any) -> str:
  imo = str(valor or "").strip()
  if imo.endswith(".0") and imo[:-2].isdigit():
    imo = imo[:-2]
  return "" if normalizar(imo) in ("", "N/A", "NAN", "NONE") else imo


def _chave(navio: Registro) -> tuple[str, str]:
  imo = _imo(navio.get("imo"))
  return ("imo", imo) if imo else ("nome", normalizar(navio.get("nome")))


def _data_operacao(navio: Registro) -> datetime:
  for campo in ("etb", "eta"):
    valor = str(navio.get(campo) or "").strip()
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%y %H:%M:%S",
                    "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
      try:
        return datetime.strptime(valor, formato)
      except ValueError:
        continue
  return datetime.min


def consolidar_coleta(registros: list[Registro]) -> list[Registro]:
  """Mantem uma ocorrencia por IMO ou nome, priorizando a operacao recente."""
  consolidados: dict[tuple[str, str], Registro] = {}
  for registro in registros:
    if not normalizar(registro.get("nome")):
      continue
    chave = _chave(registro)
    anterior = consolidados.get(chave)
    if anterior is None or _data_operacao(registro) >= _data_operacao(anterior):
      consolidados[chave] = registro
  return list(consolidados.values())


def _mesmo_navio(a, b):
  ia, ib = _imo(a.get("imo")).lstrip("0"), _imo(b.get("imo")).lstrip("0")
  if ia and ib:
    return ia == ib
  return normalizar(a.get("nome")) == normalizar(b.get("nome"))


def _escala_conflitante(a, b):
  return any(a.get(c) and b.get(c) and normalizar(a[c]) != normalizar(b[c])
             for c in ("viagem", "duv"))


def mesclar_fontes(painel, programadas, atracados=None, fundeados=None):
  """Não resolve conflitos por ordem de coleta ou por data prevista."""
  grupos = []
  for fonte, registros in (("APS_ATRACACOES_PROGRAMADAS", programadas),
                           ("APS_PAINEL", painel), ("APS_ATRACADOS", atracados or []),
                           ("APS_FUNDEADOS", fundeados or [])):
    for original in registros:
      navio = dict(original, fonte=fonte)
      candidatos = [g for g in grupos if any(_mesmo_navio(n, navio) or normalizar(n.get("nome")) == normalizar(navio.get("nome")) for n in g)]
      if candidatos:
        grupo = candidatos[0]
        grupo.append(navio)
        for outro in candidatos[1:]:
          grupo.extend(outro)
          grupos.remove(outro)
      else:
        grupos.append([navio])
  resultado = []
  for grupo in grupos:
    # Base operacional mantida, mas previsão é obtida da programação quando existe.
    base = dict(grupo[0])
    for n in grupo[1:]:
      for c, v in n.items():
        if v not in (None, ""):
          base[c] = v
    fontes = list(dict.fromkeys(n["fonte"] for n in grupo))
    conflito = any(_escala_conflitante(a, b) or
                   (_imo(a.get("imo")) and _imo(b.get("imo")) and not _mesmo_navio(a, b))
                   for i, a in enumerate(grupo) for b in grupo[i+1:])
    # Homônimos/duplicatas sem identificador de escala não comprovam uma única escala.
    for fonte in fontes:
      registros = [n for n in grupo if n["fonte"] == fonte]
      if len(registros) > 1 and any(not n.get("viagem") and not n.get("duv") for n in registros):
        conflito = conflito or any(n != registros[0] for n in registros[1:])
    atracado, fundeado = "APS_ATRACADOS" in fontes, "APS_FUNDEADOS" in fontes
    if conflito or (atracado and fundeado):
      base["evento"] = "SITUACAO_EM_VERIFICACAO"
      for c in ("eta", "etb", "local"):
        base[c] = None
    else:
      programacao = [n for n in grupo if n["fonte"] == "APS_ATRACACOES_PROGRAMADAS"]
      if programacao:
        for c in ("eta", "etb"):
          base[c] = programacao[-1].get(c)
      if atracado:
        base["evento"] = "ATRACADO"
        base["etb"] = None  # ETB não comprova a data efetiva de atracação.
      elif fundeado:
        base["evento"] = "FUNDEADO"
      elif normalizar(base.get("evento")) in ("ATRACACAO", "PROGRAMADO", "ATRACACAO PROGRAMADA"):
        base["evento"] = "ATRACACAO PROGRAMADA"
    base["fonte"] = " + ".join(fontes)
    resultado.append(base)
  return resultado


def coletar_catalogo_completo() -> tuple[list[Registro], int, int, int]:
  from monitor_aps import coletar_aps
  from monitor_atracacoes import coletar_atracacoes_programadas
  from monitor_atracados import coletar_navios_atracados
  from monitor_fundeados import coletar_navios_fundeados

  painel = coletar_com_tentativas(coletar_aps)
  validar_coleta(painel, [])
  programadas = coletar_com_tentativas(coletar_atracacoes_programadas)
  atracados = coletar_com_tentativas(coletar_navios_atracados)
  fundeados = coletar_com_tentativas(coletar_navios_fundeados)
  return (
      mesclar_fontes(painel, programadas, atracados, fundeados),
      len(painel),
      len(programadas),
      len(atracados),
  )


def _indisponivel(navio: Registro) -> bool:
  return not any(navio.get(campo) not in (None, "")
                 for campo in ("eta", "etb", "local", "evento"))


def _valor_comparacao(campo: str, valor: Any) -> Any:
  if campo in ("eta", "etb"):
    return formatar_data_operacional(valor)
  return valor or None


def planejar_sincronizacao(
    coletados: list[Registro],
    existentes: list[Registro],
    agora: datetime,
) -> PlanoSincronizacao:
  momento = agora.astimezone(timezone.utc).isoformat()
  plano = PlanoSincronizacao()
  por_lista_id = {
      n.get("lista_monitoramento_id"): n for n in existentes
      if n.get("lista_monitoramento_id") is not None
  }
  por_imo = {_imo(n.get("imo")): n for n in existentes if _imo(n.get("imo"))}
  por_nome = {normalizar(n.get("nome")): n for n in existentes}
  encontrados: set[int] = set()

  for coletado in consolidar_coleta(coletados):
    imo = _imo(coletado.get("imo"))
    nome = normalizar(coletado.get("nome"))
    lista_id = coletado.get("lista_monitoramento_id")
    anterior = por_lista_id.get(lista_id) if lista_id is not None else None
    anterior = anterior or (por_imo.get(imo) if imo else None)
    anterior = anterior or por_nome.get(nome)
    # O painel atual nao publica IMO ou ETA em todas as linhas. Quando o banco
    # ja possui esses valores, a ausencia na fonte nao deve apaga-los.
    dados = {campo: coletado.get(campo) for campo in CAMPOS_DADOS
             if coletado.get(campo) not in (None, "")}
    for campo in ("eta", "etb"):
      if campo in dados:
        dados[campo] = formatar_data_operacional(dados[campo])
    dados.update({
        "ultima_consulta": momento,
        "ausencias_consecutivas": 0,
        "situacao": "indisponivel" if _indisponivel(coletado) else "atualizado",
    })

    if anterior is None:
      dados["ultima_alteracao"] = momento
      plano.inserir.append(dados)
      continue

    encontrados.add(id(anterior))
    alterou = any(
        campo in dados
        and _valor_comparacao(campo, anterior.get(campo)) != dados.get(campo)
        for campo in CAMPOS_ALTERACAO
    )
    alterou_dados = any(
        campo in dados
        and _valor_comparacao(campo, anterior.get(campo)) != (dados.get(campo) or None)
        for campo in CAMPOS_DADOS
    )
    if alterou:
      dados["ultima_alteracao"] = momento
    plano.atualizar.append(Atualizacao(
        anterior, dados, alterou, localizado=True, alteracao_dados=alterou_dados
    ))

  for anterior in existentes:
    if id(anterior) in encontrados:
      continue
    ausencias = int(anterior.get("ausencias_consecutivas") or 0) + 1
    if ausencias >= 2:
      plano.remover.append(anterior)
    else:
      plano.atualizar.append(Atualizacao(
          anterior,
          {"ausencias_consecutivas": ausencias, "situacao": "desatualizado"},
          localizado=False,
      ))
  return plano


def filtrar_monitorados(
    coletados: list[Registro],
    lista: list[Registro],
) -> list[Registro]:
  catalogo = consolidar_coleta(coletados)
  por_nome = {normalizar(n.get("nome")): n for n in catalogo}
  por_imo = {
      _imo(n.get("imo")): n for n in catalogo if _imo(n.get("imo"))
  }
  resultado: list[Registro] = []
  for item in lista:
    imo = _imo(item.get("imo"))
    encontrado = por_imo.get(imo) if imo else None
    encontrado = encontrado or por_nome.get(normalizar(item.get("nome_confirmado")))
    if encontrado:
      resultado.append({**encontrado, "lista_monitoramento_id": item["id"]})
  return resultado


def validar_coleta(
    coletados: list[Registro],
    existentes: list[Registro],
    minimo_painel: int = MINIMO_REGISTROS_PAINEL,
) -> None:
  if not coletados:
    raise RuntimeError("A coleta nao retornou navios; o banco foi preservado.")
  if len(coletados) < minimo_painel:
    raise RuntimeError(
        f"A coleta retornou apenas {len(coletados)} registros do painel; "
        "o banco foi preservado por seguranca."
    )
  if existentes and len(coletados) < max(1, (len(existentes) + 1) // 2):
    raise RuntimeError(
        "A coleta retornou menos da metade dos navios existentes; "
        "o banco foi preservado por seguranca."
    )


def coletar_com_tentativas(
    coletor: Callable[[], list[Registro]],
    tentativas: int = 3,
) -> list[Registro]:
  ultimo_erro: Exception | None = None
  for tentativa in range(1, tentativas + 1):
    try:
      return coletor()
    except Exception as exc:
      ultimo_erro = exc
      print(f"Coleta falhou na tentativa {tentativa}/{tentativas}: {exc}")
      if tentativa < tentativas:
        sleep(1)
  raise RuntimeError(f"Coleta falhou apos {tentativas} tentativas") from ultimo_erro


def _filtro(tabela, registro: Registro):
  if registro.get("id") is not None:
    return tabela.eq("id", registro["id"])
  imo = _imo(registro.get("imo"))
  return tabela.eq("imo", imo) if imo else tabela.eq("nome", registro["nome"])


def _registrar_coleta(cliente, dados: Registro) -> None:
  try:
    cliente.table("coletas_monitoramento").insert(dados).execute()
  except Exception as exc:
    print(f"Aviso: nao foi possivel registrar a saude da coleta: {exc}")


def sincronizar(dry_run: bool = False) -> PlanoSincronizacao:
  from config import criar_supabase
  from lista_monitoramento import (
      carregar_destinatarios,
      carregar_lista,
      montar_visao_monitorados,
  )
  cliente = criar_supabase(administrativo=True)
  inicio = datetime.now(timezone.utc)
  try:
    lista = carregar_lista(cliente)
    if not lista:
      if not dry_run:
        _registrar_coleta(cliente, {
            "inicio": inicio.isoformat(),
            "fim": datetime.now(timezone.utc).isoformat(),
            "resultado": "sucesso",
            "navios_acompanhados": 0,
        })
      print("Nenhum navio esta na lista de acompanhamento.")
      return PlanoSincronizacao()

    (catalogo, quantidade_painel, quantidade_programadas,
     quantidade_atracados) = coletar_catalogo_completo()
    resposta = cliente.table("navios_monitorados").select("*").execute()
    existentes = [
        cast(Registro, navio) for navio in (resposta.data or [])
        if navio.get("lista_monitoramento_id") is not None
    ]
    validar_coleta(catalogo, [], minimo_painel=1)
    coletados = filtrar_monitorados(catalogo, lista)
    plano = planejar_sincronizacao(coletados, existentes, inicio)

    if not dry_run:
      if plano.inserir:
        cliente.table("navios_monitorados").insert(plano.inserir).execute()

      localizados_com_id = [
          item for item in plano.atualizar
          if item.localizado and item.anterior.get("id") is not None
      ]
      for situacao in ("atualizado", "indisponivel"):
        grupo = [
            item for item in localizados_com_id
            if item.dados["situacao"] == situacao
        ]
        if grupo:
          ids = [item.anterior["id"] for item in grupo]
          momento = grupo[0].dados["ultima_consulta"]
          (cliente.table("navios_monitorados").update({
              "ultima_consulta": momento,
              "ausencias_consecutivas": 0,
              "situacao": situacao,
          }).in_("id", ids).execute())

      for atualizacao in plano.atualizar:
        if (atualizacao.localizado and atualizacao.anterior.get("id") is not None
            and not atualizacao.alteracao_dados):
          continue
        tabela = cliente.table("navios_monitorados").update(atualizacao.dados)
        _filtro(tabela, atualizacao.anterior).execute()

      remover_com_id = [n["id"] for n in plano.remover if n.get("id") is not None]
      if remover_com_id:
        (cliente.table("navios_monitorados").delete()
         .in_("id", remover_com_id).execute())
      for navio in (n for n in plano.remover if n.get("id") is None):
        _filtro(cliente.table("navios_monitorados").delete(), navio).execute()

      _registrar_coleta(cliente, {
          "inicio": inicio.isoformat(),
          "fim": datetime.now(timezone.utc).isoformat(),
          "resultado": "sucesso",
          "navios_acompanhados": len(lista),
          "registros_painel": (
              quantidade_painel + quantidade_programadas + quantidade_atracados
          ),
          "navios_encontrados": len(coletados),
          "navios_incluidos": len(plano.inserir),
          "navios_atualizados": plano.quantidade_alterados,
          "navios_removidos": len(plano.remover),
          "navios_desatualizados": sum(
              not item.localizado for item in plano.atualizar
          ),
          "navios_indisponiveis": max(0, len(lista) - len(coletados)),
      })

      import os
      if os.getenv("RELATORIO_WHATSAPP_ATIVO", "").strip().lower() in (
          "1", "true", "sim", "yes",
      ):
        from relatorio import montar_relatorio
        from whatsapp import enviar_relatorio_whatsapp
        try:
          paginas = montar_relatorio(montar_visao_monitorados(cliente), limite=900)
          for destinatario in carregar_destinatarios(cliente):
            for pagina in paginas:
              enviar_relatorio_whatsapp(destinatario, pagina)
        except Exception as exc:
          # Uma falha da Meta nao invalida os dados que ja foram coletados.
          print(f"Aviso: coleta salva, mas o relatorio nao foi enviado: {exc}")

    prefixo = "[SIMULACAO] " if dry_run else ""
    print(
        f"{prefixo}Sincronizacao concluida: {len(lista)} acompanhados, "
        f"{len(coletados)} encontrados, "
        f"{len(plano.inserir)} incluidos, {plano.quantidade_alterados} alterados, "
        f"{len(plano.remover)} removidos. "
        f"Fontes: {quantidade_painel} no painel e "
        f"{quantidade_programadas} em atracacoes programadas e "
        f"{quantidade_atracados} atracados."
    )
    return plano
  except Exception as exc:
    if not dry_run:
      _registrar_coleta(cliente, {
          "inicio": inicio.isoformat(),
          "fim": datetime.now(timezone.utc).isoformat(),
          "resultado": "erro",
          "mensagem_erro": str(exc)[:1000],
      })
    raise


def exibir_status() -> None:
  from config import criar_supabase
  from consulta_navio import formatar_data

  cliente = criar_supabase(administrativo=True)
  navios = cliente.table("navios_monitorados").select("id", count="exact").execute()
  resposta = (cliente.table("coletas_monitoramento").select("*")
              .order("inicio", desc=True).limit(1).execute())
  coletas = cast(list[Registro], resposta.data or [])
  if not coletas:
    print("Nenhuma coleta registrada.")
    return
  coleta = coletas[0]
  print(f"Ultima coleta: {formatar_data(coleta.get('fim'))}")
  print(f"Resultado: {str(coleta.get('resultado', 'N/A')).upper()}")
  print(f"Navios no banco: {getattr(navios, 'count', None) or 0}")
  print(f"Navios acompanhados: {coleta.get('navios_acompanhados') or 0}")
  print(f"Registros nas fontes: {coleta.get('registros_painel') or 0}")
  print(f"Navios encontrados: {coleta.get('navios_encontrados') or 0}")
  print(f"Navios incluidos: {coleta.get('navios_incluidos') or 0}")
  print(f"Navios atualizados: {coleta.get('navios_atualizados') or 0}")
  print(f"Navios removidos: {coleta.get('navios_removidos') or 0}")
  print(f"Navios desatualizados: {coleta.get('navios_desatualizados') or 0}")
  print(f"Navios indisponiveis: {coleta.get('navios_indisponiveis') or 0}")
  print(f"Ultimo erro: {coleta.get('mensagem_erro') or 'nenhum'}")
