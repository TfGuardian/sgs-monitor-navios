import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from praticagem_worker import (espera_ate_proximo_ciclo,
                               observar_continuamente, vigiar_ciclos)


class SessaoFalsa:
    def __init__(self, resultados):
        self.resultados = iter(resultados)
        self.aberturas = 0
        self.fechamentos = 0

    def __enter__(self):
        self.aberturas += 1
        return self

    def __exit__(self, *_):
        self.fechamentos += 1

    def capturar(self):
        resultado = next(self.resultados)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


class WorkerPraticagemTest(unittest.TestCase):
    def test_vigia_encerra_ciclo_que_excede_limite(self):
        parar = MagicMock()
        parar.wait.return_value = False
        with patch("praticagem_worker.time.monotonic", return_value=166), \
             patch("praticagem_worker.os._exit", side_effect=SystemExit(124)) as sair, \
             redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                vigiar_ciclos([0], parar)
        sair.assert_called_once_with(124)

    def test_reserva_ocupada_nao_abre_navegador(self):
        with patch("praticagem_worker.executar", return_value=0), \
             patch("praticagem_worker.tocar_alerta") as som, \
             patch("praticagem_worker.time.sleep"), \
             redirect_stdout(StringIO()):
            observar_continuamente(object(),
                                   lambda: self.fail("Navegador aberto sem reserva"),
                                   max_ciclos=2)
        som.assert_not_called()

    def test_cadencia_e_recuo(self):
        self.assertEqual(60, espera_ate_proximo_ciclo(10, 10, 60, 0))
        self.assertEqual(40, espera_ate_proximo_ciclo(10, 30, 60, 0))
        self.assertEqual(100, espera_ate_proximo_ciclo(10, 30, 60, 1))
        self.assertEqual(100, espera_ate_proximo_ciclo(10, 30, 60, 4))

    def test_reutiliza_sessao_e_reabre_apos_falha(self):
        primeira = SessaoFalsa([{"teste": 1}, RuntimeError("falha")])
        segunda = SessaoFalsa([{"teste": 2}])
        sessoes = iter([primeira, segunda])
        coletas = []

        def processar(_cliente, coletar, _registrados):
            coletas.append(coletar())
            return 0

        with patch("praticagem_worker.executar", side_effect=processar), \
             patch("praticagem_worker.time.sleep") as dormir:
            observar_continuamente(object(), lambda: next(sessoes), max_ciclos=3)

        self.assertEqual([{"teste": 1}, {"teste": 2}], coletas)
        self.assertEqual((1, 1), (primeira.aberturas, primeira.fechamentos))
        self.assertEqual((1, 1), (segunda.aberturas, segunda.fechamentos))
        self.assertEqual(2, dormir.call_count)

    def test_aviso_registrado_aparece_na_saida(self):
        sessao = SessaoFalsa([{"teste": 1}])
        saida = StringIO()

        def processar(_cliente, coletar, registrados):
            coletar()
            registrados.append({"nome": "NAVIO TESTE", "mudancas": [
                {"campo": "fase", "antes": "previsao", "depois": "andamento"}]})
            return 1

        with patch("praticagem_worker.executar", side_effect=processar), \
             patch("praticagem_worker.tocar_alerta") as som, \
             redirect_stdout(saida):
            observar_continuamente(object(), lambda: sessao, max_ciclos=1)

        self.assertIn("AVISO SIMULADO; NÃO ENVIADO", saida.getvalue())
        self.assertIn("Manobra em andamento", saida.getvalue())
        som.assert_called_once_with()

    def test_pedido_local_aparece_no_observador_uma_vez(self):
        pedido = Path("teste.flag")
        sessao = SessaoFalsa([{"teste": 1}, {"teste": 2}])
        saida = StringIO()

        def processar(_cliente, coletar, _registrados):
            coletar()
            return 0

        with patch("praticagem_worker.executar", side_effect=processar), \
             patch("praticagem_worker.time.sleep"), \
             patch.object(Path, "unlink", side_effect=[None, FileNotFoundError]) as consumir, \
             redirect_stdout(saida):
            observar_continuamente(object(), lambda: sessao, max_ciclos=2,
                                   arquivo_teste=pedido)

        self.assertEqual(consumir.call_count, 2)
        self.assertEqual(saida.getvalue().count("FIM DO TESTE LOCAL"), 1)
        self.assertIn("Manobra em andamento", saida.getvalue())
        self.assertEqual(saida.getvalue().count("coleta concluída"), 2)

    def test_pedido_toxotis_usa_captura_do_ciclo(self):
        pedido = Path("toxotis.flag")
        captura = {"coletado_em": "2026-10-08T21:08:35+00:00",
                   "quantidades": {"movimentos": 0, "previstas": 0,
                                   "atracados": 0, "fundeados": 1},
                   "tabelas": {"movimentos": [], "previstas": [],
                               "atracados": [], "fundeados": [{"celulas": {
                                   "IMO": "9563419", "NAVIO": "TOXOTIS",
                                   "FUNDEIO": "03/10 09:38"}}]}}
        sessao = SessaoFalsa([captura])
        saida = StringIO()

        def processar(_cliente, coletar, _registrados):
            self.assertIs(coletar(), captura)
            return 0

        with patch("praticagem_worker.executar", side_effect=processar), \
             patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "unlink") as consumir, \
             redirect_stdout(saida):
            observar_continuamente(object(), lambda: sessao, max_ciclos=1,
                                   arquivo_toxotis=pedido)
        consumir.assert_called_once()
        self.assertIn("Manobra em previsão", saida.getvalue())
        self.assertIn("FIM DO TESTE TOXOTIS", saida.getvalue())

    def test_toxotis_le_portal_se_reserva_impede_coleta(self):
        pedido = Path("toxotis.flag")
        captura = {"coletado_em": "2026-10-08T21:08:35+00:00",
                   "quantidades": {"movimentos": 0, "previstas": 0,
                                   "atracados": 0, "fundeados": 1},
                   "tabelas": {"movimentos": [], "previstas": [],
                               "atracados": [], "fundeados": [{"celulas": {
                                   "IMO": "9563419", "NAVIO": "TOXOTIS",
                                   "FUNDEIO": "03/10 09:38"}}]}}
        sessao = SessaoFalsa([captura])
        saida = StringIO()
        with patch("praticagem_worker.executar", return_value=0), \
             patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "unlink") as consumir, \
             redirect_stdout(saida):
            observar_continuamente(object(), lambda: sessao, max_ciclos=1,
                                   arquivo_toxotis=pedido)
        consumir.assert_called_once()
        self.assertIn("Manobra em previsão", saida.getvalue())

    def test_recusa_intervalo_inferior_a_um_minuto(self):
        with self.assertRaisesRegex(ValueError, "60"):
            observar_continuamente(object(), lambda: None, intervalo=59,
                                   max_ciclos=0)


if __name__ == "__main__":
    unittest.main()
