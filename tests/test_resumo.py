import unittest
from consulta_navio import formatar_resumo

class ResumoTest(unittest.TestCase):
  def test_indisponivel_nao_e_ocultado_por_data_antiga(self):
    texto = formatar_resumo({"nome": "ECO CZAR", "situacao": "indisponivel", "ultima_consulta": "2020-01-01T12:00:00Z"})
    self.assertIn("Dados indisponíveis", texto)
    self.assertNotIn("IMO:", texto)
    self.assertNotIn("ETA: N/A", texto)

  def test_dados_antigos_tem_aviso(self):
    texto = formatar_resumo({"nome": "A", "situacao": "atualizado", "ultima_consulta": "2020-01-01T12:00:00Z", "etb": "23/09/2026 15:00"})
    self.assertIn("Dados desatualizados", texto)
    self.assertIn("Atracação prevista:* 23/09/2026 15:00", texto)

  def test_classificacao_nao_confunde_atracacao_com_atracado(self):
    from consulta_navio import estado_operacional
    self.assertEqual(estado_operacional({"evento":"ATRACADO"}), ("🟢", "Atracado"))
    self.assertEqual(estado_operacional({"fonte":"APS_ATRACACOES_PROGRAMADAS"}), ("🟡", "Atracação programada"))
    self.assertEqual(estado_operacional({"fonte":"APS_ATRACACOES_PROGRAMADAS + APS_ATRACADOS"}), ("🟢", "Atracado"))
    self.assertEqual(estado_operacional({"evento":"DESATRACADO"})[0], "⚪")
    self.assertEqual(estado_operacional({"evento":"SAIDA", "fonte":"APS_ATRACACOES_PROGRAMADAS"})[1], "SAIDA")

  def test_indisponivel_nao_exibe_estado_operacional_antigo(self):
    texto = formatar_resumo({"nome":"A", "situacao":"indisponivel", "evento":"ATRACADO", "local":"X"})
    self.assertIn("Dados indisponíveis", texto)
    self.assertNotIn("🟢", texto)
    self.assertNotIn("Local", texto)

  def test_atracado_e_atracacao_tem_data_e_emoji_coerentes(self):
    from consulta_navio import formatar_navio
    for formatar in (formatar_resumo, formatar_navio):
      base = {"nome":"A", "situacao":"atualizado", "etb":"24/09/2026 08:00"}
      atracado = formatar(dict(base, evento="ATRACADO"))
      self.assertIn("🟢 *Atracado*", atracado)
      self.assertNotIn("24/09/2026 08:00", atracado)
      self.assertNotIn("⏳", atracado)
      for evento, status in (("ATRACAÇÃO", "Atracação programada"), ("ATRACANDO", "Atracando")):
        previsto = formatar(dict(base, evento=evento))
        self.assertIn(f"🟡 *{status}*", previsto)
        self.assertIn("⏳ *Atracação prevista:*", previsto)
        self.assertNotIn("✅", previsto)
