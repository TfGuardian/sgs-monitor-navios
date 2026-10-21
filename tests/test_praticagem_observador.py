import unittest
from types import SimpleNamespace

from praticagem_observador import executar, resolver_monitorados


class ConsultaFalsa:
    def __init__(self, cliente, nome, dados=None):
        self.cliente, self.nome, self.dados = cliente, nome, dados

    def select(self, _colunas):
        return self

    def eq(self, _coluna, _valor):
        return self

    def limit(self, _total):
        return self

    def execute(self):
        self.cliente.chamadas.append((self.nome, self.dados))
        if self.nome == "reservar_coleta_praticagem":
            return SimpleNamespace(data="token-1")
        if self.nome == "estados_praticagem":
            return SimpleNamespace(data=[])
        if self.nome == "lista_monitoramento":
            return SimpleNamespace(data=[{"imo": "9398321", "nome_confirmado": "TORINO"}])
        if self.nome == "destinatarios_relatorio":
            return SimpleNamespace(data=[{"telefone": "5513999999999"}])
        if self.nome == "coletas_praticagem":
            return SimpleNamespace(data=[])
        return SimpleNamespace(data="coleta-1")


class ClienteFalso:
    def __init__(self):
        self.chamadas = []

    def rpc(self, nome, dados=None):
        return ConsultaFalsa(self, nome, dados)

    def table(self, nome):
        return ConsultaFalsa(self, nome)


class ObservadorTest(unittest.TestCase):
    def test_nome_sem_imo_unico_detecta_primeira_aparicao(self):
        registros = [{"imo": None, "nome_confirmado": "FIGALIA PRUDENCE"}]
        snapshot = {"navios": [{"imo": "9588316", "nome": "FIGALIA PRUDENCE",
                                "manobras": [{"chave": "m-1", "fase": "previsao"}]}]}
        anteriores = {}
        resolvidos = resolver_monitorados(registros, snapshot, anteriores, True)
        self.assertEqual(resolvidos, {"9588316": "FIGALIA PRUDENCE"})
        self.assertEqual(anteriores["9588316"]["manobras"], [])

    def test_nome_sem_imo_ambiguo_falha(self):
        registros = [{"imo": None, "nome_confirmado": "BELUGA"}]
        snapshot = {"navios": [{"imo": "1111111", "nome": "BELUGA"},
                                {"imo": "2222222", "nome": "BELUGA"}]}
        with self.assertRaisesRegex(ValueError, "ambíguo"):
            resolver_monitorados(registros, snapshot, {}, True)

    def test_captura_bruta_passa_pela_normalizacao(self):
        cliente = ClienteFalso()
        raw = {"quantidades": {"movimentos": 1, "previstas": 0,
                               "atracados": 0, "fundeados": 0},
               "tabelas": {
                   "movimentos": [{"cor": "rgb(0, 191, 255)",
                                    "celulas": {"IMO": "9398321", "NAVIO": "TORINO",
                                                "MV": "E", "LOC#1": "TEV"}}],
                   "previstas": [], "atracados": [], "fundeados": []}}
        self.assertEqual(executar(cliente, lambda: raw), 0)
        pacote = next(dados for nome, dados in cliente.chamadas
                      if nome == "concluir_coleta_catalogo_praticagem")
        self.assertEqual(pacote["p_catalogo"], [{"imo": "9398321", "nome": "TORINO"}])
        self.assertEqual(pacote["p_estados"][0]["manobras"][0]["fase"],
                         "andamento")

    def test_execucao_persiste_sem_enviar(self):
        cliente = ClienteFalso()
        snapshot = {"quantidades": {"movimentos": 1, "previstas": 1,
                                     "atracados": 1, "fundeados": 1},
                    "navios": []}
        self.assertEqual(executar(cliente, lambda: snapshot), 0)
        funcoes = [nome for nome, _ in cliente.chamadas]
        self.assertIn("concluir_observacao_praticagem", funcoes)
        self.assertNotIn("enviar_texto_whatsapp", funcoes)
        pacote = next(dados for nome, dados in cliente.chamadas
                      if nome == "concluir_observacao_praticagem")
        self.assertEqual(pacote["p_estados"][0]["nome"], "TORINO")

    def test_falha_registrada_sem_publicar_snapshot_parcial(self):
        cliente = ClienteFalso()
        with self.assertRaisesRegex(ValueError, "vazias"):
            executar(cliente, lambda: {"quantidades": {
                "movimentos": 0, "previstas": 0, "atracados": 0, "fundeados": 0},
                "navios": []})
        funcoes = [nome for nome, _ in cliente.chamadas]
        self.assertIn("registrar_falha_praticagem", funcoes)
        self.assertNotIn("concluir_observacao_praticagem", funcoes)


if __name__ == "__main__":
    unittest.main()
