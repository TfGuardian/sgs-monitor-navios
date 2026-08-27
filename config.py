import os

import truststore
from dotenv import load_dotenv
from supabase import Client, create_client

# Usa os certificados confiaveis do Windows (inclusive certificados
# corporativos) em vez de desativar a verificacao HTTPS.
truststore.inject_into_ssl()
load_dotenv()


def _obrigatoria(nome: str) -> str:
  valor = os.getenv(nome, "").strip()
  if not valor:
    raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {nome}")
  return valor


SUPABASE_URL = _obrigatoria("SUPABASE_URL")
SUPABASE_KEY = _obrigatoria("SUPABASE_KEY")
APS_URL = os.getenv(
    "APS_URL",
    "https://www.portodesantos.com.br/"
    "painel-de-monitoramento-das-operacoes-portuarias/",
).strip()
PRATICAGEM_URL = os.getenv("PRATICAGEM_URL", "").strip()


def criar_supabase() -> Client:
  return create_client(SUPABASE_URL, SUPABASE_KEY)
