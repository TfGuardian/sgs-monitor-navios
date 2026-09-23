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

  def test_etapa_posterior_prevalece_sobre_fundeio(self):
    for evento in ('ATRACANDO','ATRACADO','OPERANDO','OPERANDO/BOMBEANDO','AG/DESATRACACAO','DESATRACANDO','SAIDA CONFIRMADA'):
      with self.subTest(evento=evento):
        r=mesclar_fontes([{'nome':'A','evento':evento,'viagem':'1','local':'BERCO'}],[],[],[{'nome':'A','viagem':'1','local':'TERMINAL'}])[0]
        self.assertEqual(r['evento'],evento)
        self.assertEqual(r['local'],'BERCO')
    r=mesclar_fontes([],[],[{'nome':'A','local':'BERCO'}],[{'nome':'A','local':'TERMINAL'}])[0]
    self.assertEqual(r['evento'],'ATRACADO')
    self.assertIn('🟢 *Atracado*',formatar_resumo(dict(r,situacao='atualizado')))

  def test_escala_antiga_nao_avanca_fundeado_atual(self):
    r=mesclar_fontes([{'nome':'A','evento':'OPERANDO','viagem':'antiga'}],[],[],[{'nome':'A','viagem':'atual'}])[0]
    self.assertEqual(r['evento'],'FUNDEADO')
    self.assertNotIn('APS_PAINEL',r['fonte'])

  def test_programacao_nao_confirma_saida(self):
    r=mesclar_fontes([], [{'nome':'A','evento':'DESATRACACAO','etb':'amanhã'}],[],[{'nome':'A'}])[0]
    self.assertEqual(r['evento'],'FUNDEADO')

  def test_operando_nao_vira_atracado_no_formatador(self):
    r=mesclar_fontes([{'nome':'A','evento':'OPERANDO'}],[],[{'nome':'A'}],[{'nome':'A'}])[0]
    self.assertEqual(r['evento'],'OPERANDO')
    self.assertIn('🟢 *Operando*',formatar_resumo(dict(r,situacao='atualizado')))
    from consulta_navio import etapa_evento
    self.assertEqual(etapa_evento('AG/DESATRACACAO')[2],'Aguardando desatracação')
    self.assertEqual(etapa_evento('DESATRACACAO')[0],0)

  def test_falha_fundeados_aborta_catalogo(self):
    with patch('monitor_aps.coletar_aps', return_value=[{'nome':str(i)} for i in range(60)]), patch('monitor_atracacoes.coletar_atracacoes_programadas',return_value=[]), patch('monitor_atracados.coletar_navios_atracados',return_value=[]), patch('monitor_fundeados.coletar_navios_fundeados',side_effect=RuntimeError('falha')), patch('sincronizador.sleep'):
      with self.assertRaises(RuntimeError): coletar_catalogo_completo()
