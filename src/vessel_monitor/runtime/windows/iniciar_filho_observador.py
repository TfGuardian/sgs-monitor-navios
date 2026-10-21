"""Espera a associação ao grupo do Windows antes de iniciar o processo."""
import runpy
import sys


def main() -> None:
    if sys.stdin.readline().strip() != "INICIAR":
        raise SystemExit(125)
    alvo = sys.argv[1]
    sys.argv = sys.argv[1:]
    if alvo.endswith(".py"):
        runpy.run_path(alvo, run_name="__main__")
    else:
        runpy.run_module(alvo, run_name="__main__")


if __name__ == "__main__":
    main()
