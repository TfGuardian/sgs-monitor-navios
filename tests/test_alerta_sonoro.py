import unittest
from unittest.mock import MagicMock, patch
from alerta_sonoro import ARQUIVO_SOM, tocar_alerta


class SomTest(unittest.TestCase):
    def test_reproduz_miado_local(self):
        audio = MagicMock()
        audio.SND_FILENAME, audio.SND_NODEFAULT = 0x20000, 2
        with patch.dict("sys.modules", {"winsound": audio}), \
             patch("alerta_sonoro.sys.platform", "win32"), \
             patch.dict("os.environ", {"PRATICAGEM_SOM_ATIVO": "true"}):
            tocar_alerta()
        audio.PlaySound.assert_called_once_with(str(ARQUIVO_SOM), 0x20002)

    def test_falha_no_audio_nao_interrompe_coleta(self):
        audio = MagicMock()
        audio.PlaySound.side_effect = RuntimeError("sem dispositivo")
        with patch.dict("sys.modules", {"winsound": audio}), \
             patch("alerta_sonoro.sys.platform", "win32"), \
             patch.dict("os.environ", {"PRATICAGEM_SOM_ATIVO": "true"}):
            tocar_alerta()

    def test_desativado_nao_toca(self):
        audio = MagicMock()
        with patch.dict("sys.modules", {"winsound": audio}), \
             patch.dict("os.environ", {"PRATICAGEM_SOM_ATIVO": "false"}):
            tocar_alerta()
        audio.PlaySound.assert_not_called()
