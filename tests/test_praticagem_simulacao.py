"""Movimentações artificiais, sem Supabase e sem envio de mensagens."""

import copy
import unittest

from praticagem_observador import montar_pacote
from simular_praticagem import simular_proxima_etapa_toxotis


IMO = "1018016"
DESTINATARIO_FICTICIO = "5513999999999"
QUANTIDADES = {"movimentos": 1, "previstas": 1,
               "atracados": 1, "fundeados": 1}


def estado(manobras=None, *, fundeado=False, atracado=True):
    return {"imo": IMO, "nome": "DESERT LEOPARD", "manobras": manobras or [],
            "fundeado": fundeado, "atracado": atracado}


def manobra(fase, *, pob="09/10 14:00", local1="13/14", passag=""):
    return {"chave": "saida-simulada", "mv": "S", "fase": fase,
            "pob": pob, "passag": passag, "local1": local1, "local2": ""}


def rodada(atual, anteriores):
    snapshot = {"quantidades": QUANTIDADES,
                "navios": [atual, estado_outro_navio()]}
    estados, eventos = montar_pacote(
        snapshot, {IMO: "DESERT LEOPARD"}, anteriores,
        [DESTINATARIO_FICTICIO])
    assert len(estados) == 1
    return estados[0], eventos


def estado_outro_navio():
    return {"imo": "9999999", "nome": "FORA DA LISTA", "manobras": [],
            "fundeado": False, "atracado": False}


class SimulacaoPraticagemTest(unittest.TestCase):
    def test_toxotis_fundeado_gera_previsao_so_na_memoria(self):
        captura = {
            "coletado_em": "2026-10-08T21:08:35+00:00",
            "quantidades": {"movimentos": 0, "previstas": 0,
                            "atracados": 0, "fundeados": 1},
            "tabelas": {"movimentos": [], "previstas": [], "atracados": [],
                        "fundeados": [{"celulas": {
                            "IMO": "9563419", "NAVIO": "TOXOTIS",
                            "FUNDEIO": "03/10 09:38"}, "cor": None}]},
        }
        original = copy.deepcopy(captura)
        texto = simular_proxima_etapa_toxotis(captura)
        self.assertIn("Situação observada no portal: Fundeado", texto)
        self.assertIn("Fundeio informado: 03/10 09:38", texto)
        self.assertIn("Manobra em previsão", texto)
        self.assertIn("NÃO GRAVADO / NÃO ENVIADO", texto)
        self.assertEqual(captura, original)

    def test_ciclo_completo_de_manobra_e_releitura(self):
        anterior, eventos = rodada(estado(), {})
        self.assertEqual(eventos, [])  # Primeira coleta só cria referência.

        etapas = [
            (estado([manobra("previsao")]), "Manobra em previsão", {"fase"}),
            (estado([manobra("confirmada")]), "Manobra confirmada", {"fase"}),
            (estado([manobra("andamento", pob="09/10 14:30", local1="15")]),
             "Manobra em andamento", {"fase", "pob", "local1"}),
            (estado([manobra("encerrada", pob="09/10 14:30", local1="15",
                             passag="09/10 14:50")]),
             "Manobra encerrada", {"fase", "passag"}),
        ]
        for atual, frase, campos in etapas:
            anterior, eventos = rodada(atual, {IMO: anterior})
            self.assertEqual(len(eventos), 1)
            self.assertEqual({x["campo"] for x in eventos[0]["mudancas"]}, campos)
            self.assertEqual(len(eventos[0]["alertas"]), 1)
            self.assertIn(frase, eventos[0]["alertas"][0]["texto"])

        _, eventos = rodada(copy.deepcopy(etapas[-1][0]), {IMO: anterior})
        self.assertEqual(eventos, [])  # Sem aviso duplicado.

    def test_fundeio_e_desaparecimento_nao_comprovado(self):
        anterior, _ = rodada(estado(atracado=False), {})
        novo, eventos = rodada(estado(fundeado=True, atracado=False),
                              {IMO: anterior})
        self.assertEqual(len(eventos), 1)
        self.assertIn("Fundeado", eventos[0]["alertas"][0]["texto"])
        mantido, eventos = rodada(estado(fundeado=False, atracado=False),
                                 {IMO: novo})
        self.assertEqual(eventos, [])
        self.assertTrue(mantido["fundeado"])


if __name__ == "__main__":
    unittest.main()
