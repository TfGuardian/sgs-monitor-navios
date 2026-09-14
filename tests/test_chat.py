import unittest
from unittest.mock import MagicMock, patch

from chat import processar_chat


class ChatTest(unittest.TestCase):
  def setUp(self):
    self.cliente = MagicMock()

  @patch("chat.eh_administrador", return_value=False)
  def test_usuario_comum_nao_pode_adicionar(self, _):
    resposta = processar_chat(self.cliente, "5513999999999", "Adicionar: NAVIO A")
    self.assertIn("nao possui permissao", resposta)

  @patch("chat.eh_administrador", return_value=False)
  def test_usuario_comum_nao_pode_remover(self, _):
    resposta = processar_chat(self.cliente, "5513999999999", "Remover: NAVIO A")
    self.assertIn("nao possui permissao", resposta)

  @patch("chat.definir_relatorio")
  @patch("chat.eh_administrador", return_value=False)
  def test_usuario_pode_assinar_relatorio(self, _, definir):
    resposta = processar_chat(self.cliente, "5513999999999", "Receber relatorio")
    definir.assert_called_once_with(self.cliente, "5513999999999", True)
    self.assertIn("Inscricao realizada", resposta)

  @patch("chat.montar_visao_monitorados")
  @patch("chat.eh_administrador", return_value=False)
  def test_consulta_retorna_apenas_visao_monitorada(self, _, montar):
    montar.return_value = [{"nome": "NAVIO A", "imo": "111", "situacao": "atualizado"}]
    resposta = processar_chat(self.cliente, "5513999999999", "NAVIO A")
    self.assertIn("Nome: NAVIO A", resposta)
    self.assertIn("IMO: 111", resposta)

  @patch("chat.preparar_remocao")
  @patch("chat.eh_administrador", return_value=True)
  def test_remocao_exige_confirmacao(self, _, preparar):
    preparar.return_value = {"selecionados": ["NAVIO A"], "nao_encontrados": []}
    resposta = processar_chat(self.cliente, "5513999999999", "Remover: NAVIO A")
    self.assertIn("Confirma a remocao", resposta)
    self.assertIn("Responda SIM", resposta)

  @patch("chat.eh_administrador", return_value=True)
  def test_ajuda_do_admin_exibe_comandos_de_gestao(self, _):
    resposta = processar_chat(self.cliente, "5513999999999", "ajuda")
    self.assertIn("Adicionar:", resposta)
    self.assertIn("Remover:", resposta)


if __name__ == "__main__":
  unittest.main()
