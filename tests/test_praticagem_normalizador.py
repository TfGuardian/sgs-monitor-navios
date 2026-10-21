import unittest

from praticagem_normalizador import normalizar_captura


def linha(**celulas):
    return {"celulas": celulas, "cor": None}


class NormalizadorPraticagemTest(unittest.TestCase):
    def test_fases_e_imo_ausente(self):
        azul = linha(IMO="9398321", NAVIO="TORINO", MV="E", **{"LOC#1": "TEV"})
        azul["cor"] = "rgb(0, 191, 255)"
        prevista = linha(IMO="9398321", NAVIO="TORINO", MV="S", **{"LOC#2": "AL 4"})
        captura = {"tabelas": {
            "movimentos": [azul], "previstas": [prevista],
            "atracados": [linha(IMO="", NAVIO="SEM IMO", LOCAL="TEV")],
            "fundeados": []},
            "quantidades": {"movimentos": 1, "previstas": 1,
                            "atracados": 1, "fundeados": 0}}
        resultado = normalizar_captura(captura)
        self.assertEqual([x["fase"] for x in resultado["observacoes"]],
                         ["andamento", "previsao"])
        self.assertEqual(len(resultado["ignorados"]), 1)
        self.assertEqual(resultado["ignorados"][0]["motivo"], "imo_ausente")

    def test_imo_zero_nao_agrupa_navios_desconhecidos(self):
        captura = {"tabelas": {"movimentos": [], "previstas": [
            linha(IMO="0000000", NAVIO="A", MV="E"),
            linha(IMO="0000000", NAVIO="B", MV="E"),
            linha(IMO="9398321", NAVIO="TORINO", MV="E")],
            "atracados": [], "fundeados": []},
            "quantidades": {"movimentos": 0, "previstas": 3,
                            "atracados": 0, "fundeados": 0}}
        resultado = normalizar_captura(captura)
        self.assertEqual(len(resultado["ignorados"]), 2)
        self.assertEqual([n["imo"] for n in resultado["observacoes"]], ["9398321"])

    def test_cor_desconhecida_falha(self):
        movimento = linha(IMO="9398321", NAVIO="TORINO", MV="E")
        movimento["cor"] = "rgb(1, 2, 3)"
        captura = {"tabelas": {"movimentos": [movimento], "previstas": [],
                               "atracados": [], "fundeados": []},
                   "quantidades": {"movimentos": 1, "previstas": 0,
                                   "atracados": 0, "fundeados": 0}}
        with self.assertRaisesRegex(ValueError, "desconhecida"):
            normalizar_captura(captura)


if __name__ == "__main__":
    unittest.main()
