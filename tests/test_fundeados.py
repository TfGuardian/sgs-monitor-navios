import unittest
from unittest.mock import patch
import pandas as pd
from monitor_fundeados import extrair_navios_fundeados
from sincronizador import mesclar_fontes, coletar_catalogo_completo
from consulta_navio import formatar_resumo

class FundeadosTest(unittest.TestCase):
  def test_extracao_sem_inventar_eta(self):
    tabela=pd.DataFrame([['A PROGRAMADO','01/01/2020','T','1']], columns=['Navio Ship','Cheg/Arrival','Terminal','Viagem'])
    registros, ok=extrair_navios_fundeados([tabela])
    self.assertTrue(ok)
    self.assertEqual(registros[0]['nome'],'A')
    self.assertNotIn('eta',registros[0])
    self.assertEqual(registros[0]['viagem'],'1')
    self.assertEqual(extrair_navios_fundeados([pd.DataFrame(columns=['Erro'])]),([],False))
    self.assertEqual(extrair_navios_fundeados([tabela.iloc[0:0]]),([],True))

  def test_fundeado_com_programacao(self):
    r=mesclar_fontes([], [{'nome':'A','etb':'amanhã','evento':'ATRACACAO','viagem':'1'}], [], [{'nome':'A','viagem':'1','local':'T'}])[0]
    self.assertEqual(r['evento'],'FUNDEADO')
    self.assertEqual(r['etb'],'amanhã')
    texto=formatar_resumo(dict(r,situacao='atualizado'))
    self.assertIn('⚓ *Fundeado*',texto)
    self.assertIn('Terminal previsto',texto)

  def test_conflitos_nao_sao_resolvidos_pela_ordem(self):
    for a,b in [({'nome':'A'},{'nome':'A'}),({'nome':'A','viagem':'1'},{'nome':'A','viagem':'2'})]:
      r=mesclar_fontes([],[],[a],[b])[0]
      self.assertEqual(r['evento'],'SITUACAO_EM_VERIFICACAO')
      self.assertIsNone(r['etb'])
      self.assertIn('⚠️ *Situação em verificação*',formatar_resumo(dict(r,situacao='atualizado')))

  def test_escala_distinta_e_homonimos(self):
    for p,f in [({'nome':'A','viagem':'1'},{'nome':'A','viagem':'2'}),({'nome':'A','imo':'111'},{'nome':'A','imo':'222'})]:
      r=mesclar_fontes([],[p],[],[f])
      self.assertEqual(len(r),1)
      self.assertEqual(r[0]['evento'],'SITUACAO_EM_VERIFICACAO')

  def test_falha_fundeados_aborta_catalogo(self):
    with patch('monitor_aps.coletar_aps', return_value=[{'nome':str(i)} for i in range(60)]), patch('monitor_atracacoes.coletar_atracacoes_programadas',return_value=[]), patch('monitor_atracados.coletar_navios_atracados',return_value=[]), patch('monitor_fundeados.coletar_navios_fundeados',side_effect=RuntimeError('falha')), patch('sincronizador.sleep'):
      with self.assertRaises(RuntimeError): coletar_catalogo_completo()
