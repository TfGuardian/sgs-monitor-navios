import io
import pandas as pd
import requests
import urllib3
from supabase import Client, create_client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURAÇÕES DO SUPABASE ---
SUPABASE_URL = "https://tshgnkpzzlorwiyrotnr.supabase.co"
SUPABASE_KEY = "sb_publishable_gm8CfcTl9cr8knkq8ZKOqQ_7DzecS-R"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

URL_PRATICAGEM = "https://www.portodesantos.com.br/informacoes-operacionais/operacoes-portuarias/navegacao-e-movimento-de-navios/atracacoes-programadas/"

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


def processar_praticagem():
  print("🔎 Buscando dados de manobras na Santos Pilots (Praticagem)...")
  try:
    response = requests.get(URL_PRATICAGEM, headers=HEADERS, verify=False)
    if response.status_code != 200:
      print(f"⚠️ Erro ao acessar Praticagem: Status {response.status_code}")
      return

    tabelas = pd.read_html(io.StringIO(response.text))
    if not tabelas:
      print("⚠️ Nenhuma tabela de manobra encontrada na Praticagem.")
      return

    df = tabelas[0]
    df.columns = [str(c).strip() for c in df.columns]

    col_navio = buscar_coluna(df, ["navio", "vessel", "nome"])
    col_manobra = buscar_coluna(df, ["manobra", "tipo", "evento"])
    col_data_hora = buscar_coluna(df, ["data", "hora", "horario", "pob"])
    col_local = buscar_coluna(df, ["local", "berço", "berco"])

    if not col_navio:
      print("❌ Coluna de navios não encontrada na tabela da Praticagem.")
      return

    # Limpeza do nome do navio para comparação
    df["navio_limpo"] = (
        df[col_navio]
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.upper()
    )

    # Busca navios ativos cadastrados no Supabase
    res = supabase.table("navios_monitorados").select("imo, nome").execute()
    navios_cadastrados = res.data

    for navio in navios_cadastrados:
      nome_busca = navio["nome"].strip().upper()
      resultado = df[df["navio_limpo"].str.contains(nome_busca, na=False)]

      if not resultado.empty:
        for _, row in resultado.iterrows():
          manobra = (
              str(row.get(col_manobra, "N/A")).strip() if col_manobra else "N/A"
          )
          horario = (
              str(row.get(col_data_hora, "N/A")).strip()
              if col_data_hora
              else "N/A"
          )
          local = str(row.get(col_local, "N/A")).strip() if col_local else "N/A"

          # Atualiza os dados de praticagem mantendo o registro do navio
          dados_atualizados = {
              "evento": f"Praticagem: {manobra}",
              "eta": horario,
              "local": local,
              "fonte": "SANTOS_PILOTS",
          }

          supabase.table("navios_monitorados").update(
              dados_atualizados
          ).eq("imo", navio["imo"]).execute()
          print(
              f"✅ Manobra da Praticagem atualizada para {navio['nome']}:"
              f" {manobra} às {horario}"
          )

  except Exception as e:
    print(f"❌ Erro na execução da Praticagem: {e}")


if __name__ == "__main__":
  processar_praticagem()