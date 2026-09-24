import { parse } from "npm:node-html-parser@7.0.1";
import { createClient } from "npm:@supabase/supabase-js@2";

type Registro = Record<string, unknown>;
type Navio = Registro & {
  id?: number; lista_monitoramento_id?: number | null; nome?: string | null;
  imo?: string | null; local?: string | null; eta?: string | null;
  etb?: string | null; evento?: string | null; fonte?: string | null;
  ultima_consulta?: string | null; ultima_alteracao?: string | null;
  situacao?: string | null;
};
type MensagemMeta = { from?: string; id?: string; type?: string; text?: { body?: string } };

const META_ACCESS_TOKEN = Deno.env.get("META_ACCESS_TOKEN") ?? "";
const META_APP_SECRET = Deno.env.get("META_APP_SECRET") ?? "";
const META_PHONE_NUMBER_ID = Deno.env.get("META_PHONE_NUMBER_ID") ?? "";
const META_VERIFY_TOKEN = Deno.env.get("META_VERIFY_TOKEN") ?? "";
const META_GRAPH_API_VERSION = Deno.env.get("META_GRAPH_API_VERSION")?.trim() || "v26.0";
const APS_URL = Deno.env.get("APS_URL")?.trim() ||
  "https://www.portodesantos.com.br/painel-de-monitoramento-das-operacoes-portuarias/";
const ATRACACOES_PROGRAMADAS_URL = Deno.env.get("ATRACACOES_PROGRAMADAS_URL")?.trim() ||
  "https://www.portodesantos.com.br/informacoes-operacionais/operacoes-portuarias/" +
  "navegacao-e-movimento-de-navios/atracacoes-programadas/";
const ATRACADOS_URL = Deno.env.get("ATRACADOS_URL")?.trim() ||
  "https://www.portodesantos.com.br/informacoes-operacionais/operacoes-portuarias/" +
  "navegacao-e-movimento-de-navios/atracados-porto-terminais/";

const FUNDEADOS_URL = Deno.env.get("FUNDEADOS_URL")?.trim() ||
  "https://www.portodesantos.com.br/informacoes-operacionais/operacoes-portuarias/navegacao-e-movimento-de-navios/navios-fundeados/";

function chaveSupabase(): string {
  const legada = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (legada) return legada;
  const novas = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (!novas) throw new Error("Chave administrativa do Supabase ausente");
  const chaves = JSON.parse(novas) as Record<string, string>;
  if (!chaves.default) throw new Error("Chave default do Supabase ausente");
  return chaves.default;
}

const supabase = createClient(Deno.env.get("SUPABASE_URL") ?? "", chaveSupabase(), {
  auth: { persistSession: false },
});

function normalizar(valor: unknown): string {
  return String(valor ?? "").normalize("NFD").replace(/\p{Diacritic}/gu, "")
    .replace(/[^A-Z0-9 ]/gi, " ").replace(/\s+/g, " ").trim().toUpperCase();
}
const telefone = (valor: string) => valor.replace(/\D/g, "");
const termos = (valor: string) => valor.split(/[;\n]+/).map((i) => i.trim()).filter(Boolean);
const argumentos = (texto: string, comando: string) => termos(
  texto.replace(new RegExp(`^\\s*${comando}\\s*:?`, "i"), ""),
);

function seguroIgual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diferenca = 0;
  for (let i = 0; i < a.length; i += 1) diferenca |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diferenca === 0;
}

async function assinaturaValida(corpo: string, assinatura: string): Promise<boolean> {
  if (!META_APP_SECRET || !assinatura.startsWith("sha256=")) return false;
  const chave = await crypto.subtle.importKey("raw", new TextEncoder().encode(META_APP_SECRET),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const calculada = await crypto.subtle.sign("HMAC", chave, new TextEncoder().encode(corpo));
  const hexadecimal = Array.from(new Uint8Array(calculada))
    .map((byte) => byte.toString(16).padStart(2, "0")).join("");
  return seguroIgual(assinatura.slice(7).toLowerCase(), hexadecimal);
}

function dataHora(valor: unknown): string {
  if (!valor) return "N/A";
  const data = new Date(String(valor));
  if (Number.isNaN(data.getTime())) return String(valor);
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Sao_Paulo", dateStyle: "short", timeStyle: "short",
  }).format(data);
}

function etapaEvento(valor: unknown): [number, string, string] {
  const e = normalizar(valor);
  if (["SAIDA CONFIRMADA", "SAIU"].includes(e)) return [7, "🚢", "Saída confirmada"];
  if (e === "DESATRACADO") return [6, "🚢", "Desatracado"];
  if (["DESATRACANDO", "EM DESATRACACAO"].includes(e)) return [6, "🚢", "Desatracando"];
  if (["AG DESATRACACAO", "AGUARDANDO DESATRACACAO", "AGUARD DESATRACACAO", "AGUAR DESATRACACAO"].includes(e)) return [5, "🟢", "Aguardando desatracação"];
  if (["OPERANDO", "OPERANDO BOMBEANDO", "EM OPERACAO"].includes(e)) return [4, "🟢", "Operando"];
  if (e === "ATRACADO") return [3, "🟢", "Atracado"];
  if (["ATRACANDO", "EM ATRACACAO"].includes(e)) return [2, "🚢", "Atracando"];
  if (e === "FUNDEADO") return [1, "⚓", "Fundeado"];
  if (["ATRACACAO", "ATRACACAO PROGRAMADA", "PROGRAMADO", "AGUARDANDO ATRACACAO"].includes(e)) return [0, "🟡", "Atracação programada"];
  return [0, "⚪", String(valor || "Situação não informada")];
}

function formatarLocal(valor: unknown): string {
  return String(valor ?? "").trim().replace(/\b(?:ultraf[eé]rtil|ultraf|tiplan|tiplam)\b/gi, "Tiplam");
}

function formatarDados(navio: Navio, completo: boolean): string {
  const blocos = completo ? ["🔎 *Detalhes do navio*"] : [];
  blocos.push(`🚢 *${navio.nome || "N/A"}*` + (completo && navio.imo ? `\n*IMO:* ${navio.imo}` : ""));
  const indisponivel = normalizar(navio.situacao || "indisponivel") === "INDISPONIVEL";
  const antigo = normalizar(navio.situacao) === "DESATUALIZADO" || Boolean(navio.ultima_consulta && Date.now() - new Date(navio.ultima_consulta).getTime() > 7200000);
  const fontes = String(navio.fonte || "").split(" + ");
  let [rank, emoji, estado] = etapaEvento(navio.evento);
  if (normalizar(navio.evento) === "SITUACAO EM VERIFICACAO") { emoji = "⚠️"; estado = "Situação em verificação"; }
  else if (rank < 3 && fontes.includes("APS_ATRACADOS")) { rank = 3; emoji = "🟢"; estado = "Atracado"; }
  else if (!navio.evento && fontes.includes("APS_ATRACACOES_PROGRAMADAS")) { emoji = "🟡"; estado = "Atracação programada"; }
  if (indisponivel) blocos.push("⚪ *Dados indisponíveis*", "Não localizado nas fontes consultadas nesta coleta.");
  else {
    if (antigo) blocos.push("⚠️ *Dados desatualizados*", "As informações abaixo correspondem à última consulta disponível.");
    let status = antigo ? `*Última situação registrada:* ${estado}` : `${emoji} *${estado}*`;
    if (navio.local && navio.local !== "N/A") status += `\n📍 *${rank < 3 ? "Terminal previsto" : "Local"}:* ${formatarLocal(navio.local)}`;
    blocos.push(status);
    const previsoes = [];
    if (navio.eta && navio.eta !== "N/A") previsoes.push(`*Chegada (ETA):* ${navio.eta}`);
    if (rank < 3 && navio.etb && navio.etb !== "N/A") previsoes.push(`⏳ *Atracação prevista:* ${navio.etb}`);
    if (previsoes.length) blocos.push((completo ? "*Datas*\n\n" : "") + previsoes.join("\n"));
  }
  const dados = [];
  if (navio.ultima_consulta) dados.push(`🕒 *${completo ? "Última consulta" : "Consulta"}:* ${dataHora(navio.ultima_consulta)}`);
  if (completo && navio.ultima_alteracao) dados.push(`*Última alteração:* ${dataHora(navio.ultima_alteracao)}`);
  if (completo && navio.fonte) dados.push(`*Fonte:* ${navio.fonte.replaceAll("APS_ATRACACOES_PROGRAMADAS", "Atracações programadas").replaceAll("APS_FUNDEADOS", "Navios fundeados").replaceAll("APS_ATRACADOS", "Navios atracados").replaceAll("APS_PAINEL", "Painel do porto")}`);
  if (dados.length) blocos.push((completo ? "*Atualização dos dados*\n\n" : "") + dados.join("\n"));
  return blocos.join("\n\n");
}
function formatarNavio(navio: Navio): string { return formatarDados(navio, true); }
function formatarResumo(navio: Navio): string { return formatarDados(navio, false); }

function distancia(a: string, b: string): number {
  let anterior = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i += 1) {
    const atual = [i];
    for (let j = 1; j <= b.length; j += 1) {
      atual[j] = Math.min(atual[j - 1] + 1, anterior[j] + 1,
        anterior[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    anterior = atual;
  }
  return anterior[b.length];
}

function sugerir(procurado: string, navios: Navio[], limite = 5): string[] {
  const alvo = normalizar(procurado);
  return navios.filter((n) => n.nome).map((n) => ({
    nome: String(n.nome), pontos: distancia(alvo, normalizar(n.nome)),
  })).sort((a, b) => a.pontos - b.pontos).slice(0, limite)
    .filter((i) => i.pontos <= Math.max(3, Math.floor(alvo.length * 0.45))).map((i) => i.nome);
}

function localizar(consulta: string, navios: Navio[]): Navio[] {
  const alvo = normalizar(consulta);
  const exatos = navios.filter((n) => normalizar(n.nome) === alvo ||
    (alvo !== "" && normalizar(n.imo) === alvo));
  return exatos.length ? exatos : navios.filter((n) => normalizar(n.nome).includes(alvo));
}

async function ehAdministrador(numero: string): Promise<boolean> {
  const { data, error } = await supabase.from("administradores_chat").select("id")
    .eq("telefone", telefone(numero)).eq("ativo", true).limit(1);
  if (error) throw error;
  return Boolean(data?.length);
}

async function visaoMonitorados(): Promise<Navio[]> {
  const [{ data: lista, error: erroLista }, { data: dados, error: erroDados }] = await Promise.all([
    supabase.from("lista_monitoramento").select("*").eq("ativo", true).order("nome_confirmado"),
    supabase.from("navios_monitorados").select("*").not("lista_monitoramento_id", "is", null),
  ]);
  if (erroLista) throw erroLista;
  if (erroDados) throw erroDados;
  const porLista = new Map(((dados ?? []) as Navio[]).map((n) => [n.lista_monitoramento_id, n]));
  return ((lista ?? []) as Registro[]).map((item) => ({
    nome: item.nome_confirmado as string, imo: item.imo as string | null,
    situacao: "indisponivel", lista_monitoramento_id: item.id as number,
    ...(porLista.get(item.id as number) ?? {}),
  }));
}

// Mesmo intermediario publico usado por monitor_aps.py. Incorporado para permitir
// publicar apenas index.ts pelo editor do Supabase. Nao e uma chave privada.
const APS_CERTIFICADO_INTERMEDIARIO = `-----BEGIN CERTIFICATE-----
MIIGTDCCBDSgAwIBAgIQLBo8dulD3d3/GRsxiQrtcTANBgkqhkiG9w0BAQwFADBfMQswCQYDVQQG
EwJHQjEYMBYGA1UEChMPU2VjdGlnbyBMaW1pdGVkMTYwNAYDVQQDEy1TZWN0aWdvIFB1YmxpYyBT
ZXJ2ZXIgQXV0aGVudGljYXRpb24gUm9vdCBSNDYwHhcNMjEwMzIyMDAwMDAwWhcNMzYwMzIxMjM1
OTU5WjBgMQswCQYDVQQGEwJHQjEYMBYGA1UEChMPU2VjdGlnbyBMaW1pdGVkMTcwNQYDVQQDEy5T
ZWN0aWdvIFB1YmxpYyBTZXJ2ZXIgQXV0aGVudGljYXRpb24gQ0EgT1YgUjM2MIIBojANBgkqhkiG
9w0BAQEFAAOCAY8AMIIBigKCAYEApkMtJ3R06jo0fceI0M52B7K+TyMeGcv2BQ5AVc3jlYt76TvH
Iu/nNe22W/RJXX9rWUD/2GE6GF5x0V4bsY7K3IeJ8E7+KzG/TGboySfDu+F52jqQBbY62ofhYjMe
iAbLI02+FqwHeM8uIrUtcX8b2RCxF358TB0NHVccAXZcFYgZndZCeXxjuca7pJJ20LLUnXtgXcjA
E1vY4WvbReW0W6mkeZyNGdmpTcFs5Y+syy6LtE5Zocji9J9NlNnReox2RWVyEXpA1ChZ4gqN+ZpV
SIQ0HBorVFbBKyhdZyEXgZgNSNtBRwxqwIzJePJhYd4ZUhO1vk+/uP3nwDk0p95q/j7naXNCSvES
nrHPypaBWRK066nKfPRPi9m9kIOhMdYfS8giFRTcdgL24Ycilj7ecAK9Trh0VbjwouJ4WH+xbt47
u68ZFCD/ac55I0DNHkCpaPruj6e9Rmr7K46wZDAYXuEAqB7tGG/jd6JAA+H2O44CV98NRsU213f1
kScIZntNAgMBAAGjggGBMIIBfTAfBgNVHSMEGDAWgBRWc1hklfmSGrASKgRieaFAFYghSTAdBgNV
HQ4EFgQU42Z0u3BojSxdTg6mSo+bNyKcgpIwDgYDVR0PAQH/BAQDAgGGMBIGA1UdEwEB/wQIMAYB
Af8CAQAwHQYDVR0lBBYwFAYIKwYBBQUHAwEGCCsGAQUFBwMCMBsGA1UdIAQUMBIwBgYEVR0gADAI
BgZngQwBAgIwVAYDVR0fBE0wSzBJoEegRYZDaHR0cDovL2NybC5zZWN0aWdvLmNvbS9TZWN0aWdv
UHVibGljU2VydmVyQXV0aGVudGljYXRpb25Sb290UjQ2LmNybDCBhAYIKwYBBQUHAQEEeDB2ME8G
CCsGAQUFBzAChkNodHRwOi8vY3J0LnNlY3RpZ28uY29tL1NlY3RpZ29QdWJsaWNTZXJ2ZXJBdXRo
ZW50aWNhdGlvblJvb3RSNDYucDdjMCMGCCsGAQUFBzABhhdodHRwOi8vb2NzcC5zZWN0aWdvLmNv
bTANBgkqhkiG9w0BAQwFAAOCAgEABZXWDHWC3cubb/e1I1kzi8lPFiK/ZUoH09ufmVOrc5ObYH/X
KkWUexSPqRkwKFKr7r8OuG+p7VNB8rifX6uopqKAgsvZtZsq7iAFw04To6vNcxeBt1Eush3cQ4b8
nbQRMQLChgEAqwhuXp9P48T4QEBSksYav7+aFjNySsLYlPzNqVM3RNwvBdvp6vgDtGwcxlKQZVuu
NVIaoYyls8swhxDeSHKpRdxRauTLZ+pl+wGvy0pnrLEJGSz9mOEmfbode/XopR2NGqaHJ6bIjyxP
u6UtyQGI26En7UAEozACrHz06Nx2jTAY9E6NeB6XuobEwLK025ZRmvglcURG1BrV24tGHHTgxCe8
M3oGlpUSMTKQ2dkgljZVYt+gKdFtWELZMuRdi+X3XsrR8LFz+aLUiDRfQqhmw3RxjIyVKvvu9UPY
Y1nsvxYmFnUSeM+2q1z/iPUry+xDY9MC6+IhleKT094VKdFVp7LXH42+wvU+17lRolQ2mK2N/nBL
VBwaIhibQXw4VYKwB86Bc6eS6iqsc94KEgD/U4VsjmgfhK+Xp4NM+VYzTTa3QeV3p8xOM0cwq1p8
oZFA+OBcz3FYWpDIe5j0NWKlw9hXsTyPY/HeZUV59akskSOSRSmDfe8wJDPX58uB9/7lud0G3x0p
xQAcffP0ayKavNwDTw4UfJ34cEw=
-----END CERTIFICATE-----`;
let clienteHttpsAps: Deno.HttpClient | undefined;

function clienteParaAps(url: string): Deno.HttpClient | undefined {
  const destino = new URL(url);
  if (destino.protocol !== "https:" ||
      !["www.portodesantos.com.br", "portodesantos.com.br"].includes(destino.hostname)) {
    return undefined;
  }
  // Acrescenta a CA confiavel sem desativar a verificacao TLS ou do hostname.
  clienteHttpsAps ??= Deno.createHttpClient({ caCerts: [APS_CERTIFICADO_INTERMEDIARIO] });
  return clienteHttpsAps;
}

async function coletarPaginaAps(
  url: string, fonte: string, permitirVazio = false, eventoPadrao: string | null = null,
): Promise<Navio[]> {
  const response = await fetch(url, {
    client: clienteParaAps(url),
    headers: { "User-Agent": "Mozilla/5.0 (compatible; SGS-Monitor-Navios/1.0)" },
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error(`APS indisponivel: HTTP ${response.status}`);
  return extrairPaginaAps(await response.text(), fonte, permitirVazio, eventoPadrao);
}

function extrairPaginaAps(
  html: string, fonte: string, permitirVazio = false, eventoPadrao: string | null = null,
): Navio[] {
  const raiz = parse(html);
  const resultado: Navio[] = [];
  let reconhecida = false;
  for (const tabela of raiz.querySelectorAll("table")) {
    const linhas = tabela.querySelectorAll("tr");
    if (!linhas.length) continue;
    // A programacao inclui uma linha de titulo (data/turno) antes das colunas.
    // Exige Navio e outra coluna operacional para nao tratar uma linha de dados como cabecalho.
    const linhaCabecalho = linhas.findIndex((linha) => {
      const textos = linha.querySelectorAll("th,td").map((c) => normalizar(c.textContent));
      return textos.some((c) => /^(NAVIO|VESSEL|SHIP|BUQUE)/.test(c)) &&
        textos.some((c) => /^(LOCAL|BERCO|TERMINAL|ETA|IMO|STATUS|EVENTO)/.test(c));
    });
    if (linhaCabecalho < 0) continue;
    const cabecalhos = linhas[linhaCabecalho].querySelectorAll("th,td")
      .map((c) => normalizar(c.textContent));
    const indice = (nomes: string[]) => cabecalhos.findIndex((c) => nomes.some((n) => c.includes(n)));
    const iNavio = indice(["NAVIO", "VESSEL", "SHIP", "BUQUE"]);
    if (iNavio < 0) continue;
    reconhecida = true;
    const iImo = indice(["IMO"]), iEta = indice(["ETA"]), iEtb = indice(["ATRACACAO", "ETB"]);
    const iLocal = indice(["LOCAL", "BERCO", "TERMINAL"]), iEvento = indice(["STATUS", "EVENTO"]);
    const iData = indice(["DATA", "DATE", "FECHA"]), iHora = indice(["HORA", "HOUR"]);
    for (const linha of linhas.slice(linhaCabecalho + 1)) {
      const celulas = linha.querySelectorAll("td").map((c) => c.textContent.trim());
      let nome = celulas[iNavio]?.trim();
      if (fonte === "APS_FUNDEADOS") nome = nome?.replace(/\s+PROGRAMADO$/i, "").trim();
      if (!nome || normalizar(nome) === cabecalhos[iNavio]) continue;
      const etbProgramado = [iData >= 0 ? celulas[iData] : "", iHora >= 0 ? celulas[iHora] : ""]
        .filter(Boolean).join(" ") || null;
      resultado.push({ nome, imo: iImo >= 0 ? celulas[iImo] || null : null,
        eta: fonte !== "APS_FUNDEADOS" && iEta >= 0 ? celulas[iEta] || null : null,
        etb: fonte === "APS_FUNDEADOS" ? null : iEtb >= 0 ? celulas[iEtb] || null : etbProgramado,
        local: fonte !== "APS_FUNDEADOS" && iLocal >= 0 ? celulas[iLocal] || null : null,
        viagem: indice(["VIAGEM", "VOYAGE"]) >= 0 ? celulas[indice(["VIAGEM", "VOYAGE"])] || null : null,
        duv: indice(["DUV"]) >= 0 ? celulas[indice(["DUV"])] || null : null,
        evento: eventoPadrao || (iEvento >= 0 ? celulas[iEvento] || null : null), fonte });
    }
  }
  if (!reconhecida || (!permitirVazio && !resultado.length)) {
    console.error(JSON.stringify({ evento: "fonte_formato_invalido", fonte,
      tabelas: raiz.querySelectorAll("table").length, registros: resultado.length }));
    throw new Error("A APS nao retornou uma tabela reconhecida");
  }
  return resultado;
}

function adicionarFonte(atual: string | null | undefined, nova: string): string {
  const fontes = String(atual || "").split(" + ").filter(Boolean);
  if (!fontes.includes(nova)) fontes.push(nova);
  return fontes.join(" + ");
}

function identificadorEscala(valor: unknown, campo: string): string {
  const texto = String(valor ?? "").trim().replace(/\s+/g, " ").toUpperCase();
  if (campo === "viagem") {
    const partes = texto.match(/^(\d+)(?:-\d+|--)?[ /]+(\d{4})$/);
    if (partes) return `${Number(partes[1])}/${partes[2]}`;
  }
  return normalizar(texto).replace(/[^A-Z0-9]/g, "");
}

function mesclarFontes(painel: Navio[], programadas: Navio[], atracados: Navio[], fundeados: Navio[] = []): Navio[] {
  const imo = (n: Navio) => String(n.imo || "").replace(/\.0$/, "").replace(/^0+/, "");
  const mesmo = (a: Navio, b: Navio) => imo(a) && imo(b) ? imo(a) === imo(b) : normalizar(a.nome) === normalizar(b.nome);
  const grupos: Navio[][] = [];
  const entradas: [string, Navio[]][] = [["APS_ATRACACOES_PROGRAMADAS", programadas], ["APS_PAINEL", painel], ["APS_ATRACADOS", atracados], ["APS_FUNDEADOS", fundeados]];
  for (const [fonte, registros] of entradas) for (const original of registros) {
    const navio = {...original, fonte};
    if (fonte === "APS_FUNDEADOS") { delete navio.local; delete navio.eta; delete navio.etb; }
    const candidatos = grupos.filter(g => g.some(n => mesmo(n, navio) || normalizar(n.nome) === normalizar(navio.nome)));
    if (!candidatos.length) grupos.push([navio]);
    else {
      candidatos[0].push(navio);
      for (const outro of candidatos.slice(1)) { candidatos[0].push(...outro); grupos.splice(grupos.indexOf(outro), 1); }
    }
  }
  const data = (n: Navio): number => {
    for (const c of ["etb", "eta"]) {
      const v = String(n[c] || "");
      const m = v.match(/^(\d{2})\/(\d{2})\/(\d{2}|\d{4}) (\d{2}):(\d{2})(?::\d{2})?$/);
      if (m) return Date.UTC(Number(m[3]) < 100 ? 2000 + Number(m[3]) : Number(m[3]), Number(m[2])-1, Number(m[1]), Number(m[4]), Number(m[5]));
      if (/^\d{4}-\d{2}-\d{2} /.test(v)) return Date.parse(v) || 0;
    }
    return 0;
  };
  const recente = (ns: Navio[]) => ns.reduce((a,b) => data(b) > data(a) ? b : a);
  return grupos.map(grupo => {
    const identificados = grupo.filter(n => n.viagem || n.duv);
    const referencia = identificados.find(n => n.fonte === "APS_FUNDEADOS") || identificados.find(n => n.fonte === "APS_ATRACADOS") || recente(identificados.length ? identificados : grupo);
    const atuais = grupo.filter(n => !["viagem", "duv"].some(c => n[c] && referencia[c] && identificadorEscala(n[c], c) !== identificadorEscala(referencia[c], c)) && !(imo(n) && imo(referencia) && !mesmo(n,referencia)));
    const programacao = atuais.filter(n => n.fonte === "APS_ATRACACOES_PROGRAMADAS");
    const painelAtual = atuais.filter(n => n.fonte === "APS_PAINEL");
    const base: Navio = {...recente(programacao.length ? programacao : painelAtual.length ? painelAtual : atuais)};
    for (const n of painelAtual) for (const [c,v] of Object.entries(n)) if (v != null && v !== "") base[c] = v;
    const candidatos = atuais.map(n => {
      const evento = n.fonte === "APS_ATRACADOS" ? "ATRACADO" : n.fonte === "APS_FUNDEADOS" ? "FUNDEADO" : n.fonte === "APS_ATRACACOES_PROGRAMADAS" ? "ATRACACAO PROGRAMADA" : String(n.evento || "");
      return {rank: etapaEvento(evento)[0], n, evento};
    });
    const escolhido = candidatos.reduce((a,b) => b.rank > a.rank ? b : a);
    if (escolhido.rank > 0) { base.evento = escolhido.evento; if (escolhido.n.fonte !== "APS_FUNDEADOS" && escolhido.n.local) base.local = escolhido.n.local; }
    else if (["ATRACACAO", "PROGRAMADO", "ATRACACAO PROGRAMADA"].includes(normalizar(base.evento))) base.evento = "ATRACACAO PROGRAMADA";
    if (programacao.length) { base.eta = recente(programacao).eta; base.etb = recente(programacao).etb; }
    if (escolhido.rank < 3 && programacao.length) base.local = recente(programacao).local || base.local;
    if (escolhido.rank >= 3) base.etb = null;
    base.fonte = [...new Set(atuais.map(n => n.fonte))].join(" + ");
    return base;
  });
}

async function coletarAps(): Promise<Navio[]> {
  const [painel, programadas, atracados, fundeados] = await Promise.all([
    coletarPaginaAps(APS_URL, "APS_PAINEL"),
    coletarPaginaAps(
      ATRACACOES_PROGRAMADAS_URL, "APS_ATRACACOES_PROGRAMADAS", true,
    ),
    coletarPaginaAps(ATRACADOS_URL, "APS_ATRACADOS", true, "ATRACADO"),
    coletarPaginaAps(FUNDEADOS_URL, "APS_FUNDEADOS", true, "FUNDEADO"),
  ]);
  return mesclarFontes(painel, programadas, atracados, fundeados);
}

function motivoFalhaAdicao(erro: unknown): string {
  const detalhe = erro instanceof Error ? `${erro.name} ${erro.message}` : "";
  if (/certificate|unknownissuer|invalidpeer|tls|certificado/i.test(detalhe)) return "certificado_https";
  if (/timeout|abort/i.test(detalhe)) return "tempo_esgotado";
  if (/APS indisponivel: HTTP \d{3}/.test(detalhe)) {
    return `fonte_http_${detalhe.match(/HTTP (\d{3})/)?.[1]}`;
  }
  if (/tabela reconhecida/.test(detalhe)) return "formato_fonte_nao_reconhecido";
  const codigo = (erro as { code?: unknown } | null)?.code;
  if (typeof codigo === "string" && /^(?:[0-9A-Z]{5}|PGRST[0-9]{3})$/.test(codigo)) {
    return `banco_${codigo}`;
  }
  return "falha_nao_classificada";
}

async function adicionarNavios(numero: string, solicitados: string[]): Promise<string> {
  let etapa = "consultar_fontes";
  console.info(JSON.stringify({ evento: "adicionar_inicio", quantidade: solicitados.length }));
  try {
  const catalogo = await coletarAps();
  console.info(JSON.stringify({ evento: "adicionar_catalogo", registros: catalogo.length }));
  etapa = "consultar_lista";
  const atuais = await visaoMonitorados();
  const mensagens: string[] = [];
  for (const solicitado of solicitados) {
    const encontrado = catalogo.find((n) => normalizar(n.nome) === normalizar(solicitado) ||
      (normalizar(n.imo) !== "" && normalizar(n.imo) === normalizar(solicitado)));
    if (!encontrado) {
      const sugestoes = sugerir(solicitado, catalogo);
      mensagens.push(`🔎 *Navio não localizado nas fontes do porto*\n\n*${solicitado}* não foi adicionado.\n\nConfira o nome e tente novamente.` +
        (sugestoes.length ? `\n\n*Nomes semelhantes*\n\n${sugestoes.map((n) => `🚢 *${n}*`).join("\n")}` : ""));
      continue;
    }
    if (atuais.some((n) => normalizar(n.nome) === normalizar(encontrado.nome))) {
      mensagens.push(`ℹ️ *Navio já monitorado*\n\n🚢 *${encontrado.nome}*\n\nO navio já consta na lista.`);
      continue;
    }
    const agora = new Date().toISOString();
    etapa = "salvar_lista";
    const { data: item, error: erroLista } = await supabase.from("lista_monitoramento").upsert({
      nome_solicitado: solicitado, nome_confirmado: encontrado.nome,
      nome_normalizado: normalizar(encontrado.nome), imo: encontrado.imo, ativo: true,
      adicionado_por: telefone(numero), atualizado_em: agora,
    }, { onConflict: "nome_normalizado" }).select("*").single();
    if (erroLista) throw erroLista;
    const operacional = { ...encontrado, lista_monitoramento_id: item.id,
      ultima_consulta: agora, ultima_alteracao: agora, situacao: "atualizado",
      ausencias_consecutivas: 0 };
    etapa = "salvar_dados_operacionais";
    const { data: antigos, error: erroAntigos } = await supabase.from("navios_monitorados")
      .select("id,nome,imo");
    if (erroAntigos) throw erroAntigos;
    const antigo = ((antigos ?? []) as Navio[]).find((n) =>
      normalizar(n.nome) === normalizar(encontrado.nome) ||
      (normalizar(encontrado.imo) !== "" && normalizar(n.imo) === normalizar(encontrado.imo)));
    const operacao = antigo?.id
      ? supabase.from("navios_monitorados").update(operacional).eq("id", antigo.id)
      : supabase.from("navios_monitorados").insert(operacional);
    const { error: erroOperacional } = await operacao;
    if (erroOperacional) throw erroOperacional;
    mensagens.push(`✅ *Navio adicionado*\n\n🚢 *${encontrado.nome}*\n\nO navio agora faz parte da *lista de monitoramento*.`);
  }
  console.info(JSON.stringify({ evento: "adicionar_concluido" }));
  return mensagens.join("\n\n") || "🔎 *Informe o navio*\n\nEnvie o *nome completo* do navio.";
  } catch (erro) {
    const motivo = motivoFalhaAdicao(erro);
    console.error(JSON.stringify({ evento: "adicionar_falhou", etapa, motivo }));
    if (etapa === "consultar_fontes") {
      return "⚠️ *Cadastro não realizado*\n\nNão foi possível consultar as fontes do porto.\n\n*Nenhum navio foi adicionado.* Tente novamente em instantes.";
    }
    return "⚠️ *Cadastro não concluído*\n\nParte do pedido pode ter sido salva.\n\nEnvie *Lista* para conferir antes de tentar novamente.";
  }
}

async function prepararRemocao(numero: string, solicitados: string[]): Promise<string> {
  const navios = await visaoMonitorados(), selecionados: Navio[] = [], ausentes: string[] = [];
  for (const solicitado of solicitados) {
    const encontrados = localizar(solicitado, navios);
    if (encontrados.length === 1) selecionados.push(encontrados[0]); else ausentes.push(solicitado);
  }
  if (!selecionados.length) return "🔎 *Nenhum navio selecionado*\n\nOs nomes informados não foram encontrados na lista.\n\nEnvie *Lista* para conferir os nomes cadastrados.";
  const payload = { ids: selecionados.map((n) => n.lista_monitoramento_id),
    nomes: selecionados.map((n) => n.nome) };
  const { error } = await supabase.from("confirmacoes_chat").upsert({
    telefone: telefone(numero), acao: "remover_navios", payload,
    criado_em: new Date().toISOString(), expira_em: new Date(Date.now() + 600000).toISOString(),
  }, { onConflict: "telefone" });
  if (error) throw error;
  return "🗑️ *Solicitação de remoção*\n\n" + payload.nomes.map((n) => `🚢 *${n}*`).join("\n") +
    "\n\n😺 Posso remover estes navios da lista?\n\n*Confirmar* — remover\n*Cancelar* — manter\n\n⏳ Confirmação válida por *10 minutos*." +
    (ausentes.length ? `\n\n*Nomes não encontrados na lista*\n\n${ausentes.join(", ")}\n\nA confirmação vale apenas para os navios selecionados acima.` : "");
}

async function confirmarRemocao(numero: string): Promise<string> {
  const { data, error } = await supabase.rpc("confirmar_remocao_chat", { numero: telefone(numero) });
  if (error) throw error;
  const removidos = (data ?? []) as string[];
  return removidos.length ? "✅ *Remoção concluída*\n\n" + removidos.map((nome) => `🚢 *${nome}*`).join("\n") + "\n\nRemoção da *lista de monitoramento* realizada."
    : "ℹ️ *Nenhum navio removido*\n\nA solicitação não está mais válida ou os dados dos navios voltaram a ficar disponíveis.\n\nEnvie *Lista* para conferir o monitoramento atual.";
}

async function definirRelatorio(numero: string, ativo: boolean): Promise<void> {
  const agora = new Date().toISOString();
  const { error } = await supabase.from("destinatarios_relatorio").upsert({
    telefone: telefone(numero), ativo, inscrito_em: agora, cancelado_em: ativo ? null : agora,
  }, { onConflict: "telefone" });
  if (error) throw error;
}

// Reserva espaco para o numero da parte; preserva todo o conteudo.
function dividirResposta(texto: string, limite = 3800): string[] {
  const caracteres = Array.from(texto);
  const paginas: string[] = [];
  let inicio = 0;
  while (inicio < caracteres.length) {
    let fim = Math.min(inicio + limite, caracteres.length);
    if (fim < caracteres.length) {
      const trecho = caracteres.slice(inicio, fim);
      const quebra = trecho.lastIndexOf("\n");
      if (quebra > 0) fim = inicio + quebra + 1;
    }
    paginas.push(caracteres.slice(inicio, fim).join(""));
    inicio = fim;
  }
  return paginas.length > 1
    ? paginas.map((pagina, i) => `📄 *Parte ${i + 1} de ${paginas.length}*\n\n${pagina}`)
    : paginas;
}

async function responder(destinatario: string, texto: string): Promise<void> {
  if (!META_ACCESS_TOKEN || !META_PHONE_NUMBER_ID) throw new Error("Credenciais da Meta ausentes");
  const response = await fetch(
    `https://graph.facebook.com/${META_GRAPH_API_VERSION}/${META_PHONE_NUMBER_ID}/messages`, {
      method: "POST", headers: { Authorization: `Bearer ${META_ACCESS_TOKEN}`,
        "Content-Type": "application/json" },
      body: JSON.stringify({ messaging_product: "whatsapp", recipient_type: "individual",
        to: destinatario, type: "text", text: { preview_url: false, body: texto } }),
    });
  if (!response.ok) throw new Error(`Meta recusou a resposta: ${await response.text()}`);
  console.info(JSON.stringify({ evento: "resposta_aceita_pela_meta", http_status: response.status }));
}

// Dispara somente o executor fixo; nunca aceita URL ou workflow vindos do chat.
async function dispararAtualizacaoGitHub(): Promise<boolean> {
  const token = Deno.env.get("GH_ACTIONS_TOKEN")?.trim();
  if (!token) {
    console.info(JSON.stringify({ evento: "disparo_github", resultado: "nao_configurado" }));
    return false;
  }
  try {
    const resposta = await fetch(
      "https://api.github.com/repos/TfGuardian/sgs-monitor-navios/actions/workflows/atualizar-chat.yml/dispatches",
      {
        method: "POST",
        redirect: "error",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2026-03-10",
          "User-Agent": "sgs-monitor-navios",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: "main" }),
        signal: AbortSignal.timeout(4000),
      },
    );
    console.info(JSON.stringify({ evento: "disparo_github", http_status: resposta.status,
      resultado: resposta.ok ? "aceito" : "recusado" }));
    await resposta.body?.cancel();
    return resposta.ok;
  } catch {
    console.warn(JSON.stringify({ evento: "disparo_github", resultado: "falha_rede_ou_timeout" }));
    return false;
  }
}

const atualizacaoAtiva = () => ["true", "1", "sim"].includes(
  (Deno.env.get("ATUALIZACAO_CHAT_ATIVA") ?? "").trim().toLowerCase(),
);

async function respostaComando(remetente: string, texto: string): Promise<string> {
  const comando = normalizar(texto), admin = await ehAdministrador(remetente);
  if (comando === "ATUALIZAR") {
    if (!admin) return "🔒 *Acesso restrito*\n\nEste comando está disponível apenas para *administradores*.";
    if (!atualizacaoAtiva()) return "ℹ️ *Atualização temporariamente indisponível*\n\nEnvie *Resumo* para consultar os dados da última coleta.";
    const { error } = await supabase.rpc("solicitar_atualizacao_chat", { numero: telefone(remetente) });
    if (error) throw error;
    const disparado = await dispararAtualizacaoGitHub();
    return disparado
      ? "⏳ *Atualização solicitada*\n\nO *resumo atualizado* será enviado por aqui após a conclusão da coleta."
      : "⏳ *Pedido registrado*\n\nNão foi possível iniciar a coleta agora. A solicitação permanece na *fila de processamento*.";
  }
  if (["AJUDA", "MENU", "COMANDOS", "OI", "OLA", "BOM DIA", "BOA TARDE", "BOA NOITE"].includes(comando)) {
    let menu = "🚢 *Monitor de Navios*\n\nDigite o *nome do navio* ou utilize os comandos abaixo.\n\n*Consultas*\n\n🔎 *Consultar NOME* — detalhes do navio\n📋 *Lista* — navios monitorados\n📊 *Resumo* — dados da última coleta";
    if (admin && atualizacaoAtiva()) menu += "\n🔄 *Atualizar* — buscar dados novos";
    if (admin) menu += "\n\n*Gerenciar a lista*\n\n➕ *Adicionar NOME* — incluir navio\n➖ *Remover NOME* — solicitar remoção\n✅ *Confirmar* — aprovar remoção\n↩️ *Cancelar* — cancelar solicitação";
    return menu + "\n\n*Relatórios*\n\n🔔 *Assinar* — receber relatórios\n🔕 *Parar* — suspender relatórios";
  }
  if (["ASSINAR", "RECEBER RELATORIO"].includes(comando)) {
    await definirRelatorio(remetente, true);
    return "🔔 *Inscrição realizada*\n\nO recebimento de relatórios está habilitado para este número.\n\nOs relatórios serão enviados quando o *envio automático estiver ativo*.";
  }
  if (["PARAR", "PARAR RELATORIO"].includes(comando)) {
    await definirRelatorio(remetente, false);
    return "🔕 *Recebimento de relatórios desativado*\n\nPara reativar, envie *Assinar*.";
  }
  if (comando === "RESUMO") {
    const navios = await visaoMonitorados();
    const titulo = "📊 *Resumo dos navios*\n\nInformações da *última coleta*.";
    return titulo + "\n\n" + (navios.length
      ? navios.map(formatarResumo).join("\n\n───────────────\n\n")
      : "📋 *Lista de monitoramento vazia*\n\nPara incluir um navio, um administrador deve enviar *Adicionar NOME*.");
  }
  if (["LISTA", "LISTAR MONITORADOS"].includes(comando)) {
    const navios = await visaoMonitorados();
    const { error } = await supabase.from("listas_exibidas_chat").upsert({
      telefone: telefone(remetente), itens: navios.map((n) => n.lista_monitoramento_id),
      atualizado_em: new Date().toISOString(),
    }, { onConflict: "telefone" });
    if (error) throw error;
    return navios.length ? "📋 *Navios monitorados*\n\n" +
      navios.map((n, i) => `${i + 1}. *${n.nome}*`).join("\n") + "\n\n🔎 Para consultar os detalhes, envie o *número da lista* ou o *nome do navio*." : "📋 *Lista de monitoramento vazia*\n\nPara incluir um navio, um administrador deve enviar *Adicionar NOME*.";
  }
  if (["SIM", "CONFIRMAR"].includes(comando)) return admin
    ? await confirmarRemocao(remetente) : "🔒 *Acesso restrito*\n\nEste comando está disponível apenas para *administradores*.";
  if (["NAO", "CANCELAR"].includes(comando)) {
    await supabase.from("confirmacoes_chat").delete().eq("telefone", telefone(remetente));
    return "↩️ *Solicitação cancelada*\n\nA lista de monitoramento foi *mantida*.";
  }
  if (comando.startsWith("ADICIONAR")) {
    if (!admin) return "🔒 *Inclusão restrita*\n\nApenas *administradores* podem adicionar navios à lista.";
    const itens = argumentos(texto, "adicionar");
    return itens.length ? await adicionarNavios(remetente, itens) : "➕ *Informe o navio para adicionar*\n\nExemplo: *Adicionar ECO CZAR*\n\nPara vários navios, separe os nomes com *;*\n*Adicionar ECO CZAR; AETERNO*";
  }
  if (comando.startsWith("REMOVER")) {
    if (!admin) return "🔒 *Remoção restrita*\n\nApenas *administradores* podem remover navios da lista.";
    const itens = argumentos(texto, "remover");
    return itens.length ? await prepararRemocao(remetente, itens) : "➖ *Informe o navio para remover*\n\nExemplo: *Remover ECO CZAR*\n\nPara vários navios, separe os nomes com *;*\n*Remover ECO CZAR; AETERNO*";
  }
  if (/^[0-9]{1,6}$/.test(texto.trim())) {
    const { data, error } = await supabase.from("listas_exibidas_chat").select("itens")
      .eq("telefone", telefone(remetente)).limit(1);
    if (error) throw error;
    const itens = data?.[0]?.itens as (number | null)[] | undefined;
    if (!itens?.length) return "📋 *Lista necessária*\n\nEnvie *Lista* e depois o *número do navio* desejado.";
    const posicao = Number(texto.trim());
    if (posicao < 1 || posicao > itens.length) return `🔎 *Número fora da lista*\n\nDigite um número de *1 a ${itens.length}* ou envie *Lista* novamente.`;
    const navios = await visaoMonitorados();
    const selecionado = navios.find((n) => n.lista_monitoramento_id != null && n.lista_monitoramento_id === itens[posicao - 1]);
    return selecionado ? formatarNavio(selecionado) : "ℹ️ *Navio não monitorado*\n\nEste navio não está mais na lista. Envie *Lista* para consultar a relação atual.";
  }
  const navios = await visaoMonitorados();
  const consultas = comando.startsWith("CONSULTAR") ? argumentos(texto, "consultar") : termos(texto);
  const respostas: string[] = [];
  for (const consulta of consultas) {
    const encontrados = localizar(consulta, navios);
    if (encontrados.length === 1) respostas.push(formatarNavio(encontrados[0]));
    else if (encontrados.length > 1) respostas.push(`🔎 *Mais de um navio encontrado*\n\nResultados para *${consulta}*:\n\n` +
      encontrados.slice(0, 8).map((n) => `🚢 *${n.nome}*`).join("\n") + "\n\nEnvie o *nome completo* do navio desejado.");
    else {
      const sugestoes = sugerir(consulta, navios);
      respostas.push(`🔎 *Navio não encontrado*\n\n*${consulta}* não consta na lista de monitoramento.\n\nEnvie *Lista* para consultar os nomes cadastrados.` +
        (sugestoes.length ? "\n\n*Nomes semelhantes*\n\n" + sugestoes.map((n) => `🚢 *${n}*`).join("\n") : ""));
    }
  }
  return respostas.join("\n\n───────────────\n\n") || "🔎 *Informe o navio*\n\nEnvie *Consultar ECO CZAR* ou apenas *ECO CZAR*.";
}

async function processarMensagem(mensagem: MensagemMeta): Promise<void> {
  const remetente = telefone(mensagem.from ?? ""), messageId = mensagem.id ?? "";
  if (!remetente || !messageId) {
    console.info(JSON.stringify({ evento: "mensagem_ignorada", motivo: "remetente_ou_id_ausente" }));
    return;
  }
  const texto = mensagem.text?.body?.trim() ?? "";
  const { error: eventoErro } = await supabase.from("whatsapp_webhook_eventos")
    .insert({ message_id: messageId, remetente, mensagem: texto || null });
  if (eventoErro?.code === "23505") {
    console.info(JSON.stringify({ evento: "mensagem_ignorada", motivo: "duplicada" }));
    return;
  }
  if (eventoErro) throw eventoErro;
  try {
    console.info(JSON.stringify({ evento: "processando_mensagem", tipo: mensagem.type ?? "ausente" }));
    const resposta = mensagem.type === "text" && texto
      ? await respostaComando(remetente, texto) : "💬 *Envie uma mensagem de texto*\n\nO atendimento aceita *comandos e nomes de navios em texto*.\n\nEnvie *Ajuda* para consultar os comandos.";
    for (const pagina of dividirResposta(resposta)) await responder(remetente, pagina);
  } catch (erro) {
    await supabase.from("whatsapp_webhook_eventos").delete().eq("message_id", messageId);
    throw erro;
  }
}

function mensagensDoWebhook(payload: Registro): MensagemMeta[] {
  const mensagens: MensagemMeta[] = [];
  for (const entry of (Array.isArray(payload.entry) ? payload.entry : []) as Registro[]) {
    for (const change of (Array.isArray(entry.changes) ? entry.changes : []) as Registro[]) {
      const value = change.value as Registro | undefined;
      if (Array.isArray(value?.messages)) mensagens.push(...value.messages as MensagemMeta[]);
    }
  }
  return mensagens;
}

Deno.serve(async (request) => {
  try {
    if (request.method === "GET") {
      const url = new URL(request.url), modo = url.searchParams.get("hub.mode") ?? "";
      const token = url.searchParams.get("hub.verify_token") ?? "";
      const desafio = url.searchParams.get("hub.challenge") ?? "";
      return modo === "subscribe" && META_VERIFY_TOKEN && seguroIgual(token, META_VERIFY_TOKEN)
        ? new Response(desafio, { status: 200 }) : new Response("Verificacao recusada", { status: 403 });
    }
    if (request.method !== "POST") return new Response("Metodo nao permitido", { status: 405 });
    const corpo = await request.text(), assinatura = request.headers.get("x-hub-signature-256") ?? "";
    if (!(await assinaturaValida(corpo, assinatura))) return new Response("Assinatura invalida", { status: 401 });
    const payload = JSON.parse(corpo) as Registro;
    const mensagens = mensagensDoWebhook(payload);
    let totalStatus = 0;
    for (const entry of (Array.isArray(payload.entry) ? payload.entry : []) as Registro[]) {
      for (const change of (Array.isArray(entry.changes) ? entry.changes : []) as Registro[]) {
        const value = change.value as Registro | undefined;
        for (const status of (Array.isArray(value?.statuses) ? value.statuses : []) as Registro[]) {
          totalStatus += 1;
          console.info(JSON.stringify({ evento: "status_entrega", status: status.status,
            codigos_erro: (Array.isArray(status.errors) ? status.errors : [])
              .map((erro: Registro) => erro.code) }));
        }
      }
    }
    console.info(JSON.stringify({ evento: "webhook_recebido", mensagens: mensagens.length,
      atualizacoes_status: totalStatus }));
    for (const mensagem of mensagens) await processarMensagem(mensagem);
    return Response.json({ recebido: true });
  } catch (erro) {
    console.error(erro);
    return Response.json({ erro: "Falha ao processar webhook" }, { status: 500 });
  }
});
