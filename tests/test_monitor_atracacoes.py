import unittest

import pandas as pd

from monitor_atracacoes import extrair_atracacoes_programadas


class MonitorAtracacoesTest(unittest.TestCase):
  def test_extrai_campos_e_monta_etb_com_data_e_periodo(self):
    tabela = pd.DataFrame([{
        "Data Date Fecha": "15/09/2026",
        "Hora Hour Hora": "13:00/19:00",
        "ETA": "15/09/2026 08:00:00",
        "Local Place Lugar": "TECON 3",
        "Navio Ship Buque": "NAVIO A",
        "IMO": "1234567",
        "Evento Event Evento": "ATRACACAO",
    }])
    registros, reconhecida = extrair_atracacoes_programadas([tabela])
    self.assertTrue(reconhecida)
    self.assertEqual(len(registros), 1)
    self.assertEqual(registros[0]["nome"], "NAVIO A")
    self.assertEqual(registros[0]["imo"], "1234567")
    self.assertEqual(registros[0]["eta"], "15/09/2026 08:00:00")
    self.assertEqual(registros[0]["etb"], "15/09/2026 13:00/19:00")
    self.assertEqual(registros[0]["local"], "TECON 3")
    self.assertEqual(registros[0]["evento"], "ATRACACAO")

  def test_ignora_tabela_sem_navio_ou_eta(self):
    registros, reconhecida = extrair_atracacoes_programadas([
        pd.DataFrame([{"Outra coluna": "valor"}])
    ])
    self.assertFalse(reconhecida)
    self.assertEqual(registros, [])


if __name__ == "__main__":
  unittest.main()
