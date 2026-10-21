import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from atualizacao_chat import dividir, processar_fila
from atualizacao_chat import diagnostico_seguro
from chat import processar_chat


class AtualizacaoTest(unittest.TestCase):
  @patch("builtins.print")
  def test_diagnostico_preserva_codigo_sem_expor_corpo(self, imprimir):
    import requests
    resposta = requests.Response()
    resposta.status_code = 401
    resposta._content = b'{"error":{"code":190,"message":"TOKEN-SECRETO 5513999999999"}}'
    causa = requests.HTTPError(response=resposta)
    erro = RuntimeError("TOKEN-SECRETO")
    erro.__cause__ = causa
    diagnostico_seguro(erro, "enviar_whatsapp")
    saida = imprimir.call_args.args[0]
    self.assertIn('"code": 190', saida)
    self.assertIn('"http_status": 401', saida)
    self.assertNotIn("TOKEN-SECRETO", saida)
    self.assertNotIn("5513999999999", saida)

  @patch.dict("os.environ", {"GH_ACTIONS_TOKEN": "segredo-teste"})
  @patch("requests.post")
  def test_disparo_usa_workflow_fixo(self, post):
    from atualizacao_chat import disparar_github
    post.return_value.status_code = 204
    self.assertTrue(disparar_github())
    self.assertTrue(post.call_args.args[0].endswith("/atualizar-chat.yml/dispatches"))
    self.assertEqual(post.call_args.kwargs["json"], {"ref": "main"})
    self.assertFalse(post.call_args.kwargs["allow_redirects"])

  @patch.dict("os.environ", {"GH_ACTIONS_TOKEN": "segredo-teste"})
  @patch("requests.post")
  def test_disparo_falha_sem_expor_token(self, post):
    from atualizacao_chat import disparar_github
    import requests
    post.side_effect = requests.Timeout("segredo-teste")
    with patch("builtins.print") as imprimir:
      self.assertFalse(disparar_github())
    self.assertNotIn("segredo-teste", str(imprimir.call_args_list))

  @patch("atualizacao_chat.disparar_github", return_value=False)
  def test_fila_persistida_antes_do_disparo_e_preservada(self, disparar):
    from atualizacao_chat import solicitar
    cliente = MagicMock()
    def conferir():
      cliente.rpc.return_value.execute.assert_called_once()
      return False
    disparar.side_effect = conferir
    self.assertIn("Pedido registrado", solicitar(cliente, "5513111111111"))
    cliente.table.assert_not_called()

  @patch("atualizacao_chat.disparar_github")
  def test_falha_fila_nao_dispara(self, disparar):
    from atualizacao_chat import solicitar
    cliente = MagicMock()
    cliente.rpc.return_value.execute.side_effect = RuntimeError("banco")
    with self.assertRaises(RuntimeError):
      solicitar(cliente, "5513111111111")
    disparar.assert_not_called()

  def test_selecao_indisponiveis_nao_inclui_apenas_desatualizados(self):
    from atualizacao_chat import candidatos_indisponiveis
    navios = [
      {"lista_monitoramento_id":1,"nome":"A","situacao":"indisponivel"},
      {"lista_monitoramento_id":2,"nome":"B","situacao":"desatualizado"},
      {"lista_monitoramento_id":3,"nome":"C","situacao":"atualizado"},
    ]
    self.assertEqual(candidatos_indisponiveis(navios), [{"id":1,"nome":"A"}])

  @patch("atualizacao_chat.oferecer_remocao")
  def test_pergunta_somente_depois_de_todas_as_paginas(self, oferecer):
    item={"telefone":"5513111111111","solicitado_em":"2026-09-21T12:00:00Z","proxima_pagina":0}
    cliente=self.cliente({"id":"lote","estado":"pronto","paginas":["um","dois"]},[item])
    enviar=MagicMock()
    oferecer.side_effect=lambda *args: self.assertEqual(enviar.call_count,2)
    processar_fila(cliente,MagicMock(),enviar,datetime(2026,9,21,12,1,tzinfo=timezone.utc))
    oferecer.assert_called_once()

  @patch("atualizacao_chat.oferecer_remocao")
  def test_nao_pergunta_se_envio_do_resumo_falhar(self, oferecer):
    item={"telefone":"5513111111111","solicitado_em":"2026-09-21T12:00:00Z","proxima_pagina":0}
    cliente=self.cliente({"id":"lote","estado":"pronto","paginas":["um"]},[item])
    with self.assertRaises(RuntimeError):
      processar_fila(cliente,MagicMock(),MagicMock(side_effect=RuntimeError()),datetime(2026,9,21,12,1,tzinfo=timezone.utc))
    oferecer.assert_not_called()

  def test_pergunta_lista_nomes_e_nao_exclui(self):
    from atualizacao_chat import oferecer_remocao
    cliente=MagicMock()
    cliente.rpc.return_value.execute.return_value.data={"ids":[1,2],"nomes":["A","B"]}
    enviar,salvar=MagicMock(),MagicMock()
    oferecer_remocao(cliente,"lote",{"telefone":"5513111111111"},enviar,salvar)
    texto=enviar.call_args.args[1]
    self.assertIn("🚢 *A*",texto)
    self.assertIn("🚢 *B*",texto)
    self.assertIn("Confirmar",texto)
    self.assertIn("Cancelar",texto)
    cliente.table.assert_not_called()
    salvar.assert_called_once_with({"proxima_pergunta":1})

  def cliente(self, lote, destinatarios):
    cliente = MagicMock()
    cliente.rpc.return_value.execute.return_value.data = [lote] if lote else []
    consulta = cliente.table.return_value.select.return_value
    consulta.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = destinatarios
    return cliente

  def test_fila_vazia_nao_coleta_nem_envia(self):
    cliente = self.cliente(None, [])
    coletar, enviar = MagicMock(), MagicMock()
    processar_fila(cliente, coletar, enviar)
    coletar.assert_not_called()
    enviar.assert_not_called()

  @patch("atualizacao_chat.preparar_resultado", return_value=(["resultado"], "sucesso"))
  def test_um_lote_atende_dois_solicitantes(self, preparar):
    cliente = self.cliente({"id": "lote", "estado": "executando"}, [
      {"telefone": n, "solicitado_em": "2026-09-21T12:00:00Z", "proxima_pagina": 0}
      for n in ["5513111111111", "5513222222222"]
    ])
    enviar = MagicMock()
    processar_fila(cliente, MagicMock(), enviar, datetime(2026,9,21,12,1,tzinfo=timezone.utc))
    preparar.assert_called_once()
    self.assertEqual(enviar.call_count, 2)

  def test_retomada_nao_repete_coleta_nem_pagina_aceita(self):
    cliente = self.cliente({"id": "lote", "estado": "pronto", "paginas": ["um", "dois"]}, [
      {"telefone": "5513111111111", "solicitado_em": "2026-09-21T12:00:00Z", "proxima_pagina": 1}
    ])
    coletar, enviar = MagicMock(), MagicMock()
    processar_fila(cliente, coletar, enviar, datetime(2026,9,21,12,1,tzinfo=timezone.utc))
    coletar.assert_not_called()
    enviar.assert_called_once_with("5513111111111", "dois")

  @patch("lista_monitoramento.montar_visao_monitorados")
  def test_falha_coleta_nao_apresenta_dados_como_atualizados(self, visao):
    from atualizacao_chat import preparar_resultado
    paginas, resultado = preparar_resultado(MagicMock(), MagicMock(side_effect=RuntimeError("falha")))
    self.assertEqual(resultado, "falha")
    self.assertIn("desatualizados", paginas[0])
    visao.assert_not_called()

  def test_expirado_nao_envia_texto_fora_da_janela(self):
    cliente = self.cliente({"id": "lote", "estado": "pronto", "paginas": ["um"]}, [
      {"telefone": "5513111111111", "solicitado_em": "2026-09-20T12:00:00Z", "proxima_pagina": 0}
    ])
    enviar = MagicMock()
    processar_fila(cliente, MagicMock(), enviar, datetime(2026,9,21,12,1,tzinfo=timezone.utc))
    enviar.assert_not_called()

  def test_paginas_sem_perda(self):
    texto = ("NAVIO 🚢\n" * 2000)
    partes = dividir(texto)
    self.assertEqual("".join(p.split("\n\n", 1)[1] for p in partes), texto)
    self.assertTrue(all(len(p) <= 4096 for p in partes))

  def test_falha_entrega_preserva_lote_para_retomada(self):
    cliente = self.cliente({"id": "lote", "estado": "pronto", "paginas": ["um"]}, [
      {"telefone": "5513111111111", "solicitado_em": "2026-09-21T12:00:00Z", "proxima_pagina": 0}
    ])
    with self.assertRaises(RuntimeError):
      processar_fila(cliente, MagicMock(), MagicMock(side_effect=RuntimeError("rede")),
                     datetime(2026,9,21,12,1,tzinfo=timezone.utc))
    alteracoes = [c.args[0] for c in cliente.table.return_value.update.call_args_list]
    self.assertFalse(any(d.get("estado") == "concluido" for d in alteracoes))
    self.assertIn({"reserva_ate": None}, alteracoes)

  @patch("chat.eh_administrador", return_value=False)
  @patch("atualizacao_chat.solicitar")
  def test_usuario_comum_nao_enfileira(self, solicitar, admin):
    resposta = processar_chat(MagicMock(), "5513111111111", "Atualizar")
    self.assertIn("administradores", resposta)
    solicitar.assert_not_called()

  @patch.dict("os.environ", {"ATUALIZACAO_CHAT_ATIVA": "false"})
  @patch("chat.eh_administrador", return_value=True)
  @patch("atualizacao_chat.solicitar")
  def test_desativado_nao_enfileira(self, solicitar, admin):
    self.assertIn("Atualização temporariamente indisponível", processar_chat(MagicMock(), "5513111111111", "Atualizar"))
    solicitar.assert_not_called()

  @patch.dict("os.environ", {"ATUALIZACAO_CHAT_ATIVA": "true"})
  @patch("chat.eh_administrador", return_value=True)
  @patch("atualizacao_chat.solicitar", return_value="Atualizacao solicitada")
  def test_admin_enfileira(self, solicitar, admin):
    cliente = MagicMock()
    processar_chat(cliente, "5513111111111", "Atualizar")
    solicitar.assert_called_once_with(cliente, "5513111111111")


if __name__ == "__main__":
  unittest.main()
