import unittest
from unittest.mock import MagicMock, patch

from praticagem_portal import (SessaoPraticagem, TABELAS, capturar_tabelas,
                              TEMPO_ABERTURA_NAVEGADOR_MS,
                              cabecalhos_correspondem, validar_tabela)


class PortalPraticagemTest(unittest.TestCase):
    def test_releitura_aguarda_conteudo_apos_inicio_da_navegacao(self):
        sessao = SessaoPraticagem("usuario", "senha")
        sessao.page = MagicMock()
        sessao._iniciada = True
        sessao.page.get_by_placeholder.return_value.is_visible.return_value = False
        with patch("praticagem_portal.capturar_tabelas",
                   return_value={nome: [] for nome in TABELAS}) as ler:
            resultado = sessao.capturar()
        sessao.page.reload.assert_called_once_with(
            wait_until="commit", timeout=30000)
        ler.assert_called_once()
        self.assertEqual(resultado["quantidades"], {nome: 0 for nome in TABELAS})

    def test_captura_usa_uma_leitura_do_dom_e_valida_as_quatro_tabelas(self):
        page = MagicMock()
        amostras = []
        for nome, (_, campos) in TABELAS.items():
            cabecalhos = sorted(campos)
            amostras.append({"cabecalhos": cabecalhos,
                             "linhas": [{"celulas": ["x"] * len(cabecalhos),
                                         "cor": "rgb(255, 255, 255)"}]})
        page.evaluate.return_value = amostras
        tabelas = capturar_tabelas(page)
        page.evaluate.assert_called_once()
        self.assertEqual(set(tabelas), set(TABELAS))
        self.assertTrue(all(len(linhas) == 1 for linhas in tabelas.values()))
        page.evaluate.return_value = amostras[:-1]
        with self.assertRaisesRegex(ValueError, "fundeados"):
            capturar_tabelas(page)

    def test_abertura_do_edge_tem_prazo_limitado(self):
        self.assertEqual(TEMPO_ABERTURA_NAVEGADOR_MS, 60000)

    def test_cabecalhos_e_cor_de_movimento_obrigatorios(self):
        cabecalhos = ["IMO", "NAVIO", "MV", "LOC#1", "LOC#2", "POB",
                      "PASSAG", "CALADO", "AGENTE", "BORDO", "TUG"]
        linha = {"celulas": dict.fromkeys(cabecalhos, "x"),
                 "cor": "rgb(255, 255, 255)"}
        validar_tabela("movimentos", cabecalhos, [linha])
        with self.assertRaisesRegex(ValueError, "Cor"):
            validar_tabela("movimentos", cabecalhos, [{**linha, "cor": None}])
        with self.assertRaisesRegex(ValueError, "Cabeçalhos"):
            validar_tabela("movimentos", cabecalhos[:-1], [])
        with self.assertRaisesRegex(ValueError, "inesperados"):
            validar_tabela("previstas", cabecalhos, [])
        self.assertFalse(cabecalhos_correspondem("previstas", cabecalhos))
        self.assertTrue(cabecalhos_correspondem("movimentos", cabecalhos))

    def test_quatro_tabelas_tem_esquemas_distintos(self):
        validar_tabela("atracados", ["IMO", "NAVIO", "LOCAL"], [])
        validar_tabela("fundeados", ["IMO", "NAVIO", "FUNDEIO"], [])
        validar_tabela("previstas", ["IMO", "NAVIO", "MV", "LOC#1", "LOC#2",
                                     "AGENTE", "BORDO", "TUG"], [])


if __name__ == "__main__":
    unittest.main()
