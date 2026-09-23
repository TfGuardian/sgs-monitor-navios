import unittest
from datetime import datetime, timezone

from sincronizador import (
    coletar_com_tentativas,
    consolidar_coleta,
    filtrar_monitorados,
    mesclar_fontes,
    planejar_sincronizacao,
    validar_coleta,
)


class SincronizadorTest(unittest.TestCase):
  def setUp(self):
    self.agora = datetime(2026, 9, 2, 18, 0, tzinfo=timezone.utc)

  def test_primeira_importacao_cadastra_todos(self):
    coletados = [
        {"nome": "NAVIO A", "imo": "111", "eta": "02/09/2026 10:00"},
        {"nome": "NAVIO B", "imo": "222", "etb": "02/09/2026 12:00"},
    ]
    plano = planejar_sincronizacao(coletados, [], self.agora)
    self.assertEqual(len(plano.inserir), 2)
    self.assertTrue(all(n["situacao"] == "atualizado" for n in plano.inserir))
    self.assertTrue(all(n["ultima_alteracao"] for n in plano.inserir))

  def test_mesmo_imo_atualiza_nome_sem_alteracao_operacional(self):
    existentes = [{
        "id": 1, "nome": "NOME ANTIGO", "imo": "111", "eta": "10:00",
        "etb": None, "local": "BERCO 1", "evento": "PREVISTO",
    }]
    coletados = [{
        "nome": "NOME NOVO", "imo": "111", "eta": "10:00",
        "etb": None, "local": "BERCO 1", "evento": "PREVISTO", "fonte": "APS",
    }]
    plano = planejar_sincronizacao(coletados, existentes, self.agora)
    self.assertEqual(len(plano.inserir), 0)
    self.assertEqual(plano.atualizar[0].dados["nome"], "NOME NOVO")
    self.assertNotIn("ultima_alteracao", plano.atualizar[0].dados)

  def test_mudanca_de_etb_atualiza_data_da_alteracao(self):
    existentes = [{
        "id": 1, "nome": "NAVIO A", "imo": "111", "eta": "10:00",
        "etb": "11:00", "local": "BERCO 1", "evento": "PREVISTO",
    }]
    coletados = [{
        "nome": "NAVIO A", "imo": "111", "eta": "10:00",
        "etb": "12:00", "local": "BERCO 1", "evento": "PREVISTO", "fonte": "APS",
    }]
    plano = planejar_sincronizacao(coletados, existentes, self.agora)
    self.assertTrue(plano.atualizar[0].alteracao_operacional)
    self.assertIn("ultima_alteracao", plano.atualizar[0].dados)

  def test_fonte_nao_apaga_imo_ou_eta_ausentes(self):
    existentes = [{
        "id": 1, "nome": "NAVIO A", "imo": "111", "eta": "10:00",
        "etb": "11:00", "local": "BERCO 1", "evento": "PREVISTO",
    }]
    coletados = [{
        "nome": "NAVIO A", "imo": None, "eta": None, "etb": "11:00",
        "local": "BERCO 1", "evento": "PREVISTO", "fonte": "APS",
    }]
    plano = planejar_sincronizacao(coletados, existentes, self.agora)
    dados = plano.atualizar[0].dados
    self.assertNotIn("imo", dados)
    self.assertNotIn("eta", dados)

  def test_primeira_ausencia_marca_desatualizado(self):
    existentes = [{
        "id": 1, "nome": "AUSENTE", "imo": "111", "ausencias_consecutivas": 0,
    }]
    coletados = [{"nome": "PRESENTE", "imo": "222", "eta": "10:00"}]
    plano = planejar_sincronizacao(coletados, existentes, self.agora)
    ausencia = next(a for a in plano.atualizar if a.anterior["nome"] == "AUSENTE")
    self.assertEqual(ausencia.dados["ausencias_consecutivas"], 1)
    self.assertEqual(ausencia.dados["situacao"], "desatualizado")
    self.assertFalse(plano.remover)

  def test_segunda_ausencia_remove(self):
    existentes = [{
        "id": 1, "nome": "AUSENTE", "imo": "111", "ausencias_consecutivas": 1,
    }]
    coletados = [{"nome": "PRESENTE", "imo": "222", "eta": "10:00"}]
    plano = planejar_sincronizacao(coletados, existentes, self.agora)
    self.assertEqual(plano.remover, existentes)

  def test_reaparecimento_zera_ausencias(self):
    existentes = [{
        "id": 1, "nome": "NAVIO A", "imo": "111", "eta": "10:00",
        "ausencias_consecutivas": 1,
    }]
    coletados = [{"nome": "NAVIO A", "imo": "111", "eta": "10:00"}]
    plano = planejar_sincronizacao(coletados, existentes, self.agora)
    self.assertEqual(plano.atualizar[0].dados["ausencias_consecutivas"], 0)

  def test_coleta_tenta_tres_vezes(self):
    chamadas = 0

    def coletor():
      nonlocal chamadas
      chamadas += 1
      if chamadas < 3:
        raise RuntimeError("falha temporaria")
      return [{"nome": "NAVIO A"}]

    from unittest.mock import patch
    with patch("sincronizador.sleep"):
      resultado = coletar_com_tentativas(coletor)
    self.assertEqual(chamadas, 3)
    self.assertEqual(resultado[0]["nome"], "NAVIO A")

  def test_coleta_menor_que_metade_e_rejeitada(self):
    existentes = [{"nome": f"NAVIO {i}"} for i in range(5)]
    with self.assertRaises(RuntimeError):
      validar_coleta([{"nome": "NAVIO 1"}], existentes, minimo_painel=1)

  def test_painel_pequeno_demais_e_rejeitado(self):
    with self.assertRaises(RuntimeError):
      validar_coleta([{"nome": "NAVIO 1"}], [], minimo_painel=50)

  def test_consolidacao_prioriza_operacao_mais_recente(self):
    registros = [
        {"nome": "NAVIO A", "imo": "111", "etb": "02/09/2026 10:00"},
        {"nome": "NAVIO A", "imo": "111", "etb": "02/09/2026 12:00"},
    ]
    resultado = consolidar_coleta(registros)
    self.assertEqual(len(resultado), 1)
    self.assertEqual(resultado[0]["etb"], "02/09/2026 12:00")

  def test_filtra_apenas_navios_da_lista_e_vincula_id(self):
    painel = [
        {"nome": "NAVIO A", "imo": "111"},
        {"nome": "NAVIO B", "imo": "222"},
    ]
    lista = [{"id": 9, "nome_confirmado": "NAVIO B", "imo": "222"}]
    resultado = filtrar_monitorados(painel, lista)
    self.assertEqual(len(resultado), 1)
    self.assertEqual(resultado[0]["nome"], "NAVIO B")
    self.assertEqual(resultado[0]["lista_monitoramento_id"], 9)

  def test_nome_novo_e_localizado_pelo_imo_da_lista(self):
    painel = [{"nome": "NOME NOVO", "imo": "111"}]
    lista = [{"id": 9, "nome_confirmado": "NOME ANTIGO", "imo": "111"}]
    resultado = filtrar_monitorados(painel, lista)
    self.assertEqual(resultado[0]["nome"], "NOME NOVO")

  def test_fontes_sao_combinadas_sem_apagar_eta_e_imo(self):
    programadas = [{
        "nome": "NAVIO A", "imo": "1234567", "eta": "15/09/2026 08:00",
        "etb": "15/09/2026 13:00/19:00", "local": "BERCO PREVISTO",
        "evento": "ATRACACAO", "fonte": "APS_ATRACACOES_PROGRAMADAS",
    }]
    painel = [{
        "nome": "NAVIO A", "imo": None, "eta": None,
        "etb": "15/09/2026 14:00", "local": "BERCO REAL",
        "evento": "OPERANDO", "fonte": "APS",
    }]
    resultado = mesclar_fontes(painel, programadas)
    self.assertEqual(len(resultado), 1)
    self.assertEqual(resultado[0]["imo"], "1234567")
    self.assertEqual(resultado[0]["eta"], "15/09/2026 08:00")
    self.assertEqual(resultado[0]["etb"], "15/09/2026 13:00/19:00")
    self.assertEqual(resultado[0]["local"], "BERCO REAL")
    self.assertEqual(
        resultado[0]["fonte"],
        "APS_ATRACACOES_PROGRAMADAS + APS_PAINEL",
    )

  def test_navio_exclusivo_da_programacao_tambem_e_retornado(self):
    resultado = mesclar_fontes([], [{
        "nome": "NAVIO PROGRAMADO", "imo": "7654321",
        "fonte": "APS_ATRACACOES_PROGRAMADAS",
    }])
    self.assertEqual(resultado[0]["nome"], "NAVIO PROGRAMADO")

  def test_atracados_tem_prioridade_para_local_e_evento(self):
    programadas = [{
        "nome": "NAVIO A", "imo": "1234567", "eta": "15/09/2026 08:00",
        "etb": "15/09/2026 13:00/19:00", "local": "BERCO PREVISTO",
        "evento": "ATRACACAO", "fonte": "APS_ATRACACOES_PROGRAMADAS",
    }]
    atracados = [{
        "nome": "NAVIO A", "local": "TECON 3", "evento": "ATRACADO",
        "fonte": "APS_ATRACADOS",
    }]
    resultado = mesclar_fontes([], programadas, atracados)
    self.assertEqual(resultado[0]["imo"], "1234567")
    self.assertEqual(resultado[0]["eta"], "15/09/2026 08:00")
    self.assertIsNone(resultado[0]["etb"])
    self.assertEqual(resultado[0]["local"], "TECON 3")
    self.assertEqual(resultado[0]["evento"], "ATRACADO")
    self.assertIn("APS_ATRACADOS", resultado[0]["fonte"])

  def test_navio_exclusivo_de_atracados_tambem_e_retornado(self):
    resultado = mesclar_fontes([], [], [{
        "nome": "NAVIO ATRACADO", "local": "AGEO I",
    }])
    self.assertEqual(resultado[0]["nome"], "NAVIO ATRACADO")
    self.assertEqual(resultado[0]["evento"], "ATRACADO")


if __name__ == "__main__":
  unittest.main()
