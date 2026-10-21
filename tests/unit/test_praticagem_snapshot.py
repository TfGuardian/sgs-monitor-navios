import unittest

from vessel_monitor.domain.praticagem_snapshot import construir_snapshot
from vessel_monitor.application.praticagem_observador import montar_pacote


def observacao(fase="previsao", mv="S", tabela="previstas", **extras):
    return {"imo": "9398321", "nome": "TORINO", "tabela": tabela,
            "fase": fase, "mv": mv, "local1": "TEV", "local2": "",
            "pob": "", "passag": "", **extras}


def normalizado(observacoes):
    return {"observacoes": observacoes,
            "quantidades": {"movimentos": 1, "previstas": 1,
                            "atracados": 1, "fundeados": 1}}


class SnapshotPraticagemTest(unittest.TestCase):
    def test_prevista_avanca_para_andamento_com_mesma_chave(self):
        primeiro = construir_snapshot(normalizado([observacao()]), {})
        anterior = primeiro["navios"][0]
        segundo = construir_snapshot(normalizado([
            observacao(fase="andamento", tabela="movimentos", pob="08/10 12:00")]),
            {"9398321": anterior})
        atual = segundo["navios"][0]
        self.assertEqual(atual["manobras"][0]["chave"],
                         anterior["manobras"][0]["chave"])
        _, eventos = montar_pacote(segundo, {"9398321"},
                                   {"9398321": anterior}, [])
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["mudancas"][0]["depois"], "andamento")

    def test_nova_previsao_apos_manobra_encerrada(self):
        encerrada = construir_snapshot(normalizado([
            observacao(fase="encerrada", tabela="movimentos")]), {})["navios"][0]
        repetida = construir_snapshot(normalizado([
            observacao(fase="encerrada", tabela="movimentos")]),
            {"9398321": encerrada})["navios"][0]
        self.assertEqual(repetida["manobras"][0]["chave"],
                         encerrada["manobras"][0]["chave"])
        nova = construir_snapshot(normalizado([observacao()]),
                                  {"9398321": encerrada})["navios"][0]
        self.assertNotEqual(nova["manobras"][0]["chave"],
                            encerrada["manobras"][0]["chave"])

    def test_ambiguo_isolado_preserva_historico_e_outros_navios(self):
        anterior = construir_snapshot(normalizado([observacao()]), {})["navios"][0]
        snapshot = construir_snapshot(normalizado([
            observacao(), observacao(fase="andamento", tabela="movimentos"),
            observacao(imo="1234567", nome="OUTRO")]), {"9398321": anterior})
        self.assertEqual(snapshot["bloqueados"], ["9398321"])
        self.assertEqual([n["imo"] for n in snapshot["navios"]], ["1234567"])
        estados, eventos = montar_pacote(snapshot, {"9398321", "1234567"},
                                        {"9398321": anterior}, [])
        self.assertEqual([n["imo"] for n in estados], ["1234567"])
        self.assertFalse(any(e["imo"] == "9398321" for e in eventos))

    def test_correcao_do_codigo_mv_na_mesma_previsao(self):
        anterior = construir_snapshot(normalizado([
            observacao(mv="P", local1="TC 1.2", local2="TC 2")]), {})["navios"][0]
        atual = construir_snapshot(normalizado([
            observacao(mv="M", local1="TC 1.2", local2="TC 2")]),
            {"9398321": anterior})
        self.assertEqual(atual["navios"][0]["manobras"][0]["chave"],
                         anterior["manobras"][0]["chave"])
        _, eventos = montar_pacote(atual, {"9398321"},
                                   {"9398321": anterior}, [])
        self.assertEqual([m["campo"] for m in eventos[0]["mudancas"]], ["mv"])
        self.assertEqual(eventos[0]["mudancas"][0]["antes"], "P")
        self.assertEqual(eventos[0]["mudancas"][0]["depois"], "M")


if __name__ == "__main__":
    unittest.main()
