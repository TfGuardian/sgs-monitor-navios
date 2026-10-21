"""Entradas continuam funcionando quando chamadas fora da raiz do projeto."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from vessel_monitor.paths import PROJECT_ROOT, LOG_DIR, STATE_DIR
from vessel_monitor.presentation.alerta_sonoro import ARQUIVO_SOM


class EntradasTest(unittest.TestCase):
    def executar(self, *argumentos, entrada=None):
        ambiente = os.environ.copy()
        ambiente["PYTHONIOENCODING"] = "utf-8"
        ambiente["PYTHONPATH"] = os.pathsep.join((
            str(PROJECT_ROOT / "src"), ambiente.get("PYTHONPATH", "")))
        with tempfile.TemporaryDirectory() as pasta:
            return subprocess.run(
                [sys.executable, *argumentos], cwd=pasta, env=ambiente,
                input=entrada, capture_output=True, text=True, encoding="utf-8",
                timeout=20, check=False,
            )

    def test_cli_e_entrada_antiga_funcionam_fora_da_raiz(self):
        for argumentos in (("-m", "vessel_monitor", "--help"),
                           (str(PROJECT_ROOT / "main.py"), "--help")):
            with self.subTest(argumentos=argumentos):
                resposta = self.executar(*argumentos)
                self.assertEqual(resposta.returncode, 0, resposta.stderr)
                self.assertIn("--sincronizar", resposta.stdout)

    def test_processador_protegido_recusa_inicio_sem_autorizacao_do_supervisor(self):
        for argumentos in (("-m", "vessel_monitor.runtime.windows.iniciar_filho_observador"),
                           (str(PROJECT_ROOT / "iniciar_filho_observador.py"),)):
            with self.subTest(argumentos=argumentos):
                resposta = self.executar(*argumentos, entrada="NAO\n")
                self.assertEqual(resposta.returncode, 125, resposta.stderr)

    def test_recursos_sao_localizados_na_raiz_apos_mover_modulos(self):
        self.assertTrue(ARQUIVO_SOM.is_file())
        certificado = PROJECT_ROOT / "certs" / "SectigoPublicServerAuthenticationCAOVR36.pem"
        self.assertTrue(certificado.is_file())
        self.assertEqual(LOG_DIR, PROJECT_ROOT / "var" / "logs")
        self.assertEqual(STATE_DIR, PROJECT_ROOT / "var" / "state")


if __name__ == "__main__":
    unittest.main()
