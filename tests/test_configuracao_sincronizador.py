import unittest
from unittest.mock import MagicMock, patch

from sincronizador import sincronizar


class ConfiguracaoSincronizadorTest(unittest.TestCase):
  @patch("lista_monitoramento.carregar_lista")
  @patch("config.criar_supabase")
  def test_simulacao_usa_cliente_administrativo_para_ler_lista_protegida(
      self, criar_supabase, carregar_lista
  ):
    cliente = MagicMock()
    criar_supabase.return_value = cliente
    carregar_lista.return_value = []

    sincronizar(dry_run=True)

    criar_supabase.assert_called_once_with(administrativo=True)


if __name__ == "__main__":
  unittest.main()
