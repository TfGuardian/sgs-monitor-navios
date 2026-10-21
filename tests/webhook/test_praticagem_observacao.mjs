import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';

const require = createRequire(import.meta.url);
const {PGlite} = require('../../tmp/webhook-validation/node_modules/@electric-sql/pglite');
const db = new PGlite();
await db.exec(`create role anon; create role authenticated; create role service_role;
  create table destinatarios_relatorio(telefone text primary key, ativo boolean);
  insert into destinatarios_relatorio values('5513999999999',true);`);
await db.exec(readFileSync(
  'supabase/migrations/20261007180000_praticagem_observacao.sql', 'utf8'));

const token = (await db.query(
  'select reservar_coleta_praticagem() as token'
)).rows[0].token;
assert.ok(token);
assert.equal((await db.query(
  'select reservar_coleta_praticagem() as token'
)).rows[0].token, null);
await db.query(
  `select concluir_observacao_praticagem($1,$2,$3,$4,$5)`, [
    token,
    JSON.stringify([{imo:'9398321',nome:'TORINO',manobras:[]}]),
    JSON.stringify([{imo:'9398321',nome:'TORINO',manobra:'saida-1',
      mudancas:[{campo:'fase',depois:'previsao'}],
      alertas:[{telefone:'5513999999999',texto:'Manobra em previsão'},
        {telefone:'5513888888888',texto:'Sem assinatura'}]}]),
    JSON.stringify({movimentos:1}), 1000]);
assert.equal((await db.query(
  'select count(*)::int as total from public.alertas_simulados_praticagem'
)).rows[0].total, 1);
assert.equal((await db.query(
  'select count(*)::int as total from public.estados_praticagem'
)).rows[0].total, 1);
await assert.rejects(db.query(
  `select concluir_observacao_praticagem($1,'[]','[]','{}',1000)`, [token]));
const evento = (await db.query(
  'select id from public.eventos_praticagem'
)).rows[0].id;
await assert.rejects(db.query(
  `insert into public.alertas_simulados_praticagem(evento_id,telefone,texto,estado)
   values($1,'5513888888888','invalido','enviado')`, [evento]));
await db.close();
