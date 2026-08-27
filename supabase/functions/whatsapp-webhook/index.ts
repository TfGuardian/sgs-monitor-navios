import { createClient } from "npm:@supabase/supabase-js@2";

type Navio = {
  nome?: string | null;
  imo?: string | null;
  local?: string | null;
  eta?: string | null;
  etb?: string | null;
  evento?: string | null;
  fonte?: string | null;
};

type MensagemMeta = {
  from?: string;
  id?: string;
  type?: string;
  text?: { body?: string };
};

const META_ACCESS_TOKEN = Deno.env.get("META_ACCESS_TOKEN") ?? "";
const META_APP_SECRET = Deno.env.get("META_APP_SECRET") ?? "";
const META_PHONE_NUMBER_ID = Deno.env.get("META_PHONE_NUMBER_ID") ?? "";
const META_VERIFY_TOKEN = Deno.env.get("META_VERIFY_TOKEN") ?? "";
const META_GRAPH_API_VERSION =
  Deno.env.get("META_GRAPH_API_VERSION")?.trim() || "v25.0";

function chaveSupabase(): string {
  const legada = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (legada) return legada;
  const novas = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (!novas) throw new Error("Chave administrativa do Supabase ausente");
  const chaves = JSON.parse(novas) as Record<string, string>;
  if (!chaves.default) throw new Error("Chave default do Supabase ausente");
  return chaves.default;
}

const supabase = createClient(
  Deno.env.get("SUPABASE_URL") ?? "",
  chaveSupabase(),
  { auth: { persistSession: false } },
);

function normalizar(valor: unknown): string {
  return String(valor ?? "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/[^A-Z0-9 ]/gi, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase();
}

function telefoneAutorizado(telefone: string): boolean {
  const configurados = Deno.env.get("WHATSAPP_ALLOWED_PHONES")?.trim();
  if (!configurados) return true;
  const permitidos = configurados
    .split(",")
    .map((item) => item.replace(/\D/g, ""))
    .filter(Boolean);
  return permitidos.includes(telefone.replace(/\D/g, ""));
}

function seguroIgual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diferenca = 0;
  for (let i = 0; i < a.length; i += 1) {
    diferenca |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diferenca === 0;
}

async function assinaturaValida(corpo: string, assinatura: string): Promise<boolean> {
  if (!META_APP_SECRET || !assinatura.startsWith("sha256=")) return false;
  const chave = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(META_APP_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const calculada = await crypto.subtle.sign(
    "HMAC",
    chave,
    new TextEncoder().encode(corpo),
  );
  const hexadecimal = Array.from(new Uint8Array(calculada))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  return seguroIgual(assinatura.slice(7).toLowerCase(), hexadecimal);
}

function formatarNavio(navio: Navio): string {
  const valor = (campo: keyof Navio) => navio[campo] || "N/A";
  return [
    "🚢 *INFORMAÇÕES DO NAVIO*",
    "",
    `📌 *Navio:* ${valor("nome")}`,
    `🔢 *IMO:* ${valor("imo")}`,
    `📍 *Local:* ${valor("local")}`,
    `📅 *ETA:* ${valor("eta")}`,
    `⚓ *ETB:* ${valor("etb")}`,
    `🏷️ *Evento:* ${valor("evento")}`,
    `🏢 *Fonte:* ${valor("fonte")}`,
  ].join("\n");
}

const PALAVRAS_IGNORADAS = new Set([
  "A", "AS", "COM", "DA", "DAS", "DE", "DO", "DOS", "E", "EM", "ESTA",
  "ESTAO", "INFORMACAO", "INFORMACOES", "ME", "NAVIO", "O", "ONDE", "OS",
  "POR", "QUAL", "QUAIS", "QUERO", "SOBRE", "STATUS", "UM", "UMA",
]);

function localizarNavios(pergunta: string, navios: Navio[]): Navio[] {
  const consulta = normalizar(pergunta);
  const imo = consulta.match(/\b\d{7}\b/)?.[0];
  if (imo) {
    return navios.filter((navio) => String(navio.imo ?? "").replace(/\D/g, "") === imo);
  }

  const nomesContidos = navios.filter((navio) => {
    const nome = normalizar(navio.nome);
    return nome.length >= 3 && consulta.includes(nome);
  });
  if (nomesContidos.length) {
    const maior = Math.max(...nomesContidos.map((navio) => normalizar(navio.nome).length));
    return nomesContidos.filter((navio) => normalizar(navio.nome).length === maior);
  }

  const termos = consulta
    .split(" ")
    .filter((termo) => termo.length >= 3 && !PALAVRAS_IGNORADAS.has(termo));
  if (!termos.length) return [];

  const pontuados = navios.map((navio) => {
    const nome = normalizar(navio.nome);
    const pontos = termos.reduce(
      (total, termo) => total + (nome.includes(termo) ? termo.length : 0),
      0,
    );
    return { navio, pontos };
  });
  const maior = Math.max(0, ...pontuados.map((item) => item.pontos));
  return maior < 3
    ? []
    : pontuados.filter((item) => item.pontos === maior).map((item) => item.navio);
}

async function responder(destinatario: string, texto: string): Promise<void> {
  if (!META_ACCESS_TOKEN || !META_PHONE_NUMBER_ID) {
    throw new Error("Credenciais de envio da Meta ausentes");
  }
  const response = await fetch(
    `https://graph.facebook.com/${META_GRAPH_API_VERSION}/${META_PHONE_NUMBER_ID}/messages`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${META_ACCESS_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        recipient_type: "individual",
        to: destinatario,
        type: "text",
        text: { preview_url: false, body: texto.slice(0, 4096) },
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Meta recusou a resposta: ${await response.text()}`);
  }
}

async function processarMensagem(mensagem: MensagemMeta): Promise<void> {
  const remetente = mensagem.from?.replace(/\D/g, "") ?? "";
  const messageId = mensagem.id ?? "";
  if (!remetente || !messageId || !telefoneAutorizado(remetente)) return;

  const texto = mensagem.text?.body?.trim() ?? "";
  const { error: eventoErro } = await supabase
    .from("whatsapp_webhook_eventos")
    .insert({ message_id: messageId, remetente, mensagem: texto || null });
  if (eventoErro?.code === "23505") return;
  if (eventoErro) throw eventoErro;

  try {
    if (mensagem.type !== "text" || !texto) {
      await responder(remetente, "Envie o nome do navio ou o número IMO em texto.");
      return;
    }

    const { data, error } = await supabase
      .from("navios_monitorados")
      .select("nome,imo,local,eta,etb,evento,fonte");
    if (error) throw error;
    const encontrados = localizarNavios(texto, (data ?? []) as Navio[]);

    if (encontrados.length === 1) {
      await responder(remetente, formatarNavio(encontrados[0]));
      return;
    }
    if (encontrados.length > 1) {
      const opcoes = encontrados
        .slice(0, 8)
        .map((navio) => `• ${navio.nome}`)
        .join("\n");
      await responder(
        remetente,
        `Encontrei mais de um navio. Informe o nome completo ou IMO:\n${opcoes}`,
      );
      return;
    }
    await responder(
      remetente,
      "Não encontrei esse navio no monitoramento. Envie o nome completo ou o IMO com 7 dígitos.",
    );
  } catch (erro) {
    // Se a resposta falhar, libera o evento para uma nova tentativa da Meta.
    await supabase
      .from("whatsapp_webhook_eventos")
      .delete()
      .eq("message_id", messageId);
    throw erro;
  }
}

function mensagensDoWebhook(payload: Record<string, unknown>): MensagemMeta[] {
  const mensagens: MensagemMeta[] = [];
  const entries = Array.isArray(payload.entry) ? payload.entry : [];
  for (const entry of entries as Array<Record<string, unknown>>) {
    const changes = Array.isArray(entry.changes) ? entry.changes : [];
    for (const change of changes as Array<Record<string, unknown>>) {
      const value = change.value as Record<string, unknown> | undefined;
      if (Array.isArray(value?.messages)) {
        mensagens.push(...(value.messages as MensagemMeta[]));
      }
    }
  }
  return mensagens;
}

Deno.serve(async (request) => {
  try {
    if (request.method === "GET") {
      const url = new URL(request.url);
      const modo = url.searchParams.get("hub.mode") ?? "";
      const token = url.searchParams.get("hub.verify_token") ?? "";
      const desafio = url.searchParams.get("hub.challenge") ?? "";
      if (modo === "subscribe" && META_VERIFY_TOKEN && seguroIgual(token, META_VERIFY_TOKEN)) {
        return new Response(desafio, { status: 200 });
      }
      return new Response("Verificação recusada", { status: 403 });
    }

    if (request.method !== "POST") {
      return new Response("Método não permitido", { status: 405 });
    }
    const corpo = await request.text();
    const assinatura = request.headers.get("x-hub-signature-256") ?? "";
    if (!(await assinaturaValida(corpo, assinatura))) {
      return new Response("Assinatura inválida", { status: 401 });
    }
    const payload = JSON.parse(corpo) as Record<string, unknown>;
    for (const mensagem of mensagensDoWebhook(payload)) {
      await processarMensagem(mensagem);
    }
    return Response.json({ recebido: true });
  } catch (erro) {
    console.error(erro);
    return Response.json({ erro: "Falha ao processar webhook" }, { status: 500 });
  }
});
