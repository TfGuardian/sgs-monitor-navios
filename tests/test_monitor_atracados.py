import unittest

import pandas as pd

from monitor_atracados import extrair_navios_atracados


class MonitorAtracadosTest(unittest.TestCase):
  def test_extrai_nome_local_e_define_evento_atracado(self):
    tabela = pd.DataFrame([{
        "Local Local": "AGEO I",
        "Navio Ship Buque": "BOW COUGAR",
        "Carga Cargo Carga": "GRANEL LIQUIDO",
    }])
    registros, reconhecida = extrair_navios_atracados([tabela])
    self.assertTrue(reconhecida)
    self.assertEqual(len(registros), 1)
    self.assertEqual(registros[0]["nome"], "BOW COUGAR")
    self.assertEqual(registros[0]["local"], "AGEO I")
    self.assertEqual(registros[0]["evento"], "ATRACADO")
    self.assertEqual(registros[0]["fonte"], "APS_ATRACADOS")

  def test_ignora_tabela_sem_navio_ou_local(self):
    registros, reconhecida = extrair_navios_atracados([
        pd.DataFrame([{"Outra coluna": "valor"}])
    ])
    self.assertFalse(reconhecida)
    self.assertEqual(registros, [])


if __name__ == "__main__":
  unittest.main()
