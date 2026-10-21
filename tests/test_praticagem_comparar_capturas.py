import unittest

from comparar_capturas_praticagem import comparar


def captura(fase="rgb(183, 183, 255)", *, previsto=False):
    movimento = {"celulas": {"IMO": "9398321", "NAVIO": "TORINO",
                             "MV": "S", "LOC#1": "TEV", "LOC#2": "",
                             "POB": "08/10 12:00", "PASSAG": ""}, "cor": fase}
    tabelas = {"movimentos": [] if previsto else [movimento],
               "previstas": [movimento] if previsto else [],
               "atracados": [], "fundeados": []}
    return {"tabelas": tabelas,
            "quantidades": {k: len(v) for k, v in tabelas.items()}}


class CompararCapturasTest(unittest.TestCase):
    def test_releitura_idêntica(self):
        self.assertEqual(comparar(captura(), captura())["eventos"], 0)

    def test_previsao_para_andamento(self):
        resultado = comparar(captura(previsto=True),
                             captura(fase="rgb(0, 191, 255)"))
        self.assertEqual(resultado["eventos"], 1)
        self.assertEqual(resultado["mudancas_por_campo"], {"fase": 1})


if __name__ == "__main__":
    unittest.main()
