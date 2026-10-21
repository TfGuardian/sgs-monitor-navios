import io
import unittest
import os
import sys
import tempfile
import subprocess
import ctypes
from ctypes import wintypes
from pathlib import Path
from unittest.mock import Mock

from executar_praticagem_windows import Espelho, executar_filho, supervisionar


class EspelhoTest(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Grupo de processos do Windows")
    def test_saida_124_encerra_descendente_sem_afetar_processo_externo(self):
        raiz = Path(__file__).resolve().parents[1]
        externo = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            with tempfile.TemporaryDirectory() as pasta:
                alvo = Path(pasta) / "filho.py"
                alvo.write_text("import subprocess, sys, os\n"
                    "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
                    "print(p.pid, flush=True)\nos._exit(124)\n", encoding="utf-8")
                with (Path(pasta) / "log.txt").open("a", encoding="utf-8") as log:
                    codigo = executar_filho([sys.executable, "-u",
                        str(raiz / "iniciar_filho_observador.py"), str(alvo)],
                        os.environ.copy(), log, None, proteger=True)
                self.assertEqual(codigo, 124)
                pid = int((Path(pasta) / "log.txt").read_text().strip())
                api = ctypes.WinDLL("kernel32", use_last_error=True)
                api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                api.OpenProcess.restype = wintypes.HANDLE
                api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                api.CloseHandle.argtypes = [wintypes.HANDLE]
                handle = api.OpenProcess(0x100000, False, pid)
                if handle:
                    try:
                        self.assertEqual(api.WaitForSingleObject(handle, 2000), 0)
                    finally:
                        api.CloseHandle(handle)
                else:
                    self.assertEqual(ctypes.get_last_error(), 87)
                self.assertIsNone(externo.poll())
        finally:
            externo.terminate()
            externo.wait(timeout=10)

    def test_reinicia_apos_saida_real_do_watchdog(self):
        console = io.StringIO()
        codigos = iter([124, 0])
        with tempfile.NamedTemporaryFile(mode="a", encoding="utf-8", delete=False) as log:
            caminho = log.name
        try:
            with open(caminho, "a", encoding="utf-8") as log:
                def rodar():
                    codigo = next(codigos)
                    return executar_filho(
                        [sys.executable, "-u", "-c",
                         f"import os; print('filho {codigo}', flush=True); os._exit({codigo})"],
                        os.environ.copy(), log, console)
                espera = Mock()
                supervisionar(rodar, espera)
                espera.assert_called_once_with(15)
            self.assertIn("filho 124", console.getvalue())
            self.assertIn("filho 0", console.getvalue())
        finally:
            os.unlink(caminho)

    def test_guarda_emoji_no_log_mesmo_com_console_antigo(self):
        registro = io.StringIO()
        bytes_console = io.BytesIO()
        console = io.TextIOWrapper(bytes_console, encoding="cp1252")
        espelho = Espelho(registro, console)
        espelho.write("🚢 Manobra em andamento\n")
        espelho.flush()
        self.assertEqual(registro.getvalue(), "🚢 Manobra em andamento\n")
        self.assertIn(b"\\U0001f6a2", bytes_console.getvalue())


if __name__ == "__main__":
    unittest.main()
