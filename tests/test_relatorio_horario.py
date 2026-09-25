import unittest
from unittest.mock import MagicMock, patch
import re
import requests
import json
from pathlib import Path

from relatorio_horario import MODELO, preparar_paginas, processar
from relatorio import montar_relatorio


class HorarioTest(unittest.TestCase):
  def test_modelo_para_aprovacao_corresponde_ao_codigo(self):
    raiz = Path(__file__).resolve().parents[1]
    modelo = json.loads((raiz / 'templates/relatorio_horario_navios_v2.json').read_text(encoding='utf-8'))
    self.assertEqual(modelo['components'][0]['text'], MODELO)
    self.assertEqual(len(modelo['components'][0]['example']['body_text'][0]), 12)

  def test_lista_completa_impar_e_datas_por_status(self):
    navios = [{"nome": f"NAVIO {i}", "situacao": "atualizado", "evento": "FUNDEADO",
               "local": "ULTRAF - 16/17", "etb": "25/09/2026 07:00/13:00"} for i in range(5)]
    navios[0]["evento"] = "ATRACADO"
    navios[1]["situacao"] = "indisponivel"
    paginas = preparar_paginas(navios)
    self.assertEqual(len(paginas), 3)
    for i in range(5):
      self.assertEqual(sum(p.count(f"NAVIO {i}") for p in paginas), 1)
    self.assertIn("Já atracado", paginas[0][6])
    self.assertEqual(paginas[0][9:12], ["—", "—", "—"])
    self.assertEqual(paginas[1][4], "Tiplam - 16/17")
    self.assertIn("25/09/2026", paginas[1][6])
    for pagina in paginas:
      self.assertEqual(len(pagina), 12)
      self.assertTrue(all('\n' not in v for v in pagina))
      self.assertLessEqual(len(re.sub(r'\{\{(\d+)\}\}', lambda m: pagina[int(m[1])-1], MODELO)), 1024)

  def test_vazio_e_excesso_sem_truncamento(self):
    self.assertEqual(len(preparar_paginas([])), 1)
    with self.assertRaises(ValueError):
      preparar_paginas([{"nome": "X" * 1500}])

  def test_paginacao_texto_inclui_rodape_e_divide_bloco_grande(self):
    navios = [{"nome": "NAVIO", "evento": "X" * 1400, "situacao": "atualizado"}]
    paginas = montar_relatorio(navios, limite=300)
    self.assertTrue(all(len(p) <= 300 for p in paginas))
    self.assertEqual(sum(p.count('X') for p in paginas), 1400)

  def cliente(self):
    cliente = MagicMock()
    lote = {"id": "lote", "reserva_token": "token", "paginas": [["dados"]]}
    def rpc(nome, dados):
      valor = {"reservar_relatorio_horario": [lote],
               "listar_entregas_horarias": [{"id": "entrega", "telefone": "5513111111111", "parametros": ["dados"]}],
               "iniciar_entrega_horaria": True,
               "concluir_relatorio_horario": 0}.get(nome)
      return MagicMock(execute=lambda: MagicMock(data=valor))
    cliente.rpc.side_effect = rpc
    return cliente

  def test_retomada_nao_coleta_novamente_e_salva_id(self):
    cliente, coletar, enviar = self.cliente(), MagicMock(), MagicMock(return_value="wamid.1")
    processar(cliente, coletar, enviar)
    coletar.assert_not_called()
    chamadas = [c.args for c in cliente.rpc.call_args_list]
    fim = next(c[1] for c in chamadas if c[0] == 'finalizar_entrega_horaria')
    self.assertEqual(fim['mensagem'], 'wamid.1')
    self.assertEqual(chamadas[-1][0], 'liberar_relatorio_horario')

  def test_timeout_nao_e_rejeicao_confirmada(self):
    cliente = self.cliente()
    with self.assertRaises(RuntimeError):
      processar(cliente, MagicMock(), MagicMock(side_effect=requests.Timeout()))
    fim = next(c.args[1] for c in cliente.rpc.call_args_list if c.args[0] == 'finalizar_entrega_horaria')
    self.assertEqual(fim['resultado'], 'incerto')

  def test_falha_coleta_nao_envia_dados_antigos(self):
    cliente = self.cliente()
    original = cliente.rpc.side_effect
    def rpc(nome, dados):
      if nome == 'reservar_relatorio_horario':
        return MagicMock(execute=lambda: MagicMock(data=[{'id':'lote','reserva_token':'token','paginas':None}]))
      return original(nome, dados)
    cliente.rpc.side_effect = rpc
    enviar = MagicMock()
    with self.assertRaises(RuntimeError):
      processar(cliente, MagicMock(side_effect=RuntimeError('fonte indisponivel')), enviar)
    enviar.assert_not_called()
    self.assertEqual(cliente.rpc.call_args.args[0], 'liberar_relatorio_horario')

  def test_rejeicao_http_marca_falha(self):
    resposta = requests.Response()
    resposta.status_code = 429
    cliente = self.cliente()
    with self.assertRaises(RuntimeError):
      processar(cliente, MagicMock(), MagicMock(side_effect=requests.HTTPError(response=resposta)))
    fim = next(c.args[1] for c in cliente.rpc.call_args_list if c.args[0] == 'finalizar_entrega_horaria')
    self.assertEqual(fim['resultado'], 'falha')

  @patch.dict('os.environ', {'META_ACCESS_TOKEN':'TESTE', 'META_PHONE_NUMBER_ID':'ID',
                           'META_REPORT_TEMPLATE_NAME':'modelo'})
  @patch('whatsapp.requests.post')
  def test_payload_template_sem_cortar_e_com_correlacao(self, post):
    from whatsapp import enviar_modelo_relatorio
    post.return_value.json.return_value = {'messages':[{'id':'wamid.1'}]}
    parametros = preparar_paginas([{'nome':'NAVIO A'}])[0]
    self.assertEqual(enviar_modelo_relatorio('5513111111111',parametros,'uuid'), 'wamid.1')
    payload = post.call_args.kwargs['json']
    self.assertEqual(payload['biz_opaque_callback_data'], 'relatorio_horario:uuid')
    self.assertEqual([p['text'] for p in payload['template']['components'][0]['parameters']], parametros)


if __name__ == '__main__':
  unittest.main()
