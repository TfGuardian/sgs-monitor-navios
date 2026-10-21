import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';

const require = createRequire(import.meta.url);
const {PGlite} = require('../tmp/webhook-validation/node_modules/@electric-sql/pglite');
const db = new PGlite();
await db.exec(`create role anon; create role authenticated; create role service_role;
  create table administradores_chat(telefone text primary key, ativo boolean not null);
  insert into administradores_chat values ('5513999999999', true);`);
await db.exec(readFileSync('supabase/migrations/20261009150000_comando_observador.sql', 'utf8'));

await assert.rejects(db.query(`select solicitar_observador('5513888888888')`));
const a = (await db.query(`select solicitar_observador('5513999999999') as id`)).rows[0].id;
assert.equal((await db.query(`select solicitar_observador('5513999999999') as id`)).rows[0].id, a);
const reserva = (await db.query(`select * from reservar_pedido_observador()`)).rows[0];
assert.equal(reserva.pedido_id, a);
assert.equal((await db.query(`select count(*)::int as n from reservar_pedido_observador()`)).rows[0].n, 0);
assert.equal((await db.query(`select concluir_pedido_observador($1,gen_random_uuid(),true,'x') as ok`, [a])).rows[0].ok, false);
const b = (await db.query(`select solicitar_observador('5513999999999') as id`)).rows[0].id;
assert.notEqual(b, a);
assert.equal((await db.query(`select concluir_pedido_observador($1,$2,true,'iniciado') as ok`,
  [a, reserva.token])).rows[0].ok, true);
const reservaB = (await db.query(`select * from reservar_pedido_observador()`)).rows[0];
assert.equal(reservaB.pedido_id, b);
assert.equal((await db.query(`select concluir_pedido_observador($1,$2,false,'tarefa ausente') as ok`,
  [b, reservaB.token])).rows[0].ok, true);
assert.equal((await db.query(`select estado from pedidos_observador where id=$1`, [b])).rows[0].estado, 'falha');
await db.close();
