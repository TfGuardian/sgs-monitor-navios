import io
from typing import Any, cast

import pandas as pd

from config import PRATICAGEM_URL, criar_supabase
from monitor_aps import HEADERS, TIMEOUT, _sessao_http, buscar_coluna, normalizar_texto

supabase = criar_supabase()
Registro = dict[str, Any]


def processar_praticagem(dry_run: bool = False) -> list[Registro]:
  if not PRATICAGEM_URL:
    print("Praticagem ignorada: configure PRATICAGEM_URL com endpoint autorizado.")
    return []
  response = _sessao_http().get(PRATICAGEM_URL, headers=HEADERS, timeout=TIMEOUT)
  response.raise_for_status()
  try:
    tabelas = pd.read_html(io.StringIO(response.text))
  except ValueError as exc:
    raise RuntimeError("A Praticagem nao retornou tabelas HTML") from exc
  resposta = supabase.table("navios_monitorados").select("*").execute()
  monitorados = cast(list[Registro], resposta.data or [])
  alterados: list[Registro] = []
  for df in tabelas:
    df.columns = [str(c).strip() for c in df.columns]
    col_navio = buscar_coluna(df, ["navio", "vessel", "nome"])
    if col_navio is None:
      continue
    col_manobra = buscar_coluna(df, ["manobra", "tipo", "evento"])
    col_horario = buscar_coluna(df, ["data", "hora", "horario", "pob"])
    col_local = buscar_coluna(df, ["local", "berco"])
    for navio in monitorados:
      nome = normalizar_texto(navio.get("nome", ""))
      linhas = df[df[col_navio].map(normalizar_texto) == nome]
      for _, row in linhas.iterrows():
        manobra = str(row.get(col_manobra, "N/A")).strip() if col_manobra else "N/A"
        horario = str(row.get(col_horario, "N/A")).strip() if col_horario else "N/A"
        local = str(row.get(col_local, "N/A")).strip() if col_local else "N/A"
        dados = {"evento": f"Praticagem: {manobra}", "eta": horario,
                 "local": local, "fonte": "SANTOS_PILOTS"}
        if all(navio.get(k) == v for k, v in dados.items()):
          continue
        if dry_run:
          alterados.append({**navio, **dados})
          print(f"[SIMULACAO] Praticagem alteraria {navio['nome']}")
          continue
        consulta = supabase.table("navios_monitorados").update(dados)
        imo = navio.get("imo")
        consulta = (consulta.eq("imo", imo) if imo and imo != "N/A"
                    else consulta.eq("nome", navio["nome"]))
        resultado = consulta.execute()
        atualizados = cast(list[Registro], resultado.data or [])
        alterados.extend(atualizados or [{**navio, **dados}])
        print(f"Praticagem atualizada para {navio['nome']}: {manobra}")
  return alterados


if __name__ == "__main__":
  processar_praticagem()
