"""Espera o supervisor vincular o processo ao grupo antes de executar código."""
import runpy
import sys

if sys.stdin.readline().strip() != "INICIAR":
    raise SystemExit(125)
alvo = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(alvo, run_name="__main__")
