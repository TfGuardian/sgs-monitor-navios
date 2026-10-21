import unittest
from praticagem_por_nome import preparar_por_nome
from praticagem_normalizador import normalizar_captura
from praticagem_snapshot import construir_snapshot
from praticagem_observador import montar_pacote


def captura(linhas):
    tabelas = {"movimentos": linhas,"previstas":[],"atracados":[],"fundeados":[]}
    return {"tabelas":tabelas,"quantidades":{t:len(v) for t,v in tabelas.items()}}


def linha(nome, imo="0000000", cor="rgb(0, 191, 255)"):
    return {"celulas":{"NAVIO":nome,"IMO":imo,"MV":"E"},"cor":cor}


class NomeTest(unittest.TestCase):
    def test_nome_sem_imo_e_outro_navio_invalido(self):
        c = captura([linha("  BÉLUGA  "),linha("OUTRO",cor="invalida")])
        f,m,cat,b,a = preparar_por_nome(c,[{"nome_confirmado":"beluga"}],{})
        snap = construir_snapshot(normalizar_captura(f,chaves_internas=True),{})
        self.assertEqual(len(snap["navios"]),1)
        self.assertEqual(set(m),{snap["navios"][0]["imo"]})
        self.assertFalse(b)
        self.assertTrue(any(n["nome"].strip() == "BÉLUGA" and n["imo"] is None for n in cat))

    def test_preserva_historico_legado_pelo_nome(self):
        old={"9398321":{"nome":"BELUGA"}}
        f,m,_,_,_=preparar_por_nome(captura([linha("BELUGA")]),[{"nome_confirmado":"BELUGA","imo":"9999999"}],old)
        self.assertEqual(list(m),["9398321"])

    def test_imo_altera_sem_mudar_identidade(self):
        c=captura([linha("BELUGA")]); r=[{"nome_confirmado":"BELUGA"}]
        _,m,_,_,_=preparar_por_nome(c,r,{})
        chave=next(iter(m))
        _,novo,_,_,_=preparar_por_nome(captura([linha("BELUGA","9398321")]),r,{chave:{"nome":"BELUGA"}})
        self.assertEqual(m,novo)

    def test_imo_igual_nome_diferente_nao_seleciona(self):
        f,m,cat,_,_=preparar_por_nome(captura([linha("OUTRO","9398321")]),[{"nome_confirmado":"BELUGA","imo":"9398321"}],{})
        self.assertFalse(f["tabelas"]["movimentos"])
        self.assertEqual(cat,[{"nome":"OUTRO","imo":"9398321"}])

    def test_homonimos_isolados(self):
        f,m,_,b,_=preparar_por_nome(captura([linha("BELUGA","1111111"),linha("BELUGA","2222222")]),[{"nome_confirmado":"BELUGA"}],{})
        self.assertEqual(b,list(m))
        self.assertFalse(f["tabelas"]["movimentos"])

    def test_transicao_sem_imo_gera_evento(self):
        r=[{"nome_confirmado":"BELUGA"}]
        f,m,_,_,_=preparar_por_nome(captura([linha("BELUGA",cor="rgb(255, 255, 255)")]),r,{})
        inicial=construir_snapshot(normalizar_captura(f,chaves_internas=True),{})
        old={n["imo"]:n for n in inicial["navios"]}
        f,m,_,_,_=preparar_por_nome(captura([linha("BELUGA")]),r,old)
        atual=construir_snapshot(normalizar_captura(f,chaves_internas=True),old)
        _,eventos=montar_pacote(atual,m,old,[])
        self.assertEqual(eventos[0]["mudancas"][0]["depois"],"andamento")
