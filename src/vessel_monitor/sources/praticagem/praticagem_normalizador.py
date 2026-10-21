"""Normaliza as quatro tabelas visíveis da Praticagem sem inferir manobras.

Linhas sem IMO ficam em quarentena. Nenhum dado deste módulo altera o monitor
APS, persiste no Supabase ou envia mensagens.
"""

from __future__ import annotations

import re
from typing import Any


CORES_FASE = {
    "rgb(255, 255, 255)": "previsao",
    "rgb(183, 183, 255)": "confirmada",
    "rgb(0, 191, 255)": "andamento",
    "rgb(255, 74, 74)": "encerrada",
}
TABELAS = ("movimentos", "previstas", "atracados", "fundeados")


def _texto(valor: Any) -> str:
    return " ".join(str(valor or "").split())


def normalizar_captura(captura: dict[str, Any], *, chaves_internas: bool = False) -> dict[str, Any]:
    tabelas = captura.get("tabelas")
    quantidades = captura.get("quantidades")
    if not isinstance(tabelas, dict) or not isinstance(quantidades, dict):
        raise ValueError("Captura sem tabelas ou contagens")
    observacoes = []
    ignorados = []
    for tabela in TABELAS:
        linhas = tabelas.get(tabela)
        if not isinstance(linhas, list) or quantidades.get(tabela) != len(linhas):
            raise ValueError(f"Contagem divergente em {tabela}")
        for indice, linha in enumerate(linhas, start=1):
            celulas = linha.get("celulas")
            if not isinstance(celulas, dict):
                raise ValueError(f"Células inválidas em {tabela}, linha {indice}")
            imo = _texto(celulas.get("IMO"))
            if not imo or imo == "0000000":
                ignorados.append({"tabela": tabela, "linha": indice,
                                   "motivo": "imo_ausente"})
                continue
            if not (re.fullmatch(r"\d{7}", imo) or
                    (chaves_internas and re.fullmatch(r"nome:[a-f0-9]{32}", imo))):
                raise ValueError(f"IMO inválido em {tabela}, linha {indice}")
            nome = _texto(celulas.get("NAVIO"))
            if not nome:
                raise ValueError(f"Navio sem nome em {tabela}, linha {indice}")
            registro = {"imo": imo, "nome": nome, "tabela": tabela}
            if tabela in ("movimentos", "previstas"):
                fase = "previsao"
                if tabela == "movimentos":
                    cor = _texto(linha.get("cor"))
                    fase = CORES_FASE.get(cor)
                    if fase is None:
                        raise ValueError(f"Cor de fase desconhecida em movimentos, linha {indice}: {cor}")
                registro.update({
                    "fase": fase,
                    "mv": _texto(celulas.get("MV")),
                    "local1": _texto(celulas.get("LOC#1")),
                    "local2": _texto(celulas.get("LOC#2")),
                    "pob": _texto(celulas.get("POB")),
                    "passag": _texto(celulas.get("PASSAG")),
                })
            elif tabela == "atracados":
                registro["local"] = _texto(celulas.get("LOCAL"))
            else:
                registro["fundeio"] = _texto(celulas.get("FUNDEIO"))
            observacoes.append(registro)
    return {"coletado_em": captura.get("coletado_em"),
            "quantidades": {t: quantidades[t] for t in TABELAS},
            "observacoes": observacoes, "ignorados": ignorados}
