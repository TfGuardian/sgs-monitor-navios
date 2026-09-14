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

function formatarNavio(navio: Navio): string {
  const valor = (campo: keyof Navio) => String(navio[campo] || "N/A");
  return [
    `Nome: ${valor("nome")}`, `IMO: ${valor("imo")}`, `ETA: ${valor("eta")}`,
    `ETB: ${valor("etb")}`, `Local: ${valor("local")}`, `Evento: ${valor("evento")}`,
    `Fonte: ${valor("fonte")}`, `Ultima consulta: ${dataHora(navio.ultima_consulta)}`,
    `Ultima alteracao: ${dataHora(navio.ultima_alteracao)}`,
    `Situacao: ${String(navio.situacao || "indisponivel").toUpperCase()}`,
  ].join("\n");
}

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

async function coletarPaginaAps(
  url: string, fonte: string, permitirVazio = false, eventoPadrao: string | null = null,
): Promise<Navio[]> {
  const response = await fetch(url, {
    headers: { "User-Agent": "Mozilla/5.0 (compatible; SGS-Monitor-Navios/1.0)" },
  });
  if (!response.ok) throw new Error(`APS indisponivel: HTTP ${response.status}`);
  const raiz = parse(await response.text());
  const resultado: Navio[] = [];
  let reconhecida = false;
  for (const tabela of raiz.querySelectorAll("table")) {
    const linhas = tabela.querySelectorAll("tr");
    if (!linhas.length) continue;
    const cabecalhos = linhas[0].querySelectorAll("th,td").map((c) => normalizar(c.textContent));
    const indice = (nomes: string[]) => cabecalhos.findIndex((c) => nomes.some((n) => c.includes(n)));
    const iNavio = indice(["NAVIO", "VESSEL", "SHIP", "BUQUE"]);
    if (iNavio < 0) continue;
    reconhecida = true;
    const iImo = indice(["IMO"]), iEta = indice(["ETA"]), iEtb = indice(["ATRACACAO", "ETB"]);
    const iLocal = indice(["LOCAL", "BERCO", "TERMINAL"]), iEvento = indice(["STATUS", "EVENTO"]);
    const iData = indice(["DATA", "DATE", "FECHA"]), iHora = indice(["HORA", "HOUR"]);
    for (const linha of linhas.slice(1)) {
      const celulas = linha.querySelectorAll("td").map((c) => c.textContent.trim());
      const nome = celulas[iNavio]?.trim();
      if (!nome) continue;
      const etbProgramado = [iData >= 0 ? celulas[iData] : "", iHora >= 0 ? celulas[iHora] : ""]
        .filter(Boolean).join(" ") || null;
      resultado.push({ nome, imo: iImo >= 0 ? celulas[iImo] || null : null,
        eta: iEta >= 0 ? celulas[iEta] || null : null,
        etb: iEtb >= 0 ? celulas[iEtb] || null : etbProgramado,
        local: iLocal >= 0 ? celulas[iLocal] || null : null,
        evento: eventoPadrao || (iEvento >= 0 ? celulas[iEvento] || null : null), fonte });
    }
  }
  if (!reconhecida || (!permitirVazio && !resultado.length)) {
    throw new Error("A APS nao retornou uma tabela reconhecida");
  }
  const unicos = new Map<string, Navio>();
  for (const navio of resultado) unicos.set(normalizar(navio.nome), navio);
  return [...unicos.values()];
}

function adicionarFonte(atual: string | null | undefined, nova: string): string {
  const fontes = String(atual || "").split(" + ").filter(Boolean);
  if (!fontes.includes(nova)) fontes.push(nova);
  return fontes.join(" + ");
}

function mesclarFontes(painel: Navio[], programadas: Navio[], atracados: Navio[]): Navio[] {
  const resultado = programadas.map((navio) => ({ ...navio }));
  const porImo = new Map(resultado.filter((n) => normalizar(n.imo))
    .map((n) => [normalizar(n.imo), n]));
  const porNome = new Map(resultado.map((n) => [normalizar(n.nome), n]));
  for (const navio of painel) {
    const encontrado = (normalizar(navio.imo) ? porImo.get(normalizar(navio.imo)) : undefined) ||
      porNome.get(normalizar(navio.nome));
    if (!encontrado) {
      resultado.push({ ...navio, fonte: "APS_PAINEL" });
      continue;
    }
    for (const [campo, valor] of Object.entries(navio)) {
      if (valor !== null && valor !== "") encontrado[campo] = valor;
    }
    encontrado.fonte = "APS_PAINEL + APS_ATRACACOES_PROGRAMADAS";
  }
  const porNomeAtual = new Map(resultado.map((n) => [normalizar(n.nome), n]));
  const porImoAtual = new Map(resultado.filter((n) => normalizar(n.imo))
    .map((n) => [normalizar(n.imo), n]));
  for (const atracado of atracados) {
    const encontrado = (normalizar(atracado.imo)
      ? porImoAtual.get(normalizar(atracado.imo)) : undefined) ||
      porNomeAtual.get(normalizar(atracado.nome));
    if (!encontrado) {
      resultado.push({ ...atracado, evento: "ATRACADO", fonte: "APS_ATRACADOS" });
      continue;
    }
    if (atracado.nome) encontrado.nome = atracado.nome;
    if (atracado.local) encontrado.local = atracado.local;
    encontrado.evento = "ATRACADO";
    encontrado.fonte = adicionarFonte(encontrado.fonte, "APS_ATRACADOS");
  }
  return resultado;
}

async function coletarAps(): Promise<Navio[]> {
  const [painel, programadas, atracados] = await Promise.all([
    coletarPaginaAps(APS_URL, "APS_PAINEL"),
    coletarPaginaAps(
      ATRACACOES_PROGRAMADAS_URL, "APS_ATRACACOES_PROGRAMADAS", true,
    ),
    coletarPaginaAps(ATRACADOS_URL, "APS_ATRACADOS", true, "ATRACADO"),
  ]);
  return mesclarFontes(painel, programadas, atracados);
}

async function adicionarNavios(numero: string, solicitados: string[]): Promise<string> {
  const catalogo = await coletarAps();
  const atuais = await visaoMonitorados();
  const mensagens: string[] = [];
  for (const solicitado of solicitados) {
    const encontrado = catalogo.find((n) => normalizar(n.nome) === normalizar(solicitado) ||
      (normalizar(n.imo) !== "" && normalizar(n.imo) === normalizar(solicitado)));
    if (!encontrado) {
      const sugestoes = sugerir(solicitado, catalogo);
      mensagens.push(`Nao encontrado: ${solicitado}` +
        (sugestoes.length ? `\nVoce quis dizer: ${sugestoes.join(", ")}` : ""));
      continue;
    }
    if (atuais.some((n) => normalizar(n.nome) === normalizar(encontrado.nome))) {
      mensagens.push(`Ja acompanhado: ${encontrado.nome}`);
      continue;
    }
    const agora = new Date().toISOString();
    const { data: item, error: erroLista } = await supabase.from("lista_monitoramento").upsert({
      nome_solicitado: solicitado, nome_confirmado: encontrado.nome,
      nome_normalizado: normalizar(encontrado.nome), imo: encontrado.imo, ativo: true,
      adicionado_por: telefone(numero), atualizado_em: agora,
    }, { onConflict: "nome_normalizado" }).select("*").single();
    if (erroLista) throw erroLista;
    const operacional = { ...encontrado, lista_monitoramento_id: item.id,
      ultima_consulta: agora, ultima_alteracao: agora, situacao: "atualizado",
      ausencias_consecutivas: 0 };
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
    mensagens.push(`Adicionado: ${encontrado.nome}`);
  }
  return mensagens.join("\n\n") || "Nenhum navio foi informado.";
}

async function prepararRemocao(numero: string, solicitados: string[]): Promise<string> {
  const navios = await visaoMonitorados(), selecionados: Navio[] = [], ausentes: string[] = [];
  for (const solicitado of solicitados) {
    const encontrados = localizar(solicitado, navios);
    if (encontrados.length === 1) selecionados.push(encontrados[0]); else ausentes.push(solicitado);
  }
  if (!selecionados.length) return "Nenhum dos navios informados esta na lista.";
  const payload = { ids: selecionados.map((n) => n.lista_monitoramento_id),
    nomes: selecionados.map((n) => n.nome) };
  const { error } = await supabase.from("confirmacoes_chat").upsert({
    telefone: telefone(numero), acao: "remover_navios", payload,
    criado_em: new Date().toISOString(), expira_em: new Date(Date.now() + 600000).toISOString(),
  }, { onConflict: "telefone" });
  if (error) throw error;
  return "Confirma a remocao?\n\n" + payload.nomes.map((n) => `- ${n}`).join("\n") +
    "\n\nResponda SIM para confirmar ou NAO para cancelar." +
    (ausentes.length ? `\n\nNao encontrados: ${ausentes.join(", ")}` : "");
}

async function confirmarRemocao(numero: string): Promise<string> {
  const normalizado = telefone(numero);
  const { data, error } = await supabase.from("confirmacoes_chat").select("*")
    .eq("telefone", normalizado).maybeSingle();
  if (error) throw error;
  if (!data || new Date(data.expira_em).getTime() < Date.now()) {
    await supabase.from("confirmacoes_chat").delete().eq("telefone", normalizado);
    return "Nao existe uma remocao pendente ou ela expirou.";
  }
  const payload = data.payload as { ids: number[]; nomes: string[] };
  const { error: erroRemocao } = await supabase.from("lista_monitoramento").delete().in("id", payload.ids);
  if (erroRemocao) throw erroRemocao;
  await supabase.from("confirmacoes_chat").delete().eq("telefone", normalizado);
  return "Removidos:\n" + payload.nomes.map((n) => `- ${n}`).join("\n");
}

async function definirRelatorio(numero: string, ativo: boolean): Promise<void> {
  const agora = new Date().toISOString();
  const { error } = await supabase.from("destinatarios_relatorio").upsert({
    telefone: telefone(numero), ativo, inscrito_em: agora, cancelado_em: ativo ? null : agora,
  }, { onConflict: "telefone" });
  if (error) throw error;
}

async function responder(destinatario: string, texto: string): Promise<void> {
  if (!META_ACCESS_TOKEN || !META_PHONE_NUMBER_ID) throw new Error("Credenciais da Meta ausentes");
  const response = await fetch(
    `https://graph.facebook.com/${META_GRAPH_API_VERSION}/${META_PHONE_NUMBER_ID}/messages`, {
      method: "POST", headers: { Authorization: `Bearer ${META_ACCESS_TOKEN}`,
        "Content-Type": "application/json" },
      body: JSON.stringify({ messaging_product: "whatsapp", recipient_type: "individual",
        to: destinatario, type: "text", text: { preview_url: false, body: texto.slice(0, 4096) } }),
    });
  if (!response.ok) throw new Error(`Meta recusou a resposta: ${await response.text()}`);
}

async function respostaComando(remetente: string, texto: string): Promise<string> {
  const comando = normalizar(texto), admin = await ehAdministrador(remetente);
  if (["AJUDA", "MENU", "COMANDOS"].includes(comando)) {
    const base = ["Envie o nome do navio para consultar.", "Consultar: NAVIO A; NAVIO B",
      "Listar monitorados", "Receber relatorio", "Parar relatorio"];
    if (admin) base.push("Adicionar: NAVIO A; NAVIO B", "Remover: NAVIO A; NAVIO B");
    return "COMANDOS DISPONIVEIS\n\n" + base.map((i) => `- ${i}`).join("\n");
  }
  if (comando === "RECEBER RELATORIO") {
    await definirRelatorio(remetente, true);
    return "Inscricao realizada. Voce recebera o relatorio horario.";
  }
  if (comando === "PARAR RELATORIO") {
    await definirRelatorio(remetente, false);
    return "Envio do relatorio cancelado.";
  }
  if (comando === "LISTAR MONITORADOS") {
    const navios = await visaoMonitorados();
    return navios.length ? "NAVIOS ACOMPANHADOS\n\n" +
      navios.map((n, i) => `${i + 1}. ${n.nome}`).join("\n") : "Nenhum navio esta sendo acompanhado.";
  }
  if (["SIM", "CONFIRMAR"].includes(comando)) return admin
    ? await confirmarRemocao(remetente) : "Seu numero nao possui permissao administrativa.";
  if (["NAO", "CANCELAR"].includes(comando)) {
    await supabase.from("confirmacoes_chat").delete().eq("telefone", telefone(remetente));
    return "Operacao cancelada.";
  }
  if (comando.startsWith("ADICIONAR")) {
    if (!admin) return "Seu numero nao possui permissao para adicionar navios.";
    const itens = argumentos(texto, "adicionar");
    return itens.length ? await adicionarNavios(remetente, itens) : "Use: Adicionar: NAVIO A; NAVIO B";
  }
  if (comando.startsWith("REMOVER")) {
    if (!admin) return "Seu numero nao possui permissao para remover navios.";
    const itens = argumentos(texto, "remover");
    return itens.length ? await prepararRemocao(remetente, itens) : "Use: Remover: NAVIO A; NAVIO B";
  }
  const navios = await visaoMonitorados();
  const consultas = comando.startsWith("CONSULTAR") ? argumentos(texto, "consultar") : termos(texto);
  const respostas: string[] = [];
  for (const consulta of consultas) {
    const encontrados = localizar(consulta, navios);
    if (encontrados.length === 1) respostas.push(formatarNavio(encontrados[0]));
    else if (encontrados.length > 1) respostas.push(`Encontrei mais de um resultado para "${consulta}":\n` +
      encontrados.slice(0, 8).map((n) => `- ${n.nome}`).join("\n") + "\nInforme o nome completo.");
    else {
      const sugestoes = sugerir(consulta, navios);
      respostas.push(`O navio "${consulta}" nao esta na lista de acompanhamento.` +
        (sugestoes.length ? "\n\nVoce quis dizer:\n" + sugestoes.map((n) => `- ${n}`).join("\n") : ""));
    }
  }
  return respostas.join("\n\n--------------------\n\n") || "Informe o nome do navio.";
}

async function processarMensagem(mensagem: MensagemMeta): Promise<void> {
  const remetente = telefone(mensagem.from ?? ""), messageId = mensagem.id ?? "";
  if (!remetente || !messageId) return;
  const texto = mensagem.text?.body?.trim() ?? "";
  const { error: eventoErro } = await supabase.from("whatsapp_webhook_eventos")
    .insert({ message_id: messageId, remetente, mensagem: texto || null });
  if (eventoErro?.code === "23505") return;
  if (eventoErro) throw eventoErro;
  try {
    const resposta = mensagem.type === "text" && texto
      ? await respostaComando(remetente, texto) : "Envie um comando ou nome de navio em texto.";
    await responder(remetente, resposta);
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
    for (const mensagem of mensagensDoWebhook(payload)) await processarMensagem(mensagem);
    return Response.json({ recebido: true });
  } catch (erro) {
    console.error(erro);
    return Response.json({ erro: "Falha ao processar webhook" }, { status: 500 });
  }
});
