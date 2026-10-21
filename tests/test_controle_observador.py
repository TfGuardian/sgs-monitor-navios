import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from controle_observador import processar_uma_vez, reiniciar_tarefa


class ClienteFalso:
    def __init__(self, pedido=None):
        self.pedido = pedido
        self.chamadas = []

    def rpc(self, nome, dados=None):
        self.chamadas.append((nome, dados))
        if nome == "reservar_pedido_observador":
            return SimpleNamespace(execute=lambda: SimpleNamespace(
                data=[self.pedido] if self.pedido else []))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=True))


class ControleObservadorTest(unittest.TestCase):
    def test_sem_pedido_nao_aciona_tarefa(self):
        acionar = Mock()
        self.assertFalse(processar_uma_vez(ClienteFalso(), acionar))
        acionar.assert_not_called()

    def test_conclui_pedido_apos_acionar(self):
        cliente = ClienteFalso({"pedido_id": "a", "token": "b"})
        self.assertTrue(processar_uma_vez(cliente, lambda: "iniciado"))
        self.assertEqual(cliente.chamadas[-1], (
            "concluir_pedido_observador",
            {"pedido": "a", "token": "b", "sucesso": True, "detalhe": "iniciado"},
        ))

    def test_registra_falha_sem_executar_comando_remoto(self):
        cliente = ClienteFalso({"pedido_id": "a", "token": "b"})
        def falhar():
            raise RuntimeError("tarefa ausente")
        self.assertTrue(processar_uma_vez(cliente, falhar))
        self.assertFalse(cliente.chamadas[-1][1]["sucesso"])

    def test_reinicia_apenas_tarefa_fixa(self):
        executor = Mock(return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""))
        self.assertIn("iniciado/reiniciado", reiniciar_tarefa(executor))
        argumentos = executor.call_args.args[0]
        self.assertIn("SGS Praticagem Observador", argumentos[-1])
        self.assertEqual(argumentos[0], "powershell.exe")


if __name__ == "__main__":
    unittest.main()
