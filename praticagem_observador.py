"""Modo de observação da Praticagem: registra eventos, nunca envia WhatsApp.

O adaptador da fonte deve entregar um snapshot normalizado. Até validar a
coleta autenticada, este módulo aceita snapshots JSON para testes controlados.
"""

from __future__ import annotations

import argparse
import json
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable

from praticagem_normalizador import normalizar_captura
from praticagem_por_nome import preparar_por_nome
from praticagem_snapshot import construir_snapshot
from praticagem_transicoes import comparar_estados, formatar_alerta


TABELAS = ("movimentos", "previstas", "atracados", "fundeados")


def _nome_chave(nome: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", nome or "")
    return " ".join("".join(c for c in sem_acentos if not unicodedata.combining(c))
                    .upper().split())


def resolver_monitorados(
    registros: list[dict[str, Any]],
    snapshot: dict[str, Any],
    anteriores: dict[str, dict[str, Any]],
    tem_coleta_anterior: bool,
) -> dict[str, str]:
    """Associa cadastro sem IMO só quando o nome aponta para um único navio."""
    nomes: dict[str, set[str]] = {}
    for item in snapshot["navios"]:
        nomes.setdefault(_nome_chave(item.get("nome", "")), set()).add(str(item["imo"]))
    for imo, estado in anteriores.items():
        nomes.setdefault(_nome_chave(estado.get("nome", "")), set()).add(imo)
    monitorados = {}
    for item in registros:
        nome = str(item.get("nome_confirmado") or "").strip()
        imo = str(item.get("imo") or "").strip()
        if not imo:
            candidatos = nomes.get(_nome_chave(nome), set())
            if len(candidatos) > 1:
                raise ValueError(f"Nome monitorado ambíguo: {nome}")
            if not candidatos:
                continue
            imo = next(iter(candidatos))
            if imo not in anteriores and tem_coleta_anterior:
                anteriores[imo] = {"imo": imo, "nome": nome, "manobras": [],
                                  "fundeado": False, "atracado": False}
        monitorados[imo] = nome
    return monitorados


def validar_snapshot(snapshot: dict[str, Any]) -> None:
    quantidades = snapshot.get("quantidades")
    navios = snapshot.get("navios")
    if not isinstance(quantidades, dict) or not isinstance(navios, list):
        raise ValueError("Snapshot deve conter quantidades e navios")
    if any(not isinstance(quantidades.get(t), int) or quantidades[t] < 0
           for t in TABELAS):
        raise ValueError("Contagem de tabelas ausente ou inválida")
    if not sum(quantidades[t] for t in TABELAS):
        raise ValueError("Todas as tabelas vieram vazias")
    imos = [str(item.get("imo") or "").strip() for item in navios]
    if any(not imo for imo in imos) or len(set(imos)) != len(imos):
        raise ValueError("Snapshot contém IMO ausente ou duplicado")


def montar_pacote(
    snapshot: dict[str, Any],
    monitorados: dict[str, str] | set[str],
    anteriores: dict[str, dict[str, Any]],
    destinatarios: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validar_snapshot(snapshot)
    estados, eventos = [], []
    encontrados = {str(item["imo"]).strip(): item for item in snapshot["navios"]}
    for imo in sorted(monitorados):
        if imo in snapshot.get("bloqueados", []):
            continue  # Não sobrescreve estado histórico nem emite alertas deste IMO.
        estado = encontrados.get(imo)
        anterior = anteriores.get(imo)
        if estado is None:
            nome = (monitorados.get(imo) if isinstance(monitorados, dict) else imo)
            estado = {"imo": imo, "nome": (anterior or {}).get("nome") or nome,
                      "manobras": [], "fundeado": False, "atracado": False}
        if anterior:
            # Sumiço de linha não prova fim da manobra ou saída da tabela.
            # Conservar o último estado confirmado impede um falso "novo"
            # alerta quando a mesma linha reaparece na próxima coleta.
            chaves_atuais = {m["chave"] for m in estado.get("manobras", [])}
            estado = dict(estado)
            estado["manobras"] = list(estado.get("manobras", [])) + [
                m for m in anterior.get("manobras", [])
                if m["chave"] not in chaves_atuais
            ]
            for campo in ("fundeado", "atracado"):
                estado[campo] = bool(estado.get(campo) or anterior.get(campo))
        mudancas = comparar_estados(anterior, estado)
        estados.append(estado)
        for evento in mudancas:
            texto = formatar_alerta(evento)
            evento["alertas"] = [
                {"telefone": numero, "texto": texto}
                for numero in sorted(set(destinatarios))
            ]
            eventos.append(evento)
    return estados, eventos


def executar(cliente: Any, coletar: Callable[[], dict[str, Any]],
             eventos_registrados: list[dict[str, Any]] | None = None) -> int:
    resposta = cliente.rpc("reservar_coleta_praticagem").execute()
    token = resposta.data
    if not token:
        return 0
    inicio = time.monotonic()
    try:
        captura = coletar()
        anteriores = {
            str(item["imo"]): item["dados"] for item in
            (cliente.table("estados_praticagem")
             .select("imo,dados").execute().data or [])
        }
        registros = (cliente.table("lista_monitoramento")
                    .select("imo,nome_confirmado").eq("ativo", True)
                    .execute().data or [])
        if "tabelas" in captura:
            filtrada, monitorados, catalogo, bloqueados, avisos = preparar_por_nome(
                captura, registros, anteriores)
            snapshot = construir_snapshot(
                normalizar_captura(filtrada, chaves_internas=True), anteriores)
            # Contagem da fonte completa, inclusive quando nenhum monitorado aparece.
            snapshot["quantidades"] = captura["quantidades"]
            snapshot["bloqueados"].extend(bloqueados)
            snapshot["ignorados"].extend(avisos)
        else:
            snapshot = captura
            tem_coleta_anterior = bool(
                cliente.table("coletas_praticagem").select("id")
                .eq("resultado", "sucesso").limit(1).execute().data)
            monitorados = resolver_monitorados(
                registros, snapshot, anteriores, tem_coleta_anterior)
        for ignorado in snapshot.get("ignorados", []):
            print("registro_praticagem_isolado: " + json.dumps(ignorado, ensure_ascii=False),
                  flush=True)
        destinatarios = [
            str(item["telefone"]) for item in
            (cliente.table("destinatarios_relatorio")
             .select("telefone").eq("ativo", True).execute().data or [])
        ]
        estados, eventos = montar_pacote(
            snapshot, monitorados, anteriores, destinatarios)
        duracao = int((time.monotonic() - inicio) * 1000)
        parametros = {
            "p_token": token, "p_estados": estados, "p_eventos": eventos,
            "p_quantidades": snapshot["quantidades"], "p_duracao_ms": duracao,
        }
        funcao = "concluir_observacao_praticagem"
        # Snapshots de teste nunca substituem o catálogo usado no WhatsApp.
        if "tabelas" in captura:
            funcao = "concluir_coleta_catalogo_praticagem"
            parametros["p_catalogo"] = catalogo
        cliente.rpc(funcao, parametros).execute()
        if eventos_registrados is not None:
            eventos_registrados.extend(eventos)
        return len(eventos)
    except Exception as exc:
        duracao = int((time.monotonic() - inicio) * 1000)
        try:
            cliente.rpc("registrar_falha_praticagem", {
                "p_token": token, "p_erro_codigo": type(exc).__name__,
                "p_duracao_ms": duracao,
            }).execute()
        except Exception:
            pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Teste de observação sem WhatsApp")
    origem = parser.add_mutually_exclusive_group(required=True)
    origem.add_argument("--snapshot", type=Path,
                        help="JSON normalizado de teste; não acessa o site")
    origem.add_argument("--portal", action="store_true",
                        help="Uma captura autenticada; não agenda nem envia")
    parser.add_argument("--visivel", action="store_true",
                        help="Mostra o navegador quando usa --portal")
    args = parser.parse_args()
    from config import criar_supabase

    if args.portal:
        import os
        from praticagem_portal import capturar_portal
        coletar = lambda: capturar_portal(
            os.getenv("SPPILOTS_USUARIO", ""), os.getenv("SPPILOTS_SENHA", ""),
            headless=not args.visivel)
    else:
        coletar = lambda: json.loads(args.snapshot.read_text(encoding="utf-8"))
    total = executar(
        criar_supabase(administrativo=True),
        coletar,
    )
    print(f"Observação registrada: {total} evento(s) simulado(s).")


if __name__ == "__main__":
    main()
