import unittest
from datetime import datetime, timedelta, timezone

from consulta_navio import (
    formatar_data_operacional,
    formatar_navio,
    localizar_navios,
    separar_termos,
    situacao_atual,
    sugerir_navios,
)


class ConsultaNavioTest(unittest.TestCase):
  def setUp(self):
    self.navios = [
        {"nome": "CAP SAN TAINARO", "imo": "111"},
        {"nome": "MSC ATHENS", "imo": "222"},
        {"nome": "MSC SOFIA", "imo": "333"},
    ]

  def test_busca_nome_ignora_maiusculas_e_acentos(self):
    resultado = localizar_navios("cap san tainaro", self.navios)
    self.assertEqual(resultado[0]["imo"], "111")

  def test_busca_por_imo(self):
    resultado = localizar_navios("222", self.navios)
    self.assertEqual(resultado[0]["nome"], "MSC ATHENS")

  def test_busca_parcial_retorna_opcoes(self):
    resultado = localizar_navios("MSC", self.navios)
    self.assertEqual(len(resultado), 2)

  def test_separa_varios_navios(self):
    self.assertEqual(
        separar_termos("CAP SAN TAINARO; MSC ATHENS\nMSC SOFIA"),
        ["CAP SAN TAINARO", "MSC ATHENS", "MSC SOFIA"],
    )

  def test_sugere_nome_semelhante(self):
    sugestoes = sugerir_navios("CAP SAN TAINRO", self.navios)
    self.assertEqual(sugestoes[0], "CAP SAN TAINARO")

  def test_situacao_fica_desatualizada_depois_de_duas_horas(self):
    agora = datetime(2026, 9, 2, 18, 0, tzinfo=timezone.utc)
    navio = {
        "situacao": "atualizado",
        "ultima_consulta": (agora - timedelta(hours=3)).isoformat(),
    }
    self.assertEqual(situacao_atual(navio, agora), "DESATUALIZADO")

  def test_resposta_contem_os_dez_campos(self):
    texto = formatar_navio({"nome": "NAVIO A", "situacao": "atualizado"})
    for campo in ("Nome:", "IMO:", "ETA:", "ETB:", "Local:", "Evento:",
                  "Fonte:", "Ultima consulta:", "Ultima alteracao:", "Situacao:"):
      self.assertIn(campo, texto)

  def test_data_operacional_e_padronizada(self):
    self.assertEqual(
        formatar_data_operacional("02/09/26 14:55:00"),
        "02/09/2026 14:55",
    )


if __name__ == "__main__":
  unittest.main()
