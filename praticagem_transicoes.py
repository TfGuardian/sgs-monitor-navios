"""Compara estados normalizados da Praticagem sem enviar mensagens."""

from __future__ import annotations

from typing import Any


CAMPOS_MANOBRA = ("mv", "pob", "passag", "local1", "local2")
FASES = {"previsao", "confirmada", "andamento", "encerrada"}


def _texto(valor: Any) -> str:
    return " ".join(str(valor or "").split())


def _manobras(estado: dict[str, Any]) -> dict[str, dict[str, Any]]:
    resultado = {}
    for manobra in estado.get("manobras", []):
        chave = _texto(manobra.get("chave"))
        if not chave or chave in resultado:
            raise ValueError("Cada manobra precisa de uma chave de ocorrência única")
        fase = _texto(manobra.get("fase"))
        if fase not in FASES:
            raise ValueError(f"Fase de manobra não reconhecida: {fase}")
        resultado[chave] = manobra
    return resultado


def comparar_estados(
    anterior: dict[str, Any] | None,
    atual: dict[str, Any],
) -> list[dict[str, Any]]:
    """Devolve mudanças observáveis; a primeira leitura estabelece a base."""
    imo = _texto(atual.get("imo"))
    if not imo:
        raise ValueError("Estado sem IMO não pode gerar alerta automático")
    manobras_atuais = _manobras(atual)
    if anterior is None:
        return []
    if _texto(anterior.get("imo")) != imo:
        raise ValueError("Estados de navios diferentes não podem ser comparados")

    manobras_anteriores = _manobras(anterior)
    eventos = []
    for chave, manobra in manobras_atuais.items():
        anterior_manobra = manobras_anteriores.get(chave)
        mudancas = []
        if anterior_manobra is None:
            mudancas.append({"campo": "fase", "antes": None,
                             "depois": manobra["fase"]})
        else:
            if _texto(anterior_manobra.get("fase")) != _texto(manobra.get("fase")):
                mudancas.append({"campo": "fase",
                                 "antes": anterior_manobra.get("fase"),
                                 "depois": manobra.get("fase")})
            for campo in CAMPOS_MANOBRA:
                antes = _texto(anterior_manobra.get(campo))
                depois = _texto(manobra.get(campo))
                # Um campo vazio na coleta nova pode indicar dado incompleto.
                if depois and antes != depois:
                    mudancas.append({"campo": campo, "antes": antes or None,
                                     "depois": depois})
        if mudancas:
            eventos.append({"imo": imo, "nome": _texto(atual.get("nome")),
                            "manobra": chave, "mv": _texto(manobra.get("mv")),
                            "mudancas": mudancas})

    situacao = []
    for campo in ("fundeado", "atracado"):
        if bool(atual.get(campo)) and not bool(anterior.get(campo)):
            situacao.append({"campo": campo, "antes": False, "depois": True})
    if situacao:
        # Se só uma manobra mudou, reunir a situação física ao mesmo aviso.
        if len(eventos) == 1:
            eventos[0]["mudancas"].extend(situacao)
        else:
            eventos.append({"imo": imo, "nome": _texto(atual.get("nome")),
                            "manobra": None, "mv": None,
                            "mudancas": situacao})
    return eventos


def formatar_alerta(evento: dict[str, Any]) -> str:
    """Texto de prévia; não faz chamada à API de mensagens."""
    fases = {"previsao": ("⚪", "Manobra em previsão"),
             "confirmada": ("🟣", "Manobra confirmada"),
             "andamento": ("🔵", "Manobra em andamento"),
             "encerrada": ("🔴", "Manobra encerrada")}
    mudancas = evento["mudancas"]
    fase = next((m for m in mudancas if m["campo"] == "fase"), None)
    if fase:
        emoji, rotulo = fases[fase["depois"]]
        linhas = [f"🚢 *{evento['nome']}*", f"{emoji} *{rotulo}*"]
    else:
        linhas = [f"🚢 *{evento['nome']}*", "📝 *Movimentação atualizada*"]
    rotulos = {"mv": "Código da manobra", "pob": "POB", "passag": "Passagem",
               "local1": "Local 1", "local2": "Local 2"}
    for mudanca in mudancas:
        campo = mudanca["campo"]
        if campo in rotulos:
            antes = mudanca["antes"] or "N/A"
            linhas.append(f"📍 *{rotulos[campo]}:* {antes} → {mudanca['depois']}")
        elif campo == "fundeado":
            linhas.append("⚓ *Fundeado*")
        elif campo == "atracado":
            linhas.append("🟢 *Atracado*")
    return "\n".join(linhas)
