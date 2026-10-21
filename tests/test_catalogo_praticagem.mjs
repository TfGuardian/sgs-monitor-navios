import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {stripTypeScriptTypes} from 'node:module';
import vm from 'node:vm';
const require = createRequire(import.meta.url);
const {PGlite} = require('../tmp/webhook-validation/node_modules/@electric-sql/pglite');
const db = new PGlite();
await db.exec(`create role anon; create role authenticated; create role service_role;
create table destinatarios_relatorio(telefone text primary key, ativo boolean);`);
for (const file of ['20261007180000_praticagem_observacao.sql','20261013120000_catalogo_praticagem.sql'])
  await db.exec(readFileSync(`supabase/migrations/${file}`, 'utf8'));
const publish = async (catalogo) => {
  const token = (await db.query('select reservar_coleta_praticagem() token')).rows[0].token;
  return db.query(`select concluir_coleta_catalogo_praticagem($1,'[]','[]','{}',10,$2)`,
    [token, JSON.stringify(catalogo)]);
};
await publish([{imo:'9398321',nome:'TORINO'},{imo:'1111111',nome:'OUTRO'}]);
await publish([{imo:'9398321',nome:'TORINO'}]);
assert.equal((await db.query('select navios from catalogo_praticagem')).rows[0].navios.length,1);
await assert.rejects(publish([]));
assert.equal((await db.query('select count(*)::int n from coletas_praticagem')).rows[0].n,2);
await db.exec(readFileSync('supabase/migrations/20261015170000_catalogo_por_nome.sql','utf8'));
await db.exec('update controle_praticagem set reserva_token=null,reserva_ate=null');
await publish([{imo:null,nome:'SEM IMO'}]);
assert.equal((await db.query('select navios from catalogo_praticagem')).rows[0].navios[0].nome,'SEM IMO');
await db.exec('set role anon');
await assert.rejects(db.query('select * from catalogo_praticagem'));
await db.close();

const source = readFileSync('supabase/functions/whatsapp-webhook/index.ts','utf8');
const trecho = source.slice(source.indexOf('async function catalogoParaCadastro'),
  source.indexOf('async function adicionarNavios'));
let fail=false, cached={navios:[{imo:'9398321',nome:'TORINO'}],atualizado_em:new Date().toISOString()};
const context = vm.createContext({console, Date, supabase:{from:()=>({select:()=>({eq:()=>({maybeSingle:async()=>({data:cached})})})})},
  coletarAps:async()=>{if(fail) throw Error('timeout'); return [{nome:'APS'}];}});
vm.runInContext(stripTypeScriptTypes(trecho),context);
assert.equal((await context.catalogoParaCadastro()).reserva,false);
fail=true;
assert.equal((await context.catalogoParaCadastro()).navios[0].nome,'TORINO');
cached.atualizado_em = new Date(Date.now()-301000).toISOString();
await assert.rejects(context.catalogoParaCadastro());
cached=null;
await assert.rejects(context.catalogoParaCadastro());
console.log('Catálogo: substituição completa, transação, acesso restrito e fallback/frescura OK.');

let gravados=[];
Object.assign(context, {
  normalizar:x=>String(x??'').trim().toUpperCase(), telefone:x=>x,
  visaoMonitorados:async()=>[], sugerir:()=>[], motivoFalhaAdicao:()=> 'teste',
});
context.supabase.from = (table) => {
  assert.equal(table,'lista_monitoramento');
  return {upsert:(row)=>{gravados.push(row);return {select:()=>({single:async()=>({data:{id:1}})})};}};
};
context.catalogoParaCadastro=async()=>({reserva:true,navios:[{imo:'9398321',nome:'TORINO'}]});
vm.runInContext(stripTypeScriptTypes(source.slice(source.indexOf('async function adicionarNavios'),
 source.indexOf('async function prepararRemocao'))),context);
assert.match(await context.adicionarNavios('123',['TORINO','TORINO']),/Praticagem/);
assert.equal(gravados.length,1);
assert.equal(gravados[0].imo,'9398321');
assert.equal(gravados[0].ativo,true);
context.catalogoParaCadastro=async()=>({reserva:true,navios:[{imo:'1111111',nome:'IGUAL'},{imo:'2222222',nome:'IGUAL'}]});
assert.match(await context.adicionarNavios('123',['IGUAL']),/ambíguo/);
assert.equal(gravados.length,1);
console.log('Inclusão de reserva: IMO salvo, duplicidade e ambiguidade tratadas, sem dados APS inventados.');
