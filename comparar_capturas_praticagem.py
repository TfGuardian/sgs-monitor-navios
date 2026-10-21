"""Compara duas capturas locais sem Supabase e sem WhatsApp."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from praticagem_normalizador import normalizar_captura
from praticagem_observador import montar_pacote
from praticagem_snapshot import construir_snapshot


def comparar(antes: dict, depois: dict) -> dict:
    primeira = normalizar_captura(antes)
    segunda = normalizar_captura(depois)
    base = construir_snapshot(primeira, {})
    imos = {o["imo"] for o in primeira["observacoes"] + segunda["observacoes"]}
    estados_base, _ = montar_pacote(base, imos, {}, [])
    anteriores = {e["imo"]: e for e in estados_base}
    atual = construir_snapshot(segunda, anteriores)
    _, eventos = montar_pacote(atual, imos, anteriores, [])
    por_campo = Counter(m["campo"] for e in eventos for m in e["mudancas"])
    return {"navios_observados": len(imos), "eventos": len(eventos),
            "mudancas_por_campo": dict(por_campo),
            "linhas_sem_imo": len(primeira["ignorados"]) + len(segunda["ignorados"])}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara duas capturas da Praticagem")
    parser.add_argument("--antes", type=Path, required=True)
    parser.add_argument("--depois", type=Path, required=True)
    args = parser.parse_args()
    antes = json.loads(args.antes.read_text(encoding="utf-8"))
    depois = json.loads(args.depois.read_text(encoding="utf-8"))
    print(json.dumps(comparar(antes, depois), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
