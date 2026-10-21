import unittest
from unittest.mock import Mock, patch
from praticagem_portal import capturar_tabelas_com_retentativa

class RetentativaTest(unittest.TestCase):
    def test_recupera_tabela_que_carregou_depois(self):
        page = Mock()
        with patch("praticagem_portal.capturar_tabelas", side_effect=[
            ValueError("Tabela movimentos: 0 correspondências"), {"movimentos": []}]):
            self.assertEqual(capturar_tabelas_com_retentativa(page), {"movimentos": []})
        page.wait_for_timeout.assert_called_once_with(1500)

    def test_tabela_ausente_persistente_nao_vira_coleta_vazia(self):
        page = Mock()
        with patch("praticagem_portal.capturar_tabelas", side_effect=
                   ValueError("Tabela movimentos: 0 correspondências")) as ler:
            with self.assertRaises(ValueError):
                capturar_tabelas_com_retentativa(page)
            self.assertEqual(ler.call_count, 3)

    def test_ambiguidade_nao_e_repetida(self):
        with patch("praticagem_portal.capturar_tabelas", side_effect=
                   ValueError("Tabela movimentos: 2 correspondências")) as ler:
            with self.assertRaises(ValueError):
                capturar_tabelas_com_retentativa(Mock())
            self.assertEqual(ler.call_count, 1)
