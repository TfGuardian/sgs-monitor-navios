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
SUPABASE_SECRET_KEY = (
    os.getenv("SUPABASE_SECRET_KEY", "").strip()
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
)
APS_URL = os.getenv(
    "APS_URL",
    "https://www.portodesantos.com.br/"
    "painel-de-monitoramento-das-operacoes-portuarias/",
).strip()
ATRACACOES_PROGRAMADAS_URL = os.getenv(
    "ATRACACOES_PROGRAMADAS_URL",
    "https://www.portodesantos.com.br/informacoes-operacionais/"
    "operacoes-portuarias/navegacao-e-movimento-de-navios/"
    "atracacoes-programadas/",
).strip()
ATRACADOS_URL = os.getenv(
    "ATRACADOS_URL",
    "https://www.portodesantos.com.br/informacoes-operacionais/"
    "operacoes-portuarias/navegacao-e-movimento-de-navios/"
    "atracados-porto-terminais/",
).strip()
PRATICAGEM_URL = os.getenv("PRATICAGEM_URL", "").strip()


def criar_supabase(administrativo: bool = False) -> Client:
  chave = SUPABASE_KEY
  if administrativo:
    chave = SUPABASE_SECRET_KEY
    if not chave:
      raise RuntimeError(
          "Configuracao administrativa ausente: SUPABASE_SECRET_KEY"
      )
  return create_client(SUPABASE_URL, chave)
