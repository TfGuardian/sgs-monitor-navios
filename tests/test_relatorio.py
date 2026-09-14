import unittest

from relatorio import montar_relatorio


class RelatorioTest(unittest.TestCase):
  def test_relatorio_agrupa_todos_os_navios(self):
    paginas = montar_relatorio([
        {"nome": "NAVIO A", "situacao": "atualizado"},
        {"nome": "NAVIO B", "situacao": "indisponivel"},
    ])
    texto = "\n".join(paginas)
    self.assertIn("NAVIO A", texto)
    self.assertIn("NAVIO B", texto)

  def test_relatorio_longo_e_dividido_em_partes(self):
    paginas = montar_relatorio([
        {"nome": f"NAVIO {indice}", "evento": "OPERACAO " * 8,
         "situacao": "atualizado"}
        for indice in range(1, 8)
    ], limite=300)
    self.assertGreater(len(paginas), 1)
    self.assertTrue(all("Parte" in pagina for pagina in paginas))


if __name__ == "__main__":
  unittest.main()
