"""Seleciona pelo nome antes de interpretar manobras; conserva chaves legadas."""
from copy import deepcopy
import hashlib
import re
import unicodedata


def nome_chave(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).upper().split())


def imo_valido(valor):
    valor = str(valor or "").strip()
    return bool(re.fullmatch(r"[0-9]{7}", valor)) and valor != "0000000"


def preparar_por_nome(captura, registros, anteriores):
    # Valida a estrutura antes do filtro, sem interpretar fases de outros navios.
    tabelas = captura["tabelas"]
    nomes = {}
    catalogo = {}
    for tabela in ("movimentos", "previstas", "atracados", "fundeados"):
        linhas = tabelas.get(tabela)
        if not isinstance(linhas, list) or captura["quantidades"].get(tabela) != len(linhas):
            raise ValueError("Tabela incompleta: " + tabela)
        for linha in linhas:
            celulas = linha["celulas"]
            nome = nome_chave(celulas.get("NAVIO"))
            if not nome:
                continue
            imo = str(celulas.get("IMO") or "").strip()
            nomes.setdefault(nome, set())
            if imo_valido(imo):
                nomes[nome].add(imo)
                catalogo[(nome, imo)] = {"nome": celulas["NAVIO"].strip(), "imo": imo}
    for tabela in tabelas.values():
        for linha in tabela:
            nome = nome_chave(linha["celulas"].get("NAVIO"))
            if nome and not nomes.get(nome):
                catalogo[(nome, "")] = {"nome": linha["celulas"]["NAVIO"].strip(), "imo": None}
    selecionados = {}
    bloqueados = []
    avisos = []
    for item in registros:
        nome = nome_chave(item.get("nome_confirmado"))
        if not nome:
            continue
        # Prioriza a identidade por nome já gravada, mesmo se o IMO da fonte mudar.
        chave_nome = "nome:" + hashlib.sha256(nome.encode()).hexdigest()[:32]
        legados = [k for k,v in anteriores.items() if nome_chave(v.get("nome")) == nome]
        chave = chave_nome if chave_nome in anteriores else (legados[0] if len(legados) == 1 else chave_nome)
        if nome in selecionados or len(nomes.get(nome, set())) > 1 or (len(legados) > 1 and chave_nome not in anteriores):
            bloqueados.append(chave)
            avisos.append({"nome": nome, "motivo": "nome_ambiguo"})
        selecionados[nome] = (chave, item["nome_confirmado"])
    filtrada = deepcopy(captura)
    for tabela, linhas in tabelas.items():
        filtrada["tabelas"][tabela] = []
        for linha in linhas:
            nome = nome_chave(linha["celulas"].get("NAVIO"))
            if nome not in selecionados:
                continue
            chave, _ = selecionados[nome]
            if chave in bloqueados:
                continue
            copia = deepcopy(linha)
            copia["celulas"]["IMO"] = chave
            filtrada["tabelas"][tabela].append(copia)
    filtrada["quantidades"] = {t:len(v) for t,v in filtrada["tabelas"].items()}
    return filtrada, {k:n for k,n in selecionados.values()}, list(catalogo.values()), bloqueados, avisos
