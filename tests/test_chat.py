import unittest
from unittest.mock import MagicMock, patch

from chat import processar_chat


class ChatTest(unittest.TestCase):
  @patch("chat.montar_visao_monitorados")
  @patch("chat.eh_administrador", return_value=False)
  def test_resumo_inclui_navio_indisponivel_e_data(self, _, montar):
    montar.return_value = [
        {"nome": "NAVIO A", "ultima_consulta": "2026-09-21T12:00:00Z"},
        {"nome": "NAVIO B", "situacao": "indisponivel"},
    ]
    resposta = processar_chat(self.cliente, "5513999999999", "résumo")
    self.assertIn("NAVIO A", resposta)
    self.assertIn("NAVIO B", resposta)
    self.assertIn("21/09/2026", resposta)
    self.assertIn("Dados indisponíveis", resposta)
    self.assertIn("última coleta", resposta)

  @patch("chat.definir_relatorio")
  @patch("chat.eh_administrador", return_value=False)
  def test_assinar_e_parar_nao_cancelam_operacao(self, _, definir):
    processar_chat(self.cliente, "5513999999999", "Assinar")
    definir.assert_called_with(self.cliente, "5513999999999", True)
    processar_chat(self.cliente, "5513999999999", "Parar")
    definir.assert_called_with(self.cliente, "5513999999999", False)

  @patch("chat.montar_visao_monitorados", return_value=[])
  @patch("chat.eh_administrador", return_value=False)
  def test_lista_alias_e_resumo_vazio(self, _, montar):
    self.assertEqual(
        processar_chat(self.cliente, "5513999999999", "Lista"),
        processar_chat(self.cliente, "5513999999999", "Listar monitorados"),
    )
    self.assertIn("Lista de monitoramento vazia", processar_chat(self.cliente, "5513999999999", "Resumo"))

  def setUp(self):
    self.cliente = MagicMock()

  @patch("chat.eh_administrador", return_value=False)
  def test_usuario_comum_nao_pode_adicionar(self, _):
    resposta = processar_chat(self.cliente, "5513999999999", "Adicionar: NAVIO A")
    self.assertIn("administradores", resposta)

  @patch("chat.eh_administrador", return_value=False)
  def test_usuario_comum_nao_pode_remover(self, _):
    resposta = processar_chat(self.cliente, "5513999999999", "Remover: NAVIO A")
    self.assertIn("administradores", resposta)

  @patch("chat.definir_relatorio")
  @patch("chat.eh_administrador", return_value=False)
  def test_usuario_pode_assinar_relatorio(self, _, definir):
    resposta = processar_chat(self.cliente, "5513999999999", "Receber relatorio")
    definir.assert_called_once_with(self.cliente, "5513999999999", True)
    self.assertIn("Inscrição realizada", resposta)

  @patch("chat.montar_visao_monitorados")
  @patch("chat.eh_administrador", return_value=False)
  def test_consulta_retorna_apenas_visao_monitorada(self, _, montar):
    montar.return_value = [{"nome": "NAVIO A", "imo": "111", "situacao": "atualizado"}]
    resposta = processar_chat(self.cliente, "5513999999999", "NAVIO A")
    self.assertIn("🚢 *NAVIO A*", resposta)
    self.assertIn("*IMO:* 111", resposta)

  @patch("chat.preparar_remocao")
  @patch("chat.eh_administrador", return_value=True)
  def test_remocao_exige_confirmacao(self, _, preparar):
    preparar.return_value = {"selecionados": ["NAVIO A"], "nao_encontrados": []}
    resposta = processar_chat(self.cliente, "5513999999999", "Remover: NAVIO A")
    self.assertIn("Posso remover", resposta)
    self.assertIn("*Confirmar*", resposta)

  @patch("chat.eh_administrador", return_value=True)
  def test_ajuda_do_admin_exibe_comandos_de_gestao(self, _):
    resposta = processar_chat(self.cliente, "5513999999999", "ajuda")
    self.assertIn("Adicionar NOME", resposta)
    self.assertIn("Remover NOME", resposta)


if __name__ == "__main__":
  unittest.main()
