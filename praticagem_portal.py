"""Captura diagnóstica das tabelas visíveis da SP Pilots, sem gravar no banco.

Requer Playwright e credenciais em variáveis de ambiente. Este leitor faz uma
única coleta; não agenda chamadas e não envia mensagens.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


URL_LOGIN = "https://login.sppilots.com.br/santos"
URL_SERVICOS = "https://login.sppilots.com.br/servicos"
TEMPO_ABERTURA_NAVEGADOR_MS = 60000
TEMPO_NAVEGACAO_MS = 30000
TABELAS = {
    "movimentos": ("Movimentos de Navios", {"IMO", "NAVIO", "MV", "LOC#1",
                                              "LOC#2", "POB", "PASSAG", "CALADO",
                                              "AGENTE", "BORDO", "TUG"}),
    "previstas": ("Manobras Previstas", {"IMO", "NAVIO", "MV", "LOC#1",
                                           "LOC#2", "AGENTE", "BORDO", "TUG"}),
    "atracados": ("Navios Atracados", {"IMO", "NAVIO", "LOCAL"}),
    "fundeados": ("Navios Fundeados", {"IMO", "NAVIO", "FUNDEIO"}),
}


def _limpar(valor: str) -> str:
    return " ".join(valor.split())


def cabecalhos_correspondem(nome: str, cabecalhos: list[str]) -> bool:
    return TABELAS[nome][1] == {_limpar(c).upper() for c in cabecalhos}


def validar_tabela(nome: str, cabecalhos: list[str], linhas: list[dict[str, Any]]) -> None:
    if nome not in TABELAS:
        raise ValueError(f"Tabela desconhecida: {nome}")
    normalizados = {_limpar(c).upper() for c in cabecalhos}
    faltantes = TABELAS[nome][1] - normalizados
    if faltantes:
        raise ValueError(f"Cabeçalhos ausentes em {nome}: {sorted(faltantes)}")
    adicionais = normalizados - TABELAS[nome][1]
    if adicionais:
        raise ValueError(f"Cabeçalhos inesperados em {nome}: {sorted(adicionais)}")
    if len(cabecalhos) != len(set(cabecalhos)):
        raise ValueError(f"Cabeçalhos repetidos em {nome}")
    for linha in linhas:
        if len(linha["celulas"]) != len(cabecalhos):
            raise ValueError(f"Linha incompleta em {nome}")
        if nome == "movimentos" and not linha.get("cor"):
            raise ValueError("Cor de movimento ausente")


def capturar_tabelas(page: Any) -> dict[str, list[dict[str, Any]]]:
    """Lê as quatro tabelas visíveis em uma única operação no navegador."""
    for titulo, _ in TABELAS.values():
        page.get_by_text(titulo, exact=True).first.wait_for(
            state="visible", timeout=20000)
    visiveis = page.evaluate("""() => {
      const texto = el => (el.innerText || '').replace(/\\s+/g, ' ').trim();
      const visivel = el => {
        const estilo = getComputedStyle(el);
        return el.getClientRects().length > 0 &&
          estilo.display !== 'none' && estilo.visibility !== 'hidden';
      };
      return Array.from(document.querySelectorAll('table'))
        .filter(tabela => visivel(tabela) && tabela.querySelector('tr'))
        .map(tabela => {
          const trs = Array.from(tabela.querySelectorAll('tr'));
          const cabecalhos = Array.from(trs[0].querySelectorAll('th,td')).map(texto);
          const linhas = trs.slice(1).map(tr => {
            const celulas = Array.from(tr.querySelectorAll('td')).map(texto);
            let cor = null;
            for (const el of [tr.querySelector('td'), tr, tr.parentElement]) {
              if (!el) continue;
              const valor = getComputedStyle(el).backgroundColor;
              if (valor && valor !== 'rgba(0, 0, 0, 0)' && valor !== 'transparent') {
                cor = valor;
                break;
              }
            }
            return {celulas, cor};
          }).filter(linha => linha.celulas.length);
          return {cabecalhos, linhas};
        });
    }""")
    resultado = {}
    for nome, (_, esperados) in TABELAS.items():
        candidatas = [t for t in visiveis
                      if {_limpar(c).upper() for c in t["cabecalhos"]} == esperados]
        if len(candidatas) != 1:
            raise ValueError(
                f"Tabela {nome}: {len(candidatas)} correspondências; "
                f"cabeçalhos visíveis: {[t['cabecalhos'] for t in visiveis]}")
        tabela = candidatas[0]
        cabecalhos = [_limpar(c) for c in tabela["cabecalhos"]]
        linhas = []
        for linha in tabela["linhas"]:
            celulas = [_limpar(c) for c in linha["celulas"]]
            if len(celulas) != len(cabecalhos):
                raise ValueError(f"Quantidade de células inesperada em {nome}")
            linhas.append({"celulas": dict(zip(cabecalhos, celulas)),
                           "cor": linha["cor"]})
        validar_tabela(nome, cabecalhos, linhas)
        resultado[nome] = linhas
    return resultado


def capturar_tabelas_com_retentativa(page: Any) -> dict[str, Any]:
    # Aguarda renderização parcial sem transformar tabela ausente em lista vazia.
    for tentativa in range(3):
        try:
            return capturar_tabelas(page)
        except ValueError as exc:
            if "0 correspondências" not in str(exc) or tentativa == 2:
                raise
            page.wait_for_timeout(1500)
    raise RuntimeError("Leitura não concluída")


class SessaoPraticagem:
    """Mantém um navegador e renova a sessão quando o login reaparece."""

    def __init__(self, usuario: str, senha: str, *, headless: bool = True,
                 canal: str | None = None):
        if not usuario or not senha:
            raise ValueError("Configure SPPILOTS_USUARIO e SPPILOTS_SENHA no ambiente")
        self.usuario, self.senha = usuario, senha
        self.headless, self.canal = headless, canal
        self._driver = None
        self._browser = None
        self.page = None
        self._iniciada = False

    def __enter__(self) -> "SessaoPraticagem":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Instale as dependências de requirements-praticagem.txt") from exc
        self._driver = sync_playwright().start()
        try:
            self._browser = self._driver.chromium.launch(
                headless=self.headless,
                channel=self.canal or ("msedge" if os.name == "nt" else "chromium"),
                timeout=TEMPO_ABERTURA_NAVEGADOR_MS)
            self.page = self._browser.new_page()
            # As tabelas precisam de HTML, scripts e CSS (cores dos estados).
            # Imagens, vídeos e fontes decorativas não participam da leitura.
            self.page.route("**/*", lambda rota: rota.abort()
                            if rota.request.resource_type in {"image", "media", "font"}
                            else rota.continue_())
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, _tipo: Any, _erro: Any, _pilha: Any) -> None:
        try:
            if self._browser:
                self._browser.close()
        finally:
            if self._driver:
                self._driver.stop()
            self._browser = self._driver = self.page = None
            self._iniciada = False

    def _login(self) -> None:
        self.page.goto(URL_LOGIN, wait_until="commit", timeout=TEMPO_NAVEGACAO_MS)
        self.page.get_by_placeholder("Usuário").fill(self.usuario)
        self.page.get_by_placeholder("senha").fill(self.senha)
        self.page.get_by_role("button", name="Entrar").click()
        self.page.get_by_text("Movimentos de Navios", exact=True).first.wait_for(
            state="visible", timeout=30000)

    def capturar(self) -> dict[str, Any]:
        if self.page is None:
            raise RuntimeError("Sessão do navegador não iniciada")
        if not self._iniciada:
            self._login()
            self._iniciada = True
        else:
            # O portal pode atrasar DOMContentLoaded mesmo depois de receber a
            # página. Aguarde o início da nova navegação e, em seguida, o
            # conteúdo que realmente precisamos para ler as tabelas.
            self.page.reload(wait_until="commit", timeout=TEMPO_NAVEGACAO_MS)
            entrada = self.page.get_by_placeholder("Usuário")
            movimentos = self.page.get_by_text("Movimentos de Navios", exact=True).first
            entrada.or_(movimentos).first.wait_for(state="visible", timeout=30000)
            if entrada.is_visible():
                self._login()
            else:
                movimentos.wait_for(state="visible", timeout=30000)
        tabelas = capturar_tabelas_com_retentativa(self.page)
        return {"coletado_em": datetime.now(timezone.utc).isoformat(),
                "fonte": URL_SERVICOS, "tabelas": tabelas,
                "quantidades": {nome: len(linhas) for nome, linhas in tabelas.items()}}


def capturar_portal(usuario: str, senha: str, *, headless: bool = True,
                   canal: str | None = None) -> dict[str, Any]:
    with SessaoPraticagem(usuario, senha, headless=headless, canal=canal) as sessao:
        return sessao.capturar()


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description="Uma coleta diagnóstica da Praticagem")
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--visivel", action="store_true", help="Mostra o navegador")
    parser.add_argument("--canal", choices=("msedge", "chrome", "chromium"),
                        help="Canal do navegador; no Windows, padrão msedge")
    args = parser.parse_args()
    dados = capturar_portal(os.getenv("SPPILOTS_USUARIO", ""),
                           os.getenv("SPPILOTS_SENHA", ""),
                           headless=not args.visivel, canal=args.canal)
    args.saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    print("Coleta diagnóstica concluída:", dados["quantidades"])


if __name__ == "__main__":
    main()
