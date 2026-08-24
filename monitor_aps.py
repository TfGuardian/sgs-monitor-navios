import io
import pandas as pd
import requests
import urllib3
from supabase import Client, create_client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURAÇÕES DO SUPABASE ---
SUPABASE_URL = "https://tshgnkpzzlorwiyrotnr.supabase.co"
SUPABASE_KEY = "sb_publishable_gm8CfcTl9cr8knkq8ZKOqQ_7DzecS-R"  # Cole sua chave publishable ou secret aqui

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

URL_APS = "https://www.portodesantos.com.br/informacoes-operacionais/operacoes-portuarias/navegacao-e-movimento-de-navios/atracacoes-programadas/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def buscar_coluna(df, palavras_chave):
  for col in df.columns:
    col_str = str(col).lower()
    if any(p.lower() in col_str for p in palavras_chave):
      return col
  return None


def processar_e_salvar_navio(nome_navio):
  print(f"🔎 Conectando na APS e analisando tabela por tabela...\n")
  try:
    response = requests.get(URL_APS, headers=HEADERS, verify=False)
    if response.status_code != 200:
      print(f"⚠️ Erro ao acessar APS: Status {response.status_code}")
      return

    tabelas = pd.read_html(io.StringIO(response.text))
    if not tabelas:
      print("⚠️ Nenhuma tabela encontrada na página.")
      return

    navio_encontrado = False
    termo_busca = nome_navio.strip().upper()

    # Processa cada bloco/tabela da página de forma isolada
    for idx, t in enumerate(tabelas, start=1):
      # Normaliza cabeçalhos da tabela atual
      if isinstance(t.columns, pd.MultiIndex):
        t.columns = [
            " ".join([str(c) for c in col if "Unnamed" not in str(c)]).strip()
            for col in t.columns
        ]
      else:
        t.columns = [str(c).strip() for c in t.columns]

      col_navio = buscar_coluna(t, ["navio", "ship", "burque"])

      # Se a tabela não tiver coluna de navio, pula para a próxima
      if not col_navio:
        continue

      col_imo = buscar_coluna(t, ["imo"])
      col_eta = buscar_coluna(t, ["eta"])
      col_local = buscar_coluna(t, ["local", "place", "lugar"])
      col_carga = buscar_coluna(t, ["carga", "cargo"])
      col_evento = buscar_coluna(t, ["evento", "event"])
      col_duv = buscar_coluna(t, ["duv"])
      col_viagem = buscar_coluna(t, ["viagem", "voyage", "viaje"])

      # Limpa a coluna de navios desta tabela
      t["navio_limpo"] = (
          t[col_navio]
          .astype(str)
          .str.replace(r"\s+", " ", regex=True)
          .str.strip()
          .str.upper()
      )

      resultado = t[t["navio_limpo"].str.contains(termo_busca, na=False)]

      if not resultado.empty:
        navio_encontrado = True
        for _, row in resultado.iterrows():
          dados = {
              "nome": str(row.get(col_navio, "")).strip(),
              "imo": str(row.get(col_imo, "")).strip() if col_imo else "N/A",
              "eta": str(row.get(col_eta, "")).strip() if col_eta else "N/A",
              "local": (
                  str(row.get(col_local, "")).strip() if col_local else "N/A"
              ),
              "carga": (
                  str(row.get(col_carga, "")).strip() if col_carga else "N/A"
              ),
              "evento": (
                  str(row.get(col_evento, "")).strip() if col_evento else "N/A"
              ),
              "viagem": (
                  str(row.get(col_viagem, "")).strip() if col_viagem else "N/A"
              ),
              "duv": str(row.get(col_duv, "")).strip() if col_duv else "N/A",
              "fonte": "APS",
          }

          print(
              f"🎯 NAVIO LOCALIZADO NA TABELA {idx}: {dados['nome']} (IMO:"
              f" {dados['imo']})"
          )

          # Grava/Atualiza no Supabase
          res = (
              supabase.table("navios_monitorados")
              .upsert(dados, on_conflict="imo")
              .execute()
          )
          print("✅ DADOS GRAVADOS COM SUCESSO NO SUPABASE!")
          print(f"📌 Retorno: {res.data}\n")

    if not navio_encontrado:
      print(
          f"❌ O termo '{termo_busca}' não foi encontrado em nenhuma das"
          f" {len(tabelas)} tabelas analisadas."
      )

  except Exception as e:
    print(f"❌ Erro de execução: {e}")


if __name__ == "__main__":
  navio = input("Digite o nome do navio (ex: CAP SAN TAINARO): ")
  processar_e_salvar_navio(navio)