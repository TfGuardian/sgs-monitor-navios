import unittest
from unittest.mock import MagicMock, patch
from chat import processar_chat

@patch("chat.eh_administrador", return_value=False)
class NumeroTest(unittest.TestCase):
  def cliente(self, itens):
    c = MagicMock()
    c.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"itens":itens}] if itens is not None else []
    return c

  @patch("chat.montar_visao_monitorados")
  def test_ordem_salva_e_dados_atuais(self, visao, _):
    c = self.cliente([20,10])
    visao.return_value = [{"lista_monitoramento_id":10,"nome":"A"}, {"lista_monitoramento_id":20,"nome":"B","situacao":"atualizado","evento":"ATRACADO"}]
    texto = processar_chat(c,"+55 13 999999999","1")
    self.assertIn("*B*",texto)
    self.assertIn("Atracado",texto)
    c.table.return_value.select.return_value.eq.assert_called_once_with("telefone","5513999999999")

  def test_sem_lista_e_fora_do_intervalo(self, _):
    self.assertIn("Lista necessária",processar_chat(self.cliente(None),"1","2"))
    for entrada in ["0","3","999999"]:
      self.assertIn("Número fora",processar_chat(self.cliente([10,20]),"1",entrada))

  @patch("chat.montar_visao_monitorados", return_value=[])
  def test_removido_nao_redireciona(self, visao, _):
    self.assertIn("não está mais",processar_chat(self.cliente([20]),"1","1"))

  @patch("chat.montar_visao_monitorados", return_value=[{"lista_monitoramento_id":10,"nome":"A","imo":"1234567"}])
  def test_imo_preservado(self, visao, _):
    c=self.cliente([20])
    self.assertIn("*A*",processar_chat(c,"1","1234567"))
    c.table.assert_not_called()

  @patch("chat.montar_visao_monitorados", return_value=[{"lista_monitoramento_id":20,"nome":"B"},{"lista_monitoramento_id":10,"nome":"A"}])
  def test_lista_persiste_ordem_exibida(self, visao, _):
    c=self.cliente(None)
    texto=processar_chat(c,"+55 13","Lista")
    self.assertIn("1. *B*",texto)
    self.assertEqual(c.table.return_value.upsert.call_args.args[0]["itens"],[20,10])
