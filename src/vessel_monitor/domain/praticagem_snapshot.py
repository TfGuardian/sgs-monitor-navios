"""Correlaciona observações da Praticagem com ocorrências já conhecidas.

Quando há ambiguidade, isola o IMO afetado sem produzir aviso para ele. Não presume que horário ou local são IDs.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import uuid4


def _campos(manobra: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(manobra.get(c) or "") for c in
                 ("mv", "local1", "local2", "pob", "passag"))


def _chave_ocorrencia(
    imo: str,
    atual: dict[str, Any],
    anteriores: list[dict[str, Any]],
) -> str:
    mesmo_mv = [m for m in anteriores if m.get("mv") == atual["mv"]]
    ativas = [m for m in mesmo_mv if m.get("fase") != "encerrada"]
    if len(ativas) > 1:
        raise ValueError(f"Manobras anteriores ambíguas para IMO {imo}")
    if len(ativas) == 1:
        return str(ativas[0]["chave"])
    # O portal pode corrigir o código MV de uma previsão mantendo a mesma
    # origem e destino. Nesse caso é uma alteração da linha observada, não
    # evidência suficiente para anunciar outra manobra.
    if atual["fase"] == "previsao" and atual.get("fonte") == "previstas":
        locais = (atual.get("local1"), atual.get("local2"))
        if any(locais):
            candidatas = [m for m in anteriores
                          if m.get("fase") == "previsao"
                          and m.get("fonte") == "previstas"
                          and (m.get("local1"), m.get("local2")) == locais]
            if len(candidatas) > 1:
                raise ValueError(f"Correção de MV ambígua para IMO {imo}")
            if len(candidatas) == 1:
                return str(candidatas[0]["chave"])
    if atual["fase"] == "encerrada":
        iguais = [m for m in mesmo_mv if _campos(m) == _campos(atual)]
        if len(iguais) == 1:
            return str(iguais[0]["chave"])
        if mesmo_mv:
            raise ValueError(f"Manobra encerrada ambígua para IMO {imo}")
    return f"m-{uuid4().hex}"


def construir_snapshot(
    normalizado: dict[str, Any],
    anteriores: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    agrupados: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observacao in normalizado["observacoes"]:
        agrupados[observacao["imo"]].append(observacao)
    navios = []
    ignorados = list(normalizado.get("ignorados", []))
    bloqueados = set()
    for imo, observacoes in sorted(agrupados.items()):
        try:
            nomes = [o["nome"] for o in observacoes]
            manobras = [o for o in observacoes
                        if o["tabela"] in ("movimentos", "previstas")]
            pares = [(o["mv"], o["tabela"]) for o in manobras]
            if any(not mv for mv, _ in pares):
                raise ValueError(f"Manobra sem MV para IMO {imo}")
            if len({mv for mv, _ in pares}) != len(pares):
                raise ValueError(f"Mais de uma manobra com o mesmo MV para IMO {imo}")
            anteriores_imo = anteriores.get(imo, {}).get("manobras", [])
            convertidas = []
            for observacao in manobras:
                convertida = {k: observacao[k] for k in
                              ("fase", "mv", "local1", "local2", "pob", "passag")}
                convertida["fonte"] = observacao["tabela"]
                convertida["chave"] = _chave_ocorrencia(
                    imo, convertida, anteriores_imo)
                convertidas.append(convertida)
            navios.append({"imo": imo, "nome": nomes[0],
                          "manobras": convertidas,
                          "fundeado": any(o["tabela"] == "fundeados" for o in observacoes),
                          "atracado": any(o["tabela"] == "atracados" for o in observacoes)})
        except ValueError as exc:
            bloqueados.add(imo)
            ignorados.append({"imo": imo, "motivo": str(exc)})
    return {"quantidades": normalizado["quantidades"], "navios": navios,
            "ignorados": ignorados, "bloqueados": sorted(bloqueados)}
