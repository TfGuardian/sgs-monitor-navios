import unittest

from vessel_monitor.domain.praticagem_transicoes import comparar_estados, formatar_alerta
from vessel_monitor.application.praticagem_observador import montar_pacote


def navio(manobras, **extras):
    return {"imo": "9398321", "nome": "TORINO", "manobras": manobras,
            "fundeado": False, "atracado": True, **extras}


class TransicoesPraticagemTest(unittest.TestCase):
    def test_primeira_leitura_e_releitura_nao_avisam(self):
        atual = navio([{"chave": "saida-1", "mv": "S", "fase": "previsao"}])
        self.assertEqual(comparar_estados(None, atual), [])
        self.assertEqual(comparar_estados(atual, atual), [])

    def test_manobra_nova_nao_herda_fase_da_antiga(self):
        entrada = {"chave": "entrada-1", "mv": "E", "fase": "encerrada"}
        saida = {"chave": "saida-1", "mv": "S", "fase": "previsao"}
        eventos = comparar_estados(navio([entrada]), navio([entrada, saida]))
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["manobra"], "saida-1")
        self.assertEqual(eventos[0]["mudancas"][0]["depois"], "previsao")

    def test_fase_horario_e_local_geram_um_aviso(self):
        anterior = navio([{"chave": "saida-1", "fase": "previsao",
                           "pob": "02/10 14:00", "local1": "39"}])
        atual = navio([{"chave": "saida-1", "fase": "andamento",
                        "pob": "02/10 15:30", "local1": "40"}])
        eventos = comparar_estados(anterior, atual)
        self.assertEqual(len(eventos), 1)
        self.assertEqual({m["campo"] for m in eventos[0]["mudancas"]},
                         {"fase", "pob", "local1"})
        texto = formatar_alerta(eventos[0])
        self.assertIn("Manobra em andamento", texto)
        self.assertIn("02/10 14:00 → 02/10 15:30", texto)

    def test_situacao_fisica_combina_com_manobra(self):
        anterior = navio([{"chave": "entrada-1", "fase": "andamento"}])
        anterior["atracado"] = False
        atual = navio([{"chave": "entrada-1", "fase": "encerrada"}])
        eventos = comparar_estados(anterior, atual)
        self.assertEqual(len(eventos), 1)
        self.assertEqual({m["campo"] for m in eventos[0]["mudancas"]},
                         {"fase", "atracado"})

    def test_desaparecimento_nao_cria_alerta(self):
        anterior = navio([{"chave": "saida-1", "fase": "previsao"}])
        atual = navio([])
        atual["atracado"] = False
        self.assertEqual(comparar_estados(anterior, atual), [])

    def test_chave_ambigua_falha_fechada(self):
        atual = navio([{"chave": "x", "fase": "previsao"},
                       {"chave": "x", "fase": "andamento"}])
        with self.assertRaisesRegex(ValueError, "única"):
            comparar_estados(None, atual)

    def test_pacote_filtra_lista_e_destinatarios(self):
        anterior = navio([{"chave": "saida-1", "fase": "previsao"}])
        atual = navio([{"chave": "saida-1", "fase": "andamento"}])
        snapshot = {
            "quantidades": {"movimentos": 1, "previstas": 1,
                            "atracados": 1, "fundeados": 1},
            "navios": [atual, {"imo": "1234567", "nome": "OUTRO", "manobras": []}],
        }
        estados, eventos = montar_pacote(
            snapshot, {"9398321"}, {"9398321": anterior},
            ["5513999999999", "5513999999999"])
        self.assertEqual(len(estados), 1)
        self.assertEqual(len(eventos), 1)
        self.assertEqual(len(eventos[0]["alertas"]), 1)
        self.assertIn("Manobra em andamento", eventos[0]["alertas"][0]["texto"])

    def test_snapshot_vazio_falha_sem_apagar_estado(self):
        with self.assertRaisesRegex(ValueError, "vazias"):
            montar_pacote({"quantidades": dict.fromkeys(
                ("movimentos", "previstas", "atracados", "fundeados"), 0),
                "navios": []}, {"9398321"}, {}, [])

    def test_linha_reaparece_sem_falso_novo_alerta(self):
        anterior = navio([{"chave": "saida-1", "fase": "previsao"}])
        sem_linha = navio([])
        sem_linha["atracado"] = False
        quantidades = {"movimentos": 1, "previstas": 1,
                       "atracados": 1, "fundeados": 1}
        estados, eventos = montar_pacote(
            {"quantidades": quantidades, "navios": [sem_linha]},
            {"9398321"}, {"9398321": anterior}, [])
        self.assertEqual(eventos, [])
        self.assertEqual(estados[0]["manobras"][0]["chave"], "saida-1")
        self.assertTrue(estados[0]["atracado"])
        _, eventos_reapareceu = montar_pacote(
            {"quantidades": quantidades, "navios": [anterior]},
            {"9398321"}, {"9398321": estados[0]}, [])
        self.assertEqual(eventos_reapareceu, [])

    def test_navio_ausente_na_primeira_coleta_e_depois_previsto(self):
        quantidades = {"movimentos": 1, "previstas": 1,
                       "atracados": 1, "fundeados": 1}
        vazio = {"quantidades": quantidades, "navios": []}
        estados, eventos = montar_pacote(
            vazio, {"9398321": "TORINO"}, {}, ["5513999999999"])
        self.assertEqual(eventos, [])
        self.assertEqual(estados[0]["nome"], "TORINO")
        aparecimento = {"quantidades": quantidades,
                        "navios": [navio([{"chave": "saida-1", "fase": "previsao"}])]}
        _, eventos = montar_pacote(
            aparecimento, {"9398321": "TORINO"}, {"9398321": estados[0]},
            ["5513999999999"])
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["mudancas"][0]["depois"], "previsao")


if __name__ == "__main__":
    unittest.main()
