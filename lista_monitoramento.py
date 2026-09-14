from datetime import datetime, timedelta, timezone
from typing import Any, cast

from consulta_navio import localizar_navios, normalizar, sugerir_navios
from sincronizador import consolidar_coleta

Registro = dict[str, Any]


def normalizar_telefone(valor: str) -> str:
  return "".join(c for c in str(valor) if c.isdigit())


def telefone_valido(telefone: str) -> bool:
  return 10 <= len(normalizar_telefone(telefone)) <= 15


def carregar_lista(cliente, somente_ativos: bool = True) -> list[Registro]:
  consulta = cliente.table("lista_monitoramento").select("*")
  if somente_ativos:
    consulta = consulta.eq("ativo", True)
  resposta = consulta.order("nome_confirmado").execute()
  return cast(list[Registro], resposta.data or [])


def carregar_dados_monitorados(cliente) -> list[Registro]:
  resposta = cliente.table("navios_monitorados").select("*").execute()
  return [
      cast(Registro, navio) for navio in (resposta.data or [])
      if navio.get("lista_monitoramento_id") is not None
  ]


def montar_visao_monitorados(cliente) -> list[Registro]:
  lista = carregar_lista(cliente)
  dados = carregar_dados_monitorados(cliente)
  por_lista_id = {navio.get("lista_monitoramento_id"): navio for navio in dados}
  resultado: list[Registro] = []
  for item in lista:
    base: Registro = {
        "nome": item.get("nome_confirmado"),
        "imo": item.get("imo"),
        "situacao": "indisponivel",
        "lista_monitoramento_id": item.get("id"),
    }
    base.update(por_lista_id.get(item.get("id"), {}))
    resultado.append(base)
  return resultado


def eh_administrador(cliente, telefone: str) -> bool:
  numero = normalizar_telefone(telefone)
  resposta = (cliente.table("administradores_chat").select("id")
              .eq("telefone", numero).eq("ativo", True).limit(1).execute())
  return bool(resposta.data)


def cadastrar_administrador(cliente, telefone: str) -> str:
  numero = normalizar_telefone(telefone)
  if not telefone_valido(numero):
    raise ValueError("Telefone invalido; use o formato internacional com DDI e DDD.")
  cliente.table("administradores_chat").upsert(
      {"telefone": numero, "ativo": True}, on_conflict="telefone"
  ).execute()
  return numero


def _encontrar_exato(termo: str, catalogo: list[Registro]) -> Registro | None:
  procurado = normalizar(termo)
  for navio in catalogo:
    if normalizar(navio.get("nome")) == procurado:
      return navio
    if procurado and normalizar(navio.get("imo")) == procurado:
      return navio
  return None


def _dados_operacionais(navio: Registro, lista_id: int, momento: str) -> Registro:
  from consulta_navio import formatar_data_operacional
  dados = {
      campo: navio.get(campo)
      for campo in ("nome", "imo", "eta", "etb", "local", "evento", "fonte")
      if navio.get(campo) not in (None, "")
  }
  for campo in ("eta", "etb"):
    if campo in dados:
      dados[campo] = formatar_data_operacional(dados[campo])
  dados.update({
      "lista_monitoramento_id": lista_id,
      "ultima_consulta": momento,
      "ultima_alteracao": momento,
      "situacao": "atualizado",
      "ausencias_consecutivas": 0,
  })
  return dados


def adicionar_navios(
    cliente,
    termos: list[str],
    remetente: str,
    coletados: list[Registro],
) -> Registro:
  catalogo = consolidar_coleta(coletados)
  lista = carregar_lista(cliente, somente_ativos=False)
  existentes = cliente.table("navios_monitorados").select("*").execute().data or []
  por_nome = {normalizar(item.get("nome_confirmado")): item for item in lista}
  por_imo = {normalizar(item.get("imo")): item for item in lista if item.get("imo")}
  momento = datetime.now(timezone.utc).isoformat()
  resultado: Registro = {"adicionados": [], "existentes": [], "nao_encontrados": []}

  for termo in termos:
    encontrado = _encontrar_exato(termo, catalogo)
    if encontrado is None:
      resultado["nao_encontrados"].append({
          "termo": termo,
          "sugestoes": sugerir_navios(termo, catalogo),
      })
      continue

    nome_normalizado = normalizar(encontrado.get("nome"))
    imo_normalizado = normalizar(encontrado.get("imo"))
    item = por_nome.get(nome_normalizado) or (
        por_imo.get(imo_normalizado) if imo_normalizado else None
    )
    if item and item.get("ativo"):
      resultado["existentes"].append(item.get("nome_confirmado"))
      continue

    dados_lista = {
        "nome_solicitado": termo.strip(),
        "nome_confirmado": encontrado.get("nome"),
        "nome_normalizado": nome_normalizado,
        "imo": encontrado.get("imo"),
        "ativo": True,
        "adicionado_por": normalizar_telefone(remetente),
        "atualizado_em": momento,
    }
    if item:
      resposta = (cliente.table("lista_monitoramento").update(dados_lista)
                  .eq("id", item["id"]).execute())
    else:
      resposta = cliente.table("lista_monitoramento").insert(dados_lista).execute()
    salvo = cast(Registro, (resposta.data or [dados_lista])[0])
    lista_id = int(salvo["id"])

    operacional = _dados_operacionais(encontrado, lista_id, momento)
    atual = next((n for n in existentes
                  if normalizar(n.get("nome")) == nome_normalizado
                  or (imo_normalizado and normalizar(n.get("imo")) == imo_normalizado)), None)
    if atual:
      cliente.table("navios_monitorados").update(operacional).eq(
          "id", atual["id"]
      ).execute()
    else:
      cliente.table("navios_monitorados").insert(operacional).execute()
    resultado["adicionados"].append(encontrado.get("nome"))
    por_nome[nome_normalizado] = salvo
    if imo_normalizado:
      por_imo[imo_normalizado] = salvo
  return resultado


def preparar_remocao(cliente, telefone: str, termos: list[str]) -> Registro:
  lista = carregar_lista(cliente)
  selecionados: dict[int, str] = {}
  nao_encontrados: list[str] = []
  for termo in termos:
    encontrados = localizar_navios(termo, [
        {"nome": item.get("nome_confirmado"), "imo": item.get("imo"), "id": item["id"]}
        for item in lista
    ])
    if len(encontrados) == 1:
      selecionados[int(encontrados[0]["id"])] = str(encontrados[0]["nome"])
    else:
      nao_encontrados.append(termo)
  if selecionados:
    numero = normalizar_telefone(telefone)
    cliente.table("confirmacoes_chat").upsert({
        "telefone": numero,
        "acao": "remover_navios",
        "payload": {"ids": list(selecionados), "nomes": list(selecionados.values())},
        "criado_em": datetime.now(timezone.utc).isoformat(),
        "expira_em": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    }, on_conflict="telefone").execute()
  return {"selecionados": list(selecionados.values()), "nao_encontrados": nao_encontrados}


def confirmar_remocao(cliente, telefone: str) -> list[str]:
  numero = normalizar_telefone(telefone)
  resposta = (cliente.table("confirmacoes_chat").select("*")
              .eq("telefone", numero).limit(1).execute())
  pendentes = cast(list[Registro], resposta.data or [])
  if not pendentes:
    return []
  pendente = pendentes[0]
  expira = datetime.fromisoformat(str(pendente["expira_em"]).replace("Z", "+00:00"))
  if expira < datetime.now(timezone.utc):
    cliente.table("confirmacoes_chat").delete().eq("telefone", numero).execute()
    return []
  payload = cast(Registro, pendente.get("payload") or {})
  ids = [int(item) for item in payload.get("ids", [])]
  nomes = [str(item) for item in payload.get("nomes", [])]
  if ids:
    cliente.table("lista_monitoramento").delete().in_("id", ids).execute()
  cliente.table("confirmacoes_chat").delete().eq("telefone", numero).execute()
  return nomes


def cancelar_confirmacao(cliente, telefone: str) -> None:
  cliente.table("confirmacoes_chat").delete().eq(
      "telefone", normalizar_telefone(telefone)
  ).execute()


def definir_relatorio(cliente, telefone: str, ativo: bool) -> None:
  numero = normalizar_telefone(telefone)
  if not telefone_valido(numero):
    raise ValueError("Telefone invalido.")
  momento = datetime.now(timezone.utc).isoformat()
  cliente.table("destinatarios_relatorio").upsert({
      "telefone": numero,
      "ativo": ativo,
      "inscrito_em": momento,
      "cancelado_em": None if ativo else momento,
  }, on_conflict="telefone").execute()


def carregar_destinatarios(cliente) -> list[str]:
  resposta = (cliente.table("destinatarios_relatorio").select("telefone")
              .eq("ativo", True).execute())
  return [str(item["telefone"]) for item in (resposta.data or [])]
